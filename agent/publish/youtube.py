"""YouTube Shorts upload with the Data API v3 and a long-lived refresh token.

Quota: an upload costs 1,600 of the daily 10,000 units, so up to six uploads a day.
Projects that have not passed YouTube's API compliance audit get their API uploads forced
to private; the README explains how to request the audit (free, takes a few days).
"""

from __future__ import annotations

import pathlib
import time

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


def _service(settings):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(None, refresh_token=settings.yt_refresh_token, token_uri="https://oauth2.googleapis.com/token",
                        client_id=settings.yt_client_id, client_secret=settings.yt_client_secret, scopes=SCOPES)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_title(settings) -> str:
    data = _service(settings).channels().list(part="snippet", mine=True).execute()
    items = data.get("items") or []
    if not items:
        raise RuntimeError("the token works but no YouTube channel is attached to this Google account")
    return items[0]["snippet"]["title"]


def upload_short(settings, path: str | pathlib.Path, title: str, description: str, tags: list[str],
                 category_id: str = "27") -> str:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {"title": title[:100], "description": description[:4900], "tags": tags,
                    "categoryId": category_id, "defaultLanguage": "en"},
        "status": {"privacyStatus": settings.yt_privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = _service(settings).videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    retries = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as exc:
            if exc.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
    return response["id"]
