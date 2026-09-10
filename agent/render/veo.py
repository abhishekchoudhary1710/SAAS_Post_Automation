"""Generate a short visual hook with Veo through Vertex AI."""

from __future__ import annotations

import os
import pathlib
import time


def generate_hook(content: dict, out_path: pathlib.Path, seconds: int | None = None) -> pathlib.Path | None:
    """Return a short portrait cold open, or None so the card renderer can continue.

    Kept short on purpose. The opening seconds are where a viewer decides whether to stay, and
    footage with no narration and no on-screen text says nothing to the majority who watch muted.
    It is a visual beat before the hook card, not a replacement for it.
    """
    if os.environ.get("VEO_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    seconds = int(seconds or os.environ.get("VEO_SECONDS", "4"))
    seconds = max(4, min(seconds, 8))
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "video-generation-uniyal")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    model = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-001")
    topic = str(content.get("topic") or content.get("hook") or "an online job interview")
    prompt = (
        "Vertical 9:16 cinematic documentary video for a social media reel. "
        f"Illustrate this interview situation: {topic}. "
        "A young adult Indian job candidate sits at a modest desk in an Indian home, facing a laptop "
        "during an online job interview. Natural expressions and restrained movement, warm window light, "
        "subtle handheld camera, realistic skin and surroundings, shallow depth of field. End with the "
        "candidate looking calmly focused at the laptop. No spoken dialogue, no readable text, no captions, "
        "no logos, no watermark, and no visible computer interface."
    )

    try:
        from google import genai
        from google.genai import types

        print(f"[veo] generating {seconds}s hook with {model} in {project}/{location}")
        client = genai.Client(vertexai=True, project=project, location=location)
        operation = client.models.generate_videos(
            model=model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16",
                resolution="720p",
                duration_seconds=seconds,
                number_of_videos=1,
                generate_audio=False,   # our own narration goes over the top; audio also costs far more
                person_generation="allow_adult",
            ),
        )
        deadline = time.monotonic() + 20 * 60
        while not operation.done:
            if time.monotonic() >= deadline:
                raise TimeoutError("Veo generation did not finish within 20 minutes")
            time.sleep(15)
            operation = client.operations.get(operation)
        videos = operation.response.generated_videos if operation.response else []
        if not videos:
            raise RuntimeError("Veo completed without returning a video")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        video = videos[0].video
        # On the Vertex client the bytes are already attached; client.files.download() exists
        # only on the Gemini Developer client and raises here, which silently binned a clip we
        # had already been billed for.
        data = getattr(video, "video_bytes", None)
        if data:
            out_path.write_bytes(data)
        else:
            video.save(str(out_path))
        if not out_path.exists() or out_path.stat().st_size < 10_000:
            raise RuntimeError(f"clip saved but looks empty ({out_path})")
        client.close()
        print(f"[veo] hook saved to {out_path}")
        return out_path
    except Exception as exc:  # noqa: BLE001 - the normal reel remains a deliberate fallback
        print(f"[veo] unavailable, continuing with the card reel: {type(exc).__name__}: {exc}")
        return None
