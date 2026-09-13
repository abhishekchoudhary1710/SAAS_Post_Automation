"""Read available platform metrics without blocking scheduled content when access is missing."""
from __future__ import annotations

from .config import CONTENT, load_json, now_ist, save_json
from .history import History

METRICS_FILE = CONTENT / 'performance.json'


def refresh(settings):
    data = {'checked_at': now_ist().isoformat(), 'posts': {}, 'unavailable': {}}
    try:
        previous = load_json(METRICS_FILE)
        data['posts'] = previous.get('posts', {})
    except (FileNotFoundError, ValueError):
        pass
    posts = History().recent(24)
    yt_ids = list({p['posted']['youtube']['id'] for p in posts if p.get('posted', {}).get('youtube', {}).get('id')})
    if settings.has_youtube and yt_ids:
        try:
            from .publish.youtube import _service
            reply = _service(settings).videos().list(part='statistics', id=','.join(yt_ids)).execute()
            for row in reply.get('items', []):
                stats = row.get('statistics', {})
                data['posts']['youtube:' + row['id']] = {
                    'checked_at': data['checked_at'],
                    'views': int(stats.get('viewCount', 0)), 'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0))}
        except Exception as exc:
            data['unavailable']['youtube'] = type(exc).__name__
    if settings.has_instagram:
        from .publish.meta import Meta
        meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id, settings.graph_version)
        for post in posts[-8:]:
            media_id = post.get('posted', {}).get('instagram', {}).get('id')
            if not media_id:
                continue
            try:
                basic = meta.get(media_id, fields='like_count,comments_count')
                values = {'checked_at': data['checked_at'], 'likes': basic.get('like_count', 0),
                          'comments': basic.get('comments_count', 0)}
                try:
                    reply = meta.get(media_id + '/insights', metric='views,reach,saved,shares')
                    for row in reply.get('data', []):
                        v = (row.get('values') or [{}])[0].get('value')
                        if isinstance(v, (int, float)):
                            values[row['name']] = v
                except Exception as exc:
                    data['unavailable']['instagram_insights'] = type(exc).__name__
                data['posts']['instagram:' + media_id] = values
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
