"""YouTube Shorts upload with the Data API v3 and a long-lived refresh token.

Google currently lists videos.insert as 100 quota units. Channel-level daily upload
limits are separate and vary by account; seventh/eighth daily uploads are tested live.
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
    """Persist the upload session before sending bytes; recover offsets after interruptions."""
    import requests
    from urllib.parse import urlparse
    from ..config import load_json, save_json
    from ..quality import file_hash

    path = pathlib.Path(path)
    checkpoint = path.parent / 'youtube-upload.json'
    state = load_json(checkpoint) if checkpoint.exists() else {}
    digest, total = file_hash(path), path.stat().st_size
    if state and state.get('sha256') != digest:
        raise RuntimeError('YouTube checkpoint belongs to different media')
    if state.get('video_id'):
        return state['video_id']
    token = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': settings.yt_client_id, 'client_secret': settings.yt_client_secret,
        'refresh_token': settings.yt_refresh_token, 'grant_type': 'refresh_token'}, timeout=30)
    token.raise_for_status()
    headers = {'Authorization': 'Bearer ' + token.json()['access_token']}
    if not state.get('uri'):
        response = requests.post('https://www.googleapis.com/upload/youtube/v3/videos',
            params={'uploadType': 'resumable', 'part': 'snippet,status'},
            headers={**headers, 'X-Upload-Content-Length': str(total), 'X-Upload-Content-Type': 'video/mp4'},
            json={'snippet': {'title': title[:100], 'description': description[:4900], 'tags': tags,
                             'categoryId': category_id, 'defaultLanguage': 'en'},
                  'status': {'privacyStatus': settings.yt_privacy, 'selfDeclaredMadeForKids': False}}, timeout=60)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            try:
                reason = response.json().get('error', {}).get('errors', [{}])[0].get('reason', '')
            except ValueError:
                reason = ''
            raise RuntimeError(f'YouTube upload initiation failed (HTTP {response.status_code}, {reason})')
        state = {'sha256': digest, 'uri': response.headers['Location'], 'progress': 0}
        save_json(checkpoint, state)
    uri = urlparse(state['uri'])
    if uri.scheme != 'https' or uri.hostname not in ('www.googleapis.com', 'youtube.googleapis.com'):
        raise RuntimeError('Unexpected YouTube upload session host')

    def accept(response):
        if response.status_code in (200, 201):
            state['video_id'] = response.json()['id']
            state['progress'] = total
        elif response.status_code == 308:
            accepted = response.headers.get('Range')
            state['progress'] = int(accepted.rsplit('-', 1)[1]) + 1 if accepted else 0
        else:
            response.raise_for_status()
            raise RuntimeError('Unexpected YouTube upload response')
        save_json(checkpoint, state)

    failures, query = 0, True
    with path.open('rb') as video:
        while not state.get('video_id'):
            try:
                if query:
                    response = requests.put(state['uri'], headers={**headers, 'Content-Length': '0',
                        'Content-Range': f'bytes */{total}'}, data=b'', timeout=60)
                    accept(response)
                    query = False
                    if state.get('video_id'):
                        break
                offset = state['progress']
                video.seek(offset)
                chunk = video.read(1024 * 1024)
                if not chunk:
                    raise RuntimeError('Upload accepted all bytes without returning a video ID')
                response = requests.put(state['uri'], headers={**headers, 'Content-Type': 'video/mp4',
                    'Content-Range': f'bytes {offset}-{offset + len(chunk) - 1}/{total}'}, data=chunk, timeout=120)
                accept(response)
                failures = 0
            except requests.RequestException as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status is not None and status < 500 and status != 429:
                    try:
                        reason = exc.response.json().get('error', {}).get('errors', [{}])[0].get('reason', '')
                    except ValueError:
                        reason = ''
                    raise RuntimeError(f'YouTube upload failed (HTTP {status}, {reason}); session preserved') from None
                failures += 1
                if failures > 5:
                    raise RuntimeError('YouTube connection failed; resume the saved upload session') from None
                time.sleep(min(2 ** failures, 30))
                query = True
    return state['video_id']
