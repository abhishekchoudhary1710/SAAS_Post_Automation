"""One-time helper: turn a short-lived Meta user token into the two secrets the agent needs.

    python setup/meta_setup.py --app-id APP_ID --app-secret APP_SECRET --token SHORT_LIVED_USER_TOKEN

Get the short-lived token from https://developers.facebook.com/tools/explorer/ with your app
selected and "Get User Access Token". Do not worry about ticking every permission in that
fiddly picker: run this script and it will tell you exactly which ones you got and which are
still missing, so you can add just those and regenerate.

The script exchanges the token for a long-lived one, lists your Pages with their
never-expiring Page tokens, and shows the Instagram account linked to each Page.
"""

from __future__ import annotations

import argparse
import sys

import requests

VERSION = "v23.0"
GRAPH = f"https://graph.facebook.com/{VERSION}"

REQUIRED = {
    "pages_show_list": "find your Pages and their tokens",
    "pages_read_engagement": "read the Page and its linked Instagram account",
    "pages_manage_posts": "publish photos and videos to the Page",
    "instagram_basic": "see the linked Instagram account",
    "instagram_content_publish": "publish posts, carousels and reels to Instagram",
}


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
    app_token = f"{args.app_id}|{args.app_secret}"

    # 1. What did this token actually come with?
    debug = get("debug_token", input_token=args.token, access_token=app_token).get("data", {})
    granted = set(debug.get("scopes") or [])
    print("Permissions on the token you pasted:")
    for scope in sorted(granted):
        print(f"  have  {scope}")
    missing = [s for s in REQUIRED if s not in granted]
    for scope in missing:
        print(f"  MISSING  {scope}   (needed to {REQUIRED[scope]})")
    if missing:
        print("\nGo back to the Graph API Explorer, add the MISSING ones above, click")
        print("Generate Access Token again, and rerun this script with the new token.")
        print("If a permission will not appear in the picker, open your app dashboard,")
        print("click the use case, then 'Customize', and add it there first.\n")

    # 2. Long-lived user token, then the Page tokens (which do not expire).
    long_lived = get("oauth/access_token", grant_type="fb_exchange_token", client_id=args.app_id,
                     client_secret=args.app_secret, fb_exchange_token=args.token)["access_token"]
    print("Long-lived user token obtained (about 60 days; the Page tokens below do not expire).\n")

    pages = get("me/accounts", access_token=long_lived,
                fields="id,name,access_token,instagram_business_account{id,username}").get("data", [])
    if not pages:
        print("No Pages came back. Either pages_show_list was not granted, or you did not tick")
        print("the Interview Sarthi Page in the Facebook dialog. Regenerate the token and retry.")
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
            print("  IG_USER_ID=  NOT LINKED. Either instagram_basic was not granted, or this")
            print("               Page has no Instagram professional account connected.")
        token_info = get("debug_token", input_token=page["access_token"], access_token=app_token).get("data", {})
        print(f"  page token expires_at={token_info.get('expires_at', '?')} (0 means never)")
    print("=" * 72)
    if missing:
        print("\nWARNING: the permissions listed as MISSING above are not on this token, so the")
        print("Page token inherits the same gap. Fix those before relying on it.")
    else:
        print("\nAll five permissions are present. Copy the three values for your Page into")
        print("the .env file and, later, into GitHub secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
