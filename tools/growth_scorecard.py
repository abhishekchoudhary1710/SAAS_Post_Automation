"""Build an age-matched seven-day publishing scorecard from committed receipts."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'content/history.json'
METRICS = ROOT / 'content/performance.json'
OUT = ROOT / 'out/growth-scorecard.md'
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _read(path: pathlib.Path, key: str) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {key: [] if key == 'posts' else {}}


def _date(post: dict) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(post['date'], '%Y-%m-%d %H:%M IST').replace(tzinfo=IST)
    except (KeyError, TypeError, ValueError):
        return None


def build(history: dict, performance: dict, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(IST)
    posts = history.get('posts', [])
    metrics = performance.get('posts', {})
    recent = [p for p in posts if (date := _date(p)) and dt.timedelta() <= now - date < dt.timedelta(days=7)]
    lines = [f'# Social growth scorecard — {now:%Y-%m-%d} IST', '',
             'Views are compared at approximately 48 hours. A missing metric is unknown, not zero.', '',
             f'Published posts in the last seven days: **{len(recent)}** (target after launch: 70).', '']
    for product in ('interview_sarthi', 'prep_sarthi', 'apply_sarthi'):
        rows = [p for p in recent if p.get('product') == product]
        lines.append(f'- {product}: {len(rows)} posts')
    lines += ['', '| Platform | Published in 7d | 48h views measured | Median 48h views | '
              '7d views measured | Median 7d views |',
              '|---|---:|---:|---:|---:|---:|']
    scored = []
    for platform in ('youtube', 'instagram', 'facebook'):
        published = [p for p in recent if (p.get('posted') or {}).get(platform)]
        values, week_values = [], []
        for post in recent:
            media_id = ((post.get('posted') or {}).get(platform) or {}).get('id')
            row = metrics.get(platform + ':' + str(media_id), {}) if media_id else {}
            snap = row.get('snapshots', {}).get('48h') or {}
            week = row.get('snapshots', {}).get('7d') or {}
            if isinstance(snap.get('views'), (int, float)):
                values.append(snap['views'])
                scored.append((platform, snap['views'], post))
            if isinstance(week.get('views'), (int, float)):
                week_values.append(week['views'])
        median = f'{statistics.median(values):g}' if values else 'unknown'
        week_median = f'{statistics.median(week_values):g}' if week_values else 'unknown'
        lines.append(f'| {platform} | {len(published)} | {len(values)} | {median} | '
                     f'{len(week_values)} | {week_median} |')
    groups: dict[tuple[str, str, str], list[float]] = {}
    for platform, views, post in scored:
        family = str(post.get('series') or post.get('mode') or post.get('format') or 'unknown')
        key = (platform, str(post.get('product') or 'unknown'), family)
        groups.setdefault(key, []).append(views)
    lines += ['', '| Platform | Product | Content family | 48h samples | Median views |',
              '|---|---|---|---:|---:|']
    for (platform, product, family), values in sorted(groups.items()):
        lines.append(f'| {platform} | {product} | {family} | {len(values)} | '
                     f'{statistics.median(values):g} |')
    if not groups:
        lines.append('| All | — | — | 0 | unknown |')
    lines += ['', '## Reels with 48h measurements', '']
    for label, rows in (('Top five', sorted(scored, key=lambda x: x[1], reverse=True)[:5]),
                        ('Bottom five', sorted(scored, key=lambda x: x[1])[:5])):
        lines.append(f'**{label}:**')
        if not rows:
            lines.append('No age-matched view measurements yet.')
        for platform, views, post in rows:
            url = ((post.get('posted') or {}).get(platform) or {}).get('url')
            link = f' — {url}' if url else ''
            lines.append(f"- {platform}: {views} views — {post.get('product', '?')} — "
                         f"{post.get('hook', post.get('topic', '?'))}{link}")
        lines.append('')
    seconds = sum(float(p.get('veo_seconds') or 0) for p in recent)
    lines += [f'Veo openings recorded in the last seven days: **{seconds:g} seconds** '
              f'(estimated **${seconds * .08:.2f}** at the 720p no-audio list rate).',
              'Actual Cloud charges and promotional credit left: **unknown from this repository**.',
              'Qualified visits, product starts and paid conversions attributable to these posts: '
              '**unknown until tagged links and product events are joined to this scorecard**.', '']
    missing = performance.get('unavailable') or {}
    if missing:
        lines.append('Metric access errors: ' + ', '.join(f'{k} ({v})' for k, v in missing.items()) + '.')
    lines += ['', 'Decision rule: after at least ten comparable posts in a content family, '
              'keep families that grow qualified product starts. If views rise without starts, '
              'check the profile link and landing page. If attention is weak, change the first '
              'two seconds and product proof while keeping the posting volume.', '']
    return '\n'.join(lines)


def main() -> None:
    report = build(_read(HISTORY, 'posts'), _read(METRICS, 'posts'))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
