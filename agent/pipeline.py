"""One run, end to end: plan -> write -> review -> render -> publish -> remember."""

from __future__ import annotations

import os
import pathlib

from PIL import Image

from .config import OUT, SAMPLES, Settings, brand, load_json, now_ist, save_json, schedule
from .copywriter import produce, validate
from .history import History
from .llm import Gemini
from .render.cards import FEED, REEL, render_slides, render_stages
from .render.reel import build_reel
from .render.veo import generate_hook
from .strategy import decide_format, decide_language, plan_post


# ----------------------------------------------------------------------------- captions
def _merged_tags(content: dict, limit: int) -> list[str]:
    """This post's own tags first, brand tag last: the limit is small, so specificity wins the slots."""
    seen: set[str] = set()
    out: list[str] = []
    for tag in list(content.get("hashtags") or []) + brand()["hashtags_core"]:
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
    # Instagram captions and YouTube Shorts descriptions never render clickable links, so a
    # tracking URL there is unreadable noise nobody will retype. Facebook does link, and keeps it.
    plain = site.replace("https://", "")
    instagram = caption + "\n\n" + b["cta_lines"]["instagram"] + "\n\n" + " ".join(_merged_tags(content, 5))
    facebook = caption + "\n\n" + b["cta_lines"]["facebook"] + " " + link("facebook")
    if guide:
        facebook += "\nFull guide: " + guide
    facebook += "\n\n" + " ".join(_merged_tags(content, 3))
    youtube = None
    if fmt in ("reel", "film"):
        reel = content.get("reel") or {}
        title = str(reel.get("youtube_title") or content.get("hook") or content.get("topic") or "Interview tip").strip()
        if "#shorts" not in title.lower():
            title = title[:92].rstrip(" .,") + " #Shorts"
        description = str(reel.get("youtube_description") or caption).strip()
        description += "\n\n" + b["cta_lines"]["youtube"] + "\n" + plain
        if guide:
            description += "\nGuide: " + guide.replace("https://", "")
        description += "\nWindows app on the Microsoft Store: search Interview Sarthi"
        # First three show above the title on a Short, so they must be the specific ones.
        description += "\n\n" + " ".join(_merged_tags(content, 5))
        tags = [str(t)[:30] for t in (reel.get("youtube_tags") or [])][:15]
        while tags and sum(len(t) + 2 for t in tags) > 480:
            tags.pop()
        youtube = {"title": title[:100], "description": description[:4900], "tags": tags}
    return {"instagram": instagram[:2190], "facebook": facebook, "youtube": youtube}


# ----------------------------------------------------------------------------- create
def _render_film(content: dict, out_dir: pathlib.Path, plan: dict, history) -> dict:
    """Footage from Veo, then the cards. Any failure falls back to the animated card reel."""
    from .render.film import build_film
    from .render.veo import VeoBudgetExceeded, generate_story
    from .story import beat_prompts

    film = plan.get("_film") or {}
    story, persona = film.get("story"), film.get("persona")
    beats = (content.get("film") or {}).get("beats") or []
    cards = [dict(x) for x in content["slides"]]
    try:
        if not story or not persona:
            raise RuntimeError("no story or persona on the plan")
        prompts = beat_prompts(story, persona, [b.get("action", "") for b in beats])[:len(beats)]
        spent = history.veo_seconds_this_month() if history is not None else 0.0
        clips, generated = generate_story(prompts, out_dir / "footage", spent_this_month=spent)
        info = build_film(clips, [b.get("narration", "") for b in beats], cards, int(story.get("card_after_beat", 2)),
                          out_dir / "reel.mp4", language=content.get("language", "english"),
                          max_seconds=schedule().get("film", {}).get("max_seconds", 34))
        cover = out_dir / "cover.jpg"
        _first_frame(out_dir / "reel.mp4", cover)
        return {"video": str(out_dir / "reel.mp4"), "cover": str(cover), "frames": [], "seconds": info["seconds"],
                "voiced": True, "music": None, "veo_seconds": generated, "voice": info["voice"], "mode": "film"}
    except VeoBudgetExceeded as exc:
        print(f"[film] budget guard: {exc}; posting the card reel instead")
    except Exception as exc:  # noqa: BLE001 - a day without footage still gets a post
        print(f"[film] footage unavailable ({type(exc).__name__}: {str(exc)[:200]}); posting the card reel instead")
    fallback = dict(content)
    hook_line = str(content.get("hook") or content.get("topic") or "Interview Sarthi")
    fallback["slides"] = [{"type": "hook", "tag": "Interview Sarthi", "title": hook_line[:90],
                           "narration": (beats[0].get("narration") if beats else hook_line)}] + cards
    media = render_media(fallback, "reel", out_dir, allow_veo=True)
    media.update({"veo_seconds": 0.0, "mode": "card-fallback"})
    return media


def _first_frame(video: pathlib.Path, out: pathlib.Path) -> None:
    import subprocess

    from .render.reel import ffmpeg_exe

    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(video), "-frames:v", "1",
                    "-q:v", "2", str(out)], capture_output=True, timeout=120)


def render_media(content: dict, fmt: str, out_dir: pathlib.Path, allow_veo: bool = True, plan: dict | None = None,
                 history=None) -> dict:
    if fmt == "film":
        return _render_film(content, out_dir, plan or {}, history)
    if fmt in ("reel", "film"):
        slides = content["slides"]
        # Each slide is rendered as the sequence of states it passes through, so the video
        # can show it assembling. The last state is the finished card, kept on disk for the
        # cover image and for anything that wants a still.
        stages = [render_stages(spec, REEL, i, len(slides)) for i, spec in enumerate(slides, 1)]
        frames_dir = out_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        for i, slide_stages in enumerate(stages, 1):
            path = frames_dir / f"frame-{i:02d}.png"
            slide_stages[-1].save(path, "PNG", optimize=True)
            frames.append(path)
        narrations = [s.get("narration") for s in slides]
        intro = generate_hook(content, out_dir / "veo-hook.mp4") if allow_veo else None
        info = build_reel(frames, narrations, out_dir / "reel.mp4", language=content.get("language", "english"),
                          max_seconds=schedule()["reel"]["max_seconds"], stages=stages, intro=intro)
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
        film = None
        if fmt == "film":
            from .story import choose_angle, choose_persona, choose_story

            story = choose_story(history)
            angle, angle_text = choose_angle(history, story)
            persona = choose_persona(history)
            film = {"story": story, "persona": persona, "angle": angle, "angle_text": angle_text}
            print(f"[story] {story['id']} | angle {angle} | persona {persona['id']}")
        plan = plan_post(llm, history, fmt, language, topic, film=film)
        if film:
            plan.update({"story": film["story"]["id"], "angle": film["angle"], "persona": film["persona"]["id"],
                         "_film": film})
        print(f"[plan] {plan.get('pillar')} | {plan.get('language')} | {plan.get('topic')}")
        # Some topics cannot be written inside the positioning rules at all: the screen-reading
        # feature, for instance, needs words the guard rejects, so every round fails. That is a
        # reason to write about something else, not a reason to publish nothing today.
        content = notes = None
        tried: list[str] = []
        for attempt in range(3):
            try:
                content, notes = produce(llm, plan, fmt)
                break
            except RuntimeError as exc:
                tried.append(str(plan.get("topic")))
                print(f"[plan] topic {plan.get('topic')!r} could not be written: {exc}")
                if attempt == 2 or topic:
                    raise
                plan = plan_post(llm, history, fmt, language, None, avoid_topics=tried, film=film)
                if film:
                    plan.update({"story": film["story"]["id"], "angle": film["angle"],
                                 "persona": film["persona"]["id"], "_film": film})
                print(f"[plan] retrying with {plan.get('pillar')} | {plan.get('topic')}")
        if tried:
            notes.insert(0, "abandoned topics: " + "; ".join(tried))
        notes.append(f"gemini calls: {llm.calls}")
    run_dir = pathlib.Path(out_dir) if out_dir else OUT / (now_ist().strftime("%Y%m%d-%H%M") + "-" + fmt)
    run_dir.mkdir(parents=True, exist_ok=True)
    media = render_media(content, fmt, run_dir, allow_veo=not sample, plan=plan, history=history)
    plan.pop("_film", None)
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
    """Public URLs for Instagram to fetch: Cloudinary, the public repo's media branch, or, for
    photos only, Facebook's own copy.

    The Facebook fallback deliberately does not cover video. Facebook re-encodes an uploaded reel
    with HE-AAC audio, and Instagram's Reels API accepts only AAC-LC, so it rejects Facebook's copy
    with error 2207076 however long you wait. Photos come back byte-identical enough to work.
    """
    from .publish import media_host

    if settings.cloudinary_url:
        return media_host.host([pathlib.Path(f) for f in files], settings)
    if media_host.repo_is_public():
        return media_host.host([pathlib.Path(f) for f in files], settings)
    if fmt in ("reel", "film"):
        raise RuntimeError(
            "Instagram needs a public URL for the video file itself. Facebook's copy cannot be reused "
            "for reels: Facebook re-encodes the audio to HE-AAC and Instagram only accepts AAC-LC. "
            "Fix it once by making this repo public, or by setting CLOUDINARY_URL to a free Cloudinary "
            "account. Images are unaffected.")
    if meta is not None and outcome["results"].get("facebook"):
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
    files = [media["video"]] if fmt in ("reel", "film") else list(media["images"])
    meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id,
                settings.graph_version) if settings.has_meta else None
    for platform in order:
        try:
            if platform == "facebook":
                if not meta:
                    raise RuntimeError("META_PAGE_ID and META_PAGE_ACCESS_TOKEN are not set")
                if fmt in ("reel", "film"):
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
                if fmt in ("reel", "film"):
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
        "story": (manifest.get("plan") or {}).get("story"),
        "angle": (manifest.get("plan") or {}).get("angle"),
        "persona": (manifest.get("plan") or {}).get("persona"),
        "veo_seconds": float((manifest.get("media") or {}).get("veo_seconds") or 0.0),
        "mode": (manifest.get("media") or {}).get("mode"),
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
