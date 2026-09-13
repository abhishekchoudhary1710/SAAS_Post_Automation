"""Assemble the daily film: Veo footage with the app live over it, the answer card, the price card.

The film has one shape every day, so the reels read as a series:

  beat 1  footage: the question lands. Over it, the app's transcript line with the question.
  beat 2  footage, same person: a glance at the laptop, then the answer. Over it, the Interview
          Sarthi panel drafting the answer one sentence at a time.
  card    the full question and answer, rendered, so every word is exact.
  card    the price card.

Narration owns the soundtrack; Veo's own audio is never used. A small site mark sits at the top
right of the footage throughout, because most viewers are muted and the whole point is that they
go and search the site. The overlays are transparent PNG layers (agent/render/live.py) faded in
by ffmpeg at their own moments, so the footage is encoded once.

Veo's extension returns the WHOLE clip (the base plus the new seconds), so an extended beat is
played from where the previous beat ended. Playing it from zero repeated the first beat and never
reached the answer; that shipped on 11 and 12 September and will not again.
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
from .live import answer_layers, question_layers
from .reel import ffmpeg_exe
from .tts import synthesize_batch

FPS = 30
TAIL = 0.45               # silence after each narration before the next segment
FADE = 0.35               # seconds an overlay element takes to arrive
RISE = 26                 # pixels it rises while arriving
HOLD_EXTRA = 1.6          # at most this much frozen last frame if the narration outruns the clip
MARK_Y = 168              # site mark: top right, under the Reels header
# Every segment is tagged the same way. JPEG frame sequences decode as full-range yuvj420p while
# Veo clips and PNG stills are limited range; concatenated as they come, the stream changes
# parameters at the join, decoders reinitialise there, and the card can render a shade off.
COLOR_TAGS = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
TO_TV = "scale=in_range=auto:out_range=tv,setsar=1,format=yuv420p"


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
                     out: pathlib.Path, offset: float = 0.0,
                     overlays: list[tuple[pathlib.Path, float]] | None = None) -> None:
    """One footage beat: clip from `offset`, narration, the site mark, then each overlay layer
    fading in and rising slightly at its own second."""
    inputs = ["-ss", f"{offset:.3f}", "-i", str(clip), "-i", str(mark)]
    # tpad clones the last frame so a narration a little longer than the clip is not cut off
    chain = [f"[0:v]fps={FPS},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
             f"tpad=stop_mode=clone:stop_duration={HOLD_EXTRA + 1:.1f},{TO_TV}[v0]",
             f"[v0][1:v]overlay=W-w-40:{MARK_Y}[v1]"]
    if voice:
        # Narration owns the soundtrack. Veo's own audio is dropped on purpose: its prompts describe
        # the candidate answering, so Veo generates SPEECH, and under a voice-over it is a second
        # person talking. That shipped once (11 Sep) and will not again.
        inputs += ["-i", str(voice)]
        chain.append("[2:a]aresample=44100,apad[a]")
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        chain.append("[2:a]anull[a]")
    last = "v1"
    for k, (png, start) in enumerate(overlays or []):
        idx = 3 + k
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(png)]
        rise = f"-{RISE}*pow(1-min(1\\,max(0\\,(t-{start:.2f})/{FADE})),3)"
        chain.append(f"[{idx}:v]format=rgba,fade=t=in:st={start:.2f}:d={FADE}:alpha=1[o{k}]")
        chain.append(f"[{last}][o{k}]overlay=0:'{rise}':eval=frame:enable='gte(t,{start:.2f})'[v{k + 2}]")
        last = f"v{k + 2}"
    _run([*inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "[a]", "-t", f"{seconds:.3f}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", *COLOR_TAGS, "-c:a", "aac", "-b:a", "160k",
          "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(out)])


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
    _run([*src, *audio_in, "-vf", TO_TV, *amap, "-t", f"{seconds:.3f}", "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "20", *COLOR_TAGS, "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
          "-ac", "2", "-movflags", "+faststart", str(out)])


def build_film(clips: list[pathlib.Path], beat_narrations: list[str], cards: list[dict], out_mp4: pathlib.Path,
               language: str = "english", max_seconds: float = 34.0,
               offsets: list[float] | None = None) -> dict:
    """clips: one file per footage beat, in order. offsets: where each clip starts playing (an
    extended beat starts where the previous beat ended). cards: slide specs, qa first, cta last,
    each with 'narration'. The qa card's question and answer are also what the live overlays show.

    Returns {"path", "seconds", "voice": engine, "beats": n}.
    """
    out_mp4 = pathlib.Path(out_mp4)
    work = out_mp4.parent / "film-work"
    work.mkdir(parents=True, exist_ok=True)
    mark = site_mark(work)
    offsets = list(offsets or [0.0] * len(clips))
    qa = next((c for c in cards if c.get("type") == "qa"), None)

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
    for b, clip in enumerate(clips, 1):
        clip_secs, _ = probe(clip)
        offset = offsets[b - 1] if b - 1 < len(offsets) else 0.0
        remaining = max(clip_secs - offset, 1.0)
        voice = voices[b - 1]
        secs = min(max(voiced_seconds(voice, 4.0), 5.0), remaining + HOLD_EXTRA)
        overlays: list[tuple[pathlib.Path, float]] = []
        if qa is not None:
            if b == 1:
                overlays = question_layers(str(qa.get("question") or ""), work / "live", "q")
            elif b == len(clips):
                overlays = answer_layers(str(qa.get("answer") or ""), secs, work / "live", "a", language)
        seg = work / f"seg-beat-{b:02d}.mp4"
        _footage_segment(clip, voice, secs, mark, seg, offset=offset, overlays=overlays)
        segments.append(seg)
        total += secs

    card_voices = voices[len(clips):]
    for i, spec in enumerate(cards):
        secs = voiced_seconds(card_voices[i], 4.0 if spec.get("type") == "cta" else 5.0)
        seg = work / f"seg-card-{i:02d}.mp4"
        _card_segment(spec, card_voices[i], secs, work, f"card{i:02d}", seg, animated=(spec.get("type") != "cta"))
        segments.append(seg)
        total += secs

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding="utf-8")
    _run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-t", f"{max_seconds:.3f}",
          "-movflags", "+faststart", str(out_mp4)])
    seconds, _ = probe(out_mp4)
    return {"path": str(out_mp4), "seconds": round(seconds, 2), "voice": engine, "beats": len(clips)}
