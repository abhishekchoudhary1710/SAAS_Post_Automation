"""The daily jobs post: one of ApplySarthi's job lists as a short reel, "67 new Python jobs in Hyderabad
this week", who is hiring, what they ask for, where to see them, and Prep Sarthi for the interview.

Owner's decision, 26 Sep 2026: its own slot ("jobs", 13:37 IST), on Instagram and YouTube (Facebook is
off), in addition to the ten product slots, not instead of one. Every number and name comes from
ApplySarthi's feed (apply.interviewsarthi.com/api/public/job-lists, rebuilt hourly from its database),
and the words around them are fixed here: no model writes this post, so it cannot state a count or an
employer the data does not hold. The profile link stays interviewsarthi.com; the post tells people to
tap Find jobs there.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import urllib.request

from .config import OUT, Settings, now_ist, save_json
from .history import History

FEED_URL = os.environ.get("JOBLIST_FEED_URL", "https://apply.interviewsarthi.com/api/public/job-lists")
SERIES = "job_list"
REPEAT_DAYS = 21          # the same list (say, Python in Hyderabad) at most once in three weeks
REMOTE_EVERY = 3          # every third jobs post is a remote list; the rest are Indian cities

HASHTAG_CITY = {"Bengaluru": "#bangalorejobs", "Hyderabad": "#hyderabadjobs", "Pune": "#punejobs",
                "Mumbai": "#mumbaijobs", "Chennai": "#chennaijobs", "Delhi NCR": "#delhijobs"}


def fetch_lists(url: str = FEED_URL, timeout: int = 30) -> list[dict]:
    req = urllib.request.Request(url, headers={"user-agent": "sarthi-social-agent-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URL
        data = json.loads(resp.read().decode("utf-8"))
    lists = [x for x in data.get("lists") or [] if _usable(x)]
    if not lists:
        raise RuntimeError(f"the job-list feed at {url} has no usable lists")
    return lists


def _usable(item: dict) -> bool:
    return (isinstance(item, dict) and item.get("new_7d", 0) >= 1 and len(item.get("companies") or []) >= 3
            and str(item.get("url", "")).startswith("https://") and item.get("what") and item.get("where"))


def choose(lists: list[dict], history: History, today: dt.date | None = None) -> dict:
    """The list with the most new jobs that has not been posted in REPEAT_DAYS, remote on every
    REMOTE_EVERY-th jobs post and an Indian city otherwise; falls back to any unposted list."""
    today = today or now_ist().date()
    cutoff = (today - dt.timedelta(days=REPEAT_DAYS)).isoformat()
    ours = [p for p in history.posts if p.get("series") == SERIES]
    recent = {p.get("topic") for p in ours if str(p.get("date", ""))[:10] >= cutoff}
    fresh = [x for x in lists if x["id"] not in recent] or lists
    want_remote = (len(ours) + 1) % REMOTE_EVERY == 0
    preferred = [x for x in fresh if (x["where"] == "remote") == want_remote] or fresh
    return max(preferred, key=lambda x: (x["new_7d"], x["id"]))


def _names(items: list[str]) -> str:
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def headline(item: dict) -> str:
    what, where, n = item["what"], item["where"], item["new_7d"]
    if where == "remote":
        return f"{n} new remote {what} jobs this week"
    return f"{n} new {what} jobs in {where} this week"


def content_for(item: dict) -> dict:
    """The reel's slides, narration and caption, all from `item`."""
    title = headline(item)
    total = f"{item['total']:,}"
    companies = list(item["companies"])[:4]
    skills = [s for s, _ in item.get("skills") or []][:4]
    shares = [f"{s} ({p}%)" if i else f"{s} ({p}% of these jobs)" for i, (s, p) in enumerate((item.get("skills") or [])[:4])]
    where_tag = "#remotejobs" if item["where"] == "remote" else HASHTAG_CITY.get(item["where"], "#jobsinindia")
    what_tag = "#" + "".join(ch for ch in item["what"].lower() if ch.isalnum()) + "jobs"
    slides = [
        {"type": "hook", "product": "apply_sarthi", "tag": "Jobs this week", "kicker": "Fresh this week",
         "title": title, "subtitle": f"{total} open right now. Free to browse, no sign-up.",
         "narration": f"{title}."},
        {"type": "points", "product": "apply_sarthi", "tag": "Who is hiring", "title": "Hiring the most this week",
         "points": companies, "narration": f"Hiring the most: {_names(companies)}."},
    ]
    if shares:
        slides.append({"type": "points", "product": "apply_sarthi", "tag": "Skills",
                       "title": f"What these {item['what']} jobs ask for", "points": shares,
                       "narration": f"They ask most for {_names(skills)}."})
    slides += [
        {"type": "cta", "product": "apply_sarthi", "tag": "Apply free", "title": f"See all {total} jobs, free",
         "subtitle": "Link in bio, then tap Find jobs.", "note": "Each job opens the company's own application page.",
         "narration": f"See all {total}, free, at interview sarthi dot com. Tap Find jobs."},
        {"type": "cta", "product": "prep_sarthi", "tag": "Got the interview?", "title": "Practise it before the real one",
         "subtitle": "A spoken mock interview from your CV and this job's description, with feedback on every answer.",
         "narration": "Got the interview? Practise it first with Prep Sarthi."},
    ]
    body = f"{title}.\n\nHiring the most: {_names(companies)}."
    if skills:
        body += f"\nMost asked skills: {_names(skills)}."
    body += (f"\n\nSee all {total}, free, no sign-up: link in bio, then tap Find jobs."
             "\n\nGot the interview? Practise it first with Prep Sarthi. Free 7-minute demo, link in bio.")
    return {
        "pillar": "jobs", "product": "apply_sarthi", "language": "english",
        "market": "global" if item["where"] == "remote" else "india",
        "topic": item["id"], "hook": title, "caption": body,
        "hashtags": [what_tag, where_tag, "#jobsearch", "#hiring"],
        "slides": slides,
        "reel": {"youtube_title": title, "youtube_description": body + f"\n\nThe list: {item['url']}",
                 "youtube_tags": [item["what"] + " jobs", "jobs this week", "job search", "hiring now",
                                  "ApplySarthi", "Interview Sarthi"]},
        "source": {"feed": FEED_URL, "url": item["url"], "new_7d": item["new_7d"], "total": item["total"]},
    }


def create_joblist(settings: Settings, out_dir=None, sample: bool = False) -> dict:
    from .pipeline import compose_captions, render_media

    history = History()
    item = SAMPLE if sample else choose(fetch_lists(), history)
    print(f"[jobs] {item['id']}: {item['new_7d']} new, {item['total']} open -> {item['url']}", flush=True)
    content = content_for(item)
    run_dir = pathlib.Path(out_dir) if out_dir else OUT / (now_ist().strftime("%Y%m%d-%H%M") + "-jobs")
    run_dir.mkdir(parents=True, exist_ok=True)
    plan = {"pillar": "jobs", "product": "apply_sarthi", "topic": item["id"], "language": "english",
            "format": "reel", "market": content["market"], "campaign_id": run_dir.name, "guide_link": None}
    # No opening footage: the list is the news, and the Veo budget belongs to the product reels.
    media = render_media(content, "reel", run_dir, allow_veo=False, plan=plan, history=None)
    manifest = {"id": run_dir.name, "created_at": now_ist().isoformat(), "format": "reel", "sample": sample,
                "plan": plan, "content": content, "media": media,
                "captions": compose_captions(content, "reel", plan),
                "notes": [f"job list {item['id']} from {FEED_URL}"]}
    save_json(run_dir / "post.json", manifest)
    print(f"[create] jobs reel ready in {run_dir}")
    return manifest


# Used by --sample and the tests: a real list from 26 Sep 2026, so a sample run needs no network.
SAMPLE = {"id": "skill:python@hyderabad", "kind": "skill", "what": "Python", "where": "Hyderabad",
          "path": "/skills/python/hyderabad", "url": "https://apply.interviewsarthi.com/skills/python/hyderabad",
          "total": 321, "new_7d": 67, "companies": ["Micron", "Analog Devices", "ServiceNow", "Sanofi"],
          "skills": [["AWS", 38], ["SQL", 32], ["CI/CD", 30], ["LLMs", 21]]}
