"""Slide renderer. The writer produces slide specs; this file turns them into images.

Slide types and their fields (all text supports **bold** spans, drawn in the accent colour):

  hook     title, subtitle?, tag?, kicker?
  stat     number, label, note?
  points   title, points[3..6], tag?
  qa       question, answer, tag?, label_q?, label_a?
  myth     myth, fact, tag?
  product  title, caption?, image? (logo | mascot | overlay_hinglish | overlay_english | you_see)
  cta      title?, subtitle?, show_pricing? (default true)
  quote    text, by?

Each spec may carry "theme": "light" | "dark". Sizes: FEED is 1080x1350 (4:5), REEL is 1080x1920.
"""

from __future__ import annotations

import pathlib
import re

from PIL import Image, ImageDraw, ImageFilter

from ..config import ROOT, brand
from .fonts import font

FEED = (1080, 1350)
REEL = (1080, 1920)
SQUARE = (1080, 1080)

DEFAULT_THEME = {
    "hook": "light", "stat": "dark", "points": "light", "qa": "light", "myth": "light",
    "product": "dark", "cta": "dark", "quote": "dark",
}

SCREENSHOT_CROP = {  # the overlay panel inside the 1920x1080 site screenshots
    "overlay_hinglish": (560, 60, 1360, 530),
    "overlay_english": (560, 60, 1360, 530),
    "you_see": (560, 60, 1360, 530),
}


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    return (*_rgb(value), alpha)


def clean(text) -> str:
    """Dash and whitespace hygiene for anything that lands on a slide."""
    text = "" if text is None else str(text)
    text = text.replace("—", ", ").replace("–", "-").replace("‑", "-")
    text = text.replace("Rs. ", "₹").replace("Rs ", "₹").replace("INR ", "₹")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


# ----------------------------------------------------------------------------- rich text
def _tokens(text: str) -> list[tuple[str, bool, bool]]:
    """Split on **bold** markers, then into words. Returns (word, is_bold, glue) triples;
    glue is True when the word continues the previous one without a space, which happens
    for punctuation right after a closing ** marker."""
    out: list[tuple[str, bool, bool]] = []
    bold = False
    for piece in re.split(r"(\*\*)", clean(text)):
        if piece == "**":
            bold = not bold
            continue
        first = True
        for word in piece.split(" "):
            if word:
                glue = first and bool(out) and not piece.startswith(" ") and word[0] in ",.;:!?)"
                out.append((word, bold, glue))
            first = False
    return out


class Style:
    def __init__(self, size: int, weight: str, color, bold_weight: str | None = None,
                 bold_color=None, leading: float = 1.2):
        self.size = size
        self.weight = weight
        self.color = color
        self.bold_weight = bold_weight or ("bold" if weight in ("regular", "medium") else weight)
        self.bold_color = bold_color or color
        self.leading = leading

    def with_size(self, size: int) -> "Style":
        return Style(size, self.weight, self.color, self.bold_weight, self.bold_color, self.leading)

    def font_for(self, bold: bool):
        return font(self.size, self.bold_weight if bold else self.weight)

    @property
    def line_height(self) -> int:
        return int(round(self.size * self.leading))


def _wrap(tokens, style: Style, max_w: int) -> list[list[tuple[str, bool, bool]]]:
    lines: list[list[tuple[str, bool, bool]]] = []
    line: list[tuple[str, bool, bool]] = []
    width = 0.0
    space = style.font_for(False).getlength(" ")
    for word, bold, glue in tokens:
        w = style.font_for(bold).getlength(word)
        if w > max_w:  # a single over-long token: hard-break it by characters
            if line:
                lines.append(line)
                line, width = [], 0.0
            chunk = ""
            for ch in word:
                if style.font_for(bold).getlength(chunk + ch) > max_w and chunk:
                    lines.append([(chunk, bold, False)])
                    chunk = ""
                chunk += ch
            line, width = [(chunk, bold, False)], style.font_for(bold).getlength(chunk)
            continue
        extra = w if (not line or glue) else w + space
        if line and width + extra > max_w and not glue:
            lines.append(line)
            line, width = [(word, bold, False)], w
        else:
            line.append((word, bold, glue and bool(line)))
            width += extra
    if line:
        lines.append(line)
    return lines


def _line_width(line, style: Style) -> float:
    space = style.font_for(False).getlength(" ")
    total = 0.0
    for i, (w, b, glue) in enumerate(line):
        total += style.font_for(b).getlength(w)
        if i and not glue:
            total += space
    return total


def fit(text: str, style: Style, max_w: int, max_h: int, min_size: int,
        max_lines: int | None = None) -> tuple[Style, list]:
    """Shrink the font until the wrapped block fits the box. Returns the style used and the lines."""
    tokens = _tokens(text)
    size = style.size
    while True:
        st = style.with_size(size)
        lines = _wrap(tokens, st, max_w)
        ok = len(lines) * st.line_height <= max_h and (max_lines is None or len(lines) <= max_lines)
        if ok or size <= min_size:
            return st, lines
        size -= 2


def draw_lines(draw: ImageDraw.ImageDraw, lines, style: Style, x: int, y: int,
               width: int | None = None, align: str = "left") -> int:
    space = style.font_for(False).getlength(" ")
    for line in lines:
        lw = _line_width(line, style)
        if align == "center" and width:
            cx = x + (width - lw) / 2
        elif align == "right" and width:
            cx = x + width - lw
        else:
            cx = x
        for i, (word, bold, glue) in enumerate(line):
            f = style.font_for(bold)
            if i and not glue:
                cx += space
            draw.text((cx, y), word, font=f, fill=style.bold_color if bold else style.color)
            cx += f.getlength(word)
        y += style.line_height
    return y


def block_height(lines, style: Style) -> int:
    return len(lines) * style.line_height


# ----------------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, size: tuple[int, int], theme: str = "light"):
        self.w, self.h = size
        self.theme_name = theme
        cfg = brand()
        self.brand = cfg
        self.c = cfg["colors"][theme]
        self.img = Image.new("RGB", size, _rgb(self.c["bg"]))
        self.d = ImageDraw.Draw(self.img)
        # When a list is attached, step() snapshots the canvas just before each
        # revealable element is drawn. One render pass therefore yields every
        # intermediate stage with byte-identical layout, which re-rendering at
        # different "reveal" levels could not guarantee.
        self.capture: list | None = None
        self.reel = self.h >= 1700
        self.m = 84
        self.cw = self.w - 2 * self.m
        if self.reel:
            self.header_y, self.top, self.bottom, self.footer_y = 236, 350, self.h - 420, self.h - 330
        else:
            self.header_y, self.top, self.bottom, self.footer_y = 72, 214, self.h - 176, self.h - 118

    def step(self) -> None:
        """Mark the start of a revealable element. No effect unless capturing."""
        if self.capture is not None:
            self.capture.append(self.img.copy())

    # -- primitives --------------------------------------------------------
    def decor(self) -> None:
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        a1, a2 = (70, 40) if self.theme_name == "light" else (95, 60)
        r = int(self.w * 0.42)
        ld.ellipse([self.w - r, -r // 2, self.w + r // 2, r], fill=_rgba(self.c["accent"], a1))
        ld.ellipse([-r // 2, self.h - r, r, self.h + r // 2], fill=_rgba(self.c["accent2"], a2))
        layer = layer.filter(ImageFilter.GaussianBlur(170))
        self.img.paste(Image.alpha_composite(self.img.convert("RGBA"), layer).convert("RGB"))
        self.d = ImageDraw.Draw(self.img)

    def pill(self, text: str, x: int, y: int, fill: str, color: str, size: int = 24,
             pad_x: int = 22, pad_y: int = 12, align_right: bool = False) -> tuple[int, int]:
        f = font(size, "semibold")
        text = clean(text).upper()
        tw = f.getlength(text)
        w, h = int(tw + 2 * pad_x), int(size + 2 * pad_y)
        if align_right:
            x = x - w
        self.d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=_rgb(fill))
        self.d.text((x + pad_x, y + pad_y - size * 0.12), text, font=f, fill=_rgb(color))
        return w, h

    def card(self, box, radius: int = 28, fill: str | None = None, outline: str | None = None,
             shadow: bool = True, width: int = 2) -> None:
        x0, y0, x1, y1 = box
        if shadow:
            sh = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 14, x1, y1 + 14], radius=radius,
                                                 fill=(15, 23, 42, 46 if self.theme_name == "light" else 110))
            sh = sh.filter(ImageFilter.GaussianBlur(22))
            self.img.paste(Image.alpha_composite(self.img.convert("RGBA"), sh).convert("RGB"))
            self.d = ImageDraw.Draw(self.img)
        self.d.rounded_rectangle(box, radius=radius, fill=_rgb(fill or self.c["card"]),
                                 outline=_rgb(outline or self.c["line"]), width=width)

    def paste_rounded(self, image: Image.Image, box, radius: int = 24) -> None:
        x0, y0, x1, y1 = box
        target = image.convert("RGB").resize((x1 - x0, y1 - y0), Image.LANCZOS)
        mask = Image.new("L", target.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, target.width - 1, target.height - 1], radius=radius, fill=255)
        self.img.paste(target, (x0, y0), mask)

    def header(self, tag: str | None = None) -> None:
        y = self.header_y
        logo = Image.open(ROOT / self.brand["images"]["logo"]).convert("RGBA").resize((64, 64), Image.LANCZOS)
        self.img.paste(logo, (self.m, y), logo)
        self.d.text((self.m + 82, y + 11), self.brand["name"], font=font(34, "semibold"), fill=_rgb(self.c["text"]))
        if tag:
            fill = self.c["bubble"] if self.theme_name == "light" else self.c["card"]
            self.pill(tag[:26], self.w - self.m, y + 10, fill, self.c["accent"], align_right=True)

    def footer(self, index: int | None = None, total: int | None = None, hint: str | None = None) -> None:
        y = self.footer_y
        self.d.line([(self.m, y - 26), (self.w - self.m, y - 26)], fill=_rgb(self.c["line"]), width=2)
        self.d.text((self.m, y), "interviewsarthi.com", font=font(28, "semibold"), fill=_rgb(self.c["accent"]))
        right = ""
        if index is not None and total and total > 1:
            right = f"{index}/{total}" if not hint else f"{hint}  {index}/{total}"
        elif hint:
            right = hint
        else:
            right = self.brand["handles"].get("instagram", "")
        if right:
            f = font(28, "medium")
            self.d.text((self.w - self.m - f.getlength(right), y), right, font=f, fill=_rgb(self.c["muted"]))

    def text_block(self, text: str, box, style: Style, min_size: int, align: str = "left",
                   valign: str = "top", max_lines: int | None = None) -> int:
        x, y, w, h = box
        st, lines = fit(text, style, w, h, min_size, max_lines)
        bh = block_height(lines, st)
        if valign == "middle":
            y = y + (h - bh) // 2
        elif valign == "bottom":
            y = y + h - bh
        return draw_lines(self.d, lines, st, x, y, w, align)

    def save(self, path: pathlib.Path) -> pathlib.Path:
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in (".jpg", ".jpeg"):
            self.img.save(path, "JPEG", quality=92, optimize=True)
        else:
            self.img.save(path, "PNG", optimize=True)
        return path


# ----------------------------------------------------------------------------- slide types
def _style(cv: Canvas, size: int, weight: str, color_key: str, bold_color_key: str = "accent",
           leading: float = 1.2) -> Style:
    return Style(size, weight, _rgb(cv.c[color_key]), None, _rgb(cv.c[bold_color_key]), leading)


def slide_hook(cv: Canvas, s: dict) -> None:
    y = cv.top + (40 if cv.reel else 24)
    cv.step()
    if s.get("kicker"):
        cv.d.text((cv.m, y), clean(s["kicker"]).upper(), font=font(26, "semibold"), fill=_rgb(cv.c["accent"]))
        y += 58
    sub = clean(s.get("subtitle", ""))
    sub_h = 0
    sub_style = _style(cv, 38 if cv.reel else 36, "regular", "muted", leading=1.3)
    if sub:
        sub_st, sub_lines = fit(sub, sub_style, cv.cw, 4 * sub_style.line_height, 28, 4)
        sub_h = block_height(sub_lines, sub_st) + 36
    avail = cv.bottom - y - sub_h
    title_style = _style(cv, 84 if cv.reel else 76, "bold", "text", leading=1.12)
    st, lines = fit(clean(s.get("title", "")), title_style, cv.cw, avail, 46, 6)
    th = block_height(lines, st)
    # sit the title block a little above centre; it reads better than dead centre
    ty = y + max(0, (avail - th) // 2 - (60 if cv.reel else 30))
    y_end = draw_lines(cv.d, lines, st, cv.m, ty)
    if sub:
        cv.step()
        cv.d.rounded_rectangle([cv.m, y_end + 18, cv.m + 120, y_end + 26], radius=4, fill=_rgb(cv.c["accent"]))
        draw_lines(cv.d, sub_lines, sub_st, cv.m, y_end + 48)


def slide_stat(cv: Canvas, s: dict) -> None:
    number = clean(s.get("number", ""))
    label = clean(s.get("label", ""))
    note = clean(s.get("note", ""))
    num_style = _style(cv, 170 if cv.reel else 150, "black", "accent", leading=1.0)
    st, lines = fit(number, num_style, cv.cw, 360, 90, 2)
    lab_style = _style(cv, 50 if cv.reel else 46, "semibold", "text", leading=1.2)
    lst, llines = fit(label, lab_style, cv.cw, 4 * lab_style.line_height, 32, 4)
    note_style = _style(cv, 32, "regular", "muted", leading=1.3)
    nst, nlines = fit(note, note_style, cv.cw, 3 * note_style.line_height, 26, 3) if note else (note_style, [])
    total = block_height(lines, st) + 24 + block_height(llines, lst) + (30 + block_height(nlines, nst) if note else 0)
    y = cv.top + max(0, (cv.bottom - cv.top - total) // 2)
    cv.step()
    y = draw_lines(cv.d, lines, st, cv.m, y, cv.cw, "center") + 24
    cv.step()
    y = draw_lines(cv.d, llines, lst, cv.m, y, cv.cw, "center")
    if note:
        cv.step()
        draw_lines(cv.d, nlines, nst, cv.m, y + 30, cv.cw, "center")


def slide_points(cv: Canvas, s: dict) -> None:
    points = [clean(p) for p in (s.get("points") or []) if clean(p)][:6]
    title_style = _style(cv, 60 if cv.reel else 56, "bold", "text", leading=1.14)
    tst, tlines = fit(clean(s.get("title", "")), title_style, cv.cw, 3 * title_style.line_height, 40, 3)
    y = cv.top + 12
    cv.step()
    y = draw_lines(cv.d, tlines, tst, cv.m, y) + 40
    avail = cv.bottom - y
    size = 38 if cv.reel else 34
    while True:
        st = _style(cv, size, "medium", "text", leading=1.25)
        rows = []
        for p in points:
            lines = _wrap(_tokens(p), st, cv.cw - 150)
            rows.append((lines, max(84, block_height(lines, st) + 40)))
        total = sum(h for _, h in rows) + 18 * (len(rows) - 1)
        if total <= avail or size <= 24:
            break
        size -= 2
    if cv.reel and total < avail:
        y += min((avail - total) // 2, 140)
    for i, (lines, h) in enumerate(rows, 1):
        cv.step()
        cv.card([cv.m, y, cv.w - cv.m, y + h], radius=22)
        cx, cy = cv.m + 34, y + h // 2
        cv.d.ellipse([cx, cy - 28, cx + 56, cy + 28], fill=_rgb(cv.c["accent"]))
        nf = font(28, "bold")
        cv.d.text((cx + 28 - nf.getlength(str(i)) / 2, cy - 19), str(i), font=nf, fill=(255, 255, 255))
        ty = y + (h - block_height(lines, st)) // 2 - 2
        draw_lines(cv.d, lines, st, cv.m + 118, ty)
        y += h + 18


def slide_qa(cv: Canvas, s: dict) -> None:
    question = clean(s.get("question", ""))
    answer = clean(s.get("answer", ""))
    label_q = clean(s.get("label_q") or "Interviewer asked").upper()
    label_a = clean(s.get("label_a") or "Say this").upper()
    q_size, a_size = (48, 40) if cv.reel else (44, 37)
    avail = cv.bottom - cv.top
    pad = 40
    while True:
        qst = Style(q_size, "semibold", _rgb(cv.c["bubble_text"]), "bold", _rgb(cv.c["bubble_text"]), 1.22)
        ast = _style(cv, a_size, "regular", "text", leading=1.32)
        qlines = _wrap(_tokens(question), qst, cv.cw - 2 * pad)
        alines = _wrap(_tokens(answer), ast, cv.cw - 2 * pad - 10)
        qh = block_height(qlines, qst) + 2 * pad - 8
        ah = block_height(alines, ast) + 2 * pad
        total = 44 + qh + 44 + 44 + ah
        if total <= avail or a_size <= 26:
            break
        q_size = max(30, q_size - 2)
        a_size -= 2
    y = cv.top + max(0, (avail - total) // 2)
    cv.step()
    cv.d.text((cv.m, y), label_q, font=font(24, "semibold"), fill=_rgb(cv.c["muted"]))
    y += 44
    cv.d.rounded_rectangle([cv.m, y, cv.w - cv.m, y + qh], radius=30, fill=_rgb(cv.c["bubble"]))
    draw_lines(cv.d, qlines, qst, cv.m + pad, y + pad - 8)
    y += qh + 44
    cv.step()
    cv.d.ellipse([cv.m, y + 4, cv.m + 18, y + 22], fill=_rgb(cv.c["accent"]))
    cv.d.text((cv.m + 32, y), label_a, font=font(24, "semibold"), fill=_rgb(cv.c["accent"]))
    y += 44
    cv.card([cv.m, y, cv.w - cv.m, y + ah], radius=30)
    cv.d.rounded_rectangle([cv.m + 2, y + 34, cv.m + 12, y + ah - 34], radius=5, fill=_rgb(cv.c["accent"]))
    draw_lines(cv.d, alines, ast, cv.m + pad + 10, y + pad - 4)


def slide_myth(cv: Canvas, s: dict) -> None:
    myth = clean(s.get("myth", ""))
    fact = clean(s.get("fact", ""))
    size = 44 if cv.reel else 40
    pad = 40
    avail = cv.bottom - cv.top
    while True:
        mst = Style(size, "medium", _rgb(cv.c["muted"]), "semibold", _rgb(cv.c["muted"]), 1.28)
        fst = _style(cv, size, "semibold", "text", leading=1.28)
        mlines = _wrap(_tokens(myth), mst, cv.cw - 2 * pad)
        flines = _wrap(_tokens(fact), fst, cv.cw - 2 * pad)
        mh = block_height(mlines, mst) + 2 * pad + 60
        fh = block_height(flines, fst) + 2 * pad + 60
        total = mh + 40 + fh
        if total <= avail or size <= 26:
            break
        size -= 2
    y = cv.top + max(0, (avail - total) // 2)
    cv.card([cv.m, y, cv.w - cv.m, y + mh], radius=30, fill=cv.c["bg2"])
    cv.pill("Myth", cv.m + pad, y + pad - 6, cv.c["danger_bg"], cv.c["danger"])
    draw_lines(cv.d, mlines, mst, cv.m + pad, y + pad + 56)
    # a strike through the myth headline colour, drawn as a thin line under the label row
    y += mh + 40
    cv.card([cv.m, y, cv.w - cv.m, y + fh], radius=30)
    cv.pill("Fact", cv.m + pad, y + pad - 6, cv.c["ok_bg"], cv.c["ok"])
    draw_lines(cv.d, flines, fst, cv.m + pad, y + pad + 56)


def slide_product(cv: Canvas, s: dict) -> None:
    key = s.get("image") or "overlay_hinglish"
    images = cv.brand["images"]
    path = ROOT / images.get(key, images["overlay_hinglish"])
    title_style = _style(cv, 58 if cv.reel else 54, "bold", "text", leading=1.14)
    tst, tlines = fit(clean(s.get("title", "")), title_style, cv.cw, 3 * title_style.line_height, 38, 3)
    y = cv.top + (110 if cv.reel else 12)
    y = draw_lines(cv.d, tlines, tst, cv.m, y) + 36
    caption = clean(s.get("caption", ""))
    cap_style = _style(cv, 34 if cv.reel else 32, "regular", "muted", leading=1.3)
    cst, clines = fit(caption, cap_style, cv.cw, 3 * cap_style.line_height, 26, 3) if caption else (cap_style, [])
    cap_h = (block_height(clines, cst) + 30) if caption else 0
    img = Image.open(path).convert("RGBA")
    if key in SCREENSHOT_CROP and s.get("crop", "overlay") == "overlay":
        img = img.crop(SCREENSHOT_CROP[key])
    max_h = cv.bottom - y - cap_h
    if key in ("logo", "mascot"):
        side = min(cv.cw, max_h, 560)
        bg = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bg.alpha_composite(img)
        flat = Image.new("RGB", img.size, _rgb(cv.c["card"]))
        flat.paste(bg, (0, 0), bg)
        box = [cv.w // 2 - side // 2, y, cv.w // 2 + side // 2, y + side]
        cv.card(box, radius=40)
        inner = [box[0] + 40, box[1] + 40, box[2] - 40, box[3] - 40]
        cv.paste_rounded(flat, inner, radius=24)
        y = box[3] + 30
    else:
        ratio = img.height / img.width
        w = cv.cw
        h = int(w * ratio)
        if h > max_h:
            h = max_h
            w = int(h / ratio)
        x0 = cv.w // 2 - w // 2
        cv.card([x0 - 8, y - 8, x0 + w + 8, y + h + 8], radius=30)
        cv.paste_rounded(img, [x0, y, x0 + w, y + h], radius=22)
        y += h + 34
    if caption:
        draw_lines(cv.d, clines, cst, cv.m, y, cv.cw, "center")


def slide_cta(cv: Canvas, s: dict) -> None:
    logo = Image.open(ROOT / cv.brand["images"]["logo"]).convert("RGBA")
    side = 128 if cv.reel else 112
    logo = logo.resize((side, side), Image.LANCZOS)
    y = cv.top + (30 if cv.reel else 8)
    cv.img.paste(logo, (cv.w // 2 - side // 2, y), logo)
    y += side + 30
    title = clean(s.get("title") or "30 minutes free. No card.")
    tst, tlines = fit(title, _style(cv, 66 if cv.reel else 60, "bold", "text", leading=1.12), cv.cw, 3 * 72, 40, 3)
    y = draw_lines(cv.d, tlines, tst, cv.m, y, cv.cw, "center") + 16
    subtitle = clean(s.get("subtitle") or "Then a one-time pass in rupees. Nothing renews.")
    sst, slines = fit(subtitle, _style(cv, 34, "regular", "muted", leading=1.3), cv.cw, 3 * 44, 26, 3)
    y = draw_lines(cv.d, slines, sst, cv.m, y, cv.cw, "center") + 40
    if s.get("show_pricing", True):
        rows = cv.brand["pricing"]
        row_h = 92 if cv.reel else 84
        gap = 16
        space = cv.bottom - y - 120
        max_rows = max(2, min(len(rows), (space + gap) // (row_h + gap)))
        for row in rows[:max_rows]:
            cv.card([cv.m, y, cv.w - cv.m, y + row_h], radius=20, shadow=False)
            cv.d.text((cv.m + 30, y + row_h // 2 - 20), row["label"], font=font(32, "semibold"), fill=_rgb(cv.c["text"]))
            nf = font(24, "regular")
            cv.d.text((cv.m + 30, y + row_h // 2 + 14), row["note"], font=nf, fill=_rgb(cv.c["muted"]))
            pf = font(38, "bold")
            price = row["price"]
            cv.d.text((cv.w - cv.m - 30 - pf.getlength(price), y + row_h // 2 - 24), price, font=pf,
                      fill=_rgb(cv.c["accent"]))
            y += row_h + gap
        y += 18
    note = clean(s.get("note") or "7-day money-back on the first pass. Windows 10 and 11.")
    nst, nlines = fit(note, _style(cv, 28, "medium", "muted", leading=1.3), cv.cw, 2 * 38, 22, 2)
    draw_lines(cv.d, nlines, nst, cv.m, min(y, cv.bottom - block_height(nlines, nst)), cv.cw, "center")


def slide_quote(cv: Canvas, s: dict) -> None:
    text = clean(s.get("text", ""))
    by = clean(s.get("by", ""))
    qf = font(220, "black")
    cv.d.text((cv.m - 10, cv.top - 40), "“", font=qf, fill=_rgb(cv.c["accent"]))
    avail = cv.bottom - cv.top - 200
    st, lines = fit(text, _style(cv, 66 if cv.reel else 60, "semibold", "text", leading=1.2), cv.cw, avail, 36, 8)
    y = cv.top + 150 + max(0, (avail - block_height(lines, st)) // 2 - 40)
    y = draw_lines(cv.d, lines, st, cv.m, y) + 30
    if by:
        cv.d.text((cv.m, y), clean(by), font=font(30, "medium"), fill=_rgb(cv.c["muted"]))


RENDERERS = {
    "hook": slide_hook, "stat": slide_stat, "points": slide_points, "qa": slide_qa,
    "myth": slide_myth, "product": slide_product, "cta": slide_cta, "quote": slide_quote,
}


def _build(spec: dict, size: tuple[int, int], index: int, total: int,
           capture: list | None = None) -> Canvas:
    kind = spec.get("type", "hook")
    if kind not in RENDERERS:
        kind = "hook"
    theme = spec.get("theme") or DEFAULT_THEME[kind]
    if theme not in ("light", "dark"):
        theme = "light"
    cv = Canvas(size, theme)
    cv.decor()
    cv.header(spec.get("tag"))
    # Footer before the content, so every captured stage already carries it and
    # nothing pops in at the end of the animation.
    hint = "Swipe" if (index == 1 and total > 1 and not cv.reel) else None
    cv.footer(index, total, hint)
    cv.capture = capture
    RENDERERS[kind](cv, spec)
    return cv


def render_slide(spec: dict, size: tuple[int, int], index: int, total: int) -> Image.Image:
    return _build(spec, size, index, total).img


def render_stages(spec: dict, size: tuple[int, int], index: int, total: int) -> list[Image.Image]:
    """The slide as it builds up: one image per revealable element, last one complete.

    A renderer that marks no steps simply yields the finished slide, so formats that
    should not animate keep working untouched.
    """
    snapshots: list[Image.Image] = []
    cv = _build(spec, size, index, total, capture=snapshots)
    return snapshots[1:] + [cv.img] if snapshots else [cv.img]


def render_slides(slides: list[dict], size: tuple[int, int], out_dir: pathlib.Path,
                  prefix: str = "slide", ext: str = "jpg") -> list[pathlib.Path]:
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    total = len(slides)
    for i, spec in enumerate(slides, 1):
        img = render_slide(spec, size, i, total)
        path = out_dir / f"{prefix}-{i:02d}.{ext}"
        if ext in ("jpg", "jpeg"):
            img.save(path, "JPEG", quality=92, optimize=True)
        else:
            img.save(path, "PNG", optimize=True)
        paths.append(path)
    return paths
