"""The context pack: everything the writer needs to know, assembled from knowledge/."""

from __future__ import annotations

import json

from .config import KNOWLEDGE, brand, pillars, product, product_of, read_text

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
        lines.append(f"- id `{p['id']}` ({p['name']}, sells {p.get('product', 'interview_sarthi')}, "
                     f"weight {p['weight']}, formats {', '.join(p['formats'])}): "
                     f"{p['description']} Example topics: " + "; ".join(p["example_topics"]))
    return "\n".join(lines)


# What each product may and may not be called. Interview Sarthi's rule is the
# one the owner set on 13 September 2026 and it is unchanged; the other two
# simply were not covered by it, because they did not exist.
FRAMING = {
    "interview_sarthi": (
        "Frame the product as live help during the interview itself: an assistant on\n"
        "  your own screen that shows what to say while the interviewer is asking. It is NOT preparation: never\n"
        "  call it a practice partner, a prep tool, a mock interview, coaching, or something you rehearse with.\n"
        "  Posts that sell preparation sell the wrong product and are rejected in code."
    ),
    "prep_sarthi": (
        "Frame the product as a practice interview you speak to, before the real one: it has read the\n"
        "  candidate's CV, it asks about their own projects out loud, it asks again when an answer is vague, and it\n"
        "  scores every answer afterwards. Words like practise, mock interview and rehearse are correct here and\n"
        "  should be used. Never suggest it runs during a real interview, and never promise a job or an offer.\n"
        "  Any score, pause or words-a-minute shown is an illustration, never a real user's result."
    ),
    "apply_sarthi": (
        "Frame the product as the boring half of a job hunt, done for you: jobs ranked against the\n"
        "  candidate's CV, the CV reworded for each one, and the application form filled inside their own Chrome for\n"
        "  them to check and submit. Never say it applies by itself or submits without them, never invent a number\n"
        "  of jobs or users, and never suggest it needs their job-site passwords."
    ),
}


def voice_rules(pid: str | None = None) -> str:
    b = brand()
    pid = pid or "interview_sarthi"
    prod = product(pid)
    forbidden = ", ".join(f'"{w}"' for w in b["forbidden_words"])
    return f"""VOICE AND RULES (non-negotiable)
- Audience: Indian job seekers, freshers and early-career, interviewing online. Talk like a helpful senior
  who has sat in these interviews. Warm, direct, specific. Short sentences.
- Use ONLY facts, prices and links that appear in the business brief. Never invent testimonials, user
  counts, success rates, quotes, awards or partnerships. Never promise a job, an offer or a selection.
- THIS POST SELLS {prod["name"]} AND NOTHING ELSE. Use only the brief's section for it. At most one closing
  line may point at another of the three; never build the post around two.
- Forbidden words and framings anywhere in the output: {forbidden}. Do not talk about the overlay being
  excluded from screen share. {FRAMING[pid]}
- Do not name competitors.
- Hinglish means Hindi and English mixed the way people actually speak, written in ROMAN script (Latin
  letters) for anything that appears on screen or in a caption. Example: "Interviewer ne Hindi mein pooch
  liya? Ghabrao mat, aise bolo." Keep technical words in English.
- Never use the em dash character or the en dash. Use a comma, a colon or a full stop instead.
- No emoji in any text that appears on a slide. Emoji are fine in captions, at most three.
- On-slide text must be short. Titles under 12 words. Bullet points under 16 words. Answers under 60 words.
- Captions: first line is a hook that works without the image. Then 2 to 5 short lines of value. End with
  one soft CTA. Under 900 characters before hashtags.
- Brand name is written exactly "{prod["name"]}". Its website is {prod["site"]}.
"""


def context_pack(plan: dict | str | None = None) -> str:
    """Everything the writer needs, with the rules of the product being sold.

    `plan` is the post's plan or its pillar id. Anything that does not say gets
    Interview Sarthi's rules, which is how this behaved before there were three.
    """
    pid = product_of(plan)
    return "\n\n".join([
        "# BUSINESS BRIEF\n" + business_brief(),
        "# OWNER NOTES\n" + owner_notes(),
        "# CONTENT PILLARS\n" + pillar_text(),
        f"# THE PRODUCT THIS POST SELLS: {product(pid)['name']}",
        voice_rules(pid),
    ])


def brand_json() -> str:
    b = brand()
    keep = {k: b[k] for k in ("name", "tagline", "site", "store_url", "handles", "pricing", "hashtags_core", "hashtags_pool")}
    return json.dumps(keep, ensure_ascii=False, indent=1)
