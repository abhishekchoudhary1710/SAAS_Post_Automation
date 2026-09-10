"""Turn a slide's reveal stages into a frame sequence.

The old reel was a finished card with a slow zoom over it, which is why it looked like a
slideshow. Here each element arrives in turn: the question appears, then the answer; the
title, then each point. That mirrors what the app itself does on screen, so the motion
explains the product rather than decorating it.

Only the region that actually changed between two stages is animated. Everything already
on screen stays perfectly still, which is what makes it read as an interface rather than a
crossfade. The changed region is found by differencing the two stages, so no renderer has
to report its own geometry.
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageChops

SHIFT = 26          # pixels a new element rises as it fades in
TRANSITION = 0.28   # seconds
QUALITY = 88


def _ease_out(t: float) -> float:
    """Cubic ease-out: fast arrival, gentle settle."""
    return 1.0 - (1.0 - t) ** 3


def _changed_box(before: Image.Image, after: Image.Image):
    box = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox()
    if box is None:
        return None
    # a little margin so anti-aliased edges are not clipped as the region moves
    left, top, right, bottom = box
    return (max(left - 2, 0), max(top - 2, 0),
            min(right + 2, after.width), min(bottom + 2, after.height))


def _blend(before: Image.Image, after: Image.Image, box, t: float) -> Image.Image:
    """`after` differs from `before` by one element; bring just that element in."""
    if box is None:
        return after if t >= 1.0 else before
    eased = _ease_out(t)
    frame = before.copy()
    shifted = frame.copy()
    shifted.paste(after.crop(box), (box[0], box[1] - int(round((1.0 - eased) * SHIFT))))
    return Image.blend(frame, shifted, eased)


def stage_starts(count: int, frames: int) -> list[int]:
    """Frame index at which each stage begins, spread evenly across the slide."""
    return [round(k * frames / count) for k in range(count)]


def write_frames(stages: list[Image.Image], seconds: float, fps: int,
                 out_dir: pathlib.Path, prefix: str = "f") -> int:
    """Write the slide as JPEGs named prefix-00001.jpg upward. Returns the frame count."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = max(int(round(seconds * fps)), 1)
    starts = stage_starts(len(stages), total)
    boxes = [None] + [_changed_box(stages[k - 1], stages[k]) for k in range(1, len(stages))]
    trans = max(int(round(TRANSITION * fps)), 3)

    # Encode each still once and reuse the bytes; most frames in a slide are identical,
    # and re-encoding a 1080x1920 JPEG 30 times a second is pure waste.
    cache: dict[int, bytes] = {}

    def still_bytes(index: int) -> bytes:
        if index not in cache:
            buf = out_dir / f".{prefix}-still-{index}.jpg"
            stages[index].save(buf, "JPEG", quality=QUALITY, optimize=False)
            cache[index] = buf.read_bytes()
            buf.unlink()
        return cache[index]

    for i in range(total):
        stage = 0
        for k, start in enumerate(starts):
            if i >= start:
                stage = k
        path = out_dir / f"{prefix}-{i + 1:05d}.jpg"
        local = i - starts[stage]
        if stage > 0 and local < trans:
            t = (local + 1) / float(trans)
            _blend(stages[stage - 1], stages[stage], boxes[stage], t).save(
                path, "JPEG", quality=QUALITY, optimize=False)
        else:
            path.write_bytes(still_bytes(stage))
    return total
