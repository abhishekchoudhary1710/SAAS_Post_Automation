"""Read available platform metrics without blocking scheduled content when access is missing."""
from __future__ import annotations

import datetime as dt
import re

from .config import CONTENT, load_json, now_ist, save_json
from .history import History

METRICS_FILE = CONTENT / 'performance.json'


def _age_hours(post: dict, now: dt.datetime) -> float:
    try:
        published = dt.datetime.strptime(post['date'], '%Y-%m-%d %H:%M IST').replace(
            tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
        return (now - published).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        return -1


def _due_snapshot(post: dict, platform: str, data: dict, now: dt.datetime) -> bool:
    receipt = post.get('posted', {}).get(platform) or {}
    media_id = receipt.get('id')
    if not media_id:
        return False
    record = data['posts'].get(platform + ':' + media_id, {})
    age = _age_hours(post, now)
    return (0 <= age < 24 or
            48 <= age < 72 and '48h' not in record.get('snapshots', {}) or
            168 <= age < 192 and '7d' not in record.get('snapshots', {}))


def _record(data: dict, platform: str, media_id: str, values: dict, age: float) -> None:
    key = platform + ':' + media_id
    previous = data['posts'].get(key, {})
    snapshots = previous.get('snapshots', {})
    if 48 <= age < 72 and 'views' in values:
        snapshots.setdefault('48h', values.copy())
    if 168 <= age < 192 and 'views' in values:
        snapshots.setdefault('7d', values.copy())
    data['posts'][key] = {**previous, **values, 'snapshots': snapshots}


# A reel reports its plays under one of these names depending on how it was published
# (Reels endpoint versus the plain video fallback). The first one present is the play count.
FB_PLAYS = ('fb_reels_total_plays', 'blue_reels_play_count', 'total_video_views')
FB_AVG_WATCH_MS = ('post_video_avg_time_watched', 'total_video_avg_time_watched')
YT_ANALYTICS_SCOPE = 'https://www.googleapis.com/auth/yt-analytics.readonly'


def _meta_permission_error(exc: Exception) -> bool:
    """Graph codes 10, 190 and 200-299 mean the token lacks access; retrying other posts is pointless."""
    return bool(re.match(r'\S+ (10|190|2\d\d)/', str(exc)))


def _facebook_values(meta, video_id: str) -> dict:
    reply = meta.get(video_id + '/video_insights')
    rows = {row.get('name'): (row.get('values') or [{}])[0].get('value') for row in reply.get('data', [])}
    values = {}
    plays = next((rows[n] for n in FB_PLAYS if isinstance(rows.get(n), (int, float))), None)
    if plays is not None:
        values['views'] = plays
    if isinstance(rows.get('post_impressions_unique'), (int, float)):
        values['reach'] = rows['post_impressions_unique']
    avg = next((rows[n] for n in FB_AVG_WATCH_MS if isinstance(rows.get(n), (int, float))), None)
    if avg is not None:
        values['avg_watch_seconds'] = round(avg / 1000, 1)
    return values


def _youtube_watch(settings, video_ids: list[str], start: str, end: str) -> dict:
    """Watch time per video from the YouTube Analytics API (lags one to three days behind views)."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(None, refresh_token=settings.yt_refresh_token, token_uri='https://oauth2.googleapis.com/token',
                        client_id=settings.yt_client_id, client_secret=settings.yt_client_secret,
                        scopes=[YT_ANALYTICS_SCOPE])
    service = build('youtubeAnalytics', 'v2', credentials=creds, cache_discovery=False)
    out = {}
    for first in range(0, len(video_ids), 50):
        reply = service.reports().query(
            ids='channel==MINE', startDate=start, endDate=end, dimensions='video',
            metrics='estimatedMinutesWatched,averageViewDuration,averageViewPercentage',
            filters='video==' + ','.join(video_ids[first:first + 50]),
            sort='-estimatedMinutesWatched', maxResults=200).execute()
        headers = [h['name'] for h in reply.get('columnHeaders', [])]
        for row in reply.get('rows') or []:
            r = dict(zip(headers, row))
            out[r['video']] = {'avg_watch_seconds': r['averageViewDuration'],
                               'avg_watch_percent': round(r['averageViewPercentage'], 1),
                               'minutes_watched': r['estimatedMinutesWatched']}
    return out


def refresh(settings):
    data = {'checked_at': now_ist().isoformat(), 'posts': {}, 'unavailable': {}}
    try:
        previous = load_json(METRICS_FILE)
        data['posts'] = previous.get('posts', {})
    except (FileNotFoundError, ValueError):
        pass
    now = now_ist()
    posts = History().recent(110)
    yt_posts = {p['posted']['youtube']['id']: p for p in posts if _due_snapshot(p, 'youtube', data, now)}
    watch = {}
    if settings.has_youtube and yt_posts:
        try:
            first_day = min(p['date'][:10] for p in yt_posts.values())
            watch = _youtube_watch(settings, list(yt_posts), first_day, now.date().isoformat())
        except Exception as exc:
            data['unavailable']['youtube_analytics'] = type(exc).__name__
        try:
            from .publish.youtube import _service
            service = _service(settings)
            ids = list(yt_posts)
            for start in range(0, len(ids), 50):
                reply = service.videos().list(part='statistics', id=','.join(ids[start:start + 50])).execute()
                for row in reply.get('items', []):
                    stats = row.get('statistics', {})
                    values = {'checked_at': data['checked_at'],
                              'views': int(stats.get('viewCount', 0)), 'likes': int(stats.get('likeCount', 0)),
                              'comments': int(stats.get('commentCount', 0)), **watch.get(row['id'], {})}
                    _record(data, 'youtube', row['id'], values, _age_hours(yt_posts[row['id']], now))
        except Exception as exc:
            data['unavailable']['youtube'] = type(exc).__name__
    meta = None
    if settings.has_meta:
        from .publish.meta import Meta
        meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id, settings.graph_version)
    if meta is not None and 'facebook' in settings.platforms:
        read, failed = 0, None
        for post in posts:
            if not _due_snapshot(post, 'facebook', data, now):
                continue
            post_id = post['posted']['facebook']['id']
            if '_' in post_id:
                continue    # a photo or carousel post (page_post id): no play count to read
            try:
                values = {'checked_at': data['checked_at'], **_facebook_values(meta, post_id)}
            except Exception as exc:
                failed = type(exc).__name__
                if _meta_permission_error(exc):
                    read = 0
                    break
                continue
            read += 1
            _record(data, 'facebook', post_id, values, _age_hours(post, now))
        if failed and not read:
            data['unavailable']['facebook_insights'] = failed
    if settings.has_instagram:
        insights_blocked = False
        for post in posts:
            if not _due_snapshot(post, 'instagram', data, now):
                continue
            media_id = post.get('posted', {}).get('instagram', {}).get('id')
            if not media_id:
                continue
            try:
                basic = meta.get(media_id, fields='like_count,comments_count')
                values = {'checked_at': data['checked_at'], 'likes': basic.get('like_count', 0),
                          'comments': basic.get('comments_count', 0)}
                if not insights_blocked:
                    try:
                        reply = meta.get(media_id + '/insights', metric='views,reach,saved,shares')
                        for row in reply.get('data', []):
                            v = (row.get('values') or [{}])[0].get('value')
                            if isinstance(v, (int, float)):
                                values[row['name']] = v
                    except Exception as exc:
                        data['unavailable']['instagram_insights'] = type(exc).__name__
                        insights_blocked = True
                _record(data, 'instagram', media_id, values, _age_hours(post, now))
            except Exception as exc:
                data['unavailable']['instagram'] = type(exc).__name__
                break
    save_json(METRICS_FILE, data)
    print('[feedback] measured posts:', len(data['posts']), '| unavailable:', ', '.join(data['unavailable']) or 'none')
    return data


def prompt_feedback():
    """Surface observations, never treat a play count as a purchase or retention measure."""
    try:
        metrics = load_json(METRICS_FILE)
    except (FileNotFoundError, ValueError):
        return 'No measured performance yet. Do not invent audience preferences.'
    rows = []
    for post in History().recent(40):
        if post.get('format') != 'sales':
            continue
        for platform, receipt in post.get('posted', {}).items():
            m = metrics.get('posts', {}).get(platform + ':' + receipt.get('id', ''), {})
            if m.get('views', 0) >= 100:
                rows.append({'platform': platform, 'hook': post.get('hook'), 'variant': post.get('variant'),
                             'views': m['views'], 'likes': m.get('likes', 0), 'shares': m.get('shares'),
                             'saves': m.get('saved')})
    if len(rows) < 6:
        return 'Too few measured sales reels to infer a winner. Continue controlled variation.'
    import json
    return ('Observations only, not causal evidence or sales data. Ages and audiences can differ. '
            'Use these to suggest a hook, never invent a conversion rate:\n' + json.dumps(rows[-12:]))
