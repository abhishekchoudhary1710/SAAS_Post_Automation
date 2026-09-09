"""One run, end to end: plan -> write -> review -> render -> publish -> remember."""

from __future__ import annotations

import os
import pathlib

from PIL import Image

from .config import OUT, SAMPLES, Settings, brand, load_json, now_ist, save_json, schedule
from .copywriter import produce, validate
from .history import History
from .llm import Gemini
from .render.cards import FEED, REEL, render_slides
from .render.reel import build_reel
from .strategy import decide_format, decide_language, plan_post


# ----------------------------------------------------------------------------- captions
def _merged_tags(content: dict, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag in brand()["hashtags_core"] + list(content.get("hashtags") or []):
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out[:limit]


def compose_captions(content: dict, fmt: str, plan: dict) -> dict:
    b = brand()
    site = b["site"].rstrip("/")

    def link(platform: str) -> str:
        return f"{site}/?{b['utm'].format(platform=platform)}"

    caption = str(content.get("caption") or "").strip()
    guide = plan.get("guide_link") if isinstance(plan.get("guide_link"), str) else None
    instagram = caption + "\n\n" + b["cta_lines"]["instagram"] + "\n\n" + " ".join(_merged_tags(content, 22))
    facebook = caption + "\n\n" + b["cta_lines"]["facebook"] + " " + link("facebook")
    if guide:
        facebook += "\nFull guide: " + guide
    facebook += "\n\n" + " ".join(_merged_tags(content, 5))
    youtube = None
    if fmt == "reel":
        reel = content.get("reel") or {}
        title = str(reel.get("youtube_title") or content.get("hook") or content.get("topic") or "Interview tip").strip()
        if "#shorts" not in title.lower():
            title = title[:92].rstrip(" .,") + " #Shorts"
        description = str(reel.get("youtube_description") or caption).strip()
        description += "\n\n" + b["cta_lines"]["youtube"] + "\n" + link("youtube")
        if guide:
            description += "\nFull guide: " + guide
        description += "\nMicrosoft Store: " + b["store_url"]
        description += "\n\n" + " ".join(_merged_tags(content, 12))
        tags = [str(t)[:30] for t in (reel.get("youtube_tags") or [])][:15]
        while tags and sum(len(t) + 2 for t in tags) > 480:
            tags.pop()
        youtube = {"title": title[:100], "description": description[:4900], "tags": tags}
    return {"instagram": instagram[:2190], "facebook": facebook, "youtube": youtube}


# ----------------------------------------------------------------------------- create
def render_media(content: dict, fmt: str, out_dir: pathlib.Path) -> dict:
    if fmt == "reel":
        frames = render_slides(content["slides"], REEL, out_dir / "frames", "frame", "png")
        narrations = [s.get("narration") for s in content["slides"]]
        info = build_reel(frames, narrations, out_dir / "reel.mp4", language=content.get("language", "english"),
                          max_seconds=schedule()["reel"]["max_seconds"])
        cover = out_dir / "cover.jpg"
        Image.open(frames[0]).convert("RGB").save(cover, "JPEG", quality=90)
        return {"video": str(out_dir / "reel.mp4"), "cover": str(cover), "frames": [str(p) for p in frames],
                "seconds": info["seconds"], "voiced": info["voiced"], "music": info["music"]}
    images = render_slides(content["slides"], FEED, out_dir, "slide", "jpg")
    return {"images": [str(p) for p in images]}


def create(settings: Settings, fmt: str | None = None, topic: str | None = None, language: str | None = None,
           out_dir: str | pathlib.Path | None = None, sample: bool = False) -> dict:
    history = History()
    fmt = decide_format(fmt)
    if sample:
        content = load_json(SAMPLES / f"sample_{fmt}.json")
        content, problems = validate(content, fmt)
        if problems:
            raise RuntimeError(f"sample content is invalid: {problems}")
        plan = {"pillar": content["pillar"], "topic": content["topic"], "language": content["language"],
                "format": fmt, "sample": True, "guide_link": None}
        notes = ["sample content, no model calls"]
    else:
        llm = Gemini(settings.gemini_api_key or "", settings.gemini_models)
        language = decide_language(history, language)
        plan = plan_post(llm, history, fmt, language, topic)
        print(f"[plan] {plan.get('pillar')} | {plan.get('language')} | {plan.get('topic')}")
        content, notes = produce(llm, plan, fmt)
        notes.append(f"gemini calls: {llm.calls}")
    run_dir = pathlib.Path(out_dir) if out_dir else OUT / (now_ist().strftime("%Y%m%d-%H%M") + "-" + fmt)
    run_dir.mkdir(parents=True, exist_ok=True)
    media = render_media(content, fmt, run_dir)
    manifest = {
        "id": run_dir.name, "created_at": now_ist().isoformat(), "format": fmt, "sample": sample,
        "plan": plan, "content": content, "media": media, "captions": compose_captions(content, fmt, plan),
        "notes": notes,
    }
    save_json(run_dir / "post.json", manifest)
    print(f"[create] {fmt} ready in {run_dir}")
    return manifest


# ----------------------------------------------------------------------------- publish
def _instagram_urls(fmt: str, files: list[str], settings: Settings, meta, outcome: dict) -> dict[str, str]:
    """Public URLs for Instagram to fetch: Cloudinary, the public repo's media branch, or Facebook's own copy."""
    from .publish import media_host

    if settings.cloudinary_url:
        return media_host.host([pathlib.Path(f) for f in files], settings)
    if media_host.repo_is_public():
        return media_host.host([pathlib.Path(f) for f in files], settings)
    if meta is not None and outcome["results"].get("facebook"):
        if fmt == "reel":
            if not meta.last_video_id:
                raise RuntimeError("Facebook did not return a video id to reuse")
            return {files[0]: meta.video_source(meta.last_video_id)}
        if len(meta.last_photo_ids) < len(files):
            raise RuntimeError("Facebook did not return one photo id per image to reuse")
        return {f: meta.photo_source(pid) for f, pid in zip(files, meta.last_photo_ids)}
    raise RuntimeError("no public host for Instagram media: make the repo public, set CLOUDINARY_URL, "
                       "or keep facebook in PLATFORMS so Instagram can reuse Facebook's copy")


def publish(manifest: dict, settings: Settings, platforms: list[str] | None = None) -> dict:
    from .publish import youtube
    from .publish.meta import Meta

    fmt = manifest["format"]
    allowed = schedule()["platforms_by_format"].get(fmt, [])
    wanted = [p for p in (platforms or settings.platforms) if p in allowed]
    # Facebook goes first on purpose: with a private repo Instagram reuses Facebook's copy of the media.
    order = [p for p in ("facebook", "instagram", "youtube") if p in wanted]
    outcome: dict = {"platforms": order, "results": {}, "errors": {}, "dry_run": settings.dry_run}
    if settings.dry_run:
        print(f"[publish] DRY RUN, would post to: {', '.join(order) or 'nothing'}")
        return outcome
    media, captions = manifest["media"], manifest["captions"]
    files = [media["video"]] if fmt == "reel" else list(media["images"])
    meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id,
                settings.graph_version) if settings.has_meta else None
    for platform in order:
        try:
            if platform == "facebook":
                if not meta:
                    raise RuntimeError("META_PAGE_ID and META_PAGE_ACCESS_TOKEN are not set")
                if fmt == "reel":
                    try:
                        post_id = meta.fb_reel(media["video"], captions["facebook"])
                    except Exception as exc:  # noqa: BLE001
                        print(f"[facebook] reel endpoint failed ({exc}); posting as a normal video")
                        post_id = meta.fb_video(media["video"], captions["facebook"])
                else:
                    post_id = meta.fb_photos(media["images"], captions["facebook"])
                outcome["results"]["facebook"] = {"id": post_id, "url": f"https://www.facebook.com/{post_id}"}
            elif platform == "instagram":
                if not (meta and settings.has_instagram):
                    raise RuntimeError("IG_USER_ID (plus the Meta page secrets) is not set")
                urls = _instagram_urls(fmt, files, settings, meta, outcome)
                print(f"[publish] Instagram will fetch {len(urls)} file(s)")
                if fmt == "reel":
                    media_id = meta.ig_reel(urls[media["video"]], captions["instagram"])
                elif fmt == "carousel":
                    media_id = meta.ig_carousel([urls[p] for p in media["images"]], captions["instagram"])
                else:
                    media_id = meta.ig_image(urls[media["images"][0]], captions["instagram"])
                outcome["results"]["instagram"] = {"id": media_id, "url": meta.ig_permalink(media_id)}
            elif platform == "youtube":
                if fmt != "reel":
                    continue
                if not settings.has_youtube:
                    raise RuntimeError("YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN are not all set")
                yt = captions["youtube"]
                video_id = youtube.upload_short(settings, media["video"], yt["title"], yt["description"], yt["tags"])
                outcome["results"]["youtube"] = {"id": video_id, "url": f"https://youtube.com/shorts/{video_id}",
                                                 "privacy": settings.yt_privacy}
            print(f"[publish] {platform}: {outcome['results'].get(platform, {}).get('url', 'done')}")
        except Exception as exc:  # noqa: BLE001
            outcome["errors"][platform] = f"{type(exc).__name__}: {exc}"
            print(f"[publish] {platform} FAILED: {outcome['errors'][platform]}")
    return outcome


# ----------------------------------------------------------------------------- remember + report
def remember(manifest: dict, outcome: dict) -> None:
    if manifest.get("sample") or outcome.get("dry_run") or not outcome.get("results"):
        return
    content = manifest["content"]
    history = History()
    history.add({
        "id": manifest["id"], "format": manifest["format"], "pillar": content.get("pillar"),
        "topic": content.get("topic"), "language": content.get("language"), "hook": content.get("hook"),
        "posted": outcome.get("results", {}), "errors": outcome.get("errors", {}),
    })
    history.save()


def report(manifest: dict, outcome: dict) -> str:
    content = manifest["content"]
    lines = [f"## {manifest['format'].title()} post: {content.get('topic')}", "",
             f"- Pillar: `{content.get('pillar')}` | Language: `{content.get('language')}` | Run: `{manifest['id']}`",
             f"- Hook: {content.get('hook')}"]
    if manifest.get("plan", {}).get("reason"):
        lines.append(f"- Why: {manifest['plan']['reason']}")
    if outcome.get("dry_run"):
        lines.append(f"- DRY RUN: nothing published. Would have posted to: {', '.join(outcome.get('platforms') or [])}")
    for platform, result in (outcome.get("results") or {}).items():
        lines.append(f"- {platform}: {result.get('url')}")
    for platform, error in (outcome.get("errors") or {}).items():
        lines.append(f"- {platform} FAILED: {error}")
    media = manifest["media"]
    if "video" in media:
        lines.append(f"- Reel: {media.get('seconds')}s, voice-over {'yes' if media.get('voiced') else 'no'}")
    else:
        lines.append(f"- Images: {len(media.get('images', []))}")
    lines += ["", "### Instagram caption", "", "```", manifest["captions"]["instagram"], "```"]
    if manifest["captions"].get("youtube"):
        lines += ["", f"### YouTube title", "", manifest["captions"]["youtube"]["title"]]
    text = "\n".join(lines) + "\n"
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(text)
    return text
