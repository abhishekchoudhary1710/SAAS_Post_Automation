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
from .config import product, product_of
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
NARRATION_BUDGET = {"english": (34, 44), "hinglish": (30, 38), "hindi": (30, 38)}


def narration_budget(language: str | None) -> tuple[int, int]:
    return NARRATION_BUDGET.get(str(language or "english").lower(), NARRATION_BUDGET["english"])


SLIDE_TYPES = """SLIDE TYPES (use exactly these field names)
- {"type":"hook","title":"<under 12 words, may contain one **bold** phrase>","subtitle":"<optional, under 25 words>","tag":"<2 or 3 word label shown top right>","kicker":"<optional 3 word label above the title>"}
- {"type":"stat","number":"<short, e.g. Rs 99 or 30 min or 2 days>","label":"<under 10 words>","note":"<optional, under 18 words>"}
- {"type":"points","title":"<under 9 words>","points":["<3 to 5 items, each under 14 words>"],"tag":"..."}
- {"type":"qa","question":"<the question or prompt put to the candidate, under 18 words>","answer":"<first person, spoken style, 35 to 60 words, 1 to 3 **bold** key phrases>","tag":"...","label_q":"<optional, default {label_q}>","label_a":"<optional, default {label_a}>"} -- the "tag" on a qa slide must NOT repeat the label; use the topic instead, e.g. "Project round"
- {"type":"myth","myth":"<under 18 words>","fact":"<under 24 words>","tag":"..."}
- {"type":"product","title":"<under 14 words, mention {brand}>","caption":"<under 22 words>","image":{shot_keys},"theme":"dark"}
- {"type":"cta","title":"<under 7 words, default 30 minutes free. No card.>","subtitle":"<under 14 words>","show_pricing":true}
- {"type":"quote","text":"<under 26 words>","by":"<optional>"}
Every slide may also carry "theme": "light" or "dark".
"""

FORMAT_SPEC = {
    "image": """FORMAT: single image. Exactly ONE slide, preferably "qa" with "label_a": "{label_a}". The "tag" must NOT be the brand name (the logo is already in the corner); use the situation, e.g. "Project round" or "HR round". It must work alone, with no
CTA slide; the CTA lives in the caption. The slide needs a "tag".""",
    "carousel": """FORMAT: carousel. {min} to {max} slides. Slide 1 MUST be type "hook" with a "tag": the scroll-stopper,
a claim or a question the reader wants resolved. Middle slides deliver the value (points, qa, myth, stat, quote),
one idea per slide, in a logical order. Include at most one "product" slide, and only if it fits the topic
naturally; a "product" slide is REQUIRED in every carousel whatever the pillar, usually second to last. Slide 1's title or tag names {brand}. The LAST slide MUST be type "cta".
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
    "film": """FORMAT: film. A 22 to 28 second generated video with the SAME shape every day, so the reels read as a
series; only the person, the question and the answer change. The plan gives you a PERSON and a SELLING ANGLE.
The shape:
  Beat 1 (footage, about 6 s): the candidate is in the online interview; the interviewer's question lands and
     there is a beat of freeze. On screen, the question appears as the app's live transcript line.
  Beat 2 (footage, same person, about 7 s): a glance at the laptop, then they answer with confidence. On screen,
     the Interview Sarthi panel drafts the answer, one sentence at a time, while they speak.
  Then the answer card (the full question and answer), then the price card.
You write:
1. "film": {"beats": [beat1, beat2]}, EXACTLY two. Each beat: "action" (one line, under 20 words, what the person
   does, matching that beat and the angle) and "narration" (the spoken words over it, 9 to 15 words, natural
   speech, no markdown). Beat 1 narration is the hook: the moment, in the second person, for example "The
   interviewer asks about your project, and your mind goes blank." Beat 2 narration says "Interview Sarthi" and
   "Windows" and what it did, in the angle's terms, and it happens LIVE, during the call: "shows", "appears",
   "drafts", never "prepares" or "practises".
2. "slides": EXACTLY two cards, in this order. A "qa" card: "question" (what the interviewer asked, under 18
   words, one a stranger recognises instantly), "answer" (first person, spoken style, 3 to 5 complete sentences,
   35 to 60 words in total, each sentence under 18 words because the app shows one sentence per line, with 1 to 3
   **bold** key phrases), "label_a": "Interview Sarthi showed", a short "tag" naming the round, and a narration of
   8 to 14 words. Then a "cta" card with "show_pricing": true, title under 7 words, and a narration of 8 to 12
   words that ends by saying the site: "Search interview sarthi dot com".
3. The question line and the answer panel over the footage are the app's own interface, and they are what a
   muted viewer reads, so the question and the answer must make sense with the sound off.
TOTAL narration across beats and cards: 45 to 65 words. Never pad. Write prices as words ("99 rupees").
If the angle is privacy, the allowed line is exactly this idea: "On your screen. Not in the meeting." Never any
word from the forbidden list, and never a word that frames the app as preparation.
Also return "reel": {"youtube_title": "<under 90 characters, ends with #Shorts>", "youtube_description": "<2 to 4 lines>",
"youtube_tags": ["<8 to 12 short tags>"]}.""",
    "reel": """FORMAT: reel. {min} to {max} slides, each with an extra field "narration": the exact spoken words for that
slide, 7 to 13 words, natural speech, no markdown. TOTAL narration 34 to 44 words in English, 30 to 38 in Hinglish.
The reel begins with a short generated or library opening, then the voice delivers about two words a second over the cards.
Keep the complete video near 25 to 30 seconds. Never pad narration to reach a count. Viewers who finish are what gets a reel shown to strangers, so short wins.
Slide 1 is a "hook" whose title or tag names {brand} and whose narration says in one sentence what the app is and the moment it handles, exactly as the PRODUCT-FIRST RULE describes it. Middle slides: exactly one "qa" slide showing the app's output for the interviewer's question, with "label_a": "{label_a}"; optionally one points, myth or stat slide; a points slide in a reel carries exactly 3 points. Every reel carries exactly one "product" slide with the real screenshot ("image": {shots}), because the owner wants the interface seen in every reel. The LAST slide is that "product" slide or a "cta" slide, and its
narration ends with a spoken call to action such as "{cta_spoken}". On-screen text
stays short; the narration can say a little more. In narration write prices as words ("99 rupees" or "99 रुपये"),
never with a currency symbol.
For hinglish posts the on-screen text is Roman script, but the narration must be written in mixed script:
Hindi words in Devanagari, English words in Latin letters, because the voice reads Devanagari correctly and
Roman Hindi badly. Example narration: "Interviewer ने बीच में Hindi में पूछ लिया? घबराओ मत। जिस language में सवाल आया, उसी में जवाब दो।"
Also return "reel": {"youtube_title": "<under 90 characters, ends with #Shorts>", "youtube_description": "<2 to 4 lines>",
"youtube_tags": ["<8 to 12 short tags>"]}.""",
    "demo": """FORMAT: demo. A 22 to 28 second rendered video that shows Interview Sarthi doing its job LIVE inside an
online interview. On screen: a mock call window (the interviewer's tile, camera off), and over it the Interview Sarthi
panel on the candidate's own laptop. The interviewer asks ONE question; it types into the panel's transcript; about a
second and a half later the answer appears in the panel, one sentence at a time, drafted from the candidate's resume.
Nothing is generated by a video model: every word you write appears on screen exactly, so it must be short and exact.
You write:
1. "demo": {"headline": "<the on-screen title for the whole shot, 5 to 9 words, names the live moment, may hold one
   **bold** phrase, must read in two seconds, e.g. 'The question lands. Your answer is **already on screen.**'>",
   "app": "Google Meet" | "Microsoft Teams" | "Zoom", "round": "<2 to 4 words, e.g. HR round, TCS>",
   "interviewer": "<a common Indian first name>",
   "narration_hook": "<10 to 16 words spoken over the opening: names Interview Sarthi and Windows and says what is about
   to happen live in the interview>",
   "narration_question": "<8 to 14 words spoken while the interviewer asks: say the question or the moment>"}
2. "slides": EXACTLY two, in this order. A "qa" card: "question" = what the interviewer asks, exactly as it will appear
   in the transcript (under 16 words); "answer" = what Interview Sarthi showed, first person, spoken style, 30 to 50
   words in 3 or 4 SHORT sentences (each sentence is shown on its own line, so keep every sentence under 14 words),
   with 2 or 3 **bold** key phrases; "label_a": "Interview Sarthi showed"; "tag" = the round; "narration" = 9 to 15
   words spoken while the answer appears (what appeared and where it came from: your own resume, about a second and a
   half later). Then a "cta" card with "show_pricing": true, "title" under 7 words, and a "narration" of 8 to 12 words
   that ends "Search interview sarthi dot com".
3. Most viewers are muted. The headline plus the panel must make the pitch alone: an app on your screen, during the
   call, showing what to say.
TOTAL narration across the four lines: 40 to 58 words. Narration is always English, even when the on-screen question
and answer are Hinglish. Write prices as words ("99 rupees"). The app is used DURING the interview: never describe it
as preparation, practice, a mock interview or revision. Never any word from the forbidden list.
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
  "reel": null | {...},
  "film": null | {"beats": [{"action": "<one line>", "narration": "<spoken words>"}]}
}"""


def _example(fmt: str) -> str:
    sample = load_json(SAMPLES / f"sample_{fmt}.json")
    return json.dumps(sample, ensure_ascii=False, indent=1)


def _format_spec(fmt: str, pid: str = 'interview_sarthi') -> str:
    """Fill {min} and {max} in the format spec.

    Deliberately str.replace and not str.format: these specs contain literal JSON braces
    such as {"youtube_title": ...}, which str.format would read as placeholders and reject.
    """
    spec = FORMAT_SPEC[fmt]
    if fmt in ("carousel", "reel"):
        sizes = schedule()[fmt]
        spec = spec.replace("{min}", str(sizes["min_slides"])).replace("{max}", str(sizes["max_slides"]))
    return _voice(pid, spec)


# Every format spec above is written with {brand}, {label_q}, {label_a}, {shots} and {cta_spoken}
# so one set of rules can serve all three products. VOICE is what fills them in. Without this the
# reel and carousel prompts told the model to write Interview Sarthi copy whatever the post was for.
VOICE = {
    "interview_sarthi": {
        "label_q": "Interviewer asked",
        "label_a": "Interview Sarthi showed",
        "shots": '"overlay_english" or "overlay_hinglish", matching the language',
        "cta_spoken": "Try Interview Sarthi free, link in bio",
        "shot_keys": '"overlay_hinglish"|"overlay_english"|"logo"|"mascot"',
    },
    "prep_sarthi": {
        "label_q": "The interviewer asked",
        "label_a": "Your report said",
        "shots": '"prep_live" for the interview screen, or "prep_report" for the scored report',
        "cta_spoken": "Try Prep Sarthi free in your browser, link in bio",
        "shot_keys": '"prep_live"|"prep_report"|"logo"|"mascot"',
    },
    "apply_sarthi": {
        "label_q": "The job asked",
        "label_a": "ApplySarthi filled in",
        "shots": '"apply_jobs" for the ranked job list',
        "cta_spoken": "ApplySarthi is free in early access, link in bio",
        "shot_keys": '"apply_jobs"|"logo"|"mascot"',
    },
}

# The image keys a product slide may carry. A Prep Sarthi reel that fell back to the Interview
# Sarthi overlay would put the wrong app on screen, so the choice is narrowed per product.
PRODUCT_SHOTS = {
    "interview_sarthi": ("overlay_english", "overlay_hinglish"),
    "prep_sarthi": ("prep_live", "prep_report"),
    "apply_sarthi": ("apply_jobs",),
}


def _voice(pid: str, text: str) -> str:
    """Fill the product tokens. str.replace, not str.format: the specs carry literal JSON braces."""
    out = text.replace("{brand}", product(pid)["name"])
    for key, value in VOICE[pid].items():
        out = out.replace("{" + key + "}", value)
    return out


PRODUCT_FIRST = {
    "interview_sarthi":
        "(a) the hook line and slide 1 name Interview Sarthi and the interview moment, so a stranger knows in "
        "three seconds that this is a Windows app that listens to an online interview and shows what to say, "
        "live, while the interview is on (it is not a preparation or practice tool, and is never called one); "
        "(b) the middle shows the app's output for one real interviewer question, in a qa slide whose label_a is "
        "'Interview Sarthi showed', or a product slide; (c) the post ends on a product or cta slide with where it "
        "runs, 30 minutes free, passes from Rs 99. Frame it as an assistant drafting from the candidate's own "
        "resume; never as anything hidden.",
    "prep_sarthi":
        "(a) the hook line and slide 1 name Prep Sarthi and the practice moment, so a stranger knows in three "
        "seconds that this is a mock interview you speak to in your browser, before the real one, and that it has "
        "read your CV; (b) the middle shows one exchange from that practice, in a qa slide whose 'question' is what "
        "the interviewer asked about the candidate's own CV and whose label_a is 'Prep Sarthi asked again' or "
        "'Your report said', or a product slide carrying one thing the report measures; (c) the post ends on a "
        "product or cta slide with 20 minutes free, no sign-up, in a browser, then Rs 99 for 7 days. Any score or "
        "number shown is an illustration and never a real user's result.",
    "apply_sarthi":
        "(a) the hook line and slide 1 name ApplySarthi and the applying moment, so a stranger knows in three "
        "seconds that this finds jobs matching their CV and fills the application form for them; (b) the middle "
        "shows one concrete step, in a qa or points slide: a job ranked against the CV, a form filled in, a CV "
        "reworded for one job; (c) the post ends on a product or cta slide saying it is free in early access, that "
        "the form filling needs Chrome on a computer, and that you check the form and press submit yourself. Never "
        "say it applies by itself, and never invent a number of jobs or users.",
}


def write_post(llm: Gemini, plan: dict, fmt: str, feedback: str | None = None) -> dict:
    pid = product_of(plan)
    system = (f"You are the copywriter for {product(pid)['name']}. You write posts that Indian job seekers save and "
              "share, and every post is a demonstration of the product doing its job. PRODUCT-FIRST RULE, no "
              "exceptions: " + PRODUCT_FIRST[pid] + " "
              "and you follow the rules below exactly.\n\n" + context_pack(plan) + "\n\n# BRAND DATA\n" + brand_json()
              + "\n\n" + _voice(pid, SLIDE_TYPES) + "\n" + _format_spec(fmt, pid) + "\n\n" + OUTPUT_SCHEMA
              + "\n\nEXAMPLE OF THE SHAPE ONLY, taken from a different product; copy none of its topic, wording, labels or screenshot:\n" + _example(fmt))
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
    content.setdefault("product", pid)
    content.setdefault("pillar", plan.get("pillar"))
    content.setdefault("topic", plan.get("topic"))
    content.setdefault("language", plan.get("language", "english"))
    return content


REVIEW_CHECKS = {
    "interview_sarthi":
        "(8) FIRST-TIME VIEWER: after this post, would a stranger know that Interview Sarthi is a Windows app "
        "that listens to their online interview and shows what to say, that they can see it do so here, and "
        "that 30 minutes are free? If any of the three is missing, it is an issue; fix it in the hook, the qa "
        "label or the closing slide without adding length; (9) POSITIONING: the app helps DURING the interview. "
        "Any wording that presents it as preparation, practice, a mock interview, rehearsal, coaching or "
        "reviewing afterwards is an issue; rewrite it as the live moment (the interviewer asks, the answer "
        "appears on screen).",
    "prep_sarthi":
        "(8) FIRST-TIME VIEWER: after this post, would a stranger know that Prep Sarthi is a mock interview they "
        "speak to in a browser BEFORE the real one, that it has read their CV and asks about their own projects, "
        "and that 20 minutes are free with no sign-up? If any of the three is missing, it is an issue; "
        "(9) POSITIONING: it is practice, never live help during a real interview, and it never coaches while the "
        "practice is running. Any suggestion that it runs during a real interview is an issue. (10) NUMBERS: any "
        "score, pause, pace or words-a-minute must read as an illustration, not as a real user's result.",
    "apply_sarthi":
        "(8) FIRST-TIME VIEWER: after this post, would a stranger know that ApplySarthi ranks open jobs against "
        "their CV and fills the application form in their own Chrome for them to check and submit, and that it is "
        "free in early access? If any is missing, it is an issue; (9) POSITIONING: it never submits behind their "
        "back, never invents a fact about them, never answers salary or notice period for them, and never needs "
        "their job-site passwords. Any wording suggesting otherwise is an issue.",
}


def review_post(llm: Gemini, content: dict, fmt: str) -> dict:
    pid = product_of(content)
    system = (f"You are the editor and compliance reviewer for {product(pid)['name']}'s social posts. You are strict "
              "about facts and framing, and you care that the post is genuinely useful.\n\n" + context_pack(content)
              + "\n\n" + _voice(pid, SLIDE_TYPES) + "\n" + _format_spec(fmt, pid))
    budget_line = ""
    if fmt == "reel":
        lo, hi = narration_budget(content.get("language"))
        budget_line = (f"NARRATION BUDGET for this {content.get('language')} reel: {lo} to {hi} words in total. "
                       f"Only raise it as an issue if the total is under {lo - 8} or over {hi + 8}. Never pad "
                       "narration to reach a count; shorter is better than filler.\n\n")
    user = (budget_line + "Review this draft. Check, in order: (1) any fact, price, number, claim or feature that is NOT in the "
            "business brief; "
            "(2) em dashes or en dashes anywhere; (3) on-slide text that is too long for its slide type; (4) slide "
            "structure rules for the format; (5) a hook that is generic or could apply to any post; (6) language "
            "consistency (Roman-script Hinglish on screen; for reels, mixed-script narration); (7) COUNTING: if the "
            "hook, caption or any title promises a number of items, count the items actually delivered in the slides "
            "and confirm they match. Fix by changing the number to the true count, or by adding the missing item; "
            + REVIEW_CHECKS[pid] + "\n\n"
            "Return ONLY JSON: {\"ok\": true|false, \"issues\": [\"<specific issue>\"], \"revised\": <the full corrected "
            "post JSON in the same shape, or null if ok>}. When you revise, change only what the issues require.\n\n"
            "DRAFT:\n" + json.dumps(content, ensure_ascii=False, indent=1))
    verdict = llm.json(system, user, temperature=0.2, max_tokens=20000 if fmt == "reel" else 12000)
    if not isinstance(verdict, dict):
        return {"ok": True, "issues": [], "revised": None}
    return verdict


# ----------------------------------------------------------------------------- validation
DASHES = re.compile("[—–]")
# Wordings that turn a live assistant into a prep tool. Substrings, lower case: "prepar" catches
# prepare, prepared, preparation and prep-aration in Hinglish spellings too.
PREP_FRAMINGS = ("prepar", "practice", "practis", "mock interview", "mock round", "rehears", "revise",
                 "revision", "coaching", "get ready", "get interview ready", "study for", "train you",
                 "training you", "before the interview", "night before", "after the call", "afterwards")
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
    # The post must name the product it is selling, which is not always Interview Sarthi.
    pid = product_of(content)
    own_name = product(pid)["name"]
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
    elif fmt == "film":
        kinds_f = [str(x.get("type")) for x in slides]
        if kinds_f != ["qa", "cta"]:
            problems.append(f"film needs exactly two cards, qa then cta, has {kinds_f}")
        beats = ((content.get("film") or {}).get("beats")) or []
        if len(beats) != 2:
            problems.append(f"film needs exactly 2 beats (the question lands, then the answer), has {len(beats)}")
        for x in slides:
            if x.get("type") == "qa":
                # The answer panel over the footage shows one sentence per line, like the app.
                from .render.live import sentences
                parts = sentences(str(x.get("answer") or ""))
                if not 2 <= len(parts) <= 6:
                    problems.append(f"the qa answer must be 3 to 5 complete sentences, has {len(parts)}")
                longest = max((len(p.split()) for p in parts), default=0)
                if longest > 22:
                    problems.append(f"a sentence in the qa answer is {longest} words; keep each under 18 so it "
                                    "fits one line of the app's panel")
        words = 0
        for i, b in enumerate(beats, 1):
            n = str(b.get("narration") or "").strip()
            if len(n.split()) < 6:
                problems.append(f"film beat {i} narration too short")
            if len(str(b.get("action") or "").split()) > 28:
                problems.append(f"film beat {i} action is too long")
            words += len(n.split())
        for x in slides:
            words += len(str(x.get("narration") or "").split())
        if words and not 38 <= words <= 75:
            problems.append(f"total film narration is {words} words; keep it between 45 and 65")
        spoken = " ".join(str(b.get("narration") or "") for b in beats).lower()
        if own_name.lower() not in spoken:
            problems.append("the footage narration must say 'Interview Sarthi' by the end of beat 2")
        if pid == "interview_sarthi" and "windows" not in spoken and "windows" not in _all_text(content).lower():
            problems.append("say where it runs: Windows")
        for x in slides:
            if x.get("type") == "qa":
                x.setdefault("label_a", VOICE[pid]["label_a"])
    elif fmt == "demo":
        from .render.demo import sentences_of

        kinds_d = [str(x.get("type")) for x in slides]
        if kinds_d != ["qa", "cta"]:
            problems.append(f"demo needs exactly two cards, qa then cta, has {kinds_d}")
        demo = content.get("demo") if isinstance(content.get("demo"), dict) else {}
        content["demo"] = demo
        headline = str(demo.get("headline") or "").strip()
        if not headline:
            problems.append("demo.headline is missing: the on-screen title, 5 to 9 words")
        elif len(headline.replace("**", "").split()) > 11:
            problems.append("demo.headline is over 10 words; it has to read in two seconds")
        words = 0
        for key in ("narration_hook", "narration_question"):
            n = str(demo.get(key) or "").strip()
            if len(n.split()) < 6:
                problems.append(f"demo.{key} is missing or too short")
            words += len(n.split())
        for x in slides:
            words += len(str(x.get("narration") or "").split())
            if x.get("type") == "qa":
                x.setdefault("label_a", VOICE[pid]["label_a"])
                answer = str(x.get("answer") or "")
                count = len(sentences_of(answer))
                if not 2 <= count <= 5:
                    problems.append(f"the qa answer has {count} sentences; write 3 or 4 short ones, each is shown "
                                    "on its own line")
                if len(answer.split()) > 60:
                    problems.append("the qa answer is over 60 words; keep it between 30 and 50")
                if len(str(x.get("question") or "").split()) > 20:
                    problems.append("the qa question is over 20 words; it must fit the transcript box")
        if words and not 34 <= words <= 72:
            problems.append(f"total demo narration is {words} words; keep it between 40 and 58")
        if own_name.lower() not in str(demo.get("narration_hook") or "").lower():
            problems.append("demo.narration_hook must say 'Interview Sarthi'")
        if pid == "interview_sarthi" and "windows" not in _all_text(content).lower():
            problems.append("say where it runs: Windows")
        if str(demo.get("app") or "") not in ("Google Meet", "Microsoft Teams", "Zoom"):
            demo["app"] = "Google Meet"
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
    allowed_shots = PRODUCT_SHOTS[pid]
    for s in slides:
        s["product"] = pid
        if s.get("type") == "product" and s.get("image") not in allowed_shots + ("logo", "mascot"):
            s["image"] = allowed_shots[0]
    caption = str(content.get("caption") or "").strip()
    first_slide_text = " ".join(str(v) for v in (slides[0].values() if slides else []) if isinstance(v, str))
    if own_name.lower() not in (str(content.get("hook") or "") + " " + first_slide_text).lower():
        problems.append(f"the hook line or slide 1 must name {own_name}: a stranger has to know what this is "
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
    from .story import pick_tags
    content["hashtags"] = pick_tags(str(content.get("topic") or ""), tags[:8])
    if fmt == "reel":
        kinds_r = [str(s.get("type")) for s in slides]
        if "qa" not in kinds_r:
            problems.append("reel needs a qa slide showing the app's output for the interviewer's question")
        if kinds_r.count("product") != 1:
            problems.append("reel needs exactly one product slide with the real screenshot "
                            "(image overlay_english or overlay_hinglish)")
        for s in slides:
            if s.get("type") == "points" and isinstance(s.get("points"), list) and len(s["points"]) > 3:
                s["points"] = s["points"][:3]
    lowered = _all_text(content).lower()
    for word in brand()["forbidden_words"]:
        if word.lower() in lowered:
            problems.append(f"forbidden word or phrase used: {word!r}")
    # The app helps during the interview. Owner decision, 12 Sep 2026: a post that sells preparation sells a
    # product we do not have. Checked on everything except the interviewer's question and the candidate's own
    # answer, where "I prepared the report" is the candidate talking, not us describing the app.
    described = dict(content)
    described["slides"] = [{k: v for k, v in s.items() if k not in ("question", "answer")}
                           for s in slides if isinstance(s, dict)]
    lowered_desc = _all_text(described).lower()
    # Only Interview Sarthi may not be sold as preparation. For Prep Sarthi the
    # same words describe the product honestly, and for ApplySarthi they are
    # simply off topic rather than forbidden.
    if product_of(content) == "interview_sarthi":
        hit = next((f for f in PREP_FRAMINGS if f in lowered_desc), None)
        if hit:
            problems.append(f"frames the app as preparation ({hit!r}); Interview Sarthi helps DURING the interview: "
                            "the interviewer asks, the answer appears. Rewrite as the live moment")
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
            notes.append(f"round {round_no}: reviewer unavailable ({type(exc).__name__}); retrying")
            feedback = "The reviewer could not finish. Return a concise, supported draft."
            continue
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
    raise RuntimeError("could not produce a usable post:\n" + "\n".join(notes))
