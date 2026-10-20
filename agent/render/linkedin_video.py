"""Short, silent LinkedIn explainers using owned footage and readable app cards.

The clip is explicitly illustrative; screenshot sequences do not pretend to be recordings.
No paid generation, synthetic testimonials, voice services or external downloads.
"""
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw

from ..config import ROOT
from .fonts import font
from .reel import ffmpeg_exe


def render_video(images, footage, folder, product):
    if len(images) != 4:
        raise ValueError("LinkedIn videos need four storyboard cards")
    footage = Path(footage).resolve()
    if not footage.is_relative_to((ROOT / 'assets/motion').resolve()) or not footage.is_file():
        raise ValueError("LinkedIn footage must be an existing owned motion asset")
    folder = Path(folder).resolve()
    work = folder / 'video-work'
    work.mkdir(parents=True, exist_ok=True)
    # A code-rendered label sits on the illustrative footage for its entire duration.
    label = Image.new('RGBA', (720, 900), (0, 0, 0, 0))
    draw = ImageDraw.Draw(label)
    draw.rectangle((0, 0, 720, 92), fill='#0f172a')
    names = {'interview_sarthi': 'INTERVIEW SARTHI', 'prep_sarthi': 'PREP SARTHI', 'apply_sarthi': 'APPLYSARTHI'}
    draw.text((28, 16), names[product], font=font(25, 'bold'), fill='white')
    draw.text((28, 52), 'Illustrative scene • not a customer recording', font=font(20), fill='#b9cef5')
    label_path = work / 'label.png'
    label.save(label_path)
    ffmpeg = ffmpeg_exe()
    common = ['-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
              '-pix_fmt', 'yuv420p', '-r', '30', '-threads', '2']
    segments = []
    for index, (source, seconds) in enumerate([(images[0], 3), (footage, 3),
                                               (images[1], 6), (images[2], 6), (images[3], 5)]):
        target = work / f'segment-{index}.mp4'
        args = [ffmpeg, '-y', '-v', 'error']
        if index == 1:
            args += ['-i', str(source), '-i', str(label_path), '-filter_complex',
                     '[0:v]scale=720:900:force_original_aspect_ratio=increase,crop=720:900,setsar=1[clip];[clip][1:v]overlay=0:0']
        else:
            args += ['-loop', '1', '-i', str(Path(source).resolve()), '-vf', 'scale=720:900,setsar=1']
        subprocess.run(args + ['-t', str(seconds)] + common + [str(target)], check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        segments.append(target)
    # Relative fixed names keep concat paths independent of the user's checkout location.
    listing = work / 'segments.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in segments))
    target = folder / 'linkedin.mp4'
    subprocess.run([ffmpeg, '-y', '-v', 'error', '-f', 'concat', '-safe', '1', '-i', str(listing),
                    '-c', 'copy', '-movflags', '+faststart', str(target)], check=True, timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return target
