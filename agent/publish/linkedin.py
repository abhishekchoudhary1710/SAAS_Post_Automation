"""LinkedIn posts on the Interview Sarthi company page, through the official Posts and Images APIs.

Owner's decisions, 28 Sep 2026: LinkedIn carries the daily jobs post only, as text with a clickable
link to the list plus one card image. It posts AS THE PAGE, never on the owner's personal profile. Two locks keep it so:
the token is asked only for w_organization_social (it cannot post as a person at all), and `author()`
refuses anything but an organization URN.

Page posting needs LinkedIn's "Community Management API" product on the developer app, which LinkedIn
must approve and which must be the app's only product. setup/linkedin_setup.py gets the token. There
is no refresh token for most apps, so the token lasts 60 days and the owner signs in again;
LINKEDIN_TOKEN_EXPIRES lets the run warn first.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re

API = "https://api.linkedin.com"
# LinkedIn retires each monthly API version about a year after release. Override with
# LINKEDIN_API_VERSION when a run says the version is no longer supported.
DEFAULT_VERSION = "202606"
WARN_DAYS = 10

# "little text": these characters mean something in a post's commentary and must be escaped, or
# LinkedIn rejects the post or silently cuts it at the first one.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_URL = re.compile(r"(https?://\S+)")


def escape(text: str) -> str:
    """Escape the reserved characters, leaving links as they are so LinkedIn still makes them clickable."""
    return "".join(part if _URL.fullmatch(part) else _RESERVED.sub(r"\\\1", part) for part in _URL.split(text))


def hashtag(tag: str) -> str:
    word = "".join(ch for ch in tag.lstrip("#") if ch.isalnum())
    return "{hashtag|\\#|" + word + "}"


def commentary(body: str, tags: list[str]) -> str:
    """Plain text in, LinkedIn's little-text out, hashtags as real hashtags."""
    text = escape(body.strip())
    tags = [hashtag(t) for t in tags if t.strip("#")]
    return text + ("\n\n" + " ".join(tags) if tags else "")


def _headers(settings, json_body: bool = True) -> dict:
    headers = {"Authorization": "Bearer " + settings.linkedin_access_token,
               "LinkedIn-Version": settings.linkedin_api_version or DEFAULT_VERSION,
               "X-Restli-Protocol-Version": "2.0.0"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _fail(what: str, response) -> RuntimeError:
    try:
        detail = response.json().get("message") or response.text[:200]
    except ValueError:
        detail = response.text[:200]
    hint = ""
    if response.status_code == 401:
        hint = " The token has expired or was revoked: run setup/linkedin_setup.py again."
    return RuntimeError(f"LinkedIn {what} failed (HTTP {response.status_code}: {detail}).{hint}")


def expiry_warning(settings, today: dt.date | None = None) -> str | None:
    if not settings.linkedin_token_expires:
        return None
    try:
        expires = dt.date.fromisoformat(settings.linkedin_token_expires[:10])
    except ValueError:
        return None
    left = (expires - (today or dt.date.today())).days
    if left <= WARN_DAYS:
        return (f"LinkedIn token expires on {expires.isoformat()} ({left} days). "
                "Run setup/linkedin_setup.py again to sign in and save a new one.")
    return None


def author(settings) -> str:
    urn = (settings.linkedin_author_urn or "").strip()
    if not urn.startswith("urn:li:organization:"):
        raise RuntimeError("LINKEDIN_AUTHOR_URN must be the company page (urn:li:organization:<id>). "
                           "Posting on a personal profile is switched off on purpose.")
    return urn


def whoami(settings) -> str:
    until = f", token until {settings.linkedin_token_expires[:10]}" if settings.linkedin_token_expires else ""
    return f"posts as page {author(settings)}{until}"


def upload_image(settings, author: str, path: str | pathlib.Path) -> str:
    import requests

    response = requests.post(API + "/rest/images?action=initializeUpload", headers=_headers(settings),
                             json={"initializeUploadRequest": {"owner": author}}, timeout=30)
    if response.status_code != 200:
        raise _fail("image upload start", response)
    value = response.json()["value"]
    with open(path, "rb") as handle:
        put = requests.put(value["uploadUrl"], data=handle.read(), timeout=120,
                           headers={"Authorization": "Bearer " + settings.linkedin_access_token})
    if put.status_code not in (200, 201):
        raise _fail("image upload", put)
    return value["image"]


def post(settings, text: str, image: str | pathlib.Path | None = None, alt: str = "") -> str:
    """Publish `text` (already in little-text form) with an optional image; returns the post URN."""
    import requests

    author_urn = author(settings)
    body = {"author": author_urn, "commentary": text, "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if image:
        body["content"] = {"media": {"id": upload_image(settings, author_urn, image), "altText": alt[:4000]}}
    response = requests.post(API + "/rest/posts", headers=_headers(settings), json=body, timeout=60)
    if response.status_code != 201:
        raise _fail("post", response)
    return response.headers.get("x-restli-id") or response.headers.get("x-linkedin-id") or ""


def post_url(urn: str) -> str:
    return f"https://www.linkedin.com/feed/update/{urn}/"
