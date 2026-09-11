"""Brand film with ONE continuous actor: a Veo clip, then a Veo extension of that same clip.

The previous film cut between two separately generated clips, so the man in shot one and the man
in shot three were different people. Extension continues an existing clip, so face, room and light
carry through. The product and price shots stay our own rendered cards, because Veo cannot hold a
real interface (it turned our screenshot into a chat app with invented text).

Extension on Vertex needs veo-3.1-fast-generate-preview or veo-3.1-generate-preview; the Lite
model we use for cold opens does not extend. This script tries passing the clip inline first and
prints Vertex's exact answer if it insists on a Cloud Storage path instead.

Run from GitHub Actions (Workload Identity Federation). Writes out/veo-continuous/, publishes nothing.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.render.animate import write_frames  # noqa: E402
from agent.render.cards import REEL, render_slide, render_stages  # noqa: E402
from agent.render.reel import ffmpeg_exe  # noqa: E402
from agent.render.tts import synthesize  # noqa: E402

OUT = pathlib.Path("out/veo-continuous")
WORK = OUT / "work"
FPS = 30
MODEL = os.environ.get("VEO_EXTEND_MODEL", "veo-3.1-fast-generate-preview")
RATE = 0.15   # upper estimate per second for the Fast model, video only

LOOK = ("Vertical 9:16, photoreal handheld documentary footage, natural colour, shallow depth of field, "
        "soft daylight from a window, an ordinary middle class Indian home. No text, no captions, no logos, "
        "no readable screen content. ")
BASE_PROMPT = (LOOK + "A young Indian graduate with short black hair and thin rectangular glasses, wearing a "
               "light blue button shirt, sits at a small wooden desk facing an open laptop during a video job "
               "interview. He starts to answer, stops, and looks away, searching for words. His hands go still "
               "on the keyboard. Close on his face, honest and unglamorous.")
EXTEND_PROMPT = ("The same man, same glasses, same blue shirt, same room and light, continues without a cut. "
                 "He glances at the laptop, takes a short breath, his expression settles, and he begins to "
                 "answer with quiet confidence, sitting straighter and gesturing lightly as he explains. "
                 "He finishes and gives a small nod.")

SCRIPT = ("Every online interview has that one moment. You know the answer, but the words do not come. "
          "Interview Sarthi listens on Windows and shows you what to say, from your own resume. "
          "So you answer in your own words. "
          "Thirty minutes free, no card. Interview sarthi dot com.")
PRODUCT = {"type": "product", "title": "Interview Sarthi shows you what to say.",
           "caption": "It listens to your interview and drafts from your resume.",
           "image": "overlay_hinglish", "theme": "dark"}
CTA = {"type": "cta", "title": "30 minutes free. No card.",
       "subtitle": "Windows app. One-time passes from Rs 99.", "show_pricing": True, "theme": "dark"}
TIMELINE = [("struggle", 6.5), ("product", 6.5), ("confident", 7.0), ("price", 4.5)]


def ff(args: list[str], timeout: int = 300) -> None:
    p = subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stderr[-1500:])


def duration(path: pathlib.Path) -> float:
    p = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def wait(client, op, label: str):
    started = time.time()
    while not op.done:
        time.sleep(15)
        op = client.operations.get(op)
    err = getattr(op, "error", None)
    if err:
        raise RuntimeError(f"{label} failed: {err}")
    videos = op.response.generated_videos if op.response else []
    if not videos:
        raise RuntimeError(f"{label} returned no video")
    print(f"[veo] {label} done in {time.time() - started:.0f}s", flush=True)
    return videos[0].video


def save(video, path: pathlib.Path) -> pathlib.Path:
    data = getattr(video, "video_bytes", None)
    if data:
        path.write_bytes(data)
    else:
        video.save(str(path))
    return path


def generate() -> tuple[pathlib.Path, pathlib.Path | None]:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True,
                          project=os.environ.get("GOOGLE_CLOUD_PROJECT", "video-generation-uniyal"),
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
    cfg = dict(aspect_ratio="9:16", resolution="720p", number_of_videos=1, generate_audio=False,
               person_generation="allow_adult")

    print(f"[veo] base clip, 8s, {MODEL}", flush=True)
    op = client.models.generate_videos(model=MODEL, prompt=BASE_PROMPT,
                                       config=types.GenerateVideosConfig(duration_seconds=8, **cfg))
    base_video = wait(client, op, "base clip")
    base = save(base_video, OUT / "base.mp4")
    print(f"[veo] base saved {base.stat().st_size} bytes, {duration(base):.2f}s")

    extended = None
    try:
        print("[veo] extending the same clip, passing it inline", flush=True)
        src = types.Video(video_bytes=base.read_bytes(), mime_type="video/mp4")
        op = client.models.generate_videos(model=MODEL, prompt=EXTEND_PROMPT, video=src,
                                           config=types.GenerateVideosConfig(**cfg))
        extended = save(wait(client, op, "extension"), OUT / "extended.mp4")
        print(f"[veo] extension saved {extended.stat().st_size} bytes, {duration(extended):.2f}s")
    except Exception as exc:  # noqa: BLE001 - report exactly what Vertex said, keep the base clip
        print(f"[veo] EXTENSION REFUSED: {type(exc).__name__}: {str(exc)[:600]}")
    client.close()
    return base, extended


def segment(kind: str, secs: float, base: pathlib.Path, extended: pathlib.Path | None) -> pathlib.Path:
    out = WORK / f"{kind}.mp4"
    norm = f"fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p"
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)]
    if kind == "struggle":
        ff(["-i", str(base), "-vf", norm, "-t", f"{secs}", *enc])
    elif kind == "confident":
        src = extended or base
        total = duration(src)
        # extension output usually contains the original plus the new part; take the tail
        start = max(total - secs, 0.0) if total > secs + 1 else 0.0
        ff(["-ss", f"{start:.2f}", "-i", str(src), "-vf", norm, "-t", f"{secs}", *enc])
    elif kind == "product":
        stages = render_stages(PRODUCT, REEL, 1, 1)
        write_frames(stages, secs, FPS, WORK, "pf")
        ff(["-framerate", str(FPS), "-i", str(WORK / "pf-%05d.jpg"), "-vf", "format=yuv420p",
            "-t", f"{secs}", *enc])
    else:
        img = WORK / "price.png"
        render_slide(CTA, REEL, 1, 1).save(img)
        ff(["-loop", "1", "-framerate", str(FPS), "-i", str(img), "-vf", "format=yuv420p",
            "-t", f"{secs}", *enc])
    return out


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    base, extended = generate()
    segs = [segment(kind, secs, base, extended) for kind, secs in TIMELINE]
    listing = WORK / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segs), encoding="utf-8")
    joined = WORK / "joined.mp4"
    ff(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])

    total = sum(s for _, s in TIMELINE)
    voice = WORK / "voice.mp3"
    synthesize(SCRIPT, voice, language="english")
    final = OUT / "InterviewSarthi-continuous.mp4"
    # apad must be bounded, or -shortest never fires and the write never finishes
    ff(["-i", str(joined), "-i", str(voice), "-filter_complex", f"[1:a]apad=whole_dur={total}[a]",
        "-map", "0:v", "-map", "[a]", "-t", f"{total}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(final)])

    veo_seconds = duration(base) + (duration(extended) if extended else 0.0)
    print(f"\n[done] {final}  {duration(final):.2f}s")
    print(f"[continuity] {'one actor: extension worked' if extended else 'extension refused, base clip reused'}")
    print(f"[cost] about {veo_seconds:.0f}s of {MODEL}, at most ${veo_seconds * RATE:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
