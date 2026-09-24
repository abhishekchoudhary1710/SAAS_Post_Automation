"""Step 1 of a run: decide what today's post is about.

The strategist sees the business brief, the pillars and their weights, what has already
been posted, and today's format. It returns a plan the writer then executes.
"""

from __future__ import annotations

import json
import os

from .config import now_ist, pillars, product_of, schedule
from .llm import LLMError, QuotaError
from .history import History

# Cadence guard. At four posts a day a 40-post memory is only ten days, which is how a
# topic comes back around while it is still on the feed. These windows are counted in posts,
# so they must be raised whenever the cron in .github/workflows/post.yml adds a slot.
# Ten daily slots make 300 posts roughly one month and 30 posts three days.
RECALL_WINDOW = 300
PILLAR_WINDOW = 30
from .knowledge import context_pack
from .llm import Gemini

FORMAT_HELP = {
    "image": "a single 4:5 card on Instagram and Facebook; one idea, complete on its own",
    "carousel": "a 4 to 7 card swipe post on Instagram and Facebook; hook, value, product moment, CTA",
    "film": "a 22 to 28 second generated video with the same shape every day: a candidate in a live online interview, the interviewer's question appears on screen, the candidate glances at the laptop and Interview Sarthi's answer drafts in live, then the answer card and the price card; English",
    "reel": "a 25 to 30 second vertical video with a short Veo or library opening and voice-over cards for Instagram Reels, Facebook Reels and YouTube Shorts",
    "demo": "a 22 to 28 second rendered video of the app doing its job live: a mock online interview call on screen, the interviewer asks ONE question, and the Interview Sarthi panel shows the question and then the answer drafted from the candidate's resume; English narration; the same look every day, only the interview moment changes",
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


def plan_post(llm: Gemini, history: History, fmt: str, language: str, topic: str | None = None, avoid_topics: list[str] | None = None, product_id: str | None = None, film: dict | None = None) -> dict:
    now = now_ist()
    weights = ", ".join(f"{p['id']}={p['weight']}" for p in pillars())
    counts = dict(history.pillar_counts(PILLAR_WINDOW)) or "nothing yet"
    avoid = ""
    if avoid_topics:
        avoid = ("\nThese topics were just attempted and could NOT be written inside the positioning rules: "
                 + "; ".join(avoid_topics) + ". Choose a clearly different topic, and prefer a different "
                 "pillar.")
    series = os.environ.get("CONTENT_SERIES", "").strip()
    if series == "prep_question":
        avoid += ("\nThis is the 11:37 Prep question series: choose one concrete role and interview "
                  "stage, show a weak answer and a stronger answer grounded in a fictional CV, "
                  "then demonstrate Prep Sarthi's practice/report screen. Do not claim that a "
                  "named employer always asks this question. Make today's question distinct.")
    elif series == "apply_workflow":
        avoid += ("\nThis is the 20:37 Apply workflow series: choose one concrete job-search "
                  "task, show a real product step (job match, CV tailoring, or Chrome form filling), "
                  "and make clear that the user checks and submits the application. Do not promise "
                  "a job outcome or invent CV facts. Make today's task distinct.")
    # a film is a reel as far as the pillars are concerned
    allowed = [p["id"] for p in pillars() if ("reel" if fmt in ("film", "demo") else fmt) in p["formats"]]
    # A slot can be given to one product, which is how the daily split is kept:
    # four posts for the Windows app (Live Sarthi), three for Prep Sarthi and three for
    # ApplySarthi. Two of the Windows app's four arrive as the "sales" format, which
    # never reaches this function at all -- pipeline.run sends sales and image straight
    # to create_sales.
    if product_id:
        only = [i for i in allowed if product_of(i) == product_id]
        if only:
            allowed = only
    user = f"""Today is {now.strftime('%A, %d %B %Y')} (India).
Format for today: {fmt} ({FORMAT_HELP[fmt]}). Pillars that allow this format: {', '.join(allowed)}.
Preferred language for today: {language}. Keep it unless the topic clearly suits the other one.
Every post demonstrates the product selected by its pillar. Name that product in the hook and use only its own platform, trial and pricing facts from the brief. Never use Interview Sarthi's Windows platform or 30-minute trial for Prep Sarthi or ApplySarthi.
Each pillar names the product it sells, and the rules differ. For an interview_sarthi pillar the app is live help DURING the interview, not preparation: never plan a topic about practising, mock interviews, rehearsing, preparing, or reviewing afterwards; every topic is one live interviewer question and the answer that appeared on screen while the interview was on.
NEVER choose a topic about the interviewer sharing a screen, a shared code snippet, or answering an on-screen technical question. That feature exists but is not written about in social posts.
Pillar weights (long-run share): {weights}.
Pillar counts over the last {PILLAR_WINDOW} posts: {counts}. Prefer pillars that are behind their weight.{avoid}

Already posted (never repeat a topic or a hook from this list; choose something clearly different):
{history.summary_for_prompt(RECALL_WINDOW, product_id)}
"""
    if film:
        user += ("\nTHE FILM'S SHAPE (the same every day): " + film["story"]["summary"]
                 + "\nTHE PERSON ON SCREEN: " + film["persona"]["text"]
                 + "\nTHE SELLING ANGLE: " + film["angle_text"]
                 + "\nChoose the ONE interviewer question today's film is about: a question a stranger recognises "
                   "instantly (tell me about yourself, why this company, explain your project, salary expectation, "
                   "a question asked in Hindi, and so on) that lets the answer show off this angle. The topic must "
                   "differ from everything already posted.\n")
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
        except QuotaError:
            # Every model has refused for want of allowance. Two more attempts cannot
            # change that, and each one spends requests the next slot will need.
            print("[plan] the writing allowance is spent; not retrying")
            raise
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
    # The pillar decides the product, and the product decides every rule after this.
    plan["product"] = product_of(plan["pillar"])
    if plan.get("language") not in ("english", "hinglish"):
        plan["language"] = language
    if fmt in ("film", "demo"):
        # Owner decision, 11 Sep 2026: the generated films are English only, whatever the topic.
        # A language-switch story is still narrated in English; the switch is what the footage shows.
        plan["language"] = "english"
    plan["format"] = fmt
    if series:
        plan["series"] = series
    return plan
