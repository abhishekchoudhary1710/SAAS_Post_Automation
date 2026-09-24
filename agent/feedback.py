"""Read available platform metrics without blocking scheduled content when access is missing."""
from __future__ import annotations

import datetime as dt

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
    if settings.has_youtube and yt_posts:
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
                              'comments': int(stats.get('commentCount', 0))}
                    _record(data, 'youtube', row['id'], values, _age_hours(yt_posts[row['id']], now))
        except Exception as exc:
            data['unavailable']['youtube'] = type(exc).__name__
    if settings.has_instagram:
        from .publish.meta import Meta
        meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id, settings.graph_version)
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
