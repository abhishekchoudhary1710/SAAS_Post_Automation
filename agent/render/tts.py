"""Voice-over. Primary: Gemini TTS, which sounds like a person. Fallback: Microsoft Edge voices.

The owner's verdict on the Edge voices was that they sound robotic, and they do, especially sped
up. Gemini's speech models take a spoken direction ("warm, conversational, like a friendly senior")
and deliver noticeably human narration, on the same free Gemini key the agent already uses.

Two rules learned the hard way on 11 Sep 2026:

* The preview speech model has a tight per-minute limit. A reel voices four slides back to back,
  and the second or third call came back 429. So a 429 is answered by waiting exactly as long as
  Google asks (it says so in the error) and trying again, up to three times.
* A reel must never mix voices. If one slide has to fall back to Edge, every slide in that reel
  is voiced by Edge. `synthesize_batch` guarantees that; the reel builder uses it.

Any failure still falls back to Edge, which is free and has not failed us once, so audio can
never cost a post. Engine, model and voice live in knowledge/brand.json under "voices".

Hinglish narration is best written in mixed script (Devanagari for Hindi words, Latin for English
words); both engines read that correctly. The writer prompt asks for exactly that in `narration`.
"""

from __future__ import annotations

import asyncio
import base64
import os
import pathlib
import re
import shutil
import subprocess
import time
import wave

import requests

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
GEMINI_ATTEMPTS = 3
MAX_WAIT = 70          # seconds; longer than any retryDelay the free tier has asked for so far
PACE = 4.0             # seconds between consecutive Gemini calls, to stay under the per-minute limit
_last_gemini_call = 0.0


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


def _retry_after(message: str) -> float | None:
    """How long Google asked us to wait, parsed out of a 429 body. None when it did not say."""
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", message) or \
        re.search(r"retry in (\d+(?:\.\d+)?)\s*s", message, re.I)
    return min(float(m.group(1)) + 1.0, MAX_WAIT) if m else None


def _gemini_once(text: str, out: pathlib.Path, language: str) -> pathlib.Path:
    global _last_gemini_call
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise TTSError("no GEMINI_API_KEY in the environment")
    cfg = brand()["voices"]
    model = cfg.get("gemini_model", "gemini-3.1-flash-tts-preview")
    voice = cfg.get("gemini_voice", "Achird")
    from google import genai
    from google.genai import types

    gap = PACE - (time.time() - _last_gemini_call)
    if gap > 0:
        time.sleep(gap)
    client = genai.Client(api_key=key)
    _last_gemini_call = time.time()
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


def _gemini(text: str, out: pathlib.Path, language: str) -> pathlib.Path:
    """Gemini with the per-minute limit respected: wait what the 429 asks, then try again."""
    last: Exception | None = None
    for attempt in range(GEMINI_ATTEMPTS):
        try:
            return _gemini_once(text, out, language)
        except Exception as exc:  # noqa: BLE001
            last = exc
            message = str(exc)
            if "429" not in message and "RESOURCE_EXHAUSTED" not in message:
                break
            if attempt == GEMINI_ATTEMPTS - 1:
                break
            wait = _retry_after(message) or (20.0 * (attempt + 1))
            print(f"[tts] Gemini rate limit, waiting {wait:.0f}s (attempt {attempt + 1}/{GEMINI_ATTEMPTS})")
            time.sleep(wait)
    raise TTSError(f"Gemini voice unavailable: {type(last).__name__}: {str(last)[:160]}")


CHIRP_LOCALES = {"english": "en-IN", "hinglish": "hi-IN"}
CHIRP_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def _chirp(text: str, out: pathlib.Path, language: str) -> pathlib.Path:
    """Cloud Text-to-Speech, Chirp 3 HD: the same named voices as Gemini, no 10-a-day quota.

    Authenticates with whatever Google Cloud credentials the process has (on GitHub, the
    Workload Identity Federation identity the Veo step already uses), and bills that project:
    the first million characters a month are free, and a reel is about 400.
    """
    cfg = brand()["voices"]
    if cfg.get("chirp", True) is False:
        raise TTSError("Chirp disabled in brand.json")
    try:
        import google.auth
        from google.auth.transport.requests import Request

        creds, detected = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(Request())
    except Exception as exc:  # noqa: BLE001 - no Cloud identity here (a laptop without gcloud, say)
        raise TTSError(f"no Google Cloud credentials for Chirp: {type(exc).__name__}: {str(exc)[:120]}")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip() or (detected or "")
    locale = CHIRP_LOCALES.get(language, CHIRP_LOCALES["english"])
    name = f"{locale}-Chirp3-HD-{cfg.get('chirp_voice') or cfg.get('gemini_voice', 'Achird')}"
    headers = {"Authorization": f"Bearer {creds.token}"}
    if project:
        headers["x-goog-user-project"] = project
    resp = requests.post(CHIRP_URL, headers=headers, timeout=90, json={
        "input": {"text": text},
        "voice": {"languageCode": locale, "name": name},
        "audioConfig": {"audioEncoding": "MP3", "sampleRateHertz": 24000},
    })
    if resp.status_code != 200:
        # keep the whole reason: a 403 is either SERVICE_DISABLED (enable the API, the body carries
        # the activation URL) or PERMISSION_DENIED (the identity lacks a role), and they need
        # different fixes
        raise TTSError(f"Chirp HTTP {resp.status_code}: {' '.join(resp.text.split())[:700]}")
    audio = base64.b64decode(resp.json().get("audioContent") or "")
    if len(audio) < 1000:
        raise TTSError("Chirp returned no audio")
    out.write_bytes(audio)
    return out


ENGINES = {"gemini": _gemini, "chirp": _chirp}


def _engine_order() -> list[str]:
    """Human voices to try, in order, before Edge. From brand.json voices.engine_order, or the default."""
    cfg = brand()["voices"]
    if cfg.get("engine", "gemini") == "edge":
        return []
    order = cfg.get("engine_order") or ["gemini", "chirp"]
    return [e for e in order if e in ENGINES]


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
    """Write an MP3 for `text`: the first human engine that answers (Gemini, then Chirp), else Edge.

    Passing an explicit `voice` means an Edge voice name and skips the human engines.
    Raises TTSError only if every engine fails.
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if voice is None:
        for engine in _engine_order():
            try:
                return ENGINES[engine](text, out, language)
            except TTSError as exc:
                print(f"[tts] {engine}: {exc}; trying the next voice")
    return _edge(text, out, language, voice, attempts)


def synthesize_batch(texts: list[str | None], outs: list[pathlib.Path], language: str = "english",
                     attempts: int = 3) -> tuple[list[pathlib.Path | None], str]:
    """Voice several lines with ONE engine. Returns (paths, engine): "gemini", "chirp" or "edge".

    If an engine manages some lines and then fails on another, the lines it did manage are
    thrown away and everything is re-voiced by the next engine, so a reel never switches
    voice between slides.
    """
    outs = [pathlib.Path(o) for o in outs]
    for o in outs:
        o.parent.mkdir(parents=True, exist_ok=True)
    for engine in _engine_order():
        done: list[pathlib.Path | None] = []
        try:
            for text, out in zip(texts, outs):
                done.append(ENGINES[engine](text, out, language) if text else None)
            return done, engine
        except TTSError as exc:
            print(f"[tts] {engine}: {exc}; re-voicing the whole reel with the next engine")
            for p in done:
                if p is not None:
                    p.unlink(missing_ok=True)
    return [(_edge(text, out, language, None, attempts) if text else None)
            for text, out in zip(texts, outs)], "edge"
