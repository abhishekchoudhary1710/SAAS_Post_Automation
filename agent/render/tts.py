"""Voice-over through Microsoft Edge's neural voices (edge-tts). Free, no key, Indian voices.

Hinglish narration is best written in mixed script (Devanagari for Hindi words, Latin for
English words) and spoken by a hi-IN voice; Roman-script Hinglish sounds wrong in every voice.
The writer prompt asks for exactly that in the `narration` field.
"""

from __future__ import annotations

import asyncio
import pathlib
import time

from ..config import brand


class TTSError(RuntimeError):
    pass


def voice_for(language: str) -> str:
    voices = brand()["voices"]
    return voices.get(language) or voices["english"]


async def _synth(text: str, voice: str, rate: str, out: pathlib.Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out))


def synthesize(text: str, out: pathlib.Path, language: str = "english", voice: str | None = None,
               attempts: int = 3) -> pathlib.Path:
    """Write an MP3 for `text`. Raises TTSError after `attempts` failures."""
    voice = voice or voice_for(language)
    rate = brand()["voices"].get("rate", "+0%")
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            asyncio.run(_synth(text, voice, rate, out))
            if out.exists() and out.stat().st_size > 1000:
                return out
            last = TTSError("edge-tts produced an empty file")
        except Exception as exc:  # network hiccups, token refresh, and so on
            last = exc
        time.sleep(3 * (attempt + 1))
    raise TTSError(f"voice-over failed for {voice}: {last}")
