"""One-time helper: get a YouTube refresh token for the agent.

    python setup/youtube_setup.py path/to/client_secret.json
    python setup/youtube_setup.py path/to/client_secret.json --save-to OWNER/REPO

Prerequisites (Google Cloud console, all free):
  1. Create a project, enable "YouTube Data API v3" and "YouTube Analytics API".
  2. OAuth consent screen: External, add yourself as a test user, then PUBLISH the app
     (Publishing status: In production). Unpublished apps expire refresh tokens after 7 days.
  3. Credentials > Create credentials > OAuth client ID > Desktop app. Download the JSON.

A browser window opens; sign in with the Google account that owns the YouTube channel.
--save-to writes the three values into that repo's GitHub secrets with `gh` instead of printing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("client_secret")
    parser.add_argument("--save-to", metavar="OWNER/REPO", help="write the secrets to GitHub instead of printing")
    args = parser.parse_args()
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        print("No refresh token came back. Remove the app's access at myaccount.google.com/permissions and rerun.")
        return 1
    with open(args.client_secret, encoding="utf-8") as handle:
        client = json.load(handle)
    client = client.get("installed") or client.get("web") or {}
    values = {"YT_CLIENT_ID": client.get("client_id"), "YT_CLIENT_SECRET": client.get("client_secret"),
              "YT_REFRESH_TOKEN": creds.refresh_token}
    if args.save_to:
        for name, value in values.items():
            subprocess.run(["gh", "secret", "set", name, "-R", args.save_to], input=value, text=True, check=True)
        print(f"\nSaved {', '.join(values)} to {args.save_to}.")
        return 0
    print("\nAdd these as GitHub secrets (or to .env):\n")
    for name, value in values.items():
        print(f"{name}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
