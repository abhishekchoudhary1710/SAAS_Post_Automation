"""Portrait product stories. Each scene has a measured reading and speaking budget."""
from __future__ import annotations

import math
import pathlib
import subprocess

from PIL import Image, ImageDraw

from ..config import ROOT, brand
from .fonts import font
from .reel import ffmpeg_exe
from .film import COLOR_TAGS, TO_TV, probe, _run
from .tts import synthesize_batch

W, H, FPS = 1080, 1920, 60
LEFT, RIGHT = 86, 918
INK, PAPER, MUTED = '#f7f9ff', '#0b1323', '#b4c0d4'
BLUE, GREEN = '#80b8ff', '#83e3c3'


def lines_for(text, size, width, weight='regular'):
    f = font(size, weight)
    rows, row = [], ''
    for word in text.replace('**', '').split():
        trial = (row + ' ' + word).strip()
        if f.getlength(trial) <= width:
            row = trial
        else:
            if row:
                rows.append(row)
            row = word
    if row:
        rows.append(row)
    return rows


def paragraph(d, text, y, size=54, colour=INK, weight='regular', width=RIGHT-LEFT, x=LEFT,
              bottom=1530, min_size=38):
    while True:
        rows = lines_for(text, size, width, weight)
        if y + len(rows) * size * 1.36 <= bottom or size <= min_size:
            break
        size -= 2
    if y + len(rows) * size * 1.36 > bottom:
        raise ValueError('Text does not fit its safe area')
    for row in rows:
        d.text((x, y), row, font=font(size, weight), fill=colour)
        y += size * 1.36
    return y, size


def base(s, label):
    img = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 12), fill=BLUE)
    logo = Image.open(ROOT / brand()['images']['logo']).convert('RGBA').resize((60, 60))
    img.paste(logo, (LEFT, 164), logo)
    d.text((LEFT+78, 166), 'Interview Sarthi', font=font(35, 'semibold'), fill=INK)
    d.text((LEFT, 258), label.upper(), font=font(26, 'semibold'), fill=GREEN)
    d.text((LEFT, 1580), 'Windows 10/11  |  interviewsarthi.com', font=font(27, 'medium'), fill=MUTED)
    d.text((LEFT, 1630), 'Illustrative demo. Fictional resume. Edited timing.', font=font(24, 'regular'), fill=MUTED)
    return img


def screenshot(language='english'):
    # Use the real product asset. Its answer belongs to that screenshot, not today's scenario.
    key='overlay_hinglish' if language=='hinglish' else 'overlay_english'
    src = Image.open(ROOT / brand()['images'][key]).convert('RGB')
    from .cards import SCREENSHOT_CROP
    src = src.crop(SCREENSHOT_CROP[key])
    width = RIGHT - LEFT
    return src.resize((width, round(src.height * width / src.width)), Image.Resampling.LANCZOS)


class SalesScene:
    def __init__(self, s, script, kind):
        self.s, self.script, self.kind = s, script, kind
        self.minimum_font = 48
        self._base = base(s, {'hook': 'During your online interview', 'answer': 'A suggested answer',
                             'evidence': 'Why this answer fits', 'product': 'Your call. Your assistant.',
                             'cta': 'Try it on your Windows laptop'}[kind])
        self.static = self._static()

    def text(self, d, text, y, **kwargs):
        end, size = paragraph(d, text, y, **kwargs)
        self.minimum_font = min(self.minimum_font, size)
        return end

    def _static(self):
        img = self._base.copy()
        d = ImageDraw.Draw(img)
        if self.kind == 'hook':
            y = self.text(d, self.script['hook'], 345, size=82, weight='bold', bottom=780, min_size=60)
            d.text((LEFT, y+65), 'INTERVIEWER ASKS', font=font(25, 'semibold'), fill=BLUE)
            self.text(d, self.s['question'], y+118, size=48, bottom=1130)
            d.line((LEFT, 1190, RIGHT, 1190), fill='#32415b', width=2)
            d.text((LEFT, 1220), 'ANSWER EXAMPLE', font=font(25, 'semibold'), fill=GREEN)
            self.answer_y = 1278
        elif self.kind == 'answer':
            y = self.text(d, self.s['question'], 338, size=51, weight='semibold', bottom=560)
            d.line((LEFT, y+32, RIGHT, y+32), fill='#32415b', width=2)
            d.text((LEFT, y+70), 'SUGGESTED ANSWER', font=font(25, 'semibold'), fill=BLUE)
            self.answer_y = y + 128
            self.text(d, self.s['answer'], self.answer_y, size=58, bottom=1330, min_size=48)
            d.rounded_rectangle((LEFT, 1410, RIGHT, 1494), radius=15, fill='#182c32')
            self.text(d, self.s['benefit'], 1426, size=31, colour=GREEN, bottom=1490, min_size=29,
                      x=LEFT+22, width=RIGHT-LEFT-44)
        elif self.kind == 'evidence':
            self.text(d, 'The detail comes from the resume.', 342, size=70, weight='bold', bottom=660)
            d.text((LEFT, 742), 'EXAMPLE RESUME', font=font(27, 'semibold'), fill=BLUE)
            y = self.text(d, self.s['evidence'][0], 810, size=44, bottom=1010)
            d.line((LEFT, y+25, RIGHT, y+25), fill='#32415b', width=2)
            self.text(d, self.s['evidence'][1], y+70, size=50, colour=GREEN, bottom=1335)
            self.text(d, 'Your experience gives the answer context.', 1400, size=33, bottom=1520, min_size=30)
        elif self.kind == 'product':
            self.text(d, 'Keep your call open.', 345, size=76, weight='bold', bottom=610)
            self.text(d, 'Suggested answers on your screen.', 620, size=48, colour=BLUE, bottom=830)
            shot = screenshot()
            self.shot_box = (LEFT, 920, RIGHT, 920+shot.height)
            img.paste(shot, (LEFT, 920))
            d = ImageDraw.Draw(img)
            d.text((LEFT, 862), 'ACTUAL APP INTERFACE', font=font(25, 'semibold'), fill=MUTED)
            self.text(d, 'Teams  /  Zoom  /  Google Meet', 920+shot.height+44, size=32, bottom=1520, min_size=29)
        else:
            self.text(d, '30 minutes free.', 376, size=88, weight='bold', bottom=680, min_size=74)
            self.text(d, 'No payment card.', 700, size=54, colour=GREEN, bottom=820)
            d.line((LEFT, 914, RIGHT, 914), fill='#32415b', width=2)
            self.text(d, 'Then Rs 99 for 2 days.', 978, size=54, bottom=1130)
            self.text(d, 'One-time pass. Nothing renews.', 1142, size=35, colour=MUTED, bottom=1240, min_size=33)
            d.rounded_rectangle((LEFT, 1335, RIGHT, 1447), radius=18, fill='#cee3ff')
            d.text((LEFT+36, 1360), 'interviewsarthi.com', font=font(53, 'semibold'), fill='#10223e')
            d.text((LEFT, 1480), 'Setup uses your own Google Gemini key.', font=font(27, 'regular'), fill=MUTED)
        return img

    def frame(self, t, duration):
        img = self.static.copy()
        d = ImageDraw.Draw(img)
        if self.kind == 'hook' and t >= 1.1:
            first = self.s['answer'].split('. ')[0].rstrip('.') + '.'
            words = first.split()
            visible = max(1, min(len(words), int((t-1.1)*11)+1))
            self.text(d, ' '.join(words[:visible]), self.answer_y, size=40, colour=GREEN, bottom=1510, min_size=34)
        # A restrained moving progress line, with no motion applied to readable copy.
        d.rectangle((LEFT, 1545, LEFT+(RIGHT-LEFT)*min(1, t/duration), 1549), fill=BLUE)
        return img


def scene_durations(voice_durations, scenario, variant):
    # Keep the full audio and allow the displayed example to be read. No -t truncation at a global cap.
    floors = [3.4, max(6.8, len(scenario['answer'].split()) / 3.5 + .5), 4.0, 5.0]
    if variant == 'standard':
        floors = floors[:2] + [6.0, 5.5, 5.0]
    durations = [math.ceil(max(floor, voice+.35)*FPS)/FPS for voice, floor in zip(voice_durations, floors)]
    limit = 32 if variant == 'short' else 48
    if sum(durations) > limit:
        raise ValueError(f'Narration needs {sum(durations):.1f}s, beyond the {limit}s budget; do not clip it')
    return durations


def encode_scene(scene, voice, seconds, destination):
    args = [ffmpeg_exe(), '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', str(voice), '-map', '0:v', '-map', '1:a',
            '-vf', TO_TV, '-af', 'apad', '-t', f'{seconds:.4f}', '-c:v', 'libx264', '-preset', 'veryfast',
            '-crf', '20', *COLOR_TAGS, '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-ac', '2', str(destination)]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for n in range(math.ceil(seconds * FPS)):
            proc.stdin.write(scene.frame(n/FPS, seconds).tobytes())
        proc.stdin.close()
        error = proc.stderr.read().decode('utf-8', errors='replace')
        if proc.wait(timeout=180):
            raise RuntimeError('Scene encoding failed: ' + error[-600:])
    except BaseException:
        proc.kill()
        proc.wait()
        raise


def build_sales(s, script, variant, out_mp4):
    from .motion import MotionScene, music_bed
    work = out_mp4.parent / 'sales-work'
    work.mkdir(parents=True, exist_ok=True)
    lines = script['narrations']
    voices, engine = synthesize_batch(lines, [work / f'voice-{i}.mp3' for i in range(len(lines))], 'english')
    if any(not p or not p.exists() for p in voices):
        raise RuntimeError('A sales reel cannot be published without complete narration')
    voice_lengths = [probe(p)[0] for p in voices]
    if any(n <= .2 for n in voice_lengths):
        raise RuntimeError('Empty narration segment')
    durations = scene_durations(voice_lengths, s, variant)
    kinds = ['hook', 'answer', 'product', 'cta'] if variant == 'short' else ['hook', 'answer', 'evidence', 'product', 'cta']
    scenes = [MotionScene(s, script, kind) for kind in kinds]
    for i in range(1, len(scenes)):
        scenes[i].previous = (scenes[i-1], durations[i-1])
    timeline, segments, start = [], [], 0.0
    for i, (scene, voice, secs, spoken) in enumerate(zip(scenes, voices, durations, lines)):
        print(f'[sales] {scene.kind}: {secs:.1f}s', flush=True)
        segment = work / f'scene-{i}.mp4'
        encode_scene(scene, voice, secs, segment)
        segments.append(segment)
        scene.frame(min(2.5, secs-.1), secs).save(work / f'scene-{i}.jpg', quality=92)
        timeline.append({'kind': scene.kind, 'start': round(start, 3), 'duration': round(secs, 3),
                         'voice_seconds': voice_lengths[i], 'narration': spoken})
        start += secs
    listing = work / 'concat.txt'
    listing.write_text(''.join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding='utf-8')
    joined = work / 'joined.mp4'
    _run(['-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', str(joined)])
    bed = work / 'original-music.wav'
    seconds = probe(joined)[0]
    music_bed(bed, seconds, [x['start'] for x in timeline[1:]])
    _run(['-i', str(joined), '-i', str(bed), '-filter_complex',
          '[0:a]loudnorm=I=-16:TP=-1.5:LRA=9[voice];[1:a]volume=0.32[bed];'
          '[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[a]',
          '-map', '0:v', '-map', '[a]', '-vf', f'fps={FPS}', '-c:v', 'libx264',
          '-preset', 'veryfast', '-crf', '20', *COLOR_TAGS, '-c:a', 'aac', '-b:a', '128k',
          '-ar', '44100', '-ac', '2', '-use_editlist', '0', '-movflags', '+faststart', str(out_mp4)])
    cover = out_mp4.parent / 'cover.jpg'
    scenes[0].frame(2.8, durations[0]).save(cover, quality=92)
    return {'video': str(out_mp4), 'cover': str(cover), 'frames': [], 'seconds': probe(out_mp4)[0],
            'voiced': True, 'voice': engine, 'music': 'original procedural synth bed',
            'veo_seconds': 0.0, 'mode': 'sales-motion', 'visual_version': 3, 'fps': FPS,
            'timeline': timeline, 'layout': {'minimum_body_font': min(x.minimum_font for x in scenes),
                'first_answer_seconds': 1.1, 'cta_complete': True, 'variant': variant, 'fps': FPS}}
