# Automated sales reels

The `sales` format explains live, resume-based interview assistance through eight fictional
candidate scenarios. These are illustrative examples, not recorded calls or measured response
times. A separate scene shows the real app screenshot. The renderer adds this disclosure.

The prepared workflow runs the short variant at 12:37 IST and the standard variant at 19:37 IST.
No manual script approval or screen recording is required. Changing local code does not change
GitHub's running schedule until it is deployed.

## Content and rendering

`knowledge/demos.json` contains supported profiles, questions, answers and three opening hooks
per scenario. Rotation avoids the latest six scenarios. Gemini may improve the spoken script,
using a constrained JSON structure and a separate factual/creative review. Invalid or unreviewed
drafts fall back to a validated authored script. Provider model names are configurable through
`SCRIPT_MODELS`. Existing free-tier credentials are reused; no additional provider is required.

The first answer excerpt appears at 1.1 seconds. Full answers use large text with a reading
budget. Standard edits explain the resume evidence. Both edits explain Windows and supported
call apps, show the real interface and finish with the free trial and two-day offer.
Short videos have a 32-second ceiling; standard videos have a 48-second ceiling. Audio is measured
before rendering. Overlong generated copy is rebuilt once with authored copy; speech is never
cut off to force a length. One voice engine is used throughout, with existing Chirp/Gemini/Edge
fallbacks. Daily sales reels use no Veo footage.

The final encoded file must decode, contain audible audio, match the timeline, preserve the CTA,
and have portrait dimensions. Publication verifies the checked file's hash. A `published.json`
receipt allows a retry of the same output folder to skip platforms that already succeeded.
This is not an exactly-once guarantee after an ambiguous provider timeout or lost runner state.
Complete provider outages or quality failures stop publication instead of posting broken media.

## Measurement

The agent reads available YouTube and Instagram counts before a scheduled run. Metrics are
saved in `content/performance.json`; absent permissions do not block generation. After at least
six qualifying observations, hook writing receives those observations. View counts are not
retention, causal A/B evidence or sales. The format rotates both lengths; it does not claim a
winning length from insufficient data. Facebook URLs include a per-post campaign identifier.
Instagram/profile navigation and YouTube Shorts do not provide equivalent per-post attribution.

## Validation and local preview

```
python -m unittest discover -s tests -v
python -m agent create --format sales --variant short --sample --out out/short-preview
python -m agent create --format sales --variant standard --out out/standard-preview
```

`create` never publishes. `--sample` avoids script-model calls but voice synthesis still needs
network access. `VOICE_ENGINE=edge` selects the free fallback voice for local preview builds.
Each folder contains `reel.mp4`, `cover.jpg`, `post.json`, `quality.json`, `evidence.json` and scene
previews. Review the MP4 for creative quality; automated checks do not predict views or sales.
