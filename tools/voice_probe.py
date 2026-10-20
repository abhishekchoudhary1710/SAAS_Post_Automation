"""Prove each voice engine from inside GitHub Actions, where the Cloud identity exists.

Prints, per engine and language, whether it produced audio and how long it took, without
touching the posting pipeline. Chirp is the one that cannot be tested from a laptop: it needs
the Workload Identity Federation credentials the workflow provides.
"""

from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agent.render import tts  # noqa: E402

OUT = pathlib.Path("out/voice-probe")
OUT.mkdir(parents=True, exist_ok=True)
LINES = {
    "english": "Interview Sarthi listens on Windows and shows you what to say, from your own resume.",
    "hinglish": "Interviewer ने अचानक Hindi में पूछ लिया? घबराओ मत. Interview Sarthi आपके resume से जवाब draft करता है.",
}

failures = 0
for engine, fn in (("chirp", tts._chirp), ("gemini", tts._gemini)):
    for language, line in LINES.items():
        out = OUT / f"{engine}-{language}.mp3"
        started = time.time()
        try:
            fn(line, out, language)
            print(f"ok    {engine:7} {language:9} {out.stat().st_size:7d} bytes  {time.time() - started:4.1f}s")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {engine:7} {language:9} {type(exc).__name__}: {str(exc)[:300]}")
print(f"\nengine order in use: {tts._engine_order()} then edge")
sys.exit(0)
