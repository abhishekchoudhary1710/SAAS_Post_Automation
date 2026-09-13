"""Checks the actual encoded video and preserves an auditable publication gate."""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .render.reel import ffmpeg_exe
from .render.film import probe


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def inspect_video(path: Path, timeline: list, layout: dict) -> dict:
    issues = []
    seconds, has_audio = probe(path)
    expected = sum(x['duration'] for x in timeline)
    if not has_audio:
        issues.append('missing audio stream')
    if abs(seconds-expected) > .6:
        issues.append('encoded duration differs from the complete timeline')
    if not timeline or timeline[-1]['kind'] != 'cta' or not layout.get('cta_complete'):
        issues.append('missing complete CTA')
    if any(x['voice_seconds'] > x['duration']+.05 for x in timeline):
        issues.append('narration is clipped')
    if layout.get('first_answer_seconds', 99) > 3:
        issues.append('useful example arrives too late')
    if layout.get('minimum_body_font', 0) < 29:
        issues.append('body text too small')
    # Decode the entire result to catch corruption and check audio is not silent.
    p = subprocess.run([ffmpeg_exe(), '-hide_banner', '-i', str(path), '-af', 'volumedetect',
                        '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    if p.returncode:
        issues.append('video does not decode cleanly')
    if not re.search(r'1080x1920', p.stderr):
        issues.append('video is not 1080 by 1920')
    fps_match = re.search(r'(\d+(?:\.\d+)?) fps', p.stderr)
    encoded_fps = float(fps_match.group(1)) if fps_match else None
    if layout.get('fps') and (encoded_fps is None or abs(encoded_fps-layout['fps']) > .1):
        issues.append('encoded frame rate does not match the requested motion cadence')
    m = re.search(r'mean_volume:\s*([\w.+-]+) dB', p.stderr)
    try:
        volume = float(m.group(1)) if m else -100
    except ValueError:
        volume = -100
    if volume < -48:
        issues.append('audio is effectively silent')
    return {'passed': not issues, 'issues': issues, 'seconds': seconds, 'mean_volume_db': volume, 'fps': encoded_fps,
            'sha256': file_hash(path), 'version': 1}


def require_publishable(manifest):
    if manifest.get('format') != 'sales' and (manifest.get('quality') or {}).get('kind') != 'image':
        return
    quality = manifest.get('quality') or {}
    path = Path(manifest['media']['video'] if manifest['format'] == 'sales' else manifest['media']['images'][0])
    if not quality.get('passed') or quality.get('sha256') != file_hash(path):
        raise RuntimeError('Publication blocked: the final media has not passed quality checks or changed afterwards')
