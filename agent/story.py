"""Choosing the day's story shape, person and selling angle, and turning them into Veo prompts.

Variety is the whole point of the daily generated reel, so three things rotate independently and
history keeps each from repeating too soon: the story shape (never the same as yesterday, and the
least-recently-used wins), the person and setting (no combination within 14 days), and the
selling angle (least-recently-used among the shape's best fits). Also the tag picker, because it
needs the same topic-matching idea.
"""

from __future__ import annotations

import hashlib
import json
import random
import re

from .config import KNOWLEDGE, now_ist
from .history import History

_cache: dict[str, dict] = {}


def _load(name: str) -> dict:
    if name not in _cache:
        _cache[name] = json.loads((KNOWLEDGE / name).read_text(encoding="utf-8"))
    return _cache[name]


def stories() -> dict:
    return _load("stories.json")


def personas() -> dict:
    return _load("personas.json")


def hashtag_bank() -> dict:
    return _load("hashtags.json")


def _recent_values(history: History, key: str, n: int) -> list[str]:
    return [str(p.get(key)) for p in history.recent(n) if p.get(key)]


def _least_recent(options: list[str], used_order: list[str]) -> str:
    """The option whose last use is furthest back; never-used options win outright."""
    last_seen = {}
    for i, value in enumerate(reversed(used_order)):      # index 0 = most recent
        last_seen.setdefault(value, i)
    never = [o for o in options if o not in last_seen]
    if never:
        return never[0]
    return max(options, key=lambda o: last_seen[o])


def choose_story(history: History, requested: str | None = None) -> dict:
    all_stories = stories()["stories"]
    by_id = {s["id"]: s for s in all_stories}
    if requested and requested in by_id:
        return by_id[requested]
    used = _recent_values(history, "story", 30)
    yesterday = used[0] if used else None
    candidates = [s["id"] for s in all_stories if s["id"] != yesterday] or list(by_id)
    return by_id[_least_recent(candidates, used)]


def choose_angle(history: History, story: dict) -> tuple[str, str]:
    angles = stories()["angles"]
    used = _recent_values(history, "angle", 30)
    preferred = [a for a in story.get("best_angles", []) if a in angles] or list(angles)
    key = _least_recent(preferred, used)
    return key, angles[key]


def choose_persona(history: History) -> dict:
    """A person, a setting and a light. Deterministic for the day, avoids the last 14 combinations."""
    p = personas()
    used = set(_recent_values(history, "persona", 14))
    seed = int(hashlib.sha256(now_ist().strftime("%Y-%m-%d").encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    for _ in range(200):
        person = rng.choice(p["people"])
        setting = rng.choice(p["settings"])
        light = rng.choice(p["light"])
        key = hashlib.sha1(f"{person}|{setting}".encode()).hexdigest()[:10]
        if key not in used:
            break
    return {"id": key, "person": person, "setting": setting, "light": light,
            "text": f"{person}, in {setting}, {light}"}


def beat_prompts(story: dict, persona: dict, actions: list[str]) -> list[dict]:
    """Fill each beat's frame with the persona and the writer's action line."""
    look = stories()["look"]
    laptop = stories()["laptop"]
    out = []
    for i, beat in enumerate(story["beats"]):
        action = (actions[i] if i < len(actions) and actions[i] else "").strip()
        prompt = beat["frame"].format(look=look, persona=persona["text"], laptop=laptop, action=action)
        prompt = re.sub(r"\s{2,}", " ", prompt).strip()
        out.append({"kind": beat["kind"], "seconds": beat["seconds"], "prompt": prompt})
    return out


def pick_tags(topic: str, proposed: list[str] | None = None, count: int = 4) -> list[str]:
    """Four topic tags from the bank: two specific, one mid, one broad, matched to the topic.

    Tags the writer proposed are kept when they exist in the bank, so its judgement counts, but
    anything outside the bank (the generic #Motivation kind of thing) is replaced.
    """
    bank = hashtag_bank()
    text = (topic or "").lower()
    proposed_l = {t.lower() for t in (proposed or [])}

    def ranked(tier: str) -> list[str]:
        rows = bank[tier]
        scored = []
        for r in rows:
            score = sum(1 for w in r["match"] if w in text) * 10
            if r["tag"].lower() in proposed_l:
                score += 5
            scored.append((score, r["tag"]))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored]

    picks: list[str] = []
    for tier, take in (("specific", 2), ("mid", 1), ("broad", 1)):
        for tag in ranked(tier):
            if tag not in picks:
                picks.append(tag)
                take -= 1
                if take == 0:
                    break
    return picks[:count]
