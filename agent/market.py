"""Who a post is for: job seekers in India (the default, as before) or everywhere else.

Owner's decision, 25 Sep 2026: some reels are made for viewers outside India. The market is chosen
once, before anything is written, and then travels with the post: the face in the opening, the
writer's audience and rules, the prices on the cards and in the captions, the hashtags and the
voice all follow it. A post with no market is an Indian post, which is how every post behaved
before this existed. Data lives in knowledge/markets.json.
"""
from __future__ import annotations

import re

from .config import KNOWLEDGE, brand, load_json

MARKETS = ("india", "global")
# How far back choose() looks when keeping each product near its global share.
WINDOW = 12

_data: dict | None = None


def data() -> dict:
    global _data
    if _data is None:
        _data = load_json(KNOWLEDGE / "markets.json")
    return _data


def normal(market: str | None) -> str:
    return market if market in MARKETS else "india"


def is_global(market: str | None) -> bool:
    return normal(market) == "global"


def share(pid: str | None) -> float:
    return float(data()["global_share"].get(pid or "interview_sarthi", 0.0))


def choose(pid: str | None, history) -> str:
    """The market for this product's next video: whichever keeps it closest to its global share.

    Balanced against the product's own recent posts rather than drawn at random, so a product with
    a half share alternates instead of posting three of a kind in a row.
    """
    import os

    forced = os.environ.get("POST_MARKET", "").strip().lower()
    if forced in MARKETS:
        return forced                      # a manual run or a preview asking for one market
    target = share(pid)
    if target <= 0:
        return "india"
    if target >= 1:
        return "global"
    pid = pid or "interview_sarthi"
    # Only posts that recorded a market: the ones from before this existed would otherwise read as a
    # long run of Indian posts and send the next several all abroad.
    recent = [p for p in history.posts
              if (p.get("product") or "interview_sarthi") == pid and p.get("market")][-WINDOW:]
    made = sum(1 for p in recent if p.get("market") == "global")
    # Global when doing so leaves the product nearer its share than India would.
    after_global = (made + 1) / (len(recent) + 1)
    after_india = made / (len(recent) + 1)
    return "global" if abs(after_global - target) <= abs(after_india - target) else "india"


def pricing(pid: str | None, market: str | None) -> list[dict]:
    return data()[normal(market)]["pricing"][pid or "interview_sarthi"]


def product_block(pid: str | None, market: str | None, default: str) -> str:
    if not is_global(market):
        return default
    return data()["global"]["product_block"].get(pid or "interview_sarthi", default)


def facts(pid: str | None, market: str | None, text: str) -> str:
    """A product's fact sheet for this market: abroad, the rupee sentences give way to dollar ones."""
    if not is_global(market):
        return text
    kept = [line for line in text.splitlines() if not re.search(r"\bRs\b|₹|rupee|UPI", line)]
    return "\n".join(kept) + "\n" + data()["global"]["price_facts"][pid or "interview_sarthi"] + "\n"


def audience(market: str | None) -> str:
    if is_global(market):
        return data()["global"]["audience"]
    return "Indian job seekers, freshers and early-career, interviewing online."


def writing_rules(market: str | None) -> str:
    """Extra instructions for the writer, empty for India."""
    return data()["global"]["writing_rules"] if is_global(market) else ""


def card_price(pid: str | None, market: str | None, default: tuple[str, str]) -> tuple[str, str]:
    if not is_global(market):
        return default
    lines = data()["global"]["card_price"].get(pid or "interview_sarthi")
    return tuple(lines) if lines else default


def spoken_cta(pid: str | None, market: str | None, default: str) -> str:
    if not is_global(market):
        return default
    return data()["global"]["spoken_cta"].get(pid or "interview_sarthi", default)


def cta_subtitle(market: str | None, default: str) -> str:
    return data()["global"]["cta_subtitle"] if is_global(market) else default


def name_for(key: str) -> str:
    names = data()["global"]["names"]
    return names[sum(map(ord, str(key))) % len(names)]


def hashtags(pid: str | None) -> list[str]:
    return list(data()["global"]["hashtags"].get(pid or "interview_sarthi", []))


def global_tags(pid: str | None, proposed: list[str] | None = None, count: int = 4) -> list[str]:
    """Four tags for an international post: the writer's own where they are not Indian, then the pool."""
    from .story import hashtag_bank

    bank = hashtag_bank()
    indian = {t.lower() for t in brand().get("hashtags_pool") or []}
    for tier in ("specific", "mid", "broad"):
        indian |= {r["tag"].lower() for r in bank.get(tier, [])}
    indian |= {t.lower() for t in bank.get("youtube_topup") or []}
    out: list[str] = []
    for tag in list(proposed or []) + hashtags(pid):
        low = tag.lower()
        if low in indian or re.search(r"india|hindi|hinglish|fresher|placement|naukri|tcs|infosys|wipro", low):
            continue
        if low not in [t.lower() for t in out]:
            out.append(tag)
    return out[:count]


def engagement_questions(market: str | None, default: list[str]) -> list[str]:
    return list(data()["global"]["engagement_questions"]) if is_global(market) else default


def voice_language(language: str | None, market: str | None) -> str:
    """The voice to read an English post in: a neutral international voice abroad, Indian English at home."""
    language = str(language or "english")
    return "english_global" if is_global(market) and language == "english" else language


# Words an international post must not carry. Hinglish is a language, not a crime, but a viewer in
# Toronto who hears it, or reads a price in rupees, learns the post was not made for them.
NOT_FOR_ABROAD = re.compile(r"₹|\bRs\.?\s?\d|\brupees?\b|\bUPI\b|\bhinglish\b|\bfreshers?\b|\bnaukri\b", re.I)


def abroad_problems(text: str) -> list[str]:
    hit = NOT_FOR_ABROAD.search(text or "")
    if not hit:
        return []
    return [f"this post is for viewers outside India but says {hit.group(0)!r}; use the international "
            "prices in US dollars and plain international English"]
