"""One-time helper: get a YouTube refresh token for the agent.

    python setup/youtube_setup.py path/to/client_secret.json

Prerequisites (Google Cloud console, all free):
  1. Create a project, enable "YouTube Data API v3".
  2. OAuth consent screen: External, add yourself as a test user, then PUBLISH the app
     (Publishing status: In production). Unpublished apps expire refresh tokens after 7 days.
  3. Credentials > Create credentials > OAuth client ID > Desktop app. Download the JSON.

A browser window opens; sign in with the Google account that owns the YouTube channel.
"""

from __future__ import annotations

import json
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        print("No refresh token came back. Remove the app's access at myaccount.google.com/permissions and rerun.")
        return 1
    with open(sys.argv[1], encoding="utf-8") as handle:
        client = json.load(handle)
    client = client.get("installed") or client.get("web") or {}
    print("\nAdd these as GitHub secrets (or to .env):\n")
    print(f"YT_CLIENT_ID={client.get('client_id')}")
    print(f"YT_CLIENT_SECRET={client.get('client_secret')}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
