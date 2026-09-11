"""Voice-over. Primary: Gemini TTS, which sounds like a person. Fallback: Microsoft Edge voices.

The owner's verdict on the Edge voices was that they sound robotic, and they do, especially sped
up. Gemini's speech models take a spoken direction ("warm, conversational, like a friendly senior")
and deliver noticeably human narration, on the same free Gemini key the agent already uses.

That model is a preview with unpublished free-tier limits, so it is never allowed to cost a post:
any failure falls back to Edge, which is free and has not failed us once. The engine, model and
voice live in knowledge/brand.json under "voices", so changing the voice is a one-word edit.

Hinglish narration is best written in mixed script (Devanagari for Hindi words, Latin for English
words); both engines read that correctly. The writer prompt asks for exactly that in `narration`.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import subprocess
import time
import wave

from ..config import brand


class TTSError(RuntimeError):
    pass


DIRECTIONS = {
    "english": ("Read the following aloud in a natural, warm Indian English voice, like a friendly senior "
                "colleague talking to a nervous fresher. Conversational and relaxed, with natural pauses, "
                "not an announcer or an advert voice. Say the brand as Interview Saar-thee. Text: "),
    "hinglish": ("Read the following aloud in natural, warm Hinglish with an Indian accent, the way a "
                 "friendly senior talks to a fresher. Conversational and relaxed, with natural pauses, not "
                 "an announcer. Say the brand as Interview Saar-thee. Text: "),
}


def voice_for(language: str) -> str:
    """The Edge voice for a language; used by the fallback path."""
    voices = brand()["voices"]
    return voices.get(language) or voices["english"]


def _ffmpeg() -> str:
    # Local copy of reel.ffmpeg_exe: reel imports this module, so importing reel here would loop.
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _gemini(text: str, out: pathlib.Path, language: str) -> pathlib.Path:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise TTSError("no GEMINI_API_KEY in the environment")
    cfg = brand()["voices"]
    model = cfg.get("gemini_model", "gemini-3.1-flash-tts-preview")
    voice = cfg.get("gemini_voice", "Achird")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=model,
        contents=DIRECTIONS.get(language, DIRECTIONS["english"]) + text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
    cand = (resp.candidates or [None])[0]
    if cand is None or cand.content is None or not cand.content.parts:
        # Seen with the 2.5 preview models: a response with no content at all.
        raise TTSError(f"{model} returned no audio (finish_reason={getattr(cand, 'finish_reason', None)})")
    pcm = cand.content.parts[0].inline_data.data           # 16-bit mono PCM at 24 kHz
    wav = out.with_suffix(".gemini.wav")
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(pcm)
    proc = subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(out)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    wav.unlink(missing_ok=True)
    if proc.returncode or not out.exists() or out.stat().st_size < 1000:
        raise TTSError(f"could not encode the Gemini audio: {proc.stderr[-200:]}")
    return out


async def _edge_synth(text: str, voice: str, rate: str, out: pathlib.Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out))


def _edge(text: str, out: pathlib.Path, language: str, voice: str | None, attempts: int) -> pathlib.Path:
    voice = voice or voice_for(language)
    rate = brand()["voices"].get("rate", "+0%")
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            asyncio.run(_edge_synth(text, voice, rate, out))
            if out.exists() and out.stat().st_size > 1000:
                return out
            last = TTSError("edge-tts produced an empty file")
        except Exception as exc:  # network hiccups, token refresh, and so on
            last = exc
        time.sleep(3 * (attempt + 1))
    raise TTSError(f"voice-over failed for {voice}: {last}")


def synthesize(text: str, out: pathlib.Path, language: str = "english", voice: str | None = None,
               attempts: int = 3) -> pathlib.Path:
    """Write an MP3 for `text`: Gemini's human voice when it answers, Edge otherwise.

    Passing an explicit `voice` means an Edge voice name and skips Gemini.
    Raises TTSError only if both engines fail.
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if voice is None and brand()["voices"].get("engine", "gemini") == "gemini":
        for attempt in range(2):
            try:
                return _gemini(text, out, language)
            except Exception as exc:  # noqa: BLE001 - a voice is never worth losing the post
                message = str(exc)
                if "429" in message and attempt == 0:
                    time.sleep(30)
                    continue
                print(f"[tts] Gemini voice unavailable, using Edge instead: {type(exc).__name__}: {message[:160]}")
                break
    return _edge(text, out, language, voice, attempts)
