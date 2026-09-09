"""Command line: python -m agent <command>."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import traceback

from .config import OUT, Settings, load_json


def _add_content_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--format", default="auto", choices=["auto", "image", "carousel", "reel"],
                   help="auto follows knowledge/schedule.json by weekday")
    p.add_argument("--topic", default=None, help="steer today's topic")
    p.add_argument("--language", default="auto", choices=["auto", "english", "hinglish"])
    p.add_argument("--out", default=None, help="output folder (default out/<timestamp>-<format>)")
    p.add_argument("--sample", action="store_true", help="use samples/ instead of calling Gemini")


def _add_publish_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--platforms", default=None, help="comma list: instagram,facebook,youtube (default env PLATFORMS)")
    p.add_argument("--dry-run", action="store_true", help="create everything, publish nothing")


def _platforms(value: str | None, settings: Settings) -> list[str]:
    if not value:
        return settings.platforms
    return [v.strip().lower() for v in value.split(",") if v.strip()]


def cmd_run(args, settings: Settings) -> int:
    from . import pipeline

    if args.dry_run:
        settings.dry_run = True
    manifest = pipeline.create(settings, args.format, args.topic, None if args.language == "auto" else args.language,
                               args.out, sample=args.sample)
    outcome = pipeline.publish(manifest, settings, _platforms(args.platforms, settings))
    pipeline.remember(manifest, outcome)
    print(pipeline.report(manifest, outcome))
    if outcome.get("errors") and not outcome.get("results"):
        return 1
    return 0


def cmd_create(args, settings: Settings) -> int:
    from . import pipeline

    manifest = pipeline.create(settings, args.format, args.topic, None if args.language == "auto" else args.language,
                               args.out, sample=args.sample)
    print(pipeline.report(manifest, {"dry_run": True, "platforms": []}))
    return 0


def cmd_publish(args, settings: Settings) -> int:
    from . import pipeline

    if args.dry_run:
        settings.dry_run = True
    folder = pathlib.Path(args.folder)
    manifest = load_json(folder / "post.json")
    outcome = pipeline.publish(manifest, settings, _platforms(args.platforms, settings))
    pipeline.remember(manifest, outcome)
    print(pipeline.report(manifest, outcome))
    return 0 if outcome.get("results") or outcome.get("dry_run") else 1


def cmd_plan(args, settings: Settings) -> int:
    from .history import History
    from .llm import Gemini
    from .strategy import decide_format, decide_language, plan_post

    history = History()
    fmt = decide_format(args.format)
    language = decide_language(history, None if args.language == "auto" else args.language)
    llm = Gemini(settings.gemini_api_key or "", settings.gemini_models)
    plan = plan_post(llm, history, fmt, language, args.topic)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def cmd_research(args, settings: Settings) -> int:
    from . import research
    from .llm import Gemini

    llm = Gemini(settings.gemini_api_key or "", settings.gemini_models)
    research.run(llm, args.url, args.repo, pathlib.Path(args.out) if args.out else None, args.max_pages)
    return 0


def cmd_verify(args, settings: Settings) -> int:
    rows: list[tuple[str, str, str]] = []

    def check(name: str, fn):
        try:
            rows.append((name, "ok", str(fn())))
        except Exception as exc:  # noqa: BLE001
            rows.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))

    from .llm import Gemini

    if settings.gemini_api_key:
        check("Gemini", lambda: Gemini(settings.gemini_api_key, settings.gemini_models).text(
            "Reply with the single word OK.", "ping", temperature=0, max_tokens=5)[:20])
    else:
        rows.append(("Gemini", "FAIL", "GEMINI_API_KEY not set"))
    if settings.has_meta:
        from .publish.meta import Meta

        meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id, settings.graph_version)
        check("Facebook Page", lambda: meta.whoami()["page"])
        if settings.has_instagram:
            check("Instagram", lambda: meta.whoami()["instagram"])
        else:
            rows.append(("Instagram", "skip", "IG_USER_ID not set"))
    else:
        rows.append(("Facebook Page", "skip", "META_PAGE_ID / META_PAGE_ACCESS_TOKEN not set"))
    if settings.has_youtube:
        from .publish import youtube

        check("YouTube", lambda: youtube.channel_title(settings) + f" (uploads as {settings.yt_privacy})")
    else:
        rows.append(("YouTube", "skip", "YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN not set"))
    if settings.cloudinary_url:
        rows.append(("Media host", "ok", "Cloudinary"))
    else:
        from .publish import media_host

        def repo_public():
            import requests

            slug = media_host.repo_slug()
            response = requests.get(f"https://api.github.com/repos/{slug}", timeout=30)
            if response.status_code == 200 and not response.json().get("private"):
                return f"GitHub media branch on public repo {slug}"
            raise RuntimeError(f"repo {slug} is private or unreachable (HTTP {response.status_code}); "
                               "Instagram needs a public repo for raw URLs, or set CLOUDINARY_URL")

        check("Media host", repo_public)
    from .render.reel import ffmpeg_exe

    check("ffmpeg", ffmpeg_exe)
    width = max(len(r[0]) for r in rows)
    for name, status, detail in rows:
        print(f"{name.ljust(width)}  {status.ljust(4)}  {detail}")
    return 0 if all(r[1] != "FAIL" for r in rows) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m agent", description="Interview Sarthi social media agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="plan, write, render, publish, remember")
    _add_content_args(p)
    _add_publish_args(p)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("create", help="plan, write and render only; nothing is published")
    _add_content_args(p)
    p.set_defaults(fn=cmd_create)

    p = sub.add_parser("publish", help="publish a folder produced by create")
    p.add_argument("folder")
    _add_publish_args(p)
    p.set_defaults(fn=cmd_publish)

    p = sub.add_parser("plan", help="print today's plan as JSON")
    _add_content_args(p)
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("research", help="crawl the website and write knowledge/business_brief.auto.md")
    p.add_argument("--url", default="https://interviewsarthi.com")
    p.add_argument("--repo", default=None, help="local path of the product repo; its *.md files are read too")
    p.add_argument("--out", default=None)
    p.add_argument("--max-pages", type=int, default=40)
    p.set_defaults(fn=cmd_research)

    p = sub.add_parser("verify", help="check every credential and tool without posting")
    p.set_defaults(fn=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        return args.fn(args, settings)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        print(f"\nFAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
