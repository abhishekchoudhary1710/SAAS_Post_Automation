"""One run, end to end: plan -> write -> review -> render -> publish -> remember."""

from __future__ import annotations

import os
import pathlib
import re
from difflib import SequenceMatcher

from PIL import Image

from .config import OUT, ROOT, SAMPLES, VIDEO_FORMATS, Settings, brand, load_json, now_ist, product, product_of, save_json, schedule
from .copywriter import produce, validate
from .history import History
from .llm import Gemini, LLMError
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


def _youtube_tags(content: dict, limit: int = 12) -> list[str]:
    """This post's tags, topped up from the brand pool.

    YouTube indexes description hashtags for search and shows the first three above the title, so
    unused slots are wasted reach. Instagram is the opposite and stays at five: see _hashtags_note.
    Past fifteen YouTube ignores every hashtag on the video, so the limit stays under it.
    """
    from .story import hashtag_bank
    bank = hashtag_bank()
    tags = _merged_tags(content, limit)
    seen = {t.lower() for t in tags}
    # youtube_topup is ordered by evidence from the competitor-reel audit; the tiers follow as a
    # reserve. Only tags that are true of any post: an employer or exam tag on an unrelated post is
    # a lie, which is the same reason pick_tags filters the specific tier when nothing matched.
    pool = list(bank.get("youtube_topup") or [])
    pool += [r["tag"] for r in bank["specific"] if r.get("general", True)]
    pool += [r["tag"] for r in bank["mid"]] + [r["tag"] for r in bank["broad"]]
    for tag in pool:
        if len(tags) >= limit:
            break
        if tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tags


def engagement_question(plan: dict, content: dict) -> str:
    """One question per post, rotated by the post id, so a viewer has something to answer."""
    import zlib
    questions = [str(q) for q in (brand().get("engagement_questions") or []) if str(q).strip()]
    if not questions:
        return ""
    seed = str(plan.get("campaign_id") or plan.get("id") or content.get("hook") or content.get("topic") or "")
    return questions[zlib.crc32(seed.encode("utf-8")) % len(questions)]


def compose_captions(content: dict, fmt: str, plan: dict) -> dict:
    from urllib.parse import urlencode
    b = brand()
    # The three products have three homes. A Prep Sarthi post that sent people to the
    # Windows app's download page would waste the click, so the link, the call to
    # action and the block at the end all come from the product being sold.
    pid = product_of(plan if (plan.get("product") or plan.get("pillar")) else content)
    prod = product(pid)
    site = prod["site"].rstrip("/")
    cta_lines = prod["cta_lines"]
    product_block = prod["product_block"]

    def link(platform: str) -> str:
        campaign = plan.get('campaign_id')
        suffix = ('&' + urlencode({'utm_content': campaign})) if campaign else ''
        return f"{site}/?{b['utm'].format(platform=platform)}" + suffix

    caption = str(content.get("caption") or "").strip()
    guide = plan.get("guide_link") if isinstance(plan.get("guide_link"), str) else None
    question = engagement_question(plan, content)
    if question:
        caption += "\n\n" + question
    # Instagram captions and YouTube Shorts descriptions have non-clickable links. Both point
    # people to the matching profile link; tagged URLs remain for copy/paste and attribution.
    # Every post ends on the umbrella name, whichever of the three it sold (owner's
    # decision, 24 Sep 2026). A stranger who sees one Prep Sarthi reel has no reason to
    # remember "Prep Sarthi" a week later, but "Interview Sarthi" is the name all three
    # live under and the one worth searching for. It goes last, after the product's own
    # call to action, so it never competes with the click this post is asking for.
    signoff = str(b.get("signoff") or "").strip()
    instagram = caption + "\n\n" + cta_lines["instagram"]
    if signoff:
        instagram += "\n" + signoff
    instagram += "\n\n" + " ".join(_merged_tags(content, 5))
    facebook = caption + "\n\n" + cta_lines["facebook"] + " " + link("facebook")
    if guide:
        facebook += "\nFull guide: " + guide
    facebook += "\n\n" + product_block
    if signoff:
        facebook += "\n\n" + signoff
    facebook += "\n\n" + " ".join(_merged_tags(content, 3))
    youtube = None
    if fmt in VIDEO_FORMATS:
        reel = content.get("reel") or {}
        title = str(reel.get("youtube_title") or content.get("hook") or content.get("topic") or "Interview tip").strip()
        if "#shorts" not in title.lower():
            title = title[:92].rstrip(" .,") + " #Shorts"
        # A Short shows only the opening lines before "more". Lead with the profile CTA.
        description = cta_lines["youtube"] + " " + link("youtube")
        description += "\n\n" + str(reel.get("youtube_description") or caption).strip()
        if question and question not in description:
            description += "\n\n" + question
        description += "\n\n" + product_block
        if guide:
            description += "\nGuide: " + guide
        if pid == "interview_sarthi":
            description += "\n\nWindows app on the Microsoft Store: " + b["store_url"]
        description += "\nSite: " + link("youtube")
        if signoff:
            description += "\n" + signoff
        # First three show above the title on a Short, so the specific ones lead.
        description += "\n\n" + " ".join(_youtube_tags(content))
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
        # Veo's extension returns the whole clip, base plus new seconds, so an extended beat is
        # played from where the beats before it ended.
        offsets, elapsed = [], 0.0
        for p in prompts:
            offsets.append(elapsed if p.get("kind") == "extend" else 0.0)
            elapsed += float(p.get("seconds", 8))
        info = build_film(clips, [b.get("narration", "") for b in beats], cards, out_dir / "reel.mp4",
                          language=content.get("language", "english"),
                          max_seconds=schedule().get("film", {}).get("max_seconds", 34), offsets=offsets)
        cover = out_dir / "cover.jpg"
        # 2.5 s in: the question line has arrived, so the thumbnail says what the reel is about
        _first_frame(out_dir / "reel.mp4", cover, at=2.5)
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


def _render_demo(content: dict, out_dir: pathlib.Path) -> dict:
    """The rendered live demo: no footage, no gamble, the same look every day."""
    from .render.demo import build_demo

    info = build_demo(content, out_dir / "reel.mp4", language="english",
                      max_seconds=schedule().get("demo", {}).get("max_seconds", 32))
    return {"video": info["path"], "cover": info["cover"], "frames": [], "seconds": info["seconds"],
            "voiced": True, "music": None, "veo_seconds": 0.0, "voice": info["voice"], "mode": "demo"}


def _first_frame(video: pathlib.Path, out: pathlib.Path, at: float = 0.5) -> None:
    import subprocess

    from .render.reel import ffmpeg_exe

    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                    "-q:v", "2", str(out)], capture_output=True, timeout=120)


def _library_intro(history, plan: dict | None) -> pathlib.Path | None:
    """A verified clip from the motion library, so a busy Veo still leaves an opening."""
    try:
        from .creative import select_visual
        visual = select_visual(history)
        path = (ROOT / visual["clip"]).resolve()
        if not path.is_file():
            return None
        if plan is not None:
            plan["visual_clip"] = visual["clip_id"]
            plan.setdefault("visual_theme", visual.get("theme"))
        print(f"[reel] opening on the library clip {visual['clip_id']}", flush=True)
        return path
    except Exception as exc:  # noqa: BLE001 - an opening is a nicety, the post is not
        print(f"[reel] no library opening available ({type(exc).__name__}); "
              "building without one", flush=True)
        return None


# Four seconds of cold open before the first card. The opening seconds are where a viewer
# decides whether to stay, but footage carries no words, so it stays a beat rather than a scene.
INTRO_SECONDS = 4


def render_media(content: dict, fmt: str, out_dir: pathlib.Path, allow_veo: bool = True, plan: dict | None = None,
                 history=None) -> dict:
    if fmt == "demo":
        return _render_demo(content, out_dir)
    if fmt == "film":
        return _render_film(content, out_dir, plan or {}, history)
    if fmt in VIDEO_FORMATS:
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
        # A fresh cold open for every reel, not only the sales ones (owner's decision,
        # 24 Sep 2026). This used to call generate_hook, which belongs to the full Veo film
        # that has been switched off since 12 Sep, so a card reel opened on nothing at all
        # while every sales reel got new footage. generate_opening is the budgeted path the
        # sales reels already use: it obeys the monthly and total caps and returns None,
        # never an error, so a Veo problem still cannot cost the post.
        intro, opening = None, None
        # budget_stop reads history.posts to enforce the caps, so without a history there is
        # no way to know what has already been spent and no business generating more.
        if allow_veo and history is not None:
            from .render.veo_opening import CLIP_ID, generate_opening
            seed = {"id": content.get("topic") or (plan or {}).get("topic"),
                    "question": content.get("hook"),
                    "audience": (plan or {}).get("audience")}
            opening = generate_opening(seed, history, out_dir, seconds=INTRO_SECONDS)
            if opening:
                intro = pathlib.Path(opening["clip"])
                # Both are what budget_stop counts, so an opening that is not recorded here
                # is an opening the caps cannot see and the credit pays for twice over.
                if plan is not None:
                    plan["visual_clip"] = CLIP_ID
            else:
                # Veo said no, and for a card reel there was nothing behind it: the old
                # generate_hook is switched off, so the reel opened on nothing at all. The
                # sales reels have always had verified library footage to fall back on, so
                # use the same. Every reel opens on something; only "veo-fresh" is charged.
                intro = generate_hook(content, out_dir / "veo-hook.mp4") or _library_intro(history, plan)
        elif allow_veo:
            intro = generate_hook(content, out_dir / "veo-hook.mp4")
        info = build_reel(frames, narrations, out_dir / "reel.mp4", language=content.get("language", "english"),
                          max_seconds=schedule()["reel"]["max_seconds"], stages=stages, intro=intro,
                          intro_seconds=INTRO_SECONDS)
        cover = out_dir / "cover.jpg"
        Image.open(frames[0]).convert("RGB").save(cover, "JPEG", quality=90)
        return {"video": str(out_dir / "reel.mp4"), "cover": str(cover), "frames": [str(p) for p in frames],
                "seconds": info["seconds"], "voiced": info["voiced"], "music": info["music"],
                "veo_seconds": float(opening["seconds"]) if opening else 0.0,
                "opening": "veo" if opening else "none"}
    images = render_slides(content["slides"], FEED, out_dir, "slide", "jpg")
    return {"images": [str(p) for p in images]}


def create(settings: Settings, fmt: str | None = None, topic: str | None = None, language: str | None = None,
           out_dir: str | pathlib.Path | None = None, sample: bool = False, variant: str = "auto",
           product_id: str | None = None) -> dict:
    history = History()
    fmt = decide_format(fmt)
    if fmt in ('sales', 'image'):
        from .campaign import create_sales
        return create_sales(settings, out_dir=out_dir, topic=topic, sample=sample, variant=variant, still=fmt == "image")
    if not sample:
        # A reel or carousel needs the model for every word it contains, so when the writing
        # is unavailable there is nothing to render. Until 24 Sep 2026 that ended the run and
        # the slot published nothing: every failure between 21 and 24 Sep was one of these.
        # The sales path has a hand-written script, its own rotation and the same quality gate,
        # so it can always produce a finished reel. Owner's decision, 24 Sep 2026: a plainer
        # post is better than no post. The substitution is recorded so it never passes silently.
        try:
            return _create_written(settings, history, fmt, topic, language, out_dir, variant, product_id)
        except (LLMError, RuntimeError, ValueError) as exc:
            if product_id and product_id != "interview_sarthi":
                # A Prep or Apply slot must never silently publish a Windows-app ad.
                raise RuntimeError(f"{product_id} {fmt} could not be written; no other product was substituted") from exc
            from .campaign import create_sales
            print(f"[create] {fmt} could not be written ({type(exc).__name__}: {str(exc)[:120]}); "
                  "falling back to the authored sales reel so the slot still posts", flush=True)
            manifest = create_sales(settings, out_dir=out_dir, topic=None, sample=False,
                                    variant="standard", still=False)
            manifest["substituted_for"] = fmt
            manifest.setdefault("notes", []).append(
                f"substituted for a {fmt}: {type(exc).__name__}")
            return manifest
    return _create_written(settings, history, fmt, topic, language, out_dir, variant, product_id,
                           sample=True)


def _duplicate_reason(content: dict, plan: dict, history: History) -> str | None:
    """Catch near-identical briefs before rendering; compare only within the same product."""
    def clean(value: object) -> str:
        return " ".join(re.findall(r"\w+", str(value or "").casefold()))

    pid = plan.get("product") or product_of(plan)
    topic = clean(content.get("topic") or plan.get("topic"))
    hook = clean(content.get("hook"))
    for old in history.recent(300):
        if (old.get("product") or product_of(old)) != pid:
            continue
        old_topic, old_hook = clean(old.get("topic")), clean(old.get("hook"))
        if topic and old_topic and SequenceMatcher(None, topic, old_topic).ratio() >= 0.86:
            return f"topic resembles {old.get('id')}: {old.get('topic')}"
        if hook and old_hook and SequenceMatcher(None, hook, old_hook).ratio() >= 0.88:
            return f"hook resembles {old.get('id')}: {old.get('hook')}"
    return None


def _create_written(settings: Settings, history, fmt: str, topic, language, out_dir, variant,
                    product_id, sample: bool = False) -> dict:
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
        plan = plan_post(llm, history, fmt, language, topic, product_id=product_id, film=film)
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
                duplicate = _duplicate_reason(content, plan, history)
                if duplicate:
                    raise RuntimeError(f"duplicate concept: {duplicate}")
                break
            except RuntimeError as exc:
                tried.append(str(plan.get("topic")))
                print(f"[plan] topic {plan.get('topic')!r} could not be written: {exc}")
                if attempt == 2 or topic:
                    raise
                plan = plan_post(llm, history, fmt, language, None, avoid_topics=tried, product_id=product_id, film=film)
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
    if fmt in VIDEO_FORMATS:
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
    from .quality import require_publishable
    require_publishable(manifest)
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
    # Resume a partially completed run without re-posting its successful platforms.
    receipt_path = pathlib.Path(manifest['media'].get('video') or manifest['media']['images'][0]).parent / 'published.json'
    if receipt_path.exists():
        saved = load_json(receipt_path)
        if saved.get('id') != manifest['id']:
            raise RuntimeError('Publication receipt belongs to a different post')
        outcome['results'].update(saved.get('results', {}))
    media, captions = manifest["media"], manifest["captions"]
    files = [media["video"]] if fmt in VIDEO_FORMATS else list(media["images"])
    meta = Meta(settings.meta_page_id, settings.meta_page_token, settings.ig_user_id,
                settings.graph_version) if settings.has_meta else None
    for platform in order:
        if platform in outcome['results']:
            continue
        try:
            if platform == "facebook":
                if not meta:
                    raise RuntimeError("META_PAGE_ID and META_PAGE_ACCESS_TOKEN are not set")
                if fmt in VIDEO_FORMATS:
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
                if fmt == 'sales':
                    media_id = meta.ig_reel_file(media['video'], captions['instagram'])
                else:
                    urls = _instagram_urls(fmt, files, settings, meta, outcome)
                    print(f"[publish] Instagram will fetch {len(urls)} file(s)")
                if fmt in VIDEO_FORMATS and fmt != 'sales':
                    media_id = meta.ig_reel(urls[media["video"]], captions["instagram"])
                elif fmt == "carousel":
                    media_id = meta.ig_carousel([urls[p] for p in media["images"]], captions["instagram"])
                elif fmt not in VIDEO_FORMATS:
                    media_id = meta.ig_image(urls[media["images"][0]], captions["instagram"])
                outcome["results"]["instagram"] = {"id": media_id, "url": meta.ig_permalink(media_id)}
            elif platform == "youtube":
                if fmt not in VIDEO_FORMATS:
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
        save_json(receipt_path, {'id': manifest['id'], **outcome})
    return outcome


# ----------------------------------------------------------------------------- remember + report
def remember(manifest: dict, outcome: dict) -> None:
    if manifest.get("sample") or outcome.get("dry_run") or not outcome.get("results"):
        return
    content = manifest["content"]
    history = History()
    history.add({
        "id": manifest["id"], "format": manifest["format"], "pillar": content.get("pillar"),
        "slot": os.environ.get("SLOT"), "series": os.environ.get("CONTENT_SERIES"),
        # Which of the three products this post sold, so the split can be checked from history.
        "product": content.get("product") or "interview_sarthi",
        "topic": content.get("topic"), "language": content.get("language"), "hook": content.get("hook"),
        "posted": outcome.get("results", {}), "errors": outcome.get("errors", {}),
        "story": (manifest.get("plan") or {}).get("story"),
        "angle": (manifest.get("plan") or {}).get("angle"),
        "persona": (manifest.get("plan") or {}).get("persona"),
        "veo_seconds": float((manifest.get("media") or {}).get("veo_seconds") or 0.0),
        "mode": (manifest.get("media") or {}).get("mode"),
        "scenario": (manifest.get('plan') or {}).get('scenario'),
        "seed_scenario": (manifest.get('plan') or {}).get('seed_scenario'),
        "visual_clip": (manifest.get('plan') or {}).get('visual_clip'),
        "visual_theme": (manifest.get('plan') or {}).get('visual_theme'),
        "variant": (manifest.get('plan') or {}).get('variant'),
        "hook_index": (manifest.get('plan') or {}).get('hook_index'),
        # "authored" means the model draft was rejected and the template shipped verbatim.
        "script_source": (manifest.get('plan') or {}).get('script_source'),
        "creative_hash": (manifest.get('plan') or {}).get('creative_hash'),
        "campaign_id": (manifest.get('plan') or {}).get('campaign_id'),
        "quality_passed": (manifest.get('quality') or {}).get('passed'),
        # Set when the writing was unavailable and this sales reel went out in place of a
        # reel or carousel. Without it the substitution is invisible in history and the day
        # looks like a normal eight-post day at the wrong product mix.
        "substituted_for": manifest.get("substituted_for"),
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
