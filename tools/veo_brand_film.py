"""A promotional brand film for Interview Sarthi: Veo footage plus the real interface.

Three generated clips carry the story, one of them animated from an actual screenshot of the
app so the product on screen is genuinely ours rather than something Veo invented. English
voice-over throughout, and a rendered end card so the price and the address are crisp rather
than generated.

Run from GitHub Actions, where Workload Identity Federation supplies Vertex credentials.
Writes out/veo-brand/ and publishes nothing.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.render.cards import REEL, render_slide  # noqa: E402
from agent.render.reel import ffmpeg_exe  # noqa: E402
from agent.render.tts import synthesize  # noqa: E402

OUT = pathlib.Path("out/veo-brand")
CLIP_SECONDS = 8
END_CARD_SECONDS = 5.0
LOOK = ("Vertical 9:16, photoreal handheld documentary footage, natural colour, shallow depth of "
        "field, soft daylight from a window, an ordinary middle class Indian home. "
        "No text, no captions, no logos, no readable screen content. ")

# The film, written as three beats plus a close. Roughly 2 words a second when spoken.
BEATS = [
    {
        "voice": "Every online interview has that one moment. The question you know the answer to, "
                 "but the words just do not come.",
        "prompt": LOOK + "A young Indian graduate in a plain shirt sits at a small desk facing an "
                         "open laptop during a video job interview. He starts to speak, stops, and "
                         "looks away, searching for words. His hands go still on the keyboard. "
                         "Close on his face, honest and unglamorous.",
    },
    {
        "voice": "Interview Sarthi listens to your interview on Windows, and shows you what to say. "
                 "In English, Hindi or Hinglish, drawn from your own resume.",
        "image": True,   # animated from a real screenshot of the app
        "prompt": "Slow, steady camera push in towards a laptop screen showing a software interface. "
                  "The interface stays perfectly sharp, still and unchanged. Only the camera moves, "
                  "very slightly. Cinematic, calm, no distortion of any text or layout.",
    },
    {
        "voice": "So you answer in your own words, and you sound like yourself.",
        "prompt": LOOK + "The same young Indian graduate now speaks to the laptop with quiet "
                         "confidence, sitting straighter, gesturing lightly as he explains. He "
                         "finishes, listens, and gives a small nod. Warm and understated.",
    },
]
CLOSE_VOICE = "Thirty minutes free. No card. Interview sarthi dot com."


def product_still() -> pathlib.Path:
    """Veo's first frame: our own product card, which already frames the real screenshot on brand.

    Hand-composing the panel on a dark canvas left most of the frame empty. The card renderer
    already solves that, and starting from a designed frame gives Veo less room to invent.
    """
    spec = {"type": "product", "title": "Interview Sarthi shows you what to say.",
            "caption": "It listens to your interview and drafts from your resume.",
            "image": "overlay_hinglish", "theme": "dark"}
    img = render_slide(spec, REEL, 1, 1)
    path = OUT / "product-still.png"
    img.save(path)
    return path


def end_card() -> pathlib.Path:
    spec = {"type": "cta", "title": "30 minutes free. No card.",
            "subtitle": "Windows app. One-time passes from Rs 99.", "show_pricing": True,
            "theme": "dark"}
    img = render_slide(spec, REEL, 1, 1)
    path = OUT / "end-card.png"
    img.save(path)
    return path


def generate(beats: list[dict], still: pathlib.Path) -> list[pathlib.Path]:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True,
                          project=os.environ.get("GOOGLE_CLOUD_PROJECT", "video-generation-uniyal"),
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
    model = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-001")
    clips: list[pathlib.Path] = []
    for i, beat in enumerate(beats, 1):
        kind = "image-to-video (real screenshot)" if beat.get("image") else "text-to-video"
        print(f"[veo] clip {i}/{len(beats)}, {kind} ...", flush=True)
        started = time.time()
        kwargs = {}
        if beat.get("image"):
            kwargs["image"] = types.Image(image_bytes=still.read_bytes(), mime_type="image/png")
        op = client.models.generate_videos(
            model=model, prompt=beat["prompt"],
            config=types.GenerateVideosConfig(aspect_ratio="9:16", resolution="720p",
                                              duration_seconds=CLIP_SECONDS, number_of_videos=1,
                                              generate_audio=False, person_generation="allow_adult"),
            **kwargs)
        while not op.done:
            time.sleep(15)
            op = client.operations.get(op)
        videos = op.response.generated_videos if op.response else []
        if not videos:
            raise RuntimeError(f"clip {i} returned nothing: {getattr(op, 'error', '')}")
        path = OUT / f"clip-{i:02d}.mp4"
        data = getattr(videos[0].video, "video_bytes", None)
        path.write_bytes(data) if data else videos[0].video.save(str(path))
        print(f"[veo] clip {i} ok, {path.stat().st_size} bytes, {time.time() - started:.0f}s")
        clips.append(path)
    client.close()
    return clips


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    still = product_still()
    clips = generate(BEATS, still)

    # A still end card, so the price and the address are sharp rather than generated.
    card = end_card()
    card_clip = OUT / "clip-04.mp4"
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30",
                    "-t", f"{END_CARD_SECONDS}", "-i", str(card), "-vf",
                    "scale=1080:1920,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "21", str(card_clip)], check=True)
    clips.append(card_clip)

    script = " ".join([b["voice"] for b in BEATS] + [CLOSE_VOICE])
    voice = OUT / "voice.mp3"
    synthesize(script, voice, language="english")

    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in clips), encoding="utf-8")
    joined = OUT / "joined.mp4"
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                    "-r", "30", "-vf", "scale=1080:1920,format=yuv420p", str(joined)], check=True)
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(joined), "-i", str(voice),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(OUT / "brand-film.mp4")], check=True)

    seconds = len(BEATS) * CLIP_SECONDS + END_CARD_SECONDS
    (OUT / "script.txt").write_text(script, encoding="utf-8")
    print(f"\n[done] {OUT / 'brand-film.mp4'}  about {seconds:.0f}s")
    print(f"[cost] {len(BEATS) * CLIP_SECONDS}s of Veo at $0.03/s = about "
          f"${len(BEATS) * CLIP_SECONDS * 0.03:.2f}")
    print(f"[script] {len(script.split())} words:\n{script}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
