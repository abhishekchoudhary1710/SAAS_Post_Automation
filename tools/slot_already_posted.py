"""Should a late GitHub scheduled run skip, because the outside scheduler already posted this slot?

GitHub starts scheduled workflows hours late when it is busy (3 to 7 hours in September 2026).
cron-job.org triggers the same workflow on time through workflow_dispatch, naming the slot, which
the workflow's run-name turns into the title "Post to social: <slot>".

The GitHub schedule stays as a backup. When a scheduled run finally starts, this script looks for a
dispatch run of the same slot created in the last WINDOW_HOURS. It skips when that run succeeded,
is still queued or running, or failed after publishing to at least one platform. It posts only when
the outside run failed without publishing anything, or never happened.

The partial case matters (15 Sep 2026): the 10:37 run published to Facebook and YouTube, Instagram
rejected the video, the run was marked failed, and a backup would have posted the slot a second time
on Facebook and YouTube. A failed run's platform results are committed to content/history.json by
its "Save history" step, so a post recorded while that run was running means it published.

Dry runs are titled "Post to social: <slot> (dry run)", so they never match and a test can never
cancel a real post. If the GitHub API cannot be read, the script says "do not skip": an extra post
is a smaller problem than a missing one.

Usage in the workflow: SLOT=evening GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo python tools/slot_already_posted.py
It writes skip=true or skip=false to $GITHUB_OUTPUT, and prints the reason.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

# A slot recurs every 24 hours and GitHub's delay has reached about 7 hours, so 12 hours catches
# today's dispatch run without ever matching yesterday's.
WINDOW_HOURS = 12
SLOTS = ("morning", "late-morning", "prep-morning", "midday", "jobs", "early-afternoon", "afternoon", "early-evening", "evening", "apply-night", "night")
WORKFLOW_FILE = "post.yml"
HISTORY_FILE = "content/history.json"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def title_for(slot: str) -> str:
    return f"Post to social: {slot}"


def _utc(stamp: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _post_time(post: dict) -> dt.datetime | None:
    """History dates look like "2026-09-15 10:45 IST"."""
    try:
        return dt.datetime.strptime(str(post.get("date", ""))[:16], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    except ValueError:
        return None


def published_during(run: dict, posts: list[dict]) -> bool:
    """True when history holds a post with at least one platform result recorded while this run ran.

    Runs share one concurrency group, so they never overlap: a post recorded between this run's start
    and its last update belongs to this run. run_started_at is used rather than created_at because a
    run can sit queued behind another run that posts.
    """
    start = _utc(run.get("run_started_at") or run.get("created_at")) - dt.timedelta(minutes=1)
    end = _utc(run.get("updated_at") or run.get("created_at")) + dt.timedelta(minutes=2)
    for post in posts:
        when = _post_time(post)
        if when is None or not (start <= when <= end):
            continue
        if any(isinstance(result, dict) and result.get("id") for result in (post.get("posted") or {}).values()):
            return True
    return False


def run_blocks(run: dict, slot: str, now: dt.datetime, current_run_id: str | None = None,
               window_hours: int = WINDOW_HOURS, posts: list[dict] | None = None) -> bool:
    """True when this dispatch run means the scheduled run for `slot` must not post again."""
    if current_run_id and str(run.get("id")) == str(current_run_id):
        return False
    if run.get("event") != "workflow_dispatch":
        return False
    if run.get("display_title") != title_for(slot):
        return False
    if now - _utc(run.get("created_at", "")) > dt.timedelta(hours=window_hours):
        return False
    if run.get("status") != "completed":
        return True
    if run.get("conclusion") == "success":
        return True
    return published_during(run, posts or [])


def fetch_runs(repo: str, token: str, since: dt.datetime) -> list[dict]:
    created = urllib.parse.quote(">=" + since.strftime("%Y-%m-%dT%H:%M:%SZ"))
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
           f"?event=workflow_dispatch&per_page=100&created={created}")
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("workflow_runs", [])


def load_posts(path: str = HISTORY_FILE) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("posts", [])
    except (OSError, ValueError):
        return []


def decide(slot: str, runs: list[dict], now: dt.datetime, current_run_id: str | None = None,
           posts: list[dict] | None = None) -> tuple[bool, str]:
    if slot not in SLOTS:
        return False, f"slot {slot!r} is not a scheduled slot"
    today = (now + dt.timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')
    for post in posts or []:
        if (post.get('slot') == slot and str(post.get('date', '')).startswith(today)
                and post.get('posted')):
            return True, f"{slot} already has a published receipt today ({post.get('id')})"
    for run in runs:
        if run_blocks(run, slot, now, current_run_id, posts=posts):
            state = f"{run.get('status')}/{run.get('conclusion')}"
            partial = " but published to at least one platform" if run.get("conclusion") not in (None, "success") else ""
            return True, (f"the outside scheduler already ran {slot} (run {run.get('id')}, {state}{partial}, "
                          f"created {run.get('created_at')})")
    return False, f"no outside run of {slot} published in the last {WINDOW_HOURS} hours, posting as backup"


def main() -> int:
    slot = os.environ.get("SLOT", "").strip()
    now = dt.datetime.now(dt.timezone.utc)
    try:
        runs = fetch_runs(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"],
                          now - dt.timedelta(hours=WINDOW_HOURS))
        skip, reason = decide(slot, runs, now, os.environ.get("GITHUB_RUN_ID"), load_posts())
    except Exception as exc:  # noqa: BLE001 - never lose a post because the check itself broke
        skip, reason = False, f"could not read workflow runs ({type(exc).__name__}: {exc}); posting as backup"
    print(f"[slot-guard] skip={str(skip).lower()}: {reason}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"skip={str(skip).lower()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
