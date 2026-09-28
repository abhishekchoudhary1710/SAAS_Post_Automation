"""LinkedIn Page content, previews, durable publication reservations and measured results.

No model or paid media generation. Facts and authored lessons live in knowledge/linkedin.json.
The workflow saves a reservation to GitHub BEFORE submitting to Buffer. An uncertain submission
is never retried automatically. Buffer accepting a post is distinct from LinkedIn publishing it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import CONTENT, KNOWLEDGE, OUT, Settings, load_json, now_ist, save_json

STATE = CONTENT / "linkedin_growth.json"
CONFIG = KNOWLEDGE / "linkedin.json"


def state_read(path=STATE):
    return load_json(path) if path.exists() else {"posts": []}


def tracked_link(url, creative):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ("interviewsarthi.com", "apply.interviewsarthi.com"):
        raise ValueError("LinkedIn CTA must lead to a Sarthi product")
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    query += list({"utm_source": "linkedin", "utm_medium": "social",
                   "utm_campaign": "linkedin_product_growth", "utm_content": creative}.items())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def choose(day, state, config):
    if day.weekday() >= 5:
        return None
    series = config["weekday_series"][day.weekday()]
    if series == "jobs":
        return {"id": "jobs", "series": "jobs"}
    prior = {p["topic"]: p["day"] for p in sorted(state["posts"], key=lambda p: p["day"])}
    pool = [p for p in config["posts"] if p["series"] == series]
    cutoff = (day - dt.timedelta(days=config["minimum_repeat_days"])).isoformat()
    pool = [p for p in pool if prior.get(p["id"], "") <= cutoff]
    if not pool:
        raise RuntimeError("No fresh LinkedIn topic; extend knowledge/linkedin.json before posting")
    return min(pool, key=lambda p: (prior.get(p["id"], ""), config["posts"].index(p)))


def compose(day, seed, config, item=None):
    series = seed["series"]
    prod = config["products"]["apply" if series == "jobs" else series]
    topic = seed["id"] if item is None else "jobs-" + re.sub(r"[^a-z0-9]+", "-", item["id"].lower()).strip("-")
    creative = f"li-{day:%Y%m%d}-{topic}"
    if item:
        from .joblist import headline
        hook = headline(item) + "."
        companies = ", ".join(item["companies"][:4])
        skills = ", ".join(f"{s} ({p}%)" for s, p in item.get("skills", [])[:4])
        body = f"In this ApplySarthi job list, recent listings include {companies}."
        if skills:
            body += f"\n\nSkills appearing in the list: {skills}. These percentages describe this list, not the whole job market."
        body += (f"\n\n{item['total']:,} open listings in this collection when checked on {day:%d %b %Y}. "
                 "Check each employer's page for current availability, location and eligibility. "
                 "Remote does not necessarily mean work from any country."
                 "\n\nBrowse on ApplySarthi free, with no account. Each job links to the employer's application page.")
        url, cta = item["url"], "See these jobs on ApplySarthi:"
        title, points = hook, ["Fresh listings from our job feed", "Check the employer's requirements", "Browse free, no account", "Apply on the employer's own page"]
        offer = ""
    else:
        hook, body = seed["hook"], seed["body"]
        title, points = seed["card_title"], seed["points"]
        offer, url, cta = prod["offer"], prod["url"], prod["cta"]
    link = tracked_link(url, creative)
    text = "\n\n".join(x for x in (hook, body, offer, cta + "\n" + link, " ".join(prod["tags"])) if x)
    document = series == "prep"
    slides = [{"type": "points", "title": title, "points": points, "tag": prod["name"], "product": prod["id"]}]
    if document:
        slides = [
            {"type": "hook", "title": hook, "subtitle": "A practical answer framework. Try it with your own CV.", "tag": prod["name"]},
            slides[0],
            {"type": "product", "title": "Practise. Read your feedback. Try again.", "image": prod["image"],
             "caption": "Actual product interface. Displayed answers and scores are illustrative."},
            {"type": "cta", "title": "Try Prep Sarthi free", "subtitle": "7-minute spoken mock interview. No card, account or API key for the demo.",
             "show_pricing": False, "note": "Open the clickable product link in this post. interviewsarthi.com/prep/"},
        ]
    elif series == "live":
        slides = [{"type": "product", "title": title, "image": prod["image"],
                   "caption": "Actual product interface with illustrative content. Try 30 minutes free on Windows. Link in the post.",
                   "tag": prod["name"]}]
    for slide in slides:
        slide.update(product=prod["id"], market=config["market"], site=prod["url"], footer_hint="Link in post")
    manifest = {"id": creative, "day": day.isoformat(), "topic": topic, "series": series,
                "product": prod["id"], "format": "document" if document else "image",
                "hook": hook, "text": text, "url": link, "slides": slides,
                "source": {"url": item["url"], "checked": day.isoformat()} if item else str(CONFIG.relative_to(CONFIG.parent.parent))}
    validate(manifest)
    return manifest


def validate(post):
    text = post["text"]
    if len(text) > 2900:
        raise ValueError("LinkedIn post exceeds the safe character budget")
    if re.findall(r"https?://\S+", text) != [post["url"]]:
        raise ValueError("Use exactly one clickable product CTA")
    tracked_link(post["url"], post["id"])
    if re.search(r"link in bio|comment ['\"]?(yes|interested)|guaranteed|100%|limited.time offer", text, re.I):
        raise ValueError("Unsupported promise or engagement bait")
    if "utm_content=" + post["id"] not in post["url"]:
        raise ValueError("Missing creative attribution")


def render(post, folder):
    from PIL import Image
    from .render.cards import FEED, render_slides
    folder.mkdir(parents=True, exist_ok=True)
    images = render_slides(post["slides"], FEED, folder, "linkedin", "jpg")
    post["image"] = str(images[0])
    if post["format"] == "document":
        pages = [Image.open(p).convert("RGB") for p in images]
        pdf = folder / "linkedin.pdf"
        try:
            pages[0].save(pdf, "PDF", save_all=True, append_images=pages[1:], resolution=144)
        finally:
            for page in pages:
                page.close()
        post["document"] = str(pdf)
    (folder / "caption.txt").write_text(post["text"] + "\n", encoding="utf-8")
    save_json(folder / "post.json", post)
    return post


def fresh_jobs(state, day):
    import requests
    from .joblist import FEED_URL, _usable
    response = requests.get(FEED_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    built = dt.datetime.fromisoformat(str(data.get("built_at") or "").replace("Z", "+00:00"))
    if built.tzinfo is None:  # SQLite datetime('now') in the feed is UTC.
        built = built.replace(tzinfo=dt.timezone.utc)
    age = now_ist() - built
    if not dt.timedelta(minutes=-5) <= age <= dt.timedelta(hours=24):
        raise RuntimeError("Job feed is stale; no current job counts can be advertised")
    recent = {p["topic"] for p in state["posts"] if p["day"] > (day - dt.timedelta(days=28)).isoformat()}
    pool = [x for x in data.get("lists", []) if _usable(x) and
            "jobs-" + re.sub(r"[^a-z0-9]+", "-", x["id"].lower()).strip("-") not in recent]
    if not pool:
        raise RuntimeError("No fresh job list; do not recycle an old count")
    return max(pool, key=lambda x: x["new_7d"])


def prepare(day, settings, dry_run=False, state_path=STATE, folder=None):
    state, config = state_read(state_path), load_json(CONFIG)
    if not dry_run and any(p["day"] == day.isoformat() for p in state["posts"]):
        print("LinkedIn date already reserved or submitted; no duplicate created.")
        return None
    seed = choose(day, state, config)
    if not seed:
        print("No LinkedIn post on weekends.")
        return None
    item = fresh_jobs(state, day) if seed["series"] == "jobs" else None
    # Hosting and link validation happen before a reservation. Failures here can be retried safely.
    post = compose(day, seed, config, item)
    render(post, folder or OUT / "linkedin-current")
    if dry_run:
        return post
    if not settings.buffer_api_key:
        raise RuntimeError("BUFFER_API_KEY is required for the LinkedIn Page campaign")
    from .publish import buffer
    buffer.channel_id(settings)
    check_link(post["url"])
    post["owner_run"] = os.environ.get("GITHUB_RUN_ID", "local")
    entry = {k: post[k] for k in ("id", "day", "topic", "series", "product", "format", "hook", "url", "owner_run")}
    entry["status"] = "reserved"
    state["posts"].append(entry)
    save_json(state_path, state)
    save_json((folder or OUT / "linkedin-current") / "post.json", post)
    return post


def check_link(url):
    import requests
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    before, after = urlsplit(url), urlsplit(response.url)
    if after.scheme != "https" or after.hostname != before.hostname or after.path.rstrip("/") != before.path.rstrip("/"):
        raise RuntimeError("Product link redirected away from its intended landing page")
    before_q, after_q = dict(parse_qsl(before.query)), dict(parse_qsl(after.query))
    if any(after_q.get(k) != v for k, v in before_q.items() if k.startswith("utm_")):
        raise RuntimeError("Product redirect dropped campaign tracking")


def publish_prepared(settings, folder=None, state_path=STATE):
    from .publish import buffer, media_host
    folder = folder or OUT / "linkedin-current"
    post, state = load_json(folder / "post.json"), state_read(state_path)
    if post.get("sample"):
        raise RuntimeError("Preview samples cannot be published")
    validate(post)
    entry = next(p for p in state["posts"] if p["id"] == post["id"])
    if settings.dry_run:
        return
    if entry["status"] != "reserved" or entry["owner_run"] != os.environ.get("GITHUB_RUN_ID", "local"):
        raise RuntimeError("This run does not own an unsubmitted LinkedIn reservation")
    files = [pathlib.Path(post["image"])]
    if post.get("document"):
        files.append(pathlib.Path(post["document"]))
    # Keep these assets separate from the many daily reels. Buffer can fetch asynchronously.
    urls = media_host.host(files, settings) if settings.cloudinary_url else media_host._github_branch(files, branch="linkedin-media")
    entry["status"] = "submitting"
    save_json(state_path, state)
    try:
        post_id = buffer.post(settings, post["text"], urls[post["image"]],
                              document_url=urls.get(post.get("document")), title=post["hook"])
        entry.update(buffer_id=post_id, status="accepted", accepted_at=now_ist().isoformat())
    except Exception:
        entry["status"] = "unknown"
        raise
    finally:
        save_json(state_path, state)
    print("Buffer accepted " + post_id + ". Publication status is checked by the daily report.")


def refresh(settings, state_path=STATE):
    from .publish import buffer
    state = state_read(state_path)
    warning = buffer.expiry_warning(settings)
    if warning:
        state["credential_warning"] = warning
    else:
        state.pop("credential_warning", None)
    if settings.buffer_api_key:
        today = now_ist().date()
        for entry in state["posts"]:
            if not entry.get("buffer_id") or (today - dt.date.fromisoformat(entry["day"])).days > 30:
                continue
            try:
                result = buffer.inspect_post(settings, entry["buffer_id"])
                entry["status"] = result["status"]
                entry["post_url"] = result.get("externalLink")
                entry["metrics"] = {m["type"]: m["value"] for m in (result.get("metrics") or [])
                                    if m.get("value") is not None} if result.get("metricsUpdatedAt") else {}
                entry["metrics_updated_at"] = result.get("metricsUpdatedAt")
                entry["checked_at"] = now_ist().isoformat()
                age = (today - dt.date.fromisoformat(entry["day"])).days
                if 7 <= age <= 9 and entry["metrics"]:
                    entry.setdefault("seven_day_metrics", {"observed_at": entry["checked_at"],
                                                            "age_days": age, **entry["metrics"]})
                entry.pop("metrics_error", None)
            except Exception as exc:
                # Do not turn unavailable analytics into a fabricated zero or retry a post.
                entry["metrics_error"] = type(exc).__name__
    save_json(state_path, state)
    return state


def report(state):
    lines = ["# LinkedIn product growth", "", "Buffer acceptance is not proof of publication. Missing metrics are unknown.", "",
             "| Date | Product / topic | Status | Impressions | Clicks* |", "|---|---|---|---:|---:|"]
    for p in state["posts"][-30:]:
        m = p.get("metrics", {})
        lines.append(f"| {p['day']} | {p['topic']} | {p['status']} | {m.get('impressions', 'unknown')} | {m.get('clicks', 'unknown')} |")
    if state.get("credential_warning"):
        lines += ["", state["credential_warning"]]
    unresolved = [p for p in state["posts"] if p["status"] in ("reserved", "submitting", "unknown", "error", "needs_approval")]
    if unresolved:
        lines += ["", "Action needed in Buffer: " + ", ".join(p["id"] + " (" + p["status"] + ")" for p in unresolved),
                  "Inspect the Page and Buffer before clearing a reservation. These posts are not retried automatically."]
    lines += ["", "*Platform clicks can include clicks other than outbound website visits. Metrics may lag by a day.",
              "Buffer may report zero for metrics the network did not supply; zeros are not proof of no activity.",
              "", "In GA4, filter Session campaign = linkedin_product_growth; compare Session manual ad content with each li- creative ID.",
              "Review engaged sessions, product starts, checkout and verified purchases separately by product. "
              "Sales attribution is not collected by this Buffer report. Cross-device and Store purchases can be unattributed.",
              "", "After four weeks compare useful visits and product starts per post, not likes alone. "
              "Treat small samples as directional; do not automatically promote a winner from a few posts.", ""]
    lines += ["| Topic | Age at snapshot | 7-day impressions |", "|---|---:|---:|"]
    for p in state["posts"][-30:]:
        snap = p.get("seven_day_metrics", {})
        if snap:
            lines.append(f"| {p['topic']} | {snap['age_days']} days | {snap.get('impressions', 'unknown')} |")
    return "\n".join(lines)


def preview(start, days, folder):
    from .joblist import SAMPLE
    config, state, posts = load_json(CONFIG), {"posts": []}, []
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        seed = choose(day, state, config)
        if seed is None:
            continue
        post = compose(day, seed, config, SAMPLE if seed["series"] == "jobs" else None)
        post["sample"] = True
        render(post, folder / post["id"])
        state["posts"].append(post)
        posts.append(post)
    cards = []
    for p in posts:
        path = html.escape(p["id"])
        cards.append(f'<article><h2>{p["day"]} · {p["format"]} · {p["product"]}</h2>'
                     f'<img loading="lazy" src="{path}/linkedin-01.jpg"><pre>{html.escape(p["text"])}</pre>'
                     + (f'<p><a href="{path}/linkedin.pdf">Open the 4-page document</a></p>' if p.get("document") else '') + '</article>')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>LinkedIn campaign preview</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:16px;background:#f5f6fa;color:#14213d}'
        'article{background:white;padding:24px;margin:24px 0;border-radius:16px;display:flow-root}img{width:320px;max-width:100%;float:left;margin:0 24px 16px 0}'
        'pre{font:16px/1.6 system-ui;white-space:pre-wrap}h2{font-size:18px}</style><h1>LinkedIn product campaign</h1>'
        '<p>Preview only. Wednesday jobs use a labelled sample from 26 September 2026; live runs fetch current data.</p>' + ''.join(cards), encoding="utf-8")
    return posts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "prepare", "publish", "report"))
    parser.add_argument("--date", type=dt.date.fromisoformat, default=now_ist().date())
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--out", type=pathlib.Path, default=OUT / "linkedin-current")
    parser.add_argument("--dry-run", action="store_true")
    args, settings = parser.parse_args(), Settings.from_env()
    if args.command == "preview":
        preview(args.date, args.days, args.out)
        print(args.out / "index.html")
    elif args.command == "prepare":
        post = prepare(args.date, settings, args.dry_run or settings.dry_run, folder=args.out)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
                handle.write(f"ready={'true' if post else 'false'}\n")
    elif args.command == "publish":
        publish_prepared(settings, args.out)
    else:
        result = report(refresh(settings))
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "scorecard.md").write_text(result, encoding="utf-8")
        print(result)


if __name__ == "__main__":
    main()
