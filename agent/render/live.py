"""The app, live over the footage: the question lands, then the answer drafts in.

These layers are what a muted viewer reads, and most viewers are muted. Beat 1 carries the
interviewer's question as the transcript line the app shows. Beat 2 carries the Interview Sarthi
panel with the answer arriving one sentence at a time, the way the real overlay drafts it.

Each element is rendered on its own transparent 1080x1920 layer, so the film assembler can fade
it in at its own moment with ffmpeg instead of decoding the footage in Python. Layers are deltas:
a layer holds only the element that appears at that moment, never what was already on screen.

Everything sits inside the Reels safe zone: clear of the top bar, the caption band Instagram
draws over the lowest 380 px or so, and the action icons down the right edge.
"""

from __future__ import annotations

import pathlib
import re

from PIL import Image, ImageDraw, ImageFilter

from ..config import brand
from .cards import Style, _rgb, _tokens, _wrap, block_height, clean, draw_lines
from .fonts import font

W, H = 1080, 1920
M = 72                     # side margin
PANEL_BOTTOM = 1520        # lowest pixel any panel reaches
PANEL_TOP_MIN = 700        # the panel never climbs above this, so the face stays in view
GLASS = (13, 19, 33, 228)  # the app's dark surface, slightly translucent over footage
GLASS_LINE = (60, 72, 100, 255)
WHITE = (255, 255, 255)
MUTED = (160, 172, 194)


def sentences(answer: str) -> list[str]:
    """The answer as the app shows it: one sentence per line. **bold** spans survive the split."""
    text = clean(answer)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    out: list[str] = []
    open_bold = False
    for part in parts:
        if open_bold:
            part = "**" + part
        open_bold = (part.count("**") % 2) == 1
        if open_bold:
            part = part + "**"
        out.append(part)
    return out


def _layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _shadowed_box(img: Image.Image, box, radius: int, fill, outline=None) -> None:
    """A rounded glass box with a soft drop shadow, composited onto a transparent layer."""
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0, y0 + 16, x1, y1 + 16], radius=radius, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    img.alpha_composite(shadow)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 0)


def _accent() -> tuple[int, int, int]:
    return _rgb(brand()["colors"]["dark"]["accent"])


# ----------------------------------------------------------------------------- beat 1
def question_layers(question: str, out_dir: pathlib.Path, tag: str = "q") -> list[tuple[pathlib.Path, float]]:
    """The interviewer's line as the app's live transcript. Returns [(png, seconds after beat start)]."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    question = clean(question)
    pad = 44
    style = Style(50, "semibold", WHITE, "bold", WHITE, 1.24)
    while True:
        lines = _wrap(_tokens(question), style, W - 2 * M - 2 * pad)
        if len(lines) <= 4 or style.size <= 34:
            break
        style = style.with_size(style.size - 2)
    bubble_h = block_height(lines, style) + 2 * pad - 6
    bubble_bottom = 1400
    bubble_top = bubble_bottom - bubble_h
    label_y = bubble_top - 70

    # layer 1: the transcript label
    img, d = _layer()
    f = font(26, "semibold")
    text = "INTERVIEWER"
    tw = int(f.getlength(text))
    pill = [M, label_y, M + tw + 74, label_y + 50]
    d.rounded_rectangle(pill, radius=25, fill=(13, 19, 33, 210))
    d.ellipse([M + 22, label_y + 18, M + 36, label_y + 32], fill=(239, 68, 68, 255))
    d.text((M + 48, label_y + 9), text, font=f, fill=WHITE)
    lf = font(26, "medium")
    d.text((pill[2] + 18, label_y + 9), "live transcript", font=lf, fill=(235, 238, 245, 230))
    label = out_dir / f"{tag}-01-label.png"
    img.save(label)

    # layer 2: the question itself
    img, d = _layer()
    _shadowed_box(img, [M, bubble_top, W - M, bubble_bottom], 34, GLASS, GLASS_LINE)
    d = ImageDraw.Draw(img)
    draw_lines(d, lines, style, M + pad, bubble_top + pad - 10)
    bubble = out_dir / f"{tag}-02-question.png"
    img.save(bubble)
    return [(label, 0.55), (bubble, 0.85)]


# ----------------------------------------------------------------------------- beat 2
def answer_layers(answer: str, seconds: float, out_dir: pathlib.Path, tag: str = "a",
                  language: str = "english") -> list[tuple[pathlib.Path, float]]:
    """The Interview Sarthi panel drafting the answer, one sentence per layer.

    The panel frame arrives first, then each sentence at an even gap, all of them on screen by
    about three quarters of the beat so the viewer gets a moment with the finished answer.
    """
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    accent = _accent()
    lines_text = sentences(answer) or [clean(answer)]
    pad = 44
    inner_w = W - 2 * M - 2 * pad
    header_h = 60
    label_h = 46
    gap = 14
    size = 40
    while True:
        style = Style(size, "regular", WHITE, "semibold", accent, 1.3)
        wrapped = [_wrap(_tokens(s), style, inner_w) for s in lines_text]
        body_h = sum(block_height(ls, style) for ls in wrapped) + gap * (len(wrapped) - 1)
        panel_h = pad + header_h + 22 + label_h + body_h + pad
        if PANEL_BOTTOM - panel_h >= PANEL_TOP_MIN or size <= 28:
            break
        size -= 2
    top = PANEL_BOTTOM - panel_h

    # layer 1: the panel with its header and the SAY THIS label
    img, d = _layer()
    _shadowed_box(img, [M, top, W - M, PANEL_BOTTOM], 36, GLASS, GLASS_LINE)
    d = ImageDraw.Draw(img)
    y = top + pad
    d.ellipse([M + pad, y + 18, M + pad + 18, y + 36], fill=accent)
    nf = font(34, "semibold")
    d.text((M + pad + 34, y + 6), brand()["name"], font=nf, fill=WHITE)
    mf = font(26, "medium")
    lang = {"hinglish": "HI + EN", "hindi": "HI"}.get(str(language).lower(), "EN")
    d.text((M + pad + 34 + nf.getlength(brand()["name"]) + 22, y + 14), f"listening  ·  {lang}", font=mf, fill=MUTED)
    y += header_h
    d.line([(M + pad, y), (W - M - pad, y)], fill=GLASS_LINE, width=2)
    y += 22
    d.text((M + pad, y + 8), "S A Y   T H I S", font=font(24, "semibold"), fill=accent)
    d.rounded_rectangle([M + 14, y + label_h + 6, M + 22, PANEL_BOTTOM - pad], radius=4, fill=(*accent, 255))
    frame = out_dir / f"{tag}-01-panel.png"
    img.save(frame)
    layers: list[tuple[pathlib.Path, float]] = [(frame, 0.3)]

    # one layer per sentence
    y += label_h
    n = len(wrapped)
    first, last_by = 0.95, max(seconds * 0.72, 2.0)
    step = (last_by - first) / max(n - 1, 1) if n > 1 else 0.0
    step = min(step, 1.15)
    for i, ls in enumerate(wrapped):
        img, d = _layer()
        draw_lines(d, ls, style, M + pad, y)
        y += block_height(ls, style) + gap
        path = out_dir / f"{tag}-{i + 2:02d}-line.png"
        img.save(path)
        layers.append((path, round(first + i * step, 2)))
    return layers
