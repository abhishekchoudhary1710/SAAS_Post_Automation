"""Should a late GitHub scheduled run skip, because the outside scheduler already posted this slot?

GitHub starts scheduled workflows hours late when it is busy (3 to 7 hours in September 2026).
cron-job.org triggers the same workflow on time through workflow_dispatch, naming the slot, which
the workflow's run-name turns into the title "Post to social: <slot>".

The GitHub schedule stays as a backup. When a scheduled run finally starts, this script looks for a
dispatch run of the same slot created in the last WINDOW_HOURS. If that run succeeded, or is still
queued or running, the scheduled run skips. If it failed, or never happened, the backup posts.

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
SLOTS = ("morning", "late-morning", "midday", "early-afternoon", "afternoon", "early-evening", "evening", "night")
WORKFLOW_FILE = "post.yml"


def title_for(slot: str) -> str:
    return f"Post to social: {slot}"


def run_blocks(run: dict, slot: str, now: dt.datetime, current_run_id: str | None = None,
               window_hours: int = WINDOW_HOURS) -> bool:
    """True when this dispatch run means the scheduled run for `slot` must not post again."""
    if current_run_id and str(run.get("id")) == str(current_run_id):
        return False
    if run.get("event") != "workflow_dispatch":
        return False
    if run.get("display_title") != title_for(slot):
        return False
    created = dt.datetime.fromisoformat(str(run.get("created_at", "")).replace("Z", "+00:00"))
    if now - created > dt.timedelta(hours=window_hours):
        return False
    if run.get("status") != "completed":
        return True
    return run.get("conclusion") == "success"


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


def decide(slot: str, runs: list[dict], now: dt.datetime, current_run_id: str | None = None) -> tuple[bool, str]:
    if slot not in SLOTS:
        return False, f"slot {slot!r} is not a scheduled slot"
    for run in runs:
        if run_blocks(run, slot, now, current_run_id):
            return True, (f"the outside scheduler already ran {slot} (run {run.get('id')}, "
                          f"{run.get('status')}/{run.get('conclusion')}, created {run.get('created_at')})")
    return False, f"no successful outside run of {slot} in the last {WINDOW_HOURS} hours, posting as backup"


def main() -> int:
    slot = os.environ.get("SLOT", "").strip()
    now = dt.datetime.now(dt.timezone.utc)
    try:
        runs = fetch_runs(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"],
                          now - dt.timedelta(hours=WINDOW_HOURS))
        skip, reason = decide(slot, runs, now, os.environ.get("GITHUB_RUN_ID"))
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
