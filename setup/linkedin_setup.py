"""One-time helper, repeated every 60 days: let the agent post as the Interview Sarthi LinkedIn page.

It asks LinkedIn only for w_organization_social, so the token can post as the page and cannot post on
the owner's personal profile (owner's decision, 28 Sep 2026).

Step 1 prints a sign-in link:
    python setup/linkedin_setup.py
Open it in any browser, signed in to the LinkedIn account that is an admin of the page, and allow.
LinkedIn then sends the browser to a localhost address that fails to load. That is expected: copy
the whole address from the address bar.

Step 2 swaps that address for a token and saves it:
    python setup/linkedin_setup.py --code "<the localhost address>" --page <page id> --save-to OWNER/REPO [--env]

The page id is the number in the page's admin address: linkedin.com/company/<page id>/admin/.
--save-to writes LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN and LINKEDIN_TOKEN_EXPIRES to that repo's
GitHub secrets with `gh`; --env also writes them to the local .env. The token itself is never printed.

Prerequisites (linkedin.com/developers, free):
  1. Create an app attached to the Interview Sarthi page.
  2. Products tab: request "Community Management API". LinkedIn reviews the request, and it must be
     the app's only product.
  3. Auth tab: add the redirect URL http://localhost:8765/callback, then copy the Client ID and
     Client Secret into .env as LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import secrets
import subprocess
import sys
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.config import env  # noqa: E402  (loads .env)

AUTHORIZE = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"
SCOPES = "w_organization_social"
REDIRECT = "http://localhost:8765/callback"
STATE_FILE = ROOT / "out" / "linkedin-state.txt"


def _client() -> tuple[str, str]:
    client_id, client_secret = env("LINKEDIN_CLIENT_ID"), env("LINKEDIN_CLIENT_SECRET")
    if not (client_id and client_secret):
        sys.exit("Put LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first (see this file's docstring).")
    return client_id, client_secret


def sign_in_link(redirect: str) -> str:
    client_id, _ = _client()
    state = secrets.token_urlsafe(16)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(state, encoding="utf-8")
    return AUTHORIZE + "?" + urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect,
                                        "state": state, "scope": SCOPES})


def _code_from(pasted: str) -> str:
    """Accepts the whole localhost address or the bare code."""
    if "://" not in pasted:
        return pasted.strip()
    query = parse_qs(urlparse(pasted.strip()).query)
    if "error" in query:
        sys.exit("LinkedIn said: " + query.get("error_description", query["error"])[0])
    expected = STATE_FILE.read_text(encoding="utf-8").strip() if STATE_FILE.exists() else None
    if expected and query.get("state", [""])[0] != expected:
        sys.exit("That address belongs to a different sign-in attempt. Run step 1 again and use its link.")
    if "code" not in query:
        sys.exit("No code in that address. Copy the full address after allowing access.")
    return query["code"][0]


def exchange(code: str, redirect: str, page: str) -> dict[str, str]:
    import requests

    client_id, client_secret = _client()
    response = requests.post(TOKEN, data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
                                          "client_id": client_id, "client_secret": client_secret}, timeout=30)
    if response.status_code != 200:
        sys.exit(f"LinkedIn refused the code (HTTP {response.status_code}): {response.text[:300]}\n"
                 "Codes work once and for a few minutes. Run step 1 again.")
    data = response.json()
    if "w_organization_social" not in str(data.get("scope", "w_organization_social")):
        sys.exit("LinkedIn did not grant page posting. Check that Community Management API is approved on the app.")
    expires = dt.date.today() + dt.timedelta(seconds=int(data.get("expires_in", 5184000)))
    print(f"Signed in. The token posts as page {page} and works until {expires.isoformat()}.")
    return {"LINKEDIN_ACCESS_TOKEN": data["access_token"], "LINKEDIN_AUTHOR_URN": "urn:li:organization:" + page,
            "LINKEDIN_TOKEN_EXPIRES": expires.isoformat()}


def write_env(values: dict[str, str]) -> None:
    path = ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if line.split("=", 1)[0].strip() not in values]
    lines += [f"{name}={value}" for name, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--code", help="the localhost address LinkedIn sent the browser to (step 2)")
    parser.add_argument("--page", help="the company page id, the number in linkedin.com/company/<id>/admin/")
    parser.add_argument("--save-to", metavar="OWNER/REPO", help="write the token to this repo's GitHub secrets")
    parser.add_argument("--env", action="store_true", help="also write the token to the local .env")
    parser.add_argument("--redirect", default=REDIRECT, help="must match a redirect URL on the app's Auth tab")
    args = parser.parse_args()
    if not args.code:
        print("Open this link, signed in to the LinkedIn account that is an admin of the page, and allow access:\n")
        print(sign_in_link(args.redirect))
        print("\nThen copy the localhost address the browser lands on and run step 2 with --code.")
        return 0
    if not (args.page or "").isdigit():
        sys.exit("Give the page id with --page, the number in linkedin.com/company/<id>/admin/.")
    if not (args.save_to or args.env):
        sys.exit("Say where to keep the token: --save-to OWNER/REPO and/or --env. It is never printed.")
    values = exchange(_code_from(args.code), args.redirect, args.page)
    if args.save_to:
        for name, value in values.items():
            subprocess.run(["gh", "secret", "set", name, "-R", args.save_to], input=value, text=True, check=True)
        print(f"Saved {', '.join(values)} to {args.save_to}.")
    if args.env:
        write_env(values)
        print("Saved them to .env.")
    STATE_FILE.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
