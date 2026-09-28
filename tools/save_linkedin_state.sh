#!/usr/bin/env bash
# The shared social-post concurrency group serializes both production workflows.
set -euo pipefail
state_path=content/linkedin_growth.json
test -f "$state_path" || exit 0
git config user.name sarthi-social-agent
git config user.email actions@users.noreply.github.com
git add "$state_path"
if git diff --cached --quiet; then
  exit 0
fi
git commit -m "LinkedIn: save reservation, receipt or metric update"
for attempt in 1 2 3; do
  git pull --rebase origin main
  if git push origin HEAD:main; then
    exit 0
  fi
done
echo "LinkedIn state could not be saved; do not publish without a saved reservation" >&2
exit 1
