"""Steps 2 and 3 of a run: write the post, then review it against the rules.

The writer returns slide specs plus caption; the reviewer is a second model pass that
checks for invented facts, forbidden framings and weak hooks, and returns a revised
version when needed. Code-level validation runs after both, so nothing structurally
broken reaches the renderer or the publishers.
"""

from __future__ import annotations

import json
import re

from .config import SAMPLES, brand, load_json, schedule
from .knowledge import brand_json, context_pack
from .llm import Gemini, LLMError

# Broad tags put a post in a global pool it cannot win and tell the algorithm nothing about who
# should see it. Instagram allows five, so each slot has to carry information.
GENERIC_TAGS = {
    "#interviewtips", "#interviewpreparation", "#interviewprep", "#jobinterview", "#interview",
    "#interviews", "#careeradvice", "#careertips", "#career", "#careers", "#jobs", "#job", "#hiring",
    "#work", "#motivation", "#success", "#inspiration", "#freshers", "#fresher", "#interviewskills",
    "#confidence", "#tips", "#viral", "#trending", "#reels", "#shorts", "#explore", "#fyp",
}

# Total narration words per reel, by language. Measured delivery is about 1.95 words a second in
# English and 1.85 in Hindi once pauses are counted, and the target is 25 to 32 seconds on screen.
NARRATION_BUDGET = {"english": (48, 60), "hinglish": (40, 52), "hindi": (40, 52)}


def narration_budget(language: str | None) -> tuple[int, int]:
    return NARRATION_BUDGET.get(str(language or "english").lower(), NARRATION_BUDGET["english"])


SLIDE_TYPES = """SLIDE TYPES (use exactly these field names)
- {"type":"hook","title":"<under 12 words, may contain one **bold** phrase>","subtitle":"<optional, under 25 words>","tag":"<2 or 3 word label shown top right>","kicker":"<optional 3 word label above the title>"}
- {"type":"stat","number":"<short, e.g. Rs 99 or 30 min or 2 days>","label":"<under 10 words>","note":"<optional, under 18 words>"}
- {"type":"points","title":"<under 9 words>","points":["<3 to 5 items, each under 14 words>"],"tag":"..."}
- {"type":"qa","question":"<what the interviewer asks, under 18 words>","answer":"<first person, spoken style, 35 to 60 words, 1 to 3 **bold** key phrases>","tag":"...","label_q":"<optional, default Interviewer asked>","label_a":"<optional, default Interview Sarthi showed>"} -- the "tag" on a qa slide must NOT repeat the label; use the topic instead, e.g. "Project round"
- {"type":"myth","myth":"<under 18 words>","fact":"<under 24 words>","tag":"..."}
- {"type":"product","title":"<under 14 words, mention Interview Sarthi>","caption":"<under 22 words>","image":"overlay_hinglish"|"overlay_english"|"logo"|"mascot","theme":"dark"}
- {"type":"cta","title":"<under 7 words, default 30 minutes free. No card.>","subtitle":"<under 14 words>","show_pricing":true}
- {"type":"quote","text":"<under 26 words>","by":"<optional>"}
Every slide may also carry "theme": "light" or "dark".
"""

FORMAT_SPEC = {
    "image": """FORMAT: single image. Exactly ONE slide, preferably "qa" with "label_a": "Interview Sarthi showed". The "tag" must NOT be the brand name (the logo is already in the corner); use the situation, e.g. "Project round" or "HR round". It must work alone, with no
CTA slide; the CTA lives in the caption. The slide needs a "tag".""",
    "carousel": """FORMAT: carousel. {min} to {max} slides. Slide 1 MUST be type "hook" with a "tag": the scroll-stopper,
a claim or a question the reader wants resolved. Middle slides deliver the value (points, qa, myth, stat, quote),
one idea per slide, in a logical order. Include at most one "product" slide, and only if it fits the topic
naturally; a "product" slide is REQUIRED in every carousel whatever the pillar, usually second to last. Slide 1's title or tag names Interview Sarthi. The LAST slide MUST be type "cta".
HASHTAG RULE: give exactly four, and make every one specific enough that a particular person
would search it, and true of THIS post. Name a company or exam (#TCSNQT, #InfosysHiring) only when
the post is actually about that company or exam; otherwise tag the situation instead: #HRRound,
#OnlineInterview, #SalaryNegotiation, #OffCampusDrive, #CampusPlacement, #BTechJobs, #FinalYearStudents.
Never use broad tags like #CareerAdvice, #JobInterview, #InterviewTips, #Motivation, #Success,
#Jobs or #Career: they put the post in a global pool it cannot win and tell the algorithm
nothing about who should see it. Do not add a brand tag, one is appended automatically.

COUNTING RULE: if the hook, the caption or any title promises a number of things ("5 questions", "3 mistakes",
"4 lines"), the post must actually contain that many, each one clearly separate and complete. Count them before
you finish. If you can only write four good ones, say four in the hook. A promise of five answered with four is
the single most common failure here.""",
    "reel": """FORMAT: reel. {min} to {max} slides, each with an extra field "narration": the exact spoken words for that
slide, 8 to 16 words, natural speech, no markdown. TOTAL narration 48 to 60 words in English, 40 to 52 in Hinglish.
This is measured, not a guess: the voice delivers about two words a second once pauses are counted, so 60 words
is 30 seconds, and anything past 70 words gets the ending cut off. Never pad narration to reach a count. Viewers who finish are what gets a reel shown to strangers, so short wins.
Slide 1 is a "hook" whose title or tag names Interview Sarthi and whose narration says in one sentence what the app is and the moment it is about to handle. Middle slides: exactly one "qa" slide showing the app's output for the interviewer's question, with "label_a": "Interview Sarthi showed"; optionally one points, myth or stat slide; a points slide in a reel carries exactly 3 points. The LAST slide is "product" or "cta" and its
narration ends with a spoken call to action such as "Try Interview Sarthi free, link in bio". On-screen text
stays short; the narration can say a little more. In narration write prices as words ("99 rupees" or "99 रुपये"),
never with a currency symbol.
For hinglish posts the on-screen text is Roman script, but the narration must be written in mixed script:
Hindi words in Devanagari, English words in Latin letters, because the voice reads Devanagari correctly and
Roman Hindi badly. Example narration: "Interviewer ने बीच में Hindi में पूछ लिया? घबराओ मत। जिस language में सवाल आया, उसी में जवाब दो।"
Also return "reel": {"youtube_title": "<under 90 characters, ends with #Shorts>", "youtube_description": "<2 to 4 lines>",
"youtube_tags": ["<8 to 12 short tags>"]}.""",
}

OUTPUT_SCHEMA = """OUTPUT: ONLY a JSON object with exactly these keys:
{
  "pillar": "<pillar id from the plan>",
  "topic": "<from the plan>",
  "language": "english" | "hinglish",
  "hook": "<the first line of the caption, under 15 words, works without the image>",
  "slides": [ ...slide objects... ],
  "caption": "<hook line, blank line, 2 to 6 short value lines, blank line, one soft CTA line. Under 900 characters. No hashtags here.>",
  "hashtags": ["<exactly 4 hashtags, no brand tag, each starting with #. See the hashtag rule below.>"],
  "reel": null | {...}
}"""


def _example(fmt: str) -> str:
    sample = load_json(SAMPLES / f"sample_{fmt}.json")
    return json.dumps(sample, ensure_ascii=False, indent=1)


def _format_spec(fmt: str) -> str:
    """Fill {min} and {max} in the format spec.

    Deliberately str.replace and not str.format: these specs contain literal JSON braces
    such as {"youtube_title": ...}, which str.format would read as placeholders and reject.
    """
    spec = FORMAT_SPEC[fmt]
    if fmt in ("carousel", "reel"):
        sizes = schedule()[fmt]
        spec = spec.replace("{min}", str(sizes["min_slides"])).replace("{max}", str(sizes["max_slides"]))
    return spec


def write_post(llm: Gemini, plan: dict, fmt: str, feedback: str | None = None) -> dict:
    system = ("You are the copywriter for Interview Sarthi. You write posts that Indian job seekers save and share, "
              "and every post is a demonstration of the product doing its job. PRODUCT-FIRST RULE, no exceptions: "
              "(a) the hook line and slide 1 name Interview Sarthi and the interview moment, so a stranger knows in "
              "three seconds that this is a Windows app that listens to an online interview and shows what to say; "
              "(b) the middle shows the app's output for one real interviewer question, in a qa slide whose label_a is "
              "'Interview Sarthi showed', or a product slide; (c) the post ends on a product or cta slide with where it "
              "runs, 30 minutes free, passes from Rs 99. Frame it as an assistant drafting from the candidate's own "
              "resume; never as anything hidden. "
              "and you follow the rules below exactly.\n\n" + context_pack() + "\n\n# BRAND DATA\n" + brand_json()
              + "\n\n" + SLIDE_TYPES + "\n" + _format_spec(fmt) + "\n\n" + OUTPUT_SCHEMA
              + "\n\nEXAMPLE OF THE SHAPE (do not copy its topic or wording):\n" + _example(fmt))
    user = "PLAN FOR THIS POST:\n" + json.dumps(plan, ensure_ascii=False, indent=1)
    user += ("\n\nWrite the post now. Make the hook specific to the topic. Every slide must earn its place. "
             "Use only facts from the brief and the plan's facts_to_use.")
    if fmt == "reel" and plan.get("language") == "hinglish":
        # The Hindi voice reads noticeably more slowly than the English one, so the same word
        # count produces a much longer video. Measured: 114 words came out at 55 seconds.
        lo, hi = narration_budget("hinglish")
        user += (f"\n\nIMPORTANT: this reel is in Hinglish and the Hindi voice reads more slowly. Keep the TOTAL "
                 f"narration between {lo} and {hi} words, or the video runs long and the ending is cut off. "
                 "Shorter narration per slide, same number of slides.")
    if feedback:
        user += "\n\nA reviewer rejected the previous draft for these reasons; fix every one of them:\n" + feedback
    # Hinglish narration is written in Devanagari, which costs several output tokens per
    # character once JSON-escaped, so reels need noticeably more room than text posts.
    content = llm.json(system, user, temperature=0.85, max_tokens=16000 if fmt == "reel" else 10000)
    if not isinstance(content, dict) or "slides" not in content:
        raise ValueError("writer returned an unexpected shape: " + json.dumps(content)[:400])
    content.setdefault("pillar", plan.get("pillar"))
    content.setdefault("topic", plan.get("topic"))
    content.setdefault("language", plan.get("language", "english"))
    return content


def review_post(llm: Gemini, content: dict, fmt: str) -> dict:
    system = ("You are the editor and compliance reviewer for Interview Sarthi's social posts. You are strict about "
              "facts and framing, and you care that the post is genuinely useful.\n\n" + context_pack()
              + "\n\n" + SLIDE_TYPES + "\n" + _format_spec(fmt))
    budget_line = ""
    if fmt == "reel":
        lo, hi = narration_budget(content.get("language"))
        budget_line = (f"NARRATION BUDGET for this {content.get('language')} reel: {lo} to {hi} words in total. "
                       f"Only raise it as an issue if the total is under {lo - 8} or over {hi + 8}. Never pad "
                       "narration to reach a count; shorter is better than filler.\n\n")
    user = (budget_line + "Review this draft. Check, in order: (1) any fact, price, number, claim or feature that is NOT in the "
            "business brief; (2) forbidden words or framing: anything about being hidden from a screen share, and "
            "anything about the interviewer sharing a screen or a code snippet, which is never written about "
            "in social posts whatever words are used; "
            "(3) em dashes or en dashes anywhere; (4) on-slide text that is too long for its slide type; (5) slide "
            "structure rules for the format; (6) a hook that is generic or could apply to any post; (7) language "
            "consistency (Roman-script Hinglish on screen; for reels, mixed-script narration); (8) COUNTING: if the "
            "hook, caption or any title promises a number of items, count the items actually delivered in the slides "
            "and confirm they match. Fix by changing the number to the true count, or by adding the missing item; "
            "(9) FIRST-TIME VIEWER: after this post, would a stranger know that Interview Sarthi is a Windows app "
            "that listens to their online interview and shows what to say, that they can see it do so here, and "
            "that 30 minutes are free? If any of the three is missing, it is an issue; fix it in the hook, the qa "
            "label or the closing slide without adding length.\n\n"
            "Return ONLY JSON: {\"ok\": true|false, \"issues\": [\"<specific issue>\"], \"revised\": <the full corrected "
            "post JSON in the same shape, or null if ok>}. When you revise, change only what the issues require.\n\n"
            "DRAFT:\n" + json.dumps(content, ensure_ascii=False, indent=1))
    verdict = llm.json(system, user, temperature=0.2, max_tokens=20000 if fmt == "reel" else 12000)
    if not isinstance(verdict, dict):
        return {"ok": True, "issues": [], "revised": None}
    return verdict


# ----------------------------------------------------------------------------- validation
DASHES = re.compile("[—–]")
REQUIRED = {
    "hook": ["title"], "stat": ["number", "label"], "points": ["title", "points"], "qa": ["question", "answer"],
    "myth": ["myth", "fact"], "product": ["title"], "cta": [], "quote": ["text"],
}


def _strip_dashes(value):
    if isinstance(value, str):
        return DASHES.sub(lambda m: ", " if m.group(0) == "—" else "-", value).replace(" ,", ",")
    if isinstance(value, list):
        return [_strip_dashes(v) for v in value]
    if isinstance(value, dict):
        return {k: _strip_dashes(v) for k, v in value.items()}
    return value


def _all_text(content: dict) -> str:
    chunks = []

    def walk(value):
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)

    walk(content)
    return "\n".join(chunks)


def validate(content: dict, fmt: str) -> tuple[dict, list[str]]:
    """Normalise the post in place and return (content, problems). Problems are for the model to fix."""
    content = _strip_dashes(content)
    problems: list[str] = []
    sch = schedule()
    slides = content.get("slides") or []
    if not isinstance(slides, list) or not slides:
        return content, ["no slides"]
    for i, s in enumerate(slides, 1):
        if not isinstance(s, dict):
            problems.append(f"slide {i} is not an object")
            continue
        kind = s.get("type")
        if kind not in REQUIRED:
            problems.append(f"slide {i} has unknown type {kind!r}")
            continue
        for field in REQUIRED[kind]:
            if not s.get(field):
                problems.append(f"slide {i} ({kind}) is missing {field!r}")
        if kind == "points":
            pts = [p for p in (s.get("points") or []) if isinstance(p, str) and p.strip()]
            if not 2 <= len(pts) <= 6:
                problems.append(f"slide {i} (points) needs 3 to 5 points, has {len(pts)}")
            s["points"] = pts[:6]
        if kind == "qa" and len(str(s.get("answer", "")).split()) > 75:
            problems.append(f"slide {i} (qa) answer is over 75 words")
        if kind == "hook" and len(str(s.get("title", "")).split()) > 16:
            problems.append(f"slide {i} (hook) title is over 16 words")
    kinds = [s.get("type") for s in slides if isinstance(s, dict)]
    if fmt == "image":
        if len(slides) != 1:
            problems.append(f"image format needs exactly 1 slide, has {len(slides)}")
        if kinds and kinds[0] == "cta":
            problems.append("an image post must not be a cta slide")
    elif fmt == "carousel":
        lo, hi = sch["carousel"]["min_slides"], sch["carousel"]["max_slides"]
        if not lo <= len(slides) <= hi:
            problems.append(f"carousel needs {lo} to {hi} slides, has {len(slides)}")
        if kinds and kinds[0] != "hook":
            problems.append("carousel slide 1 must be a hook")
        if kinds and kinds[-1] != "cta":
            problems.append("carousel last slide must be a cta")
        if "product" not in kinds:
            problems.append("carousel needs a product slide: every post shows the app, whatever the pillar")
        if kinds.count("cta") > 1 or kinds.count("product") > 1:
            problems.append("at most one product slide and one cta slide")
    elif fmt == "reel":
        lo, hi = sch["reel"]["min_slides"], sch["reel"]["max_slides"]
        if not lo <= len(slides) <= hi:
            problems.append(f"reel needs {lo} to {hi} slides, has {len(slides)}")
        words = 0
        for i, s in enumerate(slides, 1):
            narration = str(s.get("narration") or "").strip()
            if len(narration.split()) < 5:
                problems.append(f"reel slide {i} has no usable narration")
            words += len(narration.split())
        lo, hi = narration_budget(content.get("language"))
        if words and not (lo - 14) <= words <= (hi + 18):
            problems.append(f"total narration is {words} words; the budget for a {content.get('language')} reel is "
                            f"{lo} to {hi}, because the voice delivers two words a second and the reel must finish "
                            f"inside 32 seconds")
        reel = content.get("reel") or {}
        if not reel.get("youtube_title"):
            problems.append("reel.youtube_title missing")
        content["reel"] = reel
    caption = str(content.get("caption") or "").strip()
    first_slide_text = " ".join(str(v) for v in (slides[0].values() if slides else []) if isinstance(v, str))
    if "interview sarthi" not in (str(content.get("hook") or "") + " " + first_slide_text).lower():
        problems.append("the hook line or slide 1 must name Interview Sarthi: a stranger has to know what this is "
                        "in the first three seconds")
    if len(caption) < 60:
        problems.append("caption too short")
    if len(caption) > 1400:
        problems.append("caption over 1400 characters")
    content["caption"] = caption
    tags = []
    for tag in content.get("hashtags") or []:
        tag = "#" + re.sub(r"[^0-9A-Za-z_]", "", str(tag))
        if len(tag) > 1 and tag.lower() not in [t.lower() for t in tags] and tag.lower() not in GENERIC_TAGS:
            tags.append(tag)
    if len(tags) < 3:
        # The model ignored the specificity rule; top up from the curated pool rather than fail the run.
        for tag in brand().get("hashtags_pool") or []:
            if tag.lower() not in [t.lower() for t in tags]:
                tags.append(tag)
            if len(tags) >= 4:
                break
    content["hashtags"] = tags[:8]
    if fmt == "reel":
        kinds_r = [str(s.get("type")) for s in slides]
        if not any(k in ("qa", "product") for k in kinds_r):
            problems.append("reel needs a qa or product slide showing the app's output")
        for s in slides:
            if s.get("type") == "points" and isinstance(s.get("points"), list) and len(s["points"]) > 3:
                s["points"] = s["points"][:3]
    lowered = _all_text(content).lower()
    for word in brand()["forbidden_words"]:
        if word.lower() in lowered:
            problems.append(f"forbidden word or phrase used: {word!r}")
    # The concept, not one spelling of it. A model told to avoid "screen share" will happily write
    # "screen par code dikha diya" and land in exactly the same place.
    screen_framings = ("screen share", "screen-share", "screenshare", "shared screen", "shares screen",
                       "sharing screen", "screen reading", "reads the screen", "read the screen",
                       "on-screen code", "code on screen", "screen par", "screen pe", "shared code",
                       "share a code", "shares a code", "shared a code", "code snippet")
    hit = next((f for f in screen_framings if f in lowered), None)
    if hit:
        problems.append(f"mentions the interviewer's screen ({hit!r}); screen reading is not written about in "
                        "social posts, write about language, recall or resume-grounded answers instead")
    return content, problems


def produce(llm: Gemini, plan: dict, fmt: str, max_rounds: int = 3) -> tuple[dict, list[str]]:
    """Write, validate, review, revise. Returns (content, notes). Raises if it never passes."""
    notes: list[str] = []
    feedback: str | None = None
    last_clean: dict | None = None
    for round_no in range(1, max_rounds + 1):
        try:
            content = write_post(llm, plan, fmt, feedback)
        except (LLMError, ValueError) as exc:
            # Usually a reply cut off mid-JSON. Transient, so ask again and keep the run alive.
            notes.append(f"round {round_no}: generation failed: {exc}")
            feedback = ("Your previous reply was not valid JSON, most likely because it ran past the "
                        "length limit and was cut off. Return one complete JSON object, and keep every "
                        "text field at the short end of its allowed range.")
            continue
        content, problems = validate(content, fmt)
        if problems:
            notes.append(f"round {round_no}: structural problems: {problems}")
            feedback = "\n".join(f"- {p}" for p in problems)
            continue
        last_clean = content
        try:
            verdict = review_post(llm, content, fmt)
        except (LLMError, ValueError) as exc:
            # The post already passed structural validation and the hard word rules, so a
            # reviewer outage is not a reason to publish nothing.
            notes.append(f"round {round_no}: reviewer unavailable ({exc}); accepting the validated draft")
            return content, notes
        issues = [str(i) for i in (verdict.get("issues") or [])]
        if verdict.get("ok", True) and not issues:
            notes.append(f"round {round_no}: reviewer approved")
            return content, notes
        notes.append(f"round {round_no}: reviewer issues: {issues}")
        revised = verdict.get("revised")
        if isinstance(revised, dict) and revised.get("slides"):
            revised, problems = validate(revised, fmt)
            if not problems:
                notes.append(f"round {round_no}: reviewer's revision accepted")
                return revised, notes
            notes.append(f"round {round_no}: reviewer's revision had problems: {problems}")
        feedback = "\n".join(f"- {i}" for i in issues)
    if last_clean is not None:
        notes.append("no round fully satisfied the reviewer; publishing the last structurally valid draft")
        return last_clean, notes
    raise RuntimeError("could not produce a usable post:\n" + "\n".join(notes))
