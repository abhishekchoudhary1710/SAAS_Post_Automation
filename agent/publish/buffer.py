"""Posts the day's LinkedIn post on the Interview Sarthi page through Buffer's free API.

Owner's decision, 28 Sep 2026: LinkedIn's page API is only for registered companies. Buffer's free plan
includes its API (1 key, 3,000 requests a month) and posts to a LinkedIn Page through Buffer's own
approved LinkedIn app, so it is the first choice for the page; Make.com is the backup. Only the page is
connected in Buffer. The post is picked by channel name, and a run refuses to guess between two.

Images go in by public URL only (developers.buffer.com/guides/hosting-media.html), so the card is put on
the same public host Instagram uses before the post is created.
"""

from __future__ import annotations

import datetime as dt
import json

API = "https://api.buffer.com"
WARN_DAYS = 10


def _gql(key: str, query: str) -> dict:
    import requests

    response = requests.post(API, json={"query": query}, timeout=60,
                             headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code != 200 or body.get("errors"):
        detail = "; ".join(str(e.get("message")) for e in body.get("errors") or []) or response.text[:200]
        raise RuntimeError(f"Buffer API failed (HTTP {response.status_code}: {detail})")
    return body["data"]


def channels(key: str) -> list[dict]:
    orgs = _gql(key, "query { account { organizations { id name } } }")["account"]["organizations"]
    found = []
    for org in orgs:
        query = ("query { channels(input: {organizationId: %s}) { id name displayName type service "
                 "isDisconnected } }" % json.dumps(org["id"]))
        found += _gql(key, query)["channels"]
    return found


def _plain(name) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def channel_id(settings) -> str:
    """The one LinkedIn PAGE channel with our name. Buffer names it by the page's address
    ("interview-sarthi") and shows "Interview Sarthi", so both are compared without case or punctuation.
    A personal profile (type "profile") is never used, whatever its name."""
    want = _plain(settings.buffer_channel)
    matches = [c for c in channels(settings.buffer_api_key)
               if c.get("service") == "linkedin" and c.get("type") == "page"
               and (c.get("id") == settings.buffer_channel_id if settings.buffer_channel_id else
                    want in (_plain(c.get("name")), _plain(c.get("displayName"))))]
    if len(matches) != 1:
        raise RuntimeError(f"expected one LinkedIn Page named {settings.buffer_channel!r} in Buffer, "
                           f"found {len(matches)}. Connect the Interview Sarthi page (not a profile).")
    if matches[0].get("isDisconnected"):
        raise RuntimeError("the Interview Sarthi page is disconnected in Buffer: reconnect it under Channels")
    return matches[0]["id"]


def post(settings, text: str, image_url: str | None, *, document_url: str | None = None,
         video_url: str | None = None, title: str = "") -> str:
    """Submit to Buffer; its returned ID is acceptance, not confirmed publication."""
    if video_url and document_url:
        raise ValueError("A post cannot combine video and document assets")
    fields = [f"text: {json.dumps(text)}", f"channelId: {json.dumps(channel_id(settings))}",
              "schedulingType: automatic", "mode: shareNow"]
    if video_url:
        fields.append("assets: [{video: {url: %s}}]" % json.dumps(video_url))
    elif document_url:
        if not image_url or not title:
            raise ValueError("A Buffer document needs a thumbnail and title")
        fields.append("assets: [{document: {url: %s, thumbnailUrl: %s, title: %s}}]" %
                      (json.dumps(document_url), json.dumps(image_url), json.dumps(title[:100])))
    elif image_url:
        fields.append("assets: [{image: {url: %s}}]" % json.dumps(image_url))
    else:
        fields.append("assets: []")
    query = ("mutation { createPost(input: {%s}) { ... on PostActionSuccess { post { id } } "
             "... on MutationError { message } } }" % ", ".join(fields))
    result = _gql(settings.buffer_api_key, query)["createPost"]
    if not result.get("post"):
        raise RuntimeError("Buffer refused the post: " + str(result.get("message") or result))
    return str(result["post"]["id"])


def inspect_post(settings, post_id: str) -> dict:
    """Read publication status and available metrics; unsupported metrics remain missing."""
    query = ("query { post(input: {id: %s}) { id status externalLink metricsUpdatedAt "
             "metrics { type value } } }" % json.dumps(post_id))
    return _gql(settings.buffer_api_key, query)["post"]


def expiry_warning(settings, today: dt.date | None = None) -> str | None:
    """Buffer API keys expire (the current one on the date in BUFFER_KEY_EXPIRES). The free plan allows one
    key, so replacing it means deleting the old one first, then putting the new one in the BUFFER_API_KEY
    secret."""
    try:
        expires = dt.date.fromisoformat(str(settings.buffer_key_expires or "")[:10])
    except ValueError:
        return None
    left = (expires - (today or dt.date.today())).days
    if left > WARN_DAYS:
        return None
    return (f"The Buffer API key expires on {expires.isoformat()} ({left} days). LinkedIn page posts stop then. "
            "In Buffer: Settings > API, delete the old key, create a new one, and put it in the BUFFER_API_KEY "
            "secret; set BUFFER_KEY_EXPIRES to its new date.")
