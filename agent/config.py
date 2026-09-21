"""Paths, environment and the knowledge files. Everything else imports from here."""

from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
ASSETS = ROOT / "assets"
CONTENT = ROOT / "content"
OUT = ROOT / "out"
SAMPLES = ROOT / "samples"
HISTORY_FILE = CONTENT / "history.json"

# Formats that produce one vertical video and go to Reels, Facebook Reels and Shorts.
VIDEO_FORMATS = ("reel", "film", "demo", "sales")
ALL_FORMATS = ("image", "carousel", "reel", "film", "demo", "sales")

try:  # a local .env is a convenience; GitHub Actions passes real env vars
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30), "IST")


def now_ist() -> _dt.datetime:
    return _dt.datetime.now(IST)


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_json(path: pathlib.Path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_text(path: pathlib.Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def brand() -> dict:
    return load_json(KNOWLEDGE / "brand.json")


def product_of(plan: dict | str | None) -> str:
    """Which product a post sells, from its plan or pillar id.

    Everything downstream, the brief the writer sees, the caption block, the
    facts a video script may state and the wording it may not use, follows
    from this. Anything that does not say defaults to Interview Sarthi, which
    is how the bot behaved before the other two products existed.
    """
    if isinstance(plan, dict):
        named = plan.get("product")
        if named in ("interview_sarthi", "prep_sarthi", "apply_sarthi"):
            return named
        plan = plan.get("pillar")
    for p in pillars():
        if p["id"] == plan:
            return p.get("product", "interview_sarthi")
    return "interview_sarthi"


def product(pid: str | None = None) -> dict:
    """A product's name, site, calls to action and caption block."""
    b = brand()
    pid = pid or "interview_sarthi"
    known = b.get("products", {})
    if pid in known:
        return known[pid]
    return {"name": b["name"], "site": b["site"], "cta_lines": b["cta_lines"], "product_block": b["product_block"]}


def pillars() -> list[dict]:
    return load_json(KNOWLEDGE / "pillars.json")["pillars"]


def schedule() -> dict:
    return load_json(KNOWLEDGE / "schedule.json")


@dataclass
class Settings:
    gemini_api_key: str | None
    gemini_models: list[str]
    meta_page_id: str | None
    meta_page_token: str | None
    ig_user_id: str | None
    yt_client_id: str | None
    yt_client_secret: str | None
    yt_refresh_token: str | None
    yt_privacy: str
    cloudinary_url: str | None
    graph_version: str
    dry_run: bool
    platforms: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        models = env("SCRIPT_MODELS", env("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash"))
        platforms = env("PLATFORMS", "instagram,facebook,youtube")
        return cls(
            gemini_api_key=env("GEMINI_API_KEY"),
            gemini_models=[m.strip() for m in models.split(",") if m.strip()],
            meta_page_id=env("META_PAGE_ID"),
            meta_page_token=env("META_PAGE_ACCESS_TOKEN"),
            ig_user_id=env("IG_USER_ID"),
            yt_client_id=env("YT_CLIENT_ID"),
            yt_client_secret=env("YT_CLIENT_SECRET"),
            yt_refresh_token=env("YT_REFRESH_TOKEN"),
            yt_privacy=env("YT_PRIVACY", "public"),
            cloudinary_url=env("CLOUDINARY_URL"),
            graph_version=env("META_GRAPH_VERSION", "v23.0"),
            dry_run=env_bool("DRY_RUN", False),
            platforms=[p.strip().lower() for p in platforms.split(",") if p.strip()],
        )

    @property
    def has_meta(self) -> bool:
        return bool(self.meta_page_id and self.meta_page_token)

    @property
    def has_instagram(self) -> bool:
        return self.has_meta and bool(self.ig_user_id)

    @property
    def has_youtube(self) -> bool:
        return bool(self.yt_client_id and self.yt_client_secret and self.yt_refresh_token)


# The two labels on a qa slide, per product. cards.py reads them directly so it can brand a
# slide the copywriter never touched; copywriter.VOICE carries these same values.
VOICE_LABELS = {
    "interview_sarthi": {"label_q": "Interviewer asked", "label_a": "Interview Sarthi showed"},
    "prep_sarthi": {"label_q": "The interviewer asked", "label_a": "Your report said"},
    "apply_sarthi": {"label_q": "The job asked", "label_a": "ApplySarthi filled in"},
}
