"""Experiment: build a reel whose visuals are entirely Veo, for comparison against the cards.

Run from GitHub Actions, where Workload Identity Federation provides Vertex credentials.
Writes out/veo-full/reel.mp4 plus the individual clips, and prints what it cost.

This is deliberately NOT wired into the posting pipeline. It exists so the difference between
"beautiful footage that never shows the product" and "cards that demonstrate it" can be judged
by watching both, rather than argued about.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.config import Settings, schedule  # noqa: E402
from agent.copywriter import produce  # noqa: E402
from agent.history import History  # noqa: E402
from agent.llm import Gemini  # noqa: E402
from agent.render.reel import ffmpeg_exe  # noqa: E402
from agent.render.tts import synthesize  # noqa: E402
from agent.strategy import decide_language, plan_post  # noqa: E402

OUT = pathlib.Path("out/veo-full")
CLIP_SECONDS = 8
RATE_PER_SECOND = 0.03      # veo-3.1-lite, video only, 720p
LOOK = ("Vertical 9:16, realistic handheld documentary footage, natural colour, shallow depth of "
        "field, warm daylight from a window, an ordinary Indian home. No text, no captions, no "
        "logos, no visible screen content, no user interface. ")


def shot_prompts(content: dict) -> list[str]:
    """Three beats: the problem, the turn, the result. Veo gets people, never interfaces."""
    topic = str(content.get("topic") or "an online job interview")
    return [
        LOOK + f"A young Indian graduate sits at a small desk facing a laptop during an online job "
               f"interview about {topic}. He hesitates, searching for words, visibly unsure. "
               "Close on his face, then his hands still on the keyboard.",
        LOOK + "The same young man glances down at something beside his laptop, takes a short "
               "breath, and his expression settles as he finds his footing. A small, real moment "
               "of relief, not a grin.",
        LOOK + "The same young man now speaks to the laptop with easy confidence, gesturing "
               "lightly as he explains, sitting straighter. He finishes, listens, and nods.",
    ]


def generate(prompts: list[str]) -> list[pathlib.Path]:
    from google import genai
    from google.genai import types
    import os

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "video-generation-uniyal")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    model = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-001")
    client = genai.Client(vertexai=True, project=project, location=location)
    clips: list[pathlib.Path] = []
    for i, prompt in enumerate(prompts, 1):
        print(f"[veo] clip {i}/{len(prompts)} ({CLIP_SECONDS}s) ...", flush=True)
        started = time.time()
        op = client.models.generate_videos(
            model=model, prompt=prompt,
            config=types.GenerateVideosConfig(aspect_ratio="9:16", resolution="720p",
                                              duration_seconds=CLIP_SECONDS, number_of_videos=1,
                                              generate_audio=False, person_generation="allow_adult"),
        )
        while not op.done:
            time.sleep(15)
            op = client.operations.get(op)
        videos = op.response.generated_videos if op.response else []
        if not videos:
            raise RuntimeError(f"clip {i} returned nothing: {getattr(op, 'error', '')}")
        path = OUT / f"clip-{i:02d}.mp4"
        data = getattr(videos[0].video, "video_bytes", None)
        if data:
            path.write_bytes(data)
        else:
            videos[0].video.save(str(path))
        print(f"[veo] clip {i} saved, {path.stat().st_size} bytes, {time.time() - started:.0f}s")
        clips.append(path)
    client.close()
    return clips


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env()
    llm = Gemini(settings.gemini_api_key or "", settings.gemini_models)
    history = History()
    plan = plan_post(llm, history, "reel", decide_language(history, None), None)
    print(f"[plan] {plan.get('pillar')} | {plan.get('language')} | {plan.get('topic')}")
    content, _ = produce(llm, plan, "reel")

    clips = generate(shot_prompts(content))

    # One narration track over the whole thing, exactly as the card reel would speak it.
    script = " ".join(str(s.get("narration") or "").strip() for s in content["slides"]).strip()
    voice = OUT / "voice.mp3"
    synthesize(script, voice, language=content.get("language", "english"))

    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in clips), encoding="utf-8")
    joined = OUT / "joined.mp4"
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(joined)], check=True)
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(joined), "-i", str(voice),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", str(OUT / "reel.mp4")], check=True)

    seconds = len(clips) * CLIP_SECONDS
    (OUT / "post.json").write_text(json.dumps({"plan": plan, "content": content}, ensure_ascii=False,
                                              indent=1), encoding="utf-8")
    print(f"\n[done] {OUT / 'reel.mp4'}  ~{seconds}s of Veo, about ${seconds * RATE_PER_SECOND:.2f}")
    print(f"[note] narration is {len(script.split())} words over {seconds}s of footage")
    print(f"[note] target reel length is {schedule()['reel']['target_seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
