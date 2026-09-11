"""Step 1 of a run: decide what today's post is about.

The strategist sees the business brief, the pillars and their weights, what has already
been posted, and today's format. It returns a plan the writer then executes.
"""

from __future__ import annotations

import json

from .config import now_ist, pillars, schedule
from .llm import LLMError
from .history import History
from .knowledge import context_pack
from .llm import Gemini

FORMAT_HELP = {
    "image": "a single 4:5 card on Instagram and Facebook; one idea, complete on its own",
    "carousel": "a 4 to 7 card swipe post on Instagram and Facebook; hook, value, product moment, CTA",
    "film": "a 25 to 30 second generated video: real footage of a candidate (Veo), then the real interface card and the price card; English; no captions",
    "reel": "a 25 to 30 second vertical video with a Veo hook and voice-over cards for Instagram Reels, Facebook Reels and YouTube Shorts",
}

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def decide_format(requested: str | None) -> str:
    if requested and requested != "auto":
        return requested
    today = WEEKDAYS[now_ist().weekday()]
    return schedule()["weekday_format"].get(today, "image")


def decide_language(history: History, requested: str | None) -> str:
    if requested and requested != "auto":
        return requested
    rotation = schedule().get("language_rotation") or ["english", "hinglish"]
    return rotation[len(history.posts) % len(rotation)]


def plan_post(llm: Gemini, history: History, fmt: str, language: str, topic: str | None = None, avoid_topics: list[str] | None = None, film: dict | None = None) -> dict:
    now = now_ist()
    weights = ", ".join(f"{p['id']}={p['weight']}" for p in pillars())
    counts = dict(history.pillar_counts(12)) or "nothing yet"
    avoid = ""
    if avoid_topics:
        avoid = ("\nThese topics were just attempted and could NOT be written inside the positioning rules: "
                 + "; ".join(avoid_topics) + ". Choose a clearly different topic, and prefer a different "
                 "pillar.")
    # a film is a reel as far as the pillars are concerned
    allowed = [p["id"] for p in pillars() if ("reel" if fmt == "film" else fmt) in p["formats"]]
    user = f"""Today is {now.strftime('%A, %d %B %Y')} (India).
Format for today: {fmt} ({FORMAT_HELP[fmt]}). Pillars that allow this format: {', '.join(allowed)}.
Preferred language for today: {language}. Keep it unless the topic clearly suits the other one.
Every post is a demonstration of the app: the plan's hook must name Interview Sarthi and the interview moment, and facts_to_use must include what it is, where it runs and the free 30 minutes.
NEVER choose a topic about the interviewer sharing a screen, a shared code snippet, or answering an on-screen technical question. That feature exists but is not written about in social posts.
Pillar weights (long-run share): {weights}.
Pillar counts over the last 12 posts: {counts}. Prefer pillars that are behind their weight.{avoid}

Already posted (never repeat a topic or a hook from this list; choose something clearly different):
{history.summary_for_prompt(40)}
"""
    if film:
        user += ("\nTODAY'S STORY SHAPE: " + film["story"]["name"] + ". " + film["story"]["summary"]
                 + "\nTHE PERSON ON SCREEN: " + film["persona"]["text"]
                 + "\nTHE SELLING ANGLE: " + film["angle_text"]
                 + "\nChoose a topic and question that fit this story and angle. The topic must differ from everything already posted.\n")
    if topic:
        user += f"\nThe owner asked for this topic today, build the plan around it: {topic}\n"
    user += """
Return ONLY a JSON object:
{
  "pillar": "<pillar id>",
  "topic": "<specific topic, under 12 words>",
  "angle": "<one sentence: the specific take that makes this post worth saving>",
  "language": "english" | "hinglish",
  "persona": "<who exactly this is for, one line>",
  "facts_to_use": ["<only facts, prices or product details from the business brief that this post may state>"],
  "guide_link": "<one full URL from the brief's guide list that matches the topic, or null>",
  "reason": "<why this topic today, one line>"
}"""
    system = ("You are the content strategist for Interview Sarthi's Instagram, Facebook and YouTube Shorts. "
              "You plan one post at a time. Be specific and practical; generic advice does not get saved.\n\n"
              + context_pack())
    plan = None
    for attempt in range(3):
        try:
            candidate = llm.json(system, user, temperature=0.9 if attempt == 0 else 0.5, max_tokens=4096)
        except LLMError as exc:
            # 11 Sep 2026: a production dry run died here on a reply that was not JSON at all,
            # most likely cut off mid-object by the old 1500-token limit. Ask again instead.
            print(f"[plan] attempt {attempt + 1} was not valid JSON, retrying: {str(exc)[:90]}")
            candidate = None
        if isinstance(candidate, dict) and "topic" in candidate:
            plan = candidate
            break
        # Also seen in the wild: the model returned just the facts_to_use array. One malformed
        # plan is not a reason to publish nothing, so say what was wrong and ask again.
        if candidate is not None:
            print(f"[plan] attempt {attempt + 1} came back in the wrong shape, retrying")
        user += ("\n\nYour previous reply was not the required JSON OBJECT. Return one complete object "
                 "with the keys listed above, not a list, not prose, and keep every value short.")
    if plan is None:
        raise ValueError("strategist returned an unexpected shape three times")
    if plan.get("pillar") not in allowed:
        plan["pillar"] = allowed[0]
    if plan.get("language") not in ("english", "hinglish"):
        plan["language"] = language
    plan["format"] = fmt
    return plan
