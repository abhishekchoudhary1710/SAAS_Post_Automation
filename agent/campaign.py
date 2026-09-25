"""Evidence-led, unattended sales reels with bounded model use and an authored fallback."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from collections import Counter

from .config import KNOWLEDGE, OUT, brand, load_json, now_ist, save_json
from .history import History
from .llm import Gemini, LLMError
from . import market as mk

FACTS = """Interview Sarthi is a Windows 10/11 desktop app for live online interviews.
It listens to the interviewer and displays suggested answers using the uploaded resume.
It works alongside Teams, Zoom, Google Meet and other call apps. English, Hindi and Hinglish are supported.
The first 30 minutes are free, with no payment card. A 2-day pass costs Rs 99 once.
Nothing auto-renews. Setup requires the user's own Google Gemini API key and internet.
No guaranteed accuracy, response time, selection, interview outcome or AI cost.
It is live assistance, not a preparation service.
On Windows 10 version 2004+ and Windows 11, the app requests screen-capture exclusion.
The overlay stays visible to the user and is hidden from supported screen sharing.
Support depends on the Windows and capture setup; failures can occur and the app warns when detected.
Hooks and captions may say the interviewer did not notice, may call the overlay invisible or undetectable,
and may tell a fictional success story. The product line still names supported screen sharing.
Examples use fictional resumes and say so. A rendered illustration is not a recording of a live call.
There is no post-call AI summary in the current app. No real customer testimonials, no statistics, no guarantees.
"""
# Guarantees and features the app does not have, plus the practice framing the owner rejected.
# The absolute words (invisible, undetectable, cheat) and outcome stories came off this list on
# 17 Sep 2026 by owner decision; see knowledge/hooks.json.
BAD_CLAIMS = re.compile(
    r"\b(guarantee\w*|100\s*%|summary|summaries|"
    r"prepar\w*|practi[cs]\w*|mock interview|coaching)\b", re.I)
# Prep Sarthi IS a mock interview, so the preparation words are true there and only
# the guarantees stay banned. ApplySarthi has its own promise to avoid.
BAD_CLAIMS_BY_PRODUCT = {
    "interview_sarthi": BAD_CLAIMS,
    "prep_sarthi": re.compile(r"\b(guarantee\w*|100\s*%|hired because|will get you (a job|an offer))\b", re.I),
    "apply_sarthi": re.compile(r"\b(guarantee\w*|100\s*%|applies for you automatically|submits for you)\b", re.I),
}
FACTS_BY_PRODUCT = {
    "prep_sarthi": """Prep Sarthi is a mock interview you speak to, in a phone or laptop browser, before the real interview.
It reads the candidate's CV and asks about their own projects out loud, then asks again when an answer is vague.
At the end it scores every answer out of ten, says what was missing, and writes a stronger answer from the same CV.
It also measures speaking pace, filler words and the pause before each answer, from the microphone.
Any score or number spoken is an illustration, not a real user's result. No testimonials, no user counts, no guarantees.
Twenty minutes are free with no card and no sign-up. Then Rs 99 for seven days or Rs 249 for thirty, one payment, never renewing.
It runs on the candidate's own free Google Gemini key. English, Hinglish, Hindi or any other language.
It never runs during a real interview and never promises a job. It is practice, and it is honest about being practice.
""",
    "apply_sarthi": """ApplySarthi finds jobs that match the candidate's CV and fills the application form in their own Chrome.
Jobs come from Naukri, LinkedIn, Indeed, Foundit, Shine, Internshala, Wellfound and more than 750 company career pages.
It ranks every job against the CV, rewords the CV for each job using only real experience, and fills the form.
It stops there. The candidate reads the form, fixes anything, solves the CAPTCHA and presses submit themselves.
It never invents a fact about them, never answers salary or notice period, and never sees their job-site passwords.
Always free. It runs on the candidate's own free Google Gemini key. Form filling needs Chrome on a computer.
No guarantees, no user counts, no testimonials, no invented number of jobs.
""",
}


def facts_for(pid: str | None) -> str:
    return FACTS_BY_PRODUCT.get(pid or "", FACTS)


def bad_claims_for(pid: str | None):
    return BAD_CLAIMS_BY_PRODUCT.get(pid or "", BAD_CLAIMS)
CTA = "Try thirty minutes free on Windows. Then ninety-nine rupees for two days. Visit interviewsarthi dot com."
# Openings for the promo reel, in the shapes the 17 Sep 2026 audit of winning reels found.
PROMO_HOOKS = load_json(KNOWLEDGE / "hooks.json")["promo_hooks"]


def hook_shapes_prompt() -> str:
    shapes = load_json(KNOWLEDGE / "hooks.json")["shapes"]
    return ("Hook shapes that earned reach in this category; write the hook in one of them, never as an outcome "
            "or a guarantee. The product line, not the hook, carries the supported screen sharing qualifier: "
            + "; ".join(f"{x['name']}, e.g. {x['example']}" for x in shapes))
# narration lines, then the spoken-word floor and ceiling for the whole script
BUDGETS = {"short": (4, 36, 62), "standard": (5, 64, 100), "promo": (4, 44, 76)}


def promo_script(s: dict, hook_index: int) -> dict:
    """The feature reel: what the app does and where it runs, with no interviewer question to answer."""
    hook = PROMO_HOOKS[hook_index % len(PROMO_HOOKS)]
    lines = ["Your interviewer asks. Interview Sarthi shows a suggested answer on your screen, during the call.",
             "Answers come from your own resume and projects, in English, Hindi or Hinglish, whichever the interviewer uses.",
             "It runs beside Teams, Zoom, Meet and other call apps on your Windows laptop. Its overlay is hidden from supported screen sharing.",
             "Try thirty minutes free on Windows. Visit interviewsarthi dot com."]
    caption = (f"{hook}\n\nInterview Sarthi listens during your online interview and shows suggested answers on your own "
               "screen, built from your resume, in English, Hindi or Hinglish. It runs beside Teams, Zoom, Google Meet and other call apps "
               "on Windows. The overlay is hidden from supported screen sharing while remaining visible to you. Capture "
               "support varies.\n\nWindows 10 (2004+)/11; your own Gemini key is required.")
    return {"hook": hook, "narrations": lines, "youtube_title": hook.rstrip(".?!") + " | Interview Sarthi", "caption": caption}


def scenarios() -> list[dict]:
    return load_json(KNOWLEDGE / "demos.json")["scenarios"]


def for_abroad(seed: dict) -> dict:
    """The hand-written seed, fit for a viewer outside India, for when the model is unavailable:
    an international name and no Indian English. The model is asked for the same when it writes."""
    s = copy.deepcopy(seed)
    old, new = s.get("name") or "", mk.name_for(s.get("id") or s.get("question"))
    for key in ("name", "profile", "audience", "bridge"):
        if isinstance(s.get(key), str):
            text = s[key].replace(old, new) if old else s[key]
            text = re.sub(r"\bfreshers\b", "new graduates", text)
            s[key] = re.sub(r"\bfresher\b", "new graduate", text)
    return s


def choose_scenario(history: History, topic: str | None = None, variant: str | None = None,
                    market: str | None = None) -> tuple[dict, int]:
    pool = scenarios()
    if mk.is_global(market):
        # A Hinglish example tells a viewer abroad the reel was not made for them.
        pool = [s for s in pool if s.get("language") == "english"] or pool
    if topic:
        words = set(re.findall(r"[a-z]+", topic.lower()))
        scored = [(len(words & set(re.findall(r"[a-z]+", json.dumps(s).lower()))), s) for s in pool]
        best = max(x[0] for x in scored)
        if not best:
            raise ValueError("Requested topic has no supported demonstration; add evidence before advertising it")
        pool = [s for score, s in scored if score == best]
    counts = Counter(p.get('seed_scenario') or p.get("scenario") for p in history.posts)
    recent = [p.get('seed_scenario') or p.get("scenario") for p in history.recent(6)]
    last_variant = {p.get('seed_scenario') or p.get('scenario'): p.get('variant') for p in history.posts}
    # Fair rotation is the default. Feedback informs hooks only after enough observations exist.
    chosen = min(pool, key=lambda s: (s["id"] in recent, counts[s["id"]],
                 variant is not None and last_variant.get(s['id']) == variant, pool.index(s)))
    return copy.deepcopy(chosen), counts[chosen["id"]] % len(chosen["hooks"])


def authored_script(s: dict, variant: str, hook_index: int) -> dict:
    if variant == "promo":
        return promo_script(s, hook_index)
    intro = "Interview Sarthi listens during your online interview and shows suggested answers from your resume."
    if variant == "short":
        lines = ["Your interviewer asks: " + s["question"] if s["language"] == "english" else "Your interviewer switches to Hinglish. Here is an example.",
                 "Interview Sarthi shows suggested answers from your resume, during the call.",
                 "Its overlay is hidden from supported screen sharing on Windows.",
                 "Try thirty minutes free on Windows. Visit interviewsarthi dot com."]
    else:
        lines = ["Your interviewer asks: " + s["question"] if s["language"] == "english" else "The interviewer switches to Hinglish. Here is an example.",
                 intro, s["bridge"],
                 "You see Sarthi on your screen. Its overlay is hidden from supported screen sharing on Windows, alongside Teams, Zoom, Meet and other call apps.",
                 mk.spoken_cta("interview_sarthi", s.get("market"), CTA)]
    return {"hook": s["hooks"][hook_index], "narrations": lines,
            "youtube_title": s["hooks"][hook_index].rstrip(".?!") + " | Interview Sarthi",
            "caption": f"{s['hooks'][hook_index]}\n\nInterview Sarthi listens during your online interview and shows suggested answers using your resume. {s['benefit']}. The overlay is hidden from supported screen sharing while remaining visible to you. Capture support varies.\n\nIllustrative demo with a fictional resume. Windows 10 (2004+)/11; your own Gemini key is required."}


def script_problems(script: dict, variant: str) -> list[str]:
    problems = []
    lines = script.get("narrations")
    expected, low, high = BUDGETS[variant]
    if not isinstance(lines, list) or len(lines) != expected or any(not isinstance(x, str) for x in lines):
        return [f"needs {expected} narration lines"]
    total = sum(len(x.split()) for x in lines)
    if not low <= total <= high:
        problems.append(f"narration is {total} words, expected {low}-{high}")
    if len(lines[0].split()) > 16:
        problems.append("opening narration must be at most 16 words")
    hook = script.get("hook", "")
    if not isinstance(hook, str) or not 4 <= len(hook.split()) <= 13:
        problems.append("hook must be 4-13 words")
    text = " ".join(lines)
    if "interview sarthi" not in text.lower() or "windows" not in text.lower():
        problems.append("narration must identify Interview Sarthi and Windows")
    if "resume" not in text.lower() or not re.search(r"during|live|call", text, re.I):
        problems.append("must explain resume-based live assistance")
    if "free" not in lines[-1].lower() or "interviewsarthi" not in lines[-1].lower():
        problems.append("last line must have free trial and website")
    if not re.search(r'supported screen shar(?:e|es|ing)', lines[-2], re.I):
        problems.append('product scene must explain supported screen sharing without promising universal invisibility')
    if BAD_CLAIMS.search(json.dumps(script, ensure_ascii=False)):
        problems.append("unsupported promise or incorrect product framing")
    if any("**" in x or "#" in x for x in lines):
        problems.append("spoken text must not contain formatting")
    # Product numbers are locked; no model-invented discounts or success statistics.
    if re.search(r"\d", text):
        problems.append("write allowed offer numbers in words; do not invent metrics")
    if not isinstance(script.get("caption"), str) or not 80 <= len(script["caption"]) <= 900:
        problems.append("caption must be 80-900 characters")
    return problems


def write_script(llm: Gemini | None, s: dict, variant: str, hook_index: int) -> tuple[dict, dict]:
    fallback = authored_script(s, variant, hook_index)
    errors = script_problems(fallback, variant)
    if errors:
        raise ValueError("Invalid authored fallback: " + "; ".join(errors))
    receipt = {"source": "authored", "accepted": True, "models": [], "issues": []}
    if llm is None:
        return fallback, receipt
    market = s.get("market")
    facts = mk.facts("interview_sarthi", market, FACTS)
    system = ("You write clear, persuasive spoken scripts for " + mk.audience(market) + " "
              + mk.writing_rules(market) + "\nUse these verified facts only:\n" + facts)
    # Account history and analytics stay local; send only the current fictional example.
    user = (hook_shapes_prompt() + "\n"
            "Improve the supplied script. Preserve its scene order and meaning. Use a specific hook, natural English, "
            "and a single CTA. Do not add claims, testimonials, numbers, invented results, or features. "
            "Narration remains English even when the on-screen example is Hinglish. Do not rewrite the example. "
            "Return a top-level object with hook, narrations (array of strings), youtube_title and caption. "
            "Do not wrap it in a script or evidence object. "
            f"Variant: {variant}. Narration budget: {BUDGETS[variant][1]}-{BUDGETS[variant][2]} words; "
            "first narration at most 16 words, hook 4-13 words. "
            "The product is a Windows app helping DURING the interview.\n"
            + json.dumps({"script": fallback, "evidence": s}, ensure_ascii=False))
    for _ in range(2):
        print('[script] drafting and checking the sales story', flush=True)
        try:
            draft = llm.json(system, user, temperature=0.75, max_tokens=4000, schema={
                "type": "object", "required": ["hook", "narrations", "youtube_title", "caption"],
                "properties": {"hook": {"type": "string"}, "youtube_title": {"type": "string"},
                    "caption": {"type": "string"}, "narrations": {"type": "array", "items": {"type": "string"},
                    "minItems": len(fallback['narrations']), "maxItems": len(fallback['narrations'])}}})
            receipt["models"].append(llm.last_model)
            issues = script_problems(draft, variant) if isinstance(draft, dict) else ["not an object"]
            if not issues and mk.is_global(market):
                issues = mk.abroad_problems(json.dumps(draft, ensure_ascii=False))
            if not issues:
                review = llm.json("You are a strict factual and creative editor.\n" + facts,
                    "Review this proposed video script against the supplied scenario. Require a specific hook, "
                    "clear live assistance, supported claims and a useful demonstration. Do not pad text. "
                    "Return {\"approved\":true|false,\"clarity\":0-5,\"hook\":0-5,\"evidence\":0-5,\"issues\":[]}.\n"
                    + json.dumps({"script": draft, "scenario": s}), temperature=0.1, max_tokens=2000, schema={
                        "type": "object", "required": ["approved", "clarity", "hook", "evidence", "issues"],
                        "properties": {"approved": {"type": "boolean"},
                            "clarity": {"type": "integer"}, "hook": {"type": "integer"},
                            "evidence": {"type": "integer"},
                            "issues": {"type": "array", "items": {"type": "string"}}}})
                receipt["models"].append(llm.last_model)
                receipt.setdefault('reviews', []).append(review)
                if (isinstance(review, dict) and review.get("approved") is True and not review.get("issues")
                        and all(isinstance(review.get(k), (int, float)) and review[k] >= 4
                                for k in ("clarity", "hook", "evidence"))):
                    return draft, {**receipt, "source": "model", "review": review}
                issues = ['creative or evidence review did not pass']
                if isinstance(review, dict) and isinstance(review.get('issues'), list):
                    issues += [x[:250] for x in review['issues'] if isinstance(x, str)][:4]
            receipt["issues"].extend(issues)
            user += "\nFix these issues: " + "; ".join(issues)
        except Exception as exc:
            # Provider error strings may contain URLs. Never put them in public history.
            receipt["issues"].append(type(exc).__name__)
            break
    return fallback, receipt


def create_sales(settings, out_dir=None, topic=None, sample=False, variant="auto", still=False) -> dict:
    from .pipeline import compose_captions
    from .render.sales import build_sales
    from .quality import inspect_video

    history = History()
    if still:
        variant = "short"
    if variant == "auto":
        variant = "short" if now_ist().hour < 16 else "standard"
    if variant not in ("short", "standard", "promo"):
        raise ValueError("Unknown sales variant")
    # Chosen before a word is written: the market decides the scenario, face, words, prices and voice.
    market = mk.choose("interview_sarthi", history)
    seed, hook_index = choose_scenario(history, topic, variant, market)
    seed["market"] = market
    if mk.is_global(market):
        seed = for_abroad(seed)
    print(f"[market] {market}", flush=True)
    # Vertex needs no API key, only the Cloud credentials the workflow already holds, so the
    # client is built whenever it can be built rather than only when a key is configured.
    # Guarding on the key alone would silently drop every sales post back to the authored
    # script the moment the key is retired in favour of the credit.
    llm = None
    if not sample:
        try:
            llm = Gemini(settings.gemini_api_key or "", settings.gemini_models, timeout=60,
                         retry_waits=(8,), budget_seconds=360)
        except LLMError as exc:
            print(f"[script] no writing backend ({exc}); using the authored script", flush=True)
    from .creative import fresh_scenario, select_visual
    s, scenario_receipt = fresh_scenario(llm, seed, history)
    s['_visual'] = select_visual(history)
    script, receipt = write_script(llm, s, variant, hook_index)
    receipt['scenario'] = scenario_receipt
    run_dir = Path(out_dir) if out_dir else OUT / (now_ist().strftime("%Y%m%d-%H%M%S") + ("-image" if still else "-sales-" + variant))
    run_dir.mkdir(parents=True, exist_ok=True)
    opening = None
    if not still and not sample:
        # A fresh Veo scene for this reel's opening (15 Sep 2026). None means a library clip, never a lost post.
        from .render.veo_opening import generate_opening
        opening = generate_opening(s, history, run_dir)
        if opening:
            s['_visual'] = {**s['_visual'], 'clip': opening['clip'], 'clip_id': opening['clip_id']}
            receipt['veo_opening'] = {k: opening[k] for k in ('model', 'seconds', 'smoothed', 'prompt')}
    from .render.poster import build_poster
    def render():
        if still:
            return build_poster(s, script, run_dir / "poster.jpg")
        return build_sales(s, script, variant, run_dir / "reel.mp4")
    try:
        media = render()
    except ValueError as exc:
        if receipt['source'] != 'model':
            raise
        # An overlong generated voice or oversized hook gets one complete authored rebuild.
        receipt.update(source='authored', render_fallback=type(exc).__name__)
        script = authored_script(s, variant, hook_index)
        media = render()
    if opening:
        media.update(veo_seconds=opening['seconds'], opening='veo', veo_model=opening['model'])
    fingerprint = hashlib.sha256(json.dumps({"scenario": s, "script": script, "variant": variant, "still": still},
                                           sort_keys=True).encode()).hexdigest()
    recent_hashes = {p.get("creative_hash") for p in history.recent(24)}
    if not sample and fingerprint in recent_hashes:
        raise RuntimeError("This exact creative has already been posted recently")
    save_json(run_dir / "evidence.json", {"disclosure": "Fictional resume and illustrative answer; not a live latency measurement",
              "scenario": s, "review": receipt, "creative_hash": fingerprint})
    from .quality import file_hash
    qa = ({"passed": True, "issues": [], "sha256": file_hash(Path(media["images"][0])), "kind": "image", "dimensions": [1080, 1350]}
          if still else inspect_video(Path(media["video"]), media["timeline"], media["layout"]))
    if not qa["passed"]:
        save_json(run_dir / "quality.json", qa)
        raise RuntimeError("Rendered video failed quality checks: " + "; ".join(qa["issues"]))
    plan = {"scenario": s["id"], "seed_scenario": seed['id'], 'visual_clip':s['_visual']['clip_id'],
            'visual_theme':s['_visual']['theme'], "pillar": s["pillar"], "topic": s["question"], "language": "english",
            "market": market,
            "variant": variant, "hook_index": hook_index, "creative_hash": fingerprint, "campaign_id": run_dir.name,
            "script_source": receipt["source"],
            "reason": "Rotate supported demonstrations and compare short versus standard edits"}
    content = {"topic": s["question"], "pillar": s["pillar"], "language": "english", "hook": script["hook"],
               "caption": script["caption"], "market": market,
               "hashtags": mk.global_tags("interview_sarthi", s["tags"]) if mk.is_global(market) else s["tags"],
               "script": script,
               "reel": {"youtube_title": script["youtube_title"], "youtube_description": script["caption"],
                        "youtube_tags": ["Interview Sarthi", "live interview assistant", "Windows interview app"]}}
    manifest = {"id": run_dir.name, "created_at": now_ist().isoformat(), "format": "image" if still else "sales", "sample": sample,
                "plan": plan, "content": content, "media": media, "quality": qa,
                "captions": compose_captions(content, "image" if still else "sales", plan),
                "notes": [f"script: {receipt['source']}", f"voice: {media.get('voice', 'none')}",
                          "illustrative demonstration; fictional resume; edited timing", f"model calls: {llm.calls if llm else 0}"]}
    save_json(run_dir / "quality.json", qa)
    save_json(run_dir / "post.json", manifest)
    return manifest
