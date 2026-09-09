"""What has already been posted, so the agent never repeats itself.

`content/history.json` is committed back to the repo by the workflow after every run.
"""

from __future__ import annotations

from collections import Counter

from .config import HISTORY_FILE, load_json, now_ist, save_json


class History:
    def __init__(self, path=HISTORY_FILE):
        self.path = path
        try:
            data = load_json(path)
        except FileNotFoundError:
            data = {"posts": []}
        self.posts: list[dict] = data.get("posts", [])

    def save(self) -> None:
        save_json(self.path, {"posts": self.posts})

    def recent(self, n: int = 40) -> list[dict]:
        return self.posts[-n:]

    def pillar_counts(self, n: int = 12) -> Counter:
        return Counter(p.get("pillar", "?") for p in self.recent(n))

    def language_counts(self, n: int = 6) -> Counter:
        return Counter(p.get("language", "?") for p in self.recent(n))

    def add(self, entry: dict) -> None:
        entry.setdefault("date", now_ist().strftime("%Y-%m-%d %H:%M IST"))
        self.posts.append(entry)

    def summary_for_prompt(self, n: int = 40) -> str:
        if not self.posts:
            return "(nothing posted yet)"
        lines = []
        for post in self.recent(n):
            lines.append(f"- {post.get('date', '?')[:10]} | {post.get('format', '?')} | {post.get('pillar', '?')} | "
                         f"{post.get('language', '?')} | {post.get('topic', '?')} | hook: {post.get('hook', '')[:80]}")
        return "\n".join(lines)
