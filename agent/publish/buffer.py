"""Posts the day's LinkedIn post on the Interview Sarthi page through Buffer's free API.

Owner's decision, 28 Sep 2026: LinkedIn's page API is only for registered companies. Buffer's free plan
includes its API (1 key, 3,000 requests a month) and posts to a LinkedIn Page through Buffer's own
approved LinkedIn app, so it is the first choice for the page; Make.com is the backup. Only the page is
connected in Buffer. The post is picked by channel name, and a run refuses to guess between two.

Images go in by public URL only (developers.buffer.com/guides/hosting-media.html), so the card is put on
the same public host Instagram uses before the post is created.
"""

from __future__ import annotations

import json

API = "https://api.buffer.com"


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
        query = "query { channels(input: {organizationId: %s}) { id name service } }" % json.dumps(org["id"])
        found += _gql(key, query)["channels"]
    return found


def channel_id(settings) -> str:
    if settings.buffer_channel_id:
        return settings.buffer_channel_id
    want = settings.buffer_channel.strip().lower()
    matches = [c for c in channels(settings.buffer_api_key)
               if c.get("service") == "linkedin" and str(c.get("name", "")).strip().lower() == want]
    if len(matches) != 1:
        raise RuntimeError(f"expected one LinkedIn channel named {settings.buffer_channel!r} in Buffer, "
                           f"found {len(matches)}. Connect only the Interview Sarthi page.")
    return matches[0]["id"]


def post(settings, text: str, image_url: str | None) -> str:
    """Share now on the page; returns Buffer's post id."""
    fields = [f"text: {json.dumps(text)}", f"channelId: {json.dumps(channel_id(settings))}",
              "schedulingType: automatic", "mode: shareNow"]
    if image_url:
        fields.append("assets: [{image: {url: %s}}]" % json.dumps(image_url))
    query = ("mutation { createPost(input: {%s}) { ... on PostActionSuccess { post { id } } "
             "... on MutationError { message } } }" % ", ".join(fields))
    result = _gql(settings.buffer_api_key, query)["createPost"]
    if not result.get("post"):
        raise RuntimeError("Buffer refused the post: " + str(result.get("message") or result))
    return str(result["post"]["id"])
