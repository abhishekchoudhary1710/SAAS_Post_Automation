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
from .llm import Gemini

FACTS = """Interview Sarthi is a Windows 10/11 desktop app for live online interviews.
It listens to the interviewer and displays suggested answers using the uploaded resume.
It works alongside Teams, Zoom and Google Meet. English, Hindi and Hinglish are supported.
The first 30 minutes are free, with no payment card. A 2-day pass costs Rs 99 once.
Nothing auto-renews. Setup requires the user's own Google Gemini API key and internet.
No guaranteed accuracy, response time, selection, interview outcome or AI cost.
It is live assistance, not a preparation service.
On Windows 10 version 2004+ and Windows 11, the app requests screen-capture exclusion.
The overlay stays visible to the user and is hidden from supported screen sharing.
Support depends on the Windows and capture setup; failures can occur and the app warns when detected.
Explain this feature. Never claim universal invisibility, undetectability or guaranteed exclusion.
Examples use fictional resumes. A rendered illustration is not a recording of a live call.
There is no post-call AI summary in the current app. No customer testimonials or statistics.
"""
BAD_CLAIMS = re.compile(
    r"\b(guarantee\w*|perfectly|flawless\w*|undetectable|invisible|stealth|cheat\w*|"
    r"never blank|never generic|100\s*%|1[.,]5 seconds|instant(?:ly)?|summary|summaries|"
    r"prepar\w*|practi[cs]\w*|mock interview|coaching)\b", re.I)
CTA = "Try thirty minutes free on Windows. Then ninety-nine rupees for two days. Visit interviewsarthi dot com."


def scenarios() -> list[dict]:
    return load_json(KNOWLEDGE / "demos.json")["scenarios"]


def choose_scenario(history: History, topic: str | None = None, variant: str | None = None) -> tuple[dict, int]:
    pool = scenarios()
    if topic:
        words = set(re.findall(r"[a-z]+", topic.lower()))
        scored = [(len(words & set(re.findall(r"[a-z]+", json.dumps(s).lower()))), s) for s in pool]
        best = max(x[0] for x in scored)
        if not best:
            raise ValueError("Requested topic has no supported demonstration; add evidence before advertising it")
        pool = [s for score, s in scored if score == best]
    counts = Counter(p.get("scenario") for p in history.posts)
    recent = [p.get("scenario") for p in history.recent(6)]
    last_variant = {p.get('scenario'): p.get('variant') for p in history.posts}
    # Fair rotation is the default. Feedback informs hooks only after enough observations exist.
    chosen = min(pool, key=lambda s: (s["id"] in recent, counts[s["id"]],
                 variant is not None and last_variant.get(s['id']) == variant, pool.index(s)))
    return copy.deepcopy(chosen), counts[chosen["id"]] % len(chosen["hooks"])


def authored_script(s: dict, variant: str, hook_index: int) -> dict:
    intro = "Interview Sarthi listens during your online interview and shows suggested answers from your resume."
    if variant == "short":
        lines = ["Your interviewer asks: " + s["question"] if s["language"] == "english" else "Your interviewer switches to Hinglish. Here is an example.",
                 "Interview Sarthi shows suggested answers from your resume, during the call.",
                 "Its overlay is hidden from supported screen sharing on Windows.",
                 "Try thirty minutes free on Windows. Visit interviewsarthi dot com."]
    else:
        lines = ["Your interviewer asks: " + s["question"] if s["language"] == "english" else "The interviewer switches to Hinglish. Here is an example.",
                 intro, s["bridge"],
                 "You see Sarthi on your screen. Its overlay is hidden from supported screen sharing on Windows, alongside Teams, Zoom and Meet.", CTA]
    return {"hook": s["hooks"][hook_index], "narrations": lines,
            "youtube_title": s["hooks"][hook_index].rstrip(".?!") + " | Interview Sarthi",
            "caption": f"{s['hooks'][hook_index]}\n\nInterview Sarthi listens during your online interview and shows suggested answers using your resume. {s['benefit']}. The overlay is hidden from supported screen sharing while remaining visible to you. Capture support varies.\n\nIllustrative demo with a fictional resume. Windows 10 (2004+)/11; your own Gemini key is required."}


def script_problems(script: dict, variant: str) -> list[str]:
    problems = []
    lines = script.get("narrations")
    expected = 4 if variant == "short" else 5
    if not isinstance(lines, list) or len(lines) != expected or any(not isinstance(x, str) for x in lines):
        return [f"needs {expected} narration lines"]
    total = sum(len(x.split()) for x in lines)
    low, high = (36, 62) if variant == "short" else (64, 100)
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
    system = "You write clear, persuasive spoken scripts for Indian job seekers. Use these verified facts only:\n" + FACTS
    from .feedback import prompt_feedback
    system += '\n' + prompt_feedback()
    user = ("Improve the supplied script. Preserve its scene order and meaning. Use a specific hook, natural English, "
            "and a single CTA. Do not add claims, testimonials, numbers, invented results, or features. "
            "Narration remains English even when the on-screen example is Hinglish. Do not rewrite the example. "
            "Return a top-level object with hook, narrations (array of strings), youtube_title and caption. "
            "Do not wrap it in a script or evidence object. "
            f"Variant: {variant}. Narration budget: {'36-62' if variant == 'short' else '64-100'} words; "
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
            if not issues:
                review = llm.json("You are a strict factual and creative editor.\n" + FACTS,
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


def create_sales(settings, out_dir=None, topic=None, sample=False, variant="auto") -> dict:
    from .pipeline import compose_captions
    from .render.sales import build_sales
    from .quality import inspect_video

    history = History()
    if variant == "auto":
        variant = "short" if now_ist().hour < 16 else "standard"
    if variant not in ("short", "standard"):
        raise ValueError("Unknown sales variant")
    s, hook_index = choose_scenario(history, topic, variant)
    llm = Gemini(settings.gemini_api_key, settings.gemini_models, timeout=60, retry_waits=(8,)) if settings.gemini_api_key and not sample else None
    script, receipt = write_script(llm, s, variant, hook_index)
    run_dir = Path(out_dir) if out_dir else OUT / (now_ist().strftime("%Y%m%d-%H%M%S") + "-sales-" + variant)
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        media = build_sales(s, script, variant, run_dir / "reel.mp4")
    except ValueError as exc:
        if receipt['source'] != 'model':
            raise
        # An overlong generated voice or oversized hook gets one complete authored rebuild.
        receipt.update(source='authored', render_fallback=type(exc).__name__)
        script = authored_script(s, variant, hook_index)
        media = build_sales(s, script, variant, run_dir / "reel.mp4")
    fingerprint = hashlib.sha256(json.dumps({"scenario": s, "script": script, "variant": variant},
                                           sort_keys=True).encode()).hexdigest()
    recent_hashes = {p.get("creative_hash") for p in history.recent(24)}
    if not sample and fingerprint in recent_hashes:
        raise RuntimeError("This exact creative has already been posted recently")
    save_json(run_dir / "evidence.json", {"disclosure": "Fictional resume and illustrative answer; not a live latency measurement",
              "scenario": s, "review": receipt, "creative_hash": fingerprint})
    qa = inspect_video(Path(media["video"]), media["timeline"], media["layout"])
    if not qa["passed"]:
        save_json(run_dir / "quality.json", qa)
        raise RuntimeError("Rendered video failed quality checks: " + "; ".join(qa["issues"]))
    plan = {"scenario": s["id"], "pillar": s["pillar"], "topic": s["question"], "language": "english",
            "variant": variant, "hook_index": hook_index, "creative_hash": fingerprint, "campaign_id": run_dir.name,
            "reason": "Rotate supported demonstrations and compare short versus standard edits"}
    content = {"topic": s["question"], "pillar": s["pillar"], "language": "english", "hook": script["hook"],
               "caption": script["caption"], "hashtags": s["tags"], "script": script,
               "reel": {"youtube_title": script["youtube_title"], "youtube_description": script["caption"],
                        "youtube_tags": ["Interview Sarthi", "live interview assistant", "Windows interview app"]}}
    manifest = {"id": run_dir.name, "created_at": now_ist().isoformat(), "format": "sales", "sample": sample,
                "plan": plan, "content": content, "media": media, "quality": qa,
                "captions": compose_captions(content, "sales", plan),
                "notes": [f"script: {receipt['source']}", f"voice: {media['voice']}",
                          "illustrative demonstration; fictional resume; edited timing", f"model calls: {llm.calls if llm else 0}"]}
    save_json(run_dir / "quality.json", qa)
    save_json(run_dir / "post.json", manifest)
    return manifest
