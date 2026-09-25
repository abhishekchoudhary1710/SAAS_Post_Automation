"""A fresh Veo candidate opening scene for sales and card reels.

The sales reels opened on one of three library clips, so the same faces repeated all week.
Owner decisions, 15 September 2026: a new 8-second Veo 3.1 Fast clip for every reel, paid from the
$300 Google Cloud credit through Vertex AI. The app itself stays drawn by code, because Veo garbles
interfaces (11 September) and the product must read exactly (12 September).

Sales reels play up to six seconds; card reels request and play four. Openings are smoothed to
60 FPS with the same motion-compensated interpolation used for the library clips. Every failure,
and every budget stop, returns None: the reel then opens on a library clip.

Budget, in generated seconds (Veo 3.1 Fast at 720p without audio lists at $0.08 a second):
  VEO_OPENING_MONTHLY_SECONDS  default 1500  (up to $120 a month)
  VEO_OPENING_TOTAL_SECONDS    default 2600  (up to $208 from the start date)
  VEO_OPENING_START            default 2026-09-15 (only openings from this date count towards the total)
Seconds are counted from content/history.json, where posted reels carry visual_clip "veo-fresh".
Dry runs and runs that publish nothing are not recorded there, so the total cap keeps a margin.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import pathlib
import subprocess
import time

from ..config import ROOT, now_ist

CLIP_ID = "veo-fresh"
SECONDS = 8
PLAYED_SECONDS = 6
DEFAULT_MODEL = "veo-3.1-fast-generate-001"   # GA id; the -preview ids return 404 on this project
BUSY_WAIT = 30                                # seconds before the one retry of a busy Veo


def _is_busy(exc: Exception) -> bool:
    """A transient "come back later", as opposed to a refusal worth no second request."""
    text = str(exc).lower()
    return any(mark in text for mark in
               ("high load", "currently experiencing", "unavailable", "try again later",
                "resource_exhausted", "'code': 8", "deadline", "timeout", "503", "429"))

LOOK = "Vertical 9:16, photoreal handheld documentary footage, natural colour, shallow depth of field. "
SETTINGS = (
    "a small study desk in an ordinary middle class Indian home, soft daylight from a window",
    "a tidy shared hostel room, warm evening lamp light",
    "a compact rented flat with a bookshelf behind, cool morning light",
    "a quiet corner of a family living room, late afternoon sun through curtains",
)
OUTFITS = ("a light blue button shirt", "a plain white kurta", "a grey polo shirt",
           "a navy blazer over a white shirt", "a simple dark green top")
RULES = ("The laptop screen faces away from the camera and is never visible. No text, no captions, no logos, "
         "no watermark, no readable writing anywhere, no phone screens, no spoken dialogue.")


def enabled() -> bool:
    return os.environ.get("VEO_OPENING_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def opening_prompt(s: dict) -> str:
    """One scene per scenario; setting and clothing rotate so the week does not look the same."""
    key = int(hashlib.sha256(str(s.get("id") or s.get("question")).encode()).hexdigest(), 16)
    setting = SETTINGS[key % len(SETTINGS)]
    outfit = OUTFITS[(key // 7) % len(OUTFITS)]
    who = str(s.get("audience") or "a young job candidate").strip().rstrip(".")
    product = s.get("product")
    if product == "prep_sarthi":
        action = ("practises answering a mock interview question aloud alone at home. They listen to a practice "
                  "prompt through headphones, pause to think, then begin speaking with growing confidence. "
                  "This is private preparation, with no recruiter or live employer call shown. ")
    elif product == "apply_sarthi":
        action = ("reviews job opportunities and works on their CV at a laptop. They compare options, pause "
                  "thoughtfully, then begin typing a careful application. This is a job search at home, "
                  "not an interview or a job offer. ")
    else:
        action = ("sits facing an open laptop during an online job interview. They listen closely to the "
                  "interviewer's question, pause for a moment as if searching for words, then relax and begin "
                  "to answer with calm, growing confidence. ")
    return (LOOK + f"Setting: {setting}. A young Indian adult, {who[:1].lower() + who[1:]}, "
            f"wearing {outfit}, {action}Framed on the face and upper body, natural expressions, "
            "restrained movement. " + RULES)


def _cap(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def budget_stop(history, now: dt.datetime | None = None, seconds: float | None = None) -> str | None:
    """A reason to skip Veo for this reel, or None when one more opening fits both caps."""
    now = now or now_ist()
    # Named apart from the loop variable below, which walks each past post's own length.
    wanted = float(SECONDS if seconds is None else seconds)
    monthly_cap = _cap("VEO_OPENING_MONTHLY_SECONDS", 1500)
    total_cap = _cap("VEO_OPENING_TOTAL_SECONDS", 2600)
    start = os.environ.get("VEO_OPENING_START", "2026-09-15")
    month = now.strftime("%Y-%m")
    monthly = total = 0.0
    for post in history.posts:
        if post.get("visual_clip") != CLIP_ID:
            continue
        seconds = float(post.get("veo_seconds") or 0.0)
        date = str(post.get("date", ""))
        if date[:10] >= start:
            total += seconds
        if date.startswith(month):
            monthly += seconds
    if monthly + wanted > monthly_cap:
        return f"monthly Veo opening cap reached ({monthly:.0f}s of {monthly_cap:.0f}s)"
    if total + wanted > total_cap:
        return f"total Veo opening budget reached ({total:.0f}s of {total_cap:.0f}s)"
    return None


def _generate(prompt: str, out_path: pathlib.Path, model: str, timeout_s: float = 600,
              seconds: int | None = None) -> None:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True,
                          project=os.environ.get("GOOGLE_CLOUD_PROJECT", "uniyal-video"),
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
    try:
        op = client.models.generate_videos(model=model, prompt=prompt, config=types.GenerateVideosConfig(
            aspect_ratio="9:16", resolution="720p",
            duration_seconds=int(SECONDS if seconds is None else seconds), number_of_videos=1,
            generate_audio=False, person_generation="allow_adult"))
        deadline = time.monotonic() + timeout_s
        while not op.done:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Veo did not finish within {timeout_s:.0f}s")
            time.sleep(10)
            op = client.operations.get(op)
        if getattr(op, "error", None):
            raise RuntimeError(f"Veo failed: {op.error}")
        videos = op.response.generated_videos if op.response else []
        if not videos:
            raise RuntimeError("Veo returned no video (the prompt may have been filtered)")
        video = videos[0].video
        data = getattr(video, "video_bytes", None)
        if data:
            out_path.write_bytes(data)
        else:
            video.save(str(out_path))
        if not out_path.exists() or out_path.stat().st_size < 10_000:
            raise RuntimeError("Veo clip saved but looks empty")
    finally:
        client.close()


def _smooth(raw: pathlib.Path, out: pathlib.Path) -> None:
    from .reel import ffmpeg_exe

    p = subprocess.run([ffmpeg_exe(), "-y", "-v", "error", "-t", str(PLAYED_SECONDS), "-i", str(raw), "-an", "-vf",
                        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,"
                        "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:vsbmc=1",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if p.returncode or not out.exists() or out.stat().st_size < 10_000:
        raise RuntimeError("smoothing failed: " + p.stderr[-300:])


def generate_opening(s: dict, history, run_dir: pathlib.Path, seconds: int | None = None) -> dict | None:
    """The clip for this reel's opening, or None so the reel uses a library clip instead.

    `seconds` exists because a card reel shows only a short cold open before its first card,
    so paying for eight seconds to play four is waste the budget cannot afford once every
    reel has an opening rather than only the sales ones.
    """
    if not enabled():
        return None
    seconds = int(SECONDS if seconds is None else seconds)
    run_dir = pathlib.Path(run_dir).resolve()
    if not run_dir.is_relative_to((ROOT / "out").resolve()):
        print("[veo-opening] run folder is outside out/, using a library clip", flush=True)
        return None
    stop = budget_stop(history, seconds=seconds)
    if stop:
        print(f"[veo-opening] {stop}; using a library clip", flush=True)
        return None
    model = os.environ.get("VEO_OPENING_MODEL", DEFAULT_MODEL)
    prompt = opening_prompt(s)
    raw, smooth = run_dir / "veo-opening-raw.mp4", run_dir / "veo-opening.mp4"
    started = time.time()
    # Veo answers "currently experiencing high load" often enough that one try is the
    # difference between fresh footage and a recycled clip (seen 24 Sep 2026). That is a
    # busy service, not a refusal, so it is worth one wait. A real refusal is not retried.
    for attempt in range(2):
        try:
            print(f"[veo-opening] generating {seconds}s with {model}", flush=True)
            _generate(prompt, raw, model, seconds=seconds)
            break
        except Exception as exc:  # noqa: BLE001 - a Veo problem must never cost the post
            detail = str(exc)[:200]
            if attempt == 0 and _is_busy(exc):
                print(f"[veo-opening] busy ({detail}); one more try in {BUSY_WAIT}s", flush=True)
                time.sleep(BUSY_WAIT)
                continue
            print(f"[veo-opening] unavailable ({type(exc).__name__}: {detail}); "
                  "using a library clip", flush=True)
            return None
    clip, smoothed = raw, False
    try:
        _smooth(raw, smooth)
        clip, smoothed = smooth, True
    except Exception as exc:  # noqa: BLE001 - the clip is already paid for, so play it unsmoothed
        print(f"[veo-opening] smoothing failed ({type(exc).__name__}); playing the unsmoothed clip", flush=True)
    print(f"[veo-opening] ready in {time.time() - started:.0f}s "
          f"({'smoothed to 60 FPS' if smoothed else 'unsmoothed'})", flush=True)
    return {"clip": str(clip), "clip_id": CLIP_ID, "seconds": float(seconds), "model": model,
            "prompt": prompt, "smoothed": smoothed}
