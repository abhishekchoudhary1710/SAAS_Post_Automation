"""Turn rendered 1080x1920 frames plus narration into a vertical MP4.

Per slide: voice-over (edge-tts) -> WAV, a slow push-in on the still (zoompan), a short
tail of silence so slides do not feel cut off. Segments are concatenated without
re-encoding, then background music is mixed in if assets/music has a track.

ffmpeg comes from the system when present (GitHub's Ubuntu runners ship it) and from the
imageio-ffmpeg wheel otherwise, so the same code runs on a Windows laptop.
"""

from __future__ import annotations

import pathlib
import random
import shutil
import subprocess
import wave

from ..config import ASSETS
from .animate import write_frames
from .tts import TTSError, synthesize, synthesize_batch  # noqa: F401 - synthesize kept for callers

FPS = 30
TAIL = 0.40           # seconds of silence after each narration
NO_VOICE_SECONDS = 3.4
MIN_SLIDE_SECONDS = 2.2
MIN_VOICED_INTRO = 1.5    # below this an opening is a flash, not a beat, so keep it silent
MUSIC_VOLUME = 0.10
# Same colour range and tags on every segment (see film.py): a joined file whose parameters change
# at a slide boundary makes decoders reinitialise there.
COLOR_TAGS = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
TO_TV = "scale=in_range=auto:out_range=tv,setsar=1,format=yuv420p"


def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> None:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + proc.stderr[-3000:])


def _has_audio(path: pathlib.Path) -> bool:
    """True when the file carries an audio stream.

    Veo clips are generated without audio (we narrate over them and audio costs far more), so
    the splice cannot assume one exists: asking ffmpeg for [0:a] on a silent file fails the whole
    filtergraph.
    """
    proc = subprocess.run([ffmpeg_exe(), "-i", str(path)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    return "Audio:" in proc.stderr


def _to_wav(src: pathlib.Path, dst: pathlib.Path) -> float:
    _run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-ar", "44100", "-ac", "2", str(dst)])
    with wave.open(str(dst), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def _trim_wav(src: pathlib.Path, dst: pathlib.Path, start: float = 0.0,
              duration: float | None = None) -> float:
    """A slice of a wav, returning its length. Used to run one line across the opening cut."""
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-ar", "44100", "-ac", "2", str(dst)]
    _run(cmd)
    with wave.open(str(dst), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def _segment(frame: pathlib.Path, wav: pathlib.Path | None, seconds: float, out: pathlib.Path) -> None:
    frames = max(int(round(seconds * FPS)), FPS)
    # upscale a little before zoompan; it removes most of the filter's jitter
    vf = (f"scale=1620:2880,zoompan=z='min(1+0.00045*on,1.18)':d=1:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={FPS},"
          f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(seconds - 0.25, 0):.2f}:d=0.25,{TO_TV}")
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS),
           "-t", f"{seconds:.3f}", "-i", str(frame)]
    if wav:
        cmd += ["-i", str(wav), "-filter_complex", f"[0:v]{vf}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", f"[0:v]{vf}[v]",
                "-map", "[v]", "-map", "1:a"]
    cmd += ["-t", f"{seconds:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", *COLOR_TAGS, "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(out)]
    _run(cmd)
    del frames


def _frames_segment(work: pathlib.Path, prefix: str, wav: pathlib.Path | None,
                    seconds: float, out: pathlib.Path) -> None:
    """One slide, built from its own animated JPEG sequence."""
    fade_out = max(seconds - 0.25, 0)
    # JPEG frames decode as full-range yuvj420p; converted to limited range and tagged like every
    # other segment, so the joined reel does not change parameters at the slide boundary
    vf = f"fade=t=in:st=0:d=0.22,fade=t=out:st={fade_out:.2f}:d=0.25,{TO_TV}"
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-framerate", str(FPS),
           "-i", str(work / f"{prefix}-%05d.jpg")]
    if wav:
        cmd += ["-i", str(wav), "-filter_complex", f"[0:v]{vf}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a"]
    cmd += ["-t", f"{seconds:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", *COLOR_TAGS, "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", str(out)]
    _run(cmd)


def pick_music() -> pathlib.Path | None:
    folder = ASSETS / "music"
    tracks = [p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")]
    return random.choice(tracks) if tracks else None


def build_reel(frames: list[pathlib.Path], narrations: list[str | None], out_mp4: pathlib.Path,
               language: str = "english", music: pathlib.Path | None = None,
               max_seconds: float = 58.0, stages: list[list] | None = None,
               intro: pathlib.Path | None = None, intro_seconds: float = 4.0) -> dict:
    """Render the reel. Returns {"path", "seconds", "voiced": bool, "music": str | None}.

    When `stages` is given (one list of reveal images per slide), each slide is animated:
    its elements arrive one at a time, timed to the narration. Without it the old
    still-plus-zoom path is used, which is what the feed formats still want.
    """
    out_mp4 = pathlib.Path(out_mp4)
    work = out_mp4.parent / "reel-work"
    work.mkdir(parents=True, exist_ok=True)
    segments: list[pathlib.Path] = []
    total = 0.0
    voiced = False
    tts_failed = False
    # Voice every slide first, with one engine for the whole reel. Voicing slide by slide inside
    # the render loop let one slide fall back to Edge while its neighbours kept the Gemini voice,
    # which sounds like two different people narrating one video.
    mp3s: list[pathlib.Path | None] = [None] * len(narrations)
    try:
        mp3s, engine = synthesize_batch(list(narrations), [work / f"voice-{i:02d}.mp3"
                                                          for i in range(1, len(narrations) + 1)], language)
        print(f"[reel] voice: {engine}")
    except TTSError as exc:
        print(f"[reel] voice-over unavailable, continuing without it: {exc}")
        tts_failed = True
    # Each slide's audio, decided before anything is rendered, because the opening needs to know
    # how long the first line runs before it can borrow the start of it.
    voices: list[tuple[pathlib.Path | None, float]] = []
    for i, text in enumerate(narrations, 1):
        mp3 = mp3s[i - 1] if i <= len(mp3s) else None
        if text and mp3 and not tts_failed:
            wav = work / f"voice-{i:02d}.wav"
            voices.append((wav, _to_wav(mp3, wav)))
        else:
            voices.append((None, 0.0))

    # The opening used to be four seconds of silence. A reel is judged in its first second and
    # most of the feed is muted, but dead air at the front still reads as a video that has not
    # started yet, and the sales reels have always spoken over their opening footage. So the
    # first line begins on the footage and carries on over the first card: one continuous
    # sentence across the cut, which is how the cut stops being noticeable.
    intro_voice: pathlib.Path | None = None
    intro_length = intro_seconds
    if intro and pathlib.Path(intro).exists():
        first_wav, first_seconds = voices[0] if voices else (None, 0.0)
        # How much of the first line the opening may take. The first card must keep enough of
        # it to still be a card, so the opening gets whatever is left above that floor, and
        # the footage is cut to exactly that: a clip longer than its narration would put the
        # silence back, one second later. A first line of about five seconds is typical, which
        # is why an earlier version that demanded more than six ran on nothing but the bench.
        usable = min(intro_seconds, max(first_seconds - MIN_SLIDE_SECONDS + TAIL, 0.0)) if first_wav else 0.0
        if first_wav and usable >= MIN_VOICED_INTRO:
            try:
                intro_voice = work / "voice-intro.wav"
                intro_length = _trim_wav(first_wav, intro_voice, duration=usable)
                rest = work / "voice-01-rest.wav"
                voices[0] = (rest, _trim_wav(first_wav, rest, start=usable))
            except Exception as exc:  # noqa: BLE001 - silence is worse but not worth losing the post
                print(f"[reel] could not split the first line over the opening "
                      f"({type(exc).__name__}); opening stays silent")
                intro_voice, intro_length = None, intro_seconds
        elif first_wav:
            print(f"[reel] first line is {first_seconds:.1f}s, too short to share with the "
                  f"opening; it stays silent")
        try:
            normalized = work / "seg-00.mp4"
            scale = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                     f"fps={FPS},format=yuv420p[v]")
            if intro_voice:
                # The clip's own audio is dropped rather than mixed: one voice per video, and Veo
                # speech under the voice-over shipped once and read as two people talking.
                graph = scale + ";[1:a]apad[a]"
                amap, second = "[a]", ["-i", str(intro_voice)]
            elif _has_audio(pathlib.Path(intro)):
                graph = scale + ";[0:a]aresample=44100[a0];[1:a]atrim=0:{:.0f}[a1];".format(intro_length) + \
                        "[a0][a1]amix=inputs=2:duration=first:normalize=0[a]"
                amap, second = "[a]", ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            else:
                graph = scale
                amap, second = "1:a", ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            _run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(intro)] + second +
                 ["-filter_complex", graph,
                  "-map", "[v]", "-map", amap, "-t", f"{intro_length:.3f}",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac",
                  "-b:a", "160k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(normalized)])
            segments.append(normalized)
            total = intro_length
            if intro_voice:
                voiced = True
        except Exception as exc:  # noqa: BLE001 - a decorative opener is never worth losing the post
            print(f"[reel] could not use the intro clip, building without it: {type(exc).__name__}: {exc}")
            segments = []
            total = 0.0
    for i, (frame, text) in enumerate(zip(frames, narrations), 1):
        wav, spoken = voices[i - 1] if i <= len(voices) else (None, 0.0)
        seconds = NO_VOICE_SECONDS
        if wav:
            seconds = max(spoken + TAIL, MIN_SLIDE_SECONDS)
            voiced = True
        if total + seconds > max_seconds and i > 1:
            seconds = max(max_seconds - total, 1.0)
        seg = work / f"seg-{i:02d}.mp4"
        slide_stages = stages[i - 1] if stages and i <= len(stages) else None
        if slide_stages and len(slide_stages) > 1:
            prefix = f"anim-{i:02d}"
            write_frames(slide_stages, seconds, FPS, work, prefix)
            _frames_segment(work, prefix, wav, seconds, seg)
        else:
            _segment(frame, wav, seconds, seg)
        segments.append(seg)
        total += seconds
        if total >= max_seconds:
            break
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding="utf-8")
    joined = work / "joined.mp4"
    _run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", "-movflags", "+faststart", str(joined)])
    music = music if music is not None else pick_music()
    if music and music.exists():
        _run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
              "-filter_complex",
              f"[1:a]volume={MUSIC_VOLUME},afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[m];"
              f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
              "-t", f"{total:.3f}", "-movflags", "+faststart", str(out_mp4)])
    else:
        shutil.copyfile(joined, out_mp4)
    if total >= max_seconds - 2:
        print(f"[reel] WARNING: {total:.1f}s is at the {max_seconds:.0f}s cap, so the last slide may be "
              f"clipped. Shorten the narration for this language.")
    return {"path": str(out_mp4), "seconds": round(total, 2), "voiced": voiced,
            "music": str(music) if music else None}
