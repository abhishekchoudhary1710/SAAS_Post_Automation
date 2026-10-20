"""The daily demo reel: Interview Sarthi shown doing its job, live, inside an online interview.

Everything on screen is rendered here, nothing comes from a video model, so the reel looks the
same every day and every word on it is exact. The scene is a phone-shaped cut of what the
candidate sees on their Windows laptop: the call window with the interviewer's tile, and the
Interview Sarthi panel floating over it. One continuous shot in three phases, then the price card:

  1. headline   the day's title fades in over the call; the panel is listening
  2. question   the interviewer's audio bars move and the question types into the transcript
  3. answer     a short drafting pause, then the answer arrives one sentence at a time
  4. price      the usual price card, so every post ends the same way

The narration is four lines, one per phase, voiced by the usual engines (Chirp, Gemini, Edge).
Most viewers are muted: the headline and the panel carry the pitch without sound.
"""

from __future__ import annotations

import math
import pathlib
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

from ..config import ROOT, brand, now_ist
from .cards import REEL, Style, _tokens, _wrap, block_height, clean, draw_lines, fit
from .film import COLOR_TAGS, FPS, TAIL, TO_TV, _card_segment, _run, probe
from .fonts import font
from .tts import synthesize_batch

W, H = REEL
QUALITY = 88

# The call window and the panel, in the app's own dark palette.
MEET_BG = (24, 28, 42)
TILE = (43, 52, 80)
TILE_EDGE = (58, 68, 100)
PANEL = (13, 19, 34)
PANEL_EDGE = (40, 50, 76)
BOX = (17, 24, 42)
BOX_EDGE = (31, 42, 68)
CARD = (15, 26, 31)
CARD_EDGE = (29, 52, 50)
TEXT = (229, 231, 235)
SOFT = (203, 213, 225)
MUTED = (110, 126, 150)
BLUE = (96, 165, 250)
LIGHT_BLUE = (147, 197, 253)
CORAL = (232, 115, 90)
GREEN = (52, 211, 153)
RED = (220, 60, 60)
WHITE = (255, 255, 255)

M = 60                                   # side margin of the call window
TILE_BOX = (M, 140, W - M, 740)
PANEL_BOX = (M, 700, W - M, 1640)
PAD = 36
AVATAR = (300, 560, 66)                  # centre x, centre y, radius
WAVE_X, WAVE_Y, WAVE_BARS = 400, 600, 22

HEADLINE_FADE = 0.6
REVEAL_MAX = 3.0                         # seconds the question takes to type, at most
DRAFTING = 1.3                           # the pause before the answer, about what the app takes
SENTENCE_GAP = 0.42
SENTENCE_RISE = 0.34
HOLD = 1.8                               # seconds the finished answer stays before the price card


def _ease(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _spaced(d: ImageDraw.ImageDraw, xy, text: str, f, fill, spacing: int = 3) -> None:
    """Small caps labels with a little letter spacing, which Pillow cannot do on its own."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + spacing


def sentences_of(answer: str) -> list[str]:
    """Each sentence on its own line, as the app shows it. **bold** spans are kept balanced."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", clean(answer)) if p.strip()]
    out: list[str] = []
    carry = False
    for part in parts:
        if carry:
            part = "**" + part
        carry = part.count("**") % 2 == 1
        if carry:
            part += "**"
        out.append(part)
    return out


@dataclass
class Timeline:
    q0: float        # the question starts typing
    reveal: float    # how long it types for
    a0: float        # the drafting pause starts
    total: float     # end of the demo shot (the price card follows)


def plan_timeline(durations: list[float], sentence_count: int, max_seconds: float) -> Timeline:
    """Phase lengths from the narration, with floors so the picture is never rushed."""
    hook, question, answer = (durations + [0.0, 0.0, 0.0])[:3]
    q0 = max(hook + 0.5, 3.0)
    reveal = min(REVEAL_MAX, max(1.6, question - 0.6))
    q_len = max(question + TAIL + 0.3, reveal + 1.0)
    a0 = q0 + q_len
    animation = DRAFTING + SENTENCE_GAP * sentence_count + SENTENCE_RISE
    a_len = max(answer + TAIL, animation + HOLD)
    if a0 + a_len > max_seconds:
        a_len = max(answer + TAIL, animation + 0.6, max_seconds - a0)
    return Timeline(q0=q0, reveal=reveal, a0=a0, total=a0 + a_len)


class Scene:
    """Draws any instant of the demo shot. The static picture is built once; each frame copies it."""

    def __init__(self, content: dict):
        demo = content.get("demo") or {}
        qa = next(s for s in content["slides"] if s.get("type") == "qa")
        self.headline = clean(demo.get("headline") or content.get("hook") or "")
        self.app = clean(demo.get("app") or "Google Meet")
        self.round = clean(demo.get("round") or qa.get("tag") or "Interview")
        self.interviewer = clean(demo.get("interviewer") or "Rohit").split(" ")[0] or "Rohit"
        self.question = clean(qa.get("question") or "")
        self.sentences = sentences_of(qa.get("answer") or "")
        self.stamp = now_ist().strftime("%H:%M")
        self.site = brand()["site"].replace("https://", "").replace("http://", "").rstrip("/")
        self._layout()
        self.base = self._background()

    # ------------------------------------------------------------------ layout
    def _layout(self) -> None:
        x0, y0, x1, y1 = PANEL_BOX
        inner = x1 - x0 - 2 * PAD
        self.px = x0 + PAD
        self.header_y = y0 + 30
        self.conv_label_y = y0 + 96
        box_top = self.conv_label_y + 34
        # the question: up to three lines, shrinking if it must
        q_style = Style(32, "regular", TEXT, "semibold", TEXT, 1.32)
        self.q_style, self.q_lines = fit(self.question, q_style, inner - 2 * 28, 3 * 42, 26, 3)
        q_h = 28 + 34 + block_height(self.q_lines, self.q_style) + 26
        self.conv_box = (x0 + PAD, box_top, x1 - PAD, box_top + q_h)
        self.say_label_y = self.conv_box[3] + 28
        self.card_box = (x0 + PAD, self.say_label_y + 34, x1 - PAD, y1 - PAD)
        # the answer: every sentence on its own line, all of it fitting the card
        c_pad = 28
        avail = (self.card_box[3] - self.card_box[1]) - 2 * c_pad - 40 - 12 - 38
        size = 34
        while True:
            style = Style(size, "regular", SOFT, "semibold", LIGHT_BLUE, 1.3)
            rows = [_wrap(_tokens(s), style, inner - 2 * c_pad - 14) for s in self.sentences]
            total = sum(block_height(r, style) for r in rows) + 10 * max(len(rows) - 1, 0)
            if total <= avail or size <= 24:
                break
            size -= 2
        self.a_style = style
        self.a_rows = rows
        self.c_pad = c_pad
        self.card_small_bottom = self.card_box[1] + 2 * c_pad + 34
        # the headline sits in the upper part of the interviewer's tile
        h_style = Style(64, "bold", WHITE, "bold", LIGHT_BLUE, 1.12)
        self.h_style, self.h_lines = fit(self.headline, h_style, x1 - x0 - 2 * 56, 3 * 72, 44, 3)
        self.h_y = 196

    # ------------------------------------------------------------------ static picture
    def _background(self) -> Image.Image:
        img = Image.new("RGB", (W, H), MEET_BG)
        d = ImageDraw.Draw(img)
        # top strip: which call this is, and the site on the right
        d.text((M, 62), f"{self.app}   ·   {self.round}", font=font(26, "medium"), fill=SOFT)
        pf = font(26, "semibold")
        pw = int(pf.getlength(self.site)) + 36
        d.rounded_rectangle([W - M - pw, 50, W - M, 98], radius=24, fill=(38, 46, 68))
        d.text((W - M - pw + 18, 58), self.site, font=pf, fill=WHITE)
        # the interviewer's tile, camera off, as most Indian HR rounds actually look
        d.rounded_rectangle(TILE_BOX, radius=34, fill=TILE, outline=TILE_EDGE, width=2)
        cx, cy, r = AVATAR
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(102, 120, 158))
        initial = self.interviewer[:1].upper()
        af = font(58, "bold")
        d.text((cx - af.getlength(initial) / 2, cy - 40), initial, font=af, fill=WHITE)
        nf = font(28, "medium")
        label = f"{self.interviewer}   ·   Interviewer"
        nw = int(nf.getlength(label)) + 40
        d.rounded_rectangle([WAVE_X, 516, WAVE_X + nw, 566], radius=12, fill=(28, 34, 52))
        d.text((WAVE_X + 20, 524), label, font=nf, fill=WHITE)
        # the panel, with a shadow so it reads as floating over the call
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            [PANEL_BOX[0], PANEL_BOX[1] + 16, PANEL_BOX[2], PANEL_BOX[3] + 16], radius=28, fill=(0, 0, 0, 150))
        shadow = shadow.filter(ImageFilter.GaussianBlur(26))
        img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(PANEL_BOX, radius=28, fill=PANEL, outline=PANEL_EDGE, width=2)
        # header: listening dot, brand, where it is listening, and the end button
        x, y = self.px, self.header_y
        d.ellipse([x, y + 13, x + 14, y + 27], fill=GREEN)
        bf = font(32, "semibold")
        d.text((x + 28, y), "Interview Sarthi", font=bf, fill=TEXT)
        sf = font(21, "regular")
        d.text((x + 28 + bf.getlength("Interview Sarthi") + 20, y + 10),
               f"listening  ·  {self.app}  ·  Windows", font=sf, fill=MUTED)
        ef = font(20, "medium")
        ew = int(ef.getlength("end")) + 28
        d.rounded_rectangle([PANEL_BOX[2] - PAD - ew, y + 4, PANEL_BOX[2] - PAD, y + 38], radius=8,
                            fill=(70, 30, 34), outline=(120, 50, 56), width=1)
        d.text((PANEL_BOX[2] - PAD - ew + 14, y + 8), "end", font=ef, fill=(240, 160, 160))
        lf = font(20, "semibold")
        _spaced(d, (x, self.conv_label_y), "CONVERSATION", lf, MUTED)
        d.rounded_rectangle(self.conv_box, radius=16, fill=BOX, outline=BOX_EDGE, width=2)
        _spaced(d, (x, self.say_label_y), "SAY THIS", lf, MUTED)
        # the answer card itself is drawn per frame: it stays small until the answer drafts in
        # the call controls, mostly under the platform's own buttons but they finish the picture
        cy = 1770
        xs = [W // 2 + (i - 2) * 100 for i in range(5)]
        for i, bx in enumerate(xs):
            d.ellipse([bx - 32, cy - 32, bx + 32, cy + 32], fill=RED if i == 4 else (40, 47, 66))
        return img

    # ------------------------------------------------------------------ dynamic parts
    @staticmethod
    def _fade_in(img: Image.Image, draw_fn, alpha: float, rise: int = 22) -> None:
        """Draw an element arriving: it fades in while sliding up a little, like the cards do."""
        if alpha >= 1.0:
            draw_fn(ImageDraw.Draw(img), 0)
            return
        if alpha <= 0.0:
            return
        eased = _ease(alpha)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(layer), int(round((1.0 - eased) * rise)))
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * eased)))
        img.paste(layer, (0, 0), layer)

    def _headline(self, img: Image.Image, alpha: float) -> None:
        def draw(d, dy):
            draw_lines(d, self.h_lines, self.h_style, TILE_BOX[0] + 56, self.h_y + dy,
                       TILE_BOX[2] - TILE_BOX[0] - 2 * 56, "center")
        self._fade_in(img, draw, alpha, rise=26)

    def _wave(self, d: ImageDraw.ImageDraw, t: float, level: float) -> None:
        for i in range(WAVE_BARS):
            centre = 1.0 - abs(i - (WAVE_BARS - 1) / 2) / (WAVE_BARS / 2 + 1)
            freq = 1.7 + (i % 5) * 0.37
            swing = 0.5 + 0.5 * math.sin(2 * math.pi * freq * t + i * 0.9)
            h = 6 + level * (10 + 30 * swing * centre)
            x = WAVE_X + i * 16
            colour = tuple(int(MUTED[k] + (LIGHT_BLUE[k] - MUTED[k]) * level) for k in range(3))
            d.rounded_rectangle([x, WAVE_Y - h, x + 9, WAVE_Y + h], radius=4, fill=colour)

    def _listening(self, d: ImageDraw.ImageDraw, t: float) -> None:
        x, y = self.conv_box[0] + 28, self.conv_box[1] + 30
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 0.9 * t)
        colour = tuple(int(MUTED[k] + (GREEN[k] - MUTED[k]) * pulse) for k in range(3))
        d.ellipse([x, y + 12, x + 14, y + 26], fill=colour)
        d.text((x + 30, y), "Listening to the call", font=font(28, "regular"), fill=MUTED)

    def _question(self, d: ImageDraw.ImageDraw, progress: float, t: float) -> None:
        x, y = self.conv_box[0] + 28, self.conv_box[1] + 24
        tf = font(26, "semibold")
        d.text((x, y), "Them", font=tf, fill=BLUE)
        d.text((x + tf.getlength("Them") + 12, y + 7), self.stamp, font=font(20, "regular"), fill=MUTED)
        y += 38
        tokens_total = sum(len(line) for line in self.q_lines)
        visible = tokens_total if progress >= 1.0 else int(math.ceil(progress * tokens_total))
        space = self.q_style.font_for(False).getlength(" ")
        shown = 0
        cx = x
        for line in self.q_lines:
            cx = x
            for i, (word, bold, glue) in enumerate(line):
                if shown >= visible:
                    break
                f = self.q_style.font_for(bold)
                if i and not glue:
                    cx += space
                d.text((cx, y), word, font=f, fill=self.q_style.color)
                cx += f.getlength(word)
                shown += 1
            if shown >= visible:
                break
            y += self.q_style.line_height
        if progress < 1.0 and (t * 3) % 1 < 0.6:
            d.rectangle([cx + 6, y + 6, cx + 9, y + self.q_style.size + 2], fill=SOFT)

    def _say_idle(self, d: ImageDraw.ImageDraw) -> None:
        x, y = self.card_box[0] + self.c_pad + 14, self.card_box[1] + self.c_pad
        d.text((x, y), "The answer appears here, drafted from your own resume.",
               font=font(26, "regular"), fill=MUTED)

    def _answer(self, img: Image.Image, ta: float) -> None:
        d = ImageDraw.Draw(img)
        x, y = self.card_box[0] + self.c_pad + 14, self.card_box[1] + self.c_pad
        hf = font(27, "semibold")
        if ta < DRAFTING:
            d.text((x, y), "SAY THIS  ·  drafting", font=hf, fill=CORAL)
            dx = x + hf.getlength("SAY THIS  ·  drafting") + 18
            for k in range(3):
                pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * 1.6 * ta - k * 1.1))
                colour = tuple(int(CARD[j] + (CORAL[j] - CARD[j]) * pulse) for j in range(3))
                d.ellipse([dx + k * 22, y + 14, dx + k * 22 + 10, y + 24], fill=colour)
            return
        short = self.question if len(self.question) <= 44 else self.question[:43].rstrip(" ,") + "..."
        d.text((x, y), "SAY THIS  ·  " + short, font=hf, fill=CORAL)
        y += 40 + 12
        done = True
        for k, rows in enumerate(self.a_rows):
            start = DRAFTING + k * SENTENCE_GAP
            alpha = _clamp((ta - start) / SENTENCE_RISE)
            if alpha < 1.0:
                done = False
            row_y = y

            def draw(dd, dy, rows=rows, row_y=row_y):
                draw_lines(dd, rows, self.a_style, x, row_y + dy)

            self._fade_in(img, draw, alpha, rise=18)
            y += block_height(rows, self.a_style) + 10
        if done:
            ImageDraw.Draw(img).text((x, self.card_box[3] - self.c_pad - 26), "high confidence",
                                     font=font(20, "medium"), fill=GREEN)

    # ------------------------------------------------------------------ one frame
    def render(self, t: float, tl: Timeline) -> Image.Image:
        img = self.base.copy()
        self._headline(img, _clamp(t / HEADLINE_FADE))
        d = ImageDraw.Draw(img)
        speaking_until = tl.q0 + tl.reveal + 0.5
        level = _clamp((t - tl.q0) / 0.25) * (1.0 - _clamp((t - speaking_until) / 0.35))
        self._wave(d, t, level)
        if t < tl.q0:
            self._listening(d, t)
        else:
            self._question(d, _clamp((t - tl.q0) / tl.reveal), t)
        grow = _ease(_clamp((t - tl.a0) / 0.35))
        c0, c1, c2, c3 = self.card_box
        bottom = int(round(self.card_small_bottom + (c3 - self.card_small_bottom) * grow))
        d.rounded_rectangle([c0, c1, c2, bottom], radius=16, fill=CARD, outline=CARD_EDGE, width=2)
        d.rounded_rectangle([c0 + 2, c1 + 18, c0 + 8, bottom - 18], radius=3, fill=GREEN)
        if t < tl.a0:
            self._say_idle(d)
        else:
            self._answer(img, t - tl.a0)
        return img


def build_demo(content: dict, out_mp4: pathlib.Path, language: str = "english", max_seconds: float = 32.0) -> dict:
    """Voice the four lines, draw every frame of the demo shot, add the price card, join them.

    Returns {"path", "seconds", "voice": engine, "cover"}.
    """
    out_mp4 = pathlib.Path(out_mp4)
    work = out_mp4.parent / "demo-work"
    work.mkdir(parents=True, exist_ok=True)
    demo = content.get("demo") or {}
    slides = content["slides"]
    qa = next(s for s in slides if s.get("type") == "qa")
    cta = next(s for s in slides if s.get("type") == "cta")
    texts = [str(demo.get("narration_hook") or ""), str(demo.get("narration_question") or ""),
             str(qa.get("narration") or ""), str(cta.get("narration") or "")]
    voices, engine = synthesize_batch(texts, [work / f"voice-{i:02d}.mp3" for i in range(4)], language)
    print(f"[demo] voice: {engine}")
    durations = [probe(v)[0] if v else 0.0 for v in voices]
    scene = Scene(content)
    cta_len = max(durations[3] + TAIL, 4.0)
    tl = plan_timeline(durations, len(scene.sentences), max_seconds - cta_len)

    for old in work.glob("demo-*.jpg"):
        old.unlink()
    count = max(int(round(tl.total * FPS)), FPS)
    for i in range(count):
        scene.render(i / FPS, tl).save(work / f"demo-{i:05d}.jpg", "JPEG", quality=QUALITY)
    cover = out_mp4.parent / "cover.jpg"
    scene.render(tl.total - 0.05, tl).save(cover, "JPEG", quality=90)

    # the demo shot: frames plus the three narration lines placed at their phase starts
    args = ["-framerate", str(FPS), "-i", str(work / "demo-%05d.jpg")]
    filters: list[str] = []
    labels: list[str] = []
    for voice, start in zip(voices[:3], (0.0, tl.q0, tl.a0)):
        if not voice:
            continue
        args += ["-i", str(voice)]
        idx = len(labels) + 1
        filters.append(f"[{idx}:a]aresample=44100,adelay={int(start * 1000)}:all=1[s{idx}]")
        labels.append(f"[s{idx}]")
    if labels:
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,apad[a]")
        amap = ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]"]
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        amap = ["-map", "0:v", "-map", "1:a"]
    shot = work / "seg-demo.mp4"
    # JPEG frames are full range; the price card is limited range with bt709 tags. Both segments
    # must match, because the concat below is a stream copy and cannot convert at the boundary.
    _run([*args, "-vf", TO_TV, *amap, "-t", f"{tl.total:.3f}", "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "20", *COLOR_TAGS, "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
          "-movflags", "+faststart", str(shot)])
    price = work / "seg-price.mp4"
    _card_segment(cta, voices[3], cta_len, work, "price", price, animated=False)

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in (shot, price)), encoding="utf-8")
    _run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-t", f"{max_seconds:.3f}",
          "-movflags", "+faststart", str(out_mp4)])
    for frame in work.glob("demo-*.jpg"):
        try:
            frame.unlink()
        except OSError:
            pass          # OneDrive sometimes still holds a frame; a leftover JPEG costs nothing
    seconds, _ = probe(out_mp4)
    print(f"[demo] {seconds:.1f}s: headline {tl.q0:.1f}s, question {tl.a0 - tl.q0:.1f}s, "
          f"answer {tl.total - tl.a0:.1f}s, price {cta_len:.1f}s")
    return {"path": str(out_mp4), "seconds": round(seconds, 2), "voice": engine, "cover": str(cover)}
