"""One-time helper: turn a short-lived Meta user token into the two secrets the agent needs.

    python setup/meta_setup.py --app-id APP_ID --app-secret APP_SECRET --token SHORT_LIVED_USER_TOKEN

Get the short-lived token from https://developers.facebook.com/tools/explorer/ with your app
selected and these permissions ticked: pages_show_list, pages_read_engagement,
pages_manage_posts, instagram_basic, instagram_content_publish, business_management.

The script exchanges it for a long-lived user token, lists your Pages with their
never-expiring Page tokens, and shows the Instagram account linked to each Page.
"""

from __future__ import annotations

import argparse
import sys

import requests

VERSION = "v23.0"
GRAPH = f"https://graph.facebook.com/{VERSION}"


def get(path: str, **params):
    response = requests.get(f"{GRAPH}/{path}", params=params, timeout=60)
    data = response.json()
    if "error" in data:
        raise SystemExit(f"Graph API error: {data['error'].get('message')}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-secret", required=True)
    parser.add_argument("--token", required=True, help="short-lived user token from the Graph API Explorer")
    args = parser.parse_args()

    long_lived = get("oauth/access_token", grant_type="fb_exchange_token", client_id=args.app_id,
                     client_secret=args.app_secret, fb_exchange_token=args.token)["access_token"]
    print("Long-lived user token obtained (valid about 60 days; the Page tokens below do not expire).\n")

    pages = get("me/accounts", access_token=long_lived,
                fields="id,name,access_token,instagram_business_account{id,username}").get("data", [])
    if not pages:
        print("No Pages found. The token needs pages_show_list and you must be an admin of a Facebook Page.")
        return 1
    for page in pages:
        ig = page.get("instagram_business_account") or {}
        print("=" * 72)
        print(f"Page: {page['name']}")
        print(f"  META_PAGE_ID={page['id']}")
        print(f"  META_PAGE_ACCESS_TOKEN={page['access_token']}")
        if ig:
            print(f"  IG_USER_ID={ig['id']}   (Instagram @{ig.get('username')})")
        else:
            print("  IG_USER_ID=  (no Instagram professional account is linked to this Page yet)")
        debug = get("debug_token", input_token=page["access_token"], access_token=f"{args.app_id}|{args.app_secret}")
        expires = debug.get("data", {}).get("expires_at", "?")
        print(f"  page token expires_at={expires} (0 means never)")
    print("=" * 72)
    print("\nCopy the three values for the Page you want into GitHub secrets (or .env).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
