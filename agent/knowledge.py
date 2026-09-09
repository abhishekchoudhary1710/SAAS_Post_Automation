"""The context pack: everything the writer needs to know, assembled from knowledge/."""

from __future__ import annotations

import json

from .config import KNOWLEDGE, brand, pillars, read_text

MAX_AUTO_BRIEF_CHARS = 12000


def business_brief() -> str:
    curated = read_text(KNOWLEDGE / "business_brief.md")
    auto = read_text(KNOWLEDGE / "business_brief.auto.md")
    if auto:
        auto = auto[:MAX_AUTO_BRIEF_CHARS]
        curated += ("\n\n---\n# Supplementary brief (auto-generated from the live website, "
                    "lower priority than everything above; if the two disagree, the curated brief wins)\n\n" + auto)
    return curated


def owner_notes() -> str:
    return read_text(KNOWLEDGE / "notes.md", "(no owner notes)")


def pillar_text() -> str:
    lines = []
    for p in pillars():
        lines.append(f"- id `{p['id']}` ({p['name']}, weight {p['weight']}, formats {', '.join(p['formats'])}): "
                     f"{p['description']} Example topics: " + "; ".join(p["example_topics"]))
    return "\n".join(lines)


def voice_rules() -> str:
    b = brand()
    forbidden = ", ".join(f'"{w}"' for w in b["forbidden_words"])
    return f"""VOICE AND RULES (non-negotiable)
- Audience: Indian job seekers, freshers and early-career, interviewing online. Talk like a helpful senior
  who has sat in these interviews. Warm, direct, specific. Short sentences.
- Use ONLY facts, prices and links that appear in the business brief. Never invent testimonials, user
  counts, success rates, quotes, awards or partnerships. Never promise a job, an offer or a selection.
- Forbidden words and framings anywhere in the output: {forbidden}. Do not talk about the overlay being
  excluded from screen share. Frame the product as an assistant, a guide and a practice partner.
- Do not name competitors.
- Hinglish means Hindi and English mixed the way people actually speak, written in ROMAN script (Latin
  letters) for anything that appears on screen or in a caption. Example: "Interviewer ne Hindi mein pooch
  liya? Ghabrao mat, aise bolo." Keep technical words in English.
- Never use the em dash character or the en dash. Use a comma, a colon or a full stop instead.
- No emoji in any text that appears on a slide. Emoji are fine in captions, at most three.
- On-slide text must be short. Titles under 12 words. Bullet points under 16 words. Answers under 60 words.
- Captions: first line is a hook that works without the image. Then 2 to 5 short lines of value. End with
  one soft CTA. Under 900 characters before hashtags.
- Brand name is written exactly "Interview Sarthi". Website is interviewsarthi.com.
"""


def context_pack() -> str:
    return "\n\n".join([
        "# BUSINESS BRIEF\n" + business_brief(),
        "# OWNER NOTES\n" + owner_notes(),
        "# CONTENT PILLARS\n" + pillar_text(),
        voice_rules(),
    ])


def brand_json() -> str:
    b = brand()
    keep = {k: b[k] for k in ("name", "tagline", "site", "store_url", "handles", "pricing", "hashtags_core", "hashtags_pool")}
    return json.dumps(keep, ensure_ascii=False, indent=1)
