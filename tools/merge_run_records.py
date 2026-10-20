"""Merge one posting run's receipts into the latest branch after concurrent runs."""
from __future__ import annotations

import argparse
import json
import pathlib


def read(path: pathlib.Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def write(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def merge_history(remote: dict, local: dict) -> dict:
    posts = {str(p['id']): dict(p) for p in remote.get('posts', []) if p.get('id')}
    for newer in local.get('posts', []):
        key = str(newer.get('id') or '')
        if not key:
            continue
        older = posts.get(key, {})
        posted = {**(older.get('posted') or {}), **(newer.get('posted') or {})}
        errors = {**(older.get('errors') or {}), **(newer.get('errors') or {})}
        for platform in posted:
            errors.pop(platform, None)
        merged = {**older, **newer, 'posted': posted, 'errors': errors}
        if older.get('date'):
            merged['date'] = older['date']
        posts[key] = merged
    return {'posts': sorted(posts.values(), key=lambda p: (str(p.get('date') or ''), str(p.get('id') or '')))}


def merge_performance(remote: dict, local: dict) -> dict:
    posts = dict(remote.get('posts') or {})
    for key, candidate in (local.get('posts') or {}).items():
        current = posts.get(key, {})
        if str(candidate.get('checked_at') or '') >= str(current.get('checked_at') or ''):
            chosen = {**current, **candidate}
        else:
            chosen = {**candidate, **current}
        chosen['snapshots'] = {**(candidate.get('snapshots') or {}), **(current.get('snapshots') or {})}
        posts[key] = chosen
    latest = local if str(local.get('checked_at') or '') >= str(remote.get('checked_at') or '') else remote
    return {'checked_at': latest.get('checked_at'), 'posts': posts,
            'unavailable': latest.get('unavailable') or {}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-history', type=pathlib.Path, required=True)
    parser.add_argument('--local-performance', type=pathlib.Path, required=True)
    args = parser.parse_args()
    history_path = pathlib.Path('content/history.json')
    performance_path = pathlib.Path('content/performance.json')
    write(history_path, merge_history(read(history_path, {'posts': []}),
                                      read(args.local_history, {'posts': []})))
    if args.local_performance.exists():
        write(performance_path, merge_performance(read(performance_path, {'posts': {}}),
                                                  read(args.local_performance, {'posts': {}})))


if __name__ == '__main__':
    main()
