"""Assemble the daily generated reel: Veo footage, the real product card, the price card.

Per beat: the clip is normalised to our 30 fps 1080x1920 timeline, its own ambient sound is
ducked under that beat's narration, and a small site mark sits in the corner throughout, because
most viewers are muted and the whole point is that they go and search the site. The product card
(the real interface with today's question and answer) and the price card are rendered, not
generated, so every word on them is exact.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

from PIL import Image, ImageDraw

from ..config import brand
from .animate import write_frames
from .cards import REEL, render_slide, render_stages
from .fonts import font
from .reel import ffmpeg_exe
from .tts import synthesize_batch

FPS = 30
AMBIENT_DB = -16          # Veo's own sound, under the voice
TAIL = 0.45               # silence after each narration before the next beat


def _run(args: list[str], timeout: int = 600) -> None:
    proc = subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode:
        raise RuntimeError("ffmpeg failed:\n" + proc.stderr[-1500:])


def probe(path: pathlib.Path) -> tuple[float, bool]:
    """(duration in seconds, has audio stream)."""
    proc = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", proc.stderr)
    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    return secs, "Audio:" in proc.stderr


def site_mark(work: pathlib.Path) -> pathlib.Path:
    """A small, soft site name for the corner of the footage. Rendered once per run."""
    text = brand()["site"].replace("https://", "").replace("http://", "").rstrip("/")
    f = font(34, "semibold")
    pad = 18
    w = int(f.getlength(text)) + 2 * pad
    h = 34 + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=(10, 14, 24, 150))
    d.text((pad, pad - 4), text, font=f, fill=(255, 255, 255, 235))
    path = work / "site-mark.png"
    img.save(path)
    return path


def _footage_segment(clip: pathlib.Path, voice: pathlib.Path | None, seconds: float, mark: pathlib.Path,
                     out: pathlib.Path) -> None:
    _, has_audio = probe(clip)
    inputs = ["-i", str(clip), "-i", str(mark)]
    video = (f"[0:v]fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
             f"format=yuv420p[v0];[v0][1:v]overlay=W-w-40:H-h-380[v]")
    if voice:
        inputs += ["-i", str(voice)]
        if has_audio:
            audio = (f"[0:a]volume={AMBIENT_DB}dB,aresample=44100[amb];[2:a]aresample=44100,apad[vo];"
                     "[amb][vo]amix=inputs=2:duration=first:normalize=0[a]")
        else:
            audio = "[2:a]aresample=44100,apad[a]"
    elif has_audio:
        audio = "[0:a]aresample=44100[a]"
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio = "[2:a]anull[a]"
    _run([*inputs, "-filter_complex", f"{video};{audio}", "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.3f}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
          "-ac", "2", "-movflags", "+faststart", str(out)])


def _card_segment(spec: dict, voice: pathlib.Path | None, seconds: float, work: pathlib.Path, tag: str,
                  out: pathlib.Path, animated: bool = True) -> None:
    if animated:
        stages = render_stages(spec, REEL, 1, 1)
        if len(stages) > 1:
            write_frames(stages, seconds, FPS, work, tag)
            src = ["-framerate", str(FPS), "-i", str(work / f"{tag}-%05d.jpg")]
        else:
            img = work / f"{tag}.png"
            stages[-1].save(img)
            src = ["-loop", "1", "-framerate", str(FPS), "-i", str(img)]
    else:
        img = work / f"{tag}.png"
        render_slide(spec, REEL, 1, 1).save(img)
        src = ["-loop", "1", "-framerate", str(FPS), "-i", str(img)]
    if voice:
        audio_in = ["-i", str(voice)]
        amap = ["-filter_complex", "[1:a]aresample=44100,apad[a]", "-map", "0:v", "-map", "[a]"]
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        amap = ["-map", "0:v", "-map", "1:a"]
    _run([*src, *audio_in, "-vf", "format=yuv420p", *amap, "-t", f"{seconds:.3f}", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
          "-movflags", "+faststart", str(out)])


def build_film(clips: list[pathlib.Path], beat_narrations: list[str], cards: list[dict], card_after_beat: int,
               out_mp4: pathlib.Path, language: str = "english", max_seconds: float = 34.0) -> dict:
    """clips: one file per footage beat, in order. cards: slide specs (qa first, cta last) with 'narration'.

    Returns {"path", "seconds", "voice": engine, "beats": n}.
    """
    out_mp4 = pathlib.Path(out_mp4)
    work = out_mp4.parent / "film-work"
    work.mkdir(parents=True, exist_ok=True)
    mark = site_mark(work)

    texts = list(beat_narrations) + [str(c.get("narration") or "") for c in cards]
    voices, engine = synthesize_batch(texts, [work / f"voice-{i:02d}.mp3" for i in range(len(texts))], language)
    print(f"[film] voice: {engine}")

    def voiced_seconds(v: pathlib.Path | None, floor: float) -> float:
        if not v:
            return floor
        secs, _ = probe(v)
        return max(secs + TAIL, floor)

    segments: list[pathlib.Path] = []
    total = 0.0
    card_voices = voices[len(clips):]
    card_index = 0

    def add_card(i: int) -> None:
        nonlocal total, card_index
        spec = cards[i]
        secs = voiced_seconds(card_voices[i], 4.0 if spec.get("type") == "cta" else 5.0)
        seg = work / f"seg-card-{i:02d}.mp4"
        _card_segment(spec, card_voices[i], secs, work, f"card{i:02d}", seg, animated=(spec.get("type") != "cta"))
        segments.append(seg)
        total += secs

    for b, clip in enumerate(clips, 1):
        clip_secs, _ = probe(clip)
        voice = voices[b - 1]
        secs = min(clip_secs, max(voiced_seconds(voice, 4.0), 5.0))
        seg = work / f"seg-beat-{b:02d}.mp4"
        _footage_segment(clip, voice, secs, mark, seg)
        segments.append(seg)
        total += secs
        if b == card_after_beat and cards:
            add_card(0)                      # the product card, right after the laptop moment
    if cards and card_after_beat > len(clips):
        add_card(0)
    for i in range(1, len(cards)):           # the price card (and anything else) closes
        add_card(i)

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding="utf-8")
    _run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-t", f"{max_seconds:.3f}",
          "-movflags", "+faststart", str(out_mp4)])
    seconds, _ = probe(out_mp4)
    return {"path": str(out_mp4), "seconds": round(seconds, 2), "voice": engine, "beats": len(clips)}
