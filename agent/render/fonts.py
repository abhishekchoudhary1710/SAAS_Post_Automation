"""Font loading with a cache. Poppins ships in assets/fonts (OFL licence, Latin plus Devanagari)."""

from __future__ import annotations

import functools
import pathlib

from PIL import ImageFont

from ..config import ASSETS, brand

FALLBACKS = {
    "regular": ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "medium": ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "semibold": ["C:/Windows/Fonts/seguisb.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "bold": ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "black": ["C:/Windows/Fonts/seguibl.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


@functools.lru_cache(maxsize=None)
def _path_for(weight: str) -> str:
    fonts = brand()["fonts"]
    candidates = [str(ASSETS / "fonts" / fonts.get(weight, ""))] + FALLBACKS.get(weight, [])
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(f"no font found for weight {weight!r}; tried {candidates}")


@functools.lru_cache(maxsize=512)
def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_path_for(weight), int(size))
