# Interview Sarthi social agent, working notes for Claude Code

Latest owner authorization: the smooth 60 FPS privacy ad is approved for publication and
unattended production. Preserve the four daily slots. All video slots use the approved motion
style, with new reviewed fictional scenarios, rotating visuals and upload recovery.
See [production automation](docs/AUTOMATION.md). Older preview-only notes are superseded.

## Current upgrade: 13 September 2026

The owner authorized implementation of better, fully automated promotional reels, keeping the
current budget first. They want finished previews to judge before this creative direction goes
live. The local `sales` format and prepared workflow supersede the old reel/demo defaults below;
local changes do not deploy GitHub Actions. Read `docs/SALES-REELS.md` for current behavior.
Short and standard edits use eight explicitly fictional resume examples and real interface
imagery. Do not describe these as recordings of live app output or measured response times.
The normal sales workflow requires no manual approvals. The present rollout is at preview review.


Read this first on any machine. It replaces the chat history: what this repo is, what the owner
has decided, what must never happen again, and what does not travel with `git pull`.
Details and dates are in `docs/DECISIONS.md`. Setting up a new PC is `docs/SETUP-ANOTHER-PC.md`.

## What this is

A fully unattended promoter for **Interview Sarthi** (interviewsarthi.com, a Windows app that
listens to an online interview and shows what to say, from the candidate's own resume, in
English, Hindi or Hinglish). It writes, renders, voices and publishes a short video every day to
the owner's own Instagram (@interviewsarthi), Facebook Page (Interview Sarthi) and YouTube
channel (@InterviewSarthi). Nothing else, nobody else's accounts.

It runs on **GitHub Actions**, not on any PC. `.github/workflows/post.yml` fires four times a
day: 09:07, 12:37, 16:37 and 19:37 IST (03:37, 07:07, 11:07 and 14:07 UTC). A laptop being off
changes nothing. Local runs are for editing and
testing only.

## How a post is made (agent/)

strategy (plan a topic, story, angle, persona) -> copywriter (script + cards, Gemini JSON) ->
reviewer (Gemini) -> `validate()` in code -> render (Veo footage via Vertex AI + our own rendered
cards) -> voice (Chirp 3 HD, then Gemini TTS, then Edge; never mixed within one video) ->
publish (Facebook, Instagram, YouTube) -> `content/history.json` committed back by the workflow.

Knowledge the model writes from: `knowledge/business_brief.md` (source of truth about the
product; edit freely, keep facts exact), `pillars.json`, `stories.json`, `personas.json`,
`hashtags.json`, `schedule.json`, `brand.json`.

`python -m agent verify` checks every credential and dependency. `python -m agent create
--format film` builds without publishing. `python -m agent publish out/<folder>` publishes a
built folder. See README.md for the rest.

## Owner decisions (do not re-open without asking)

- 12 Sep 2026: the app is **live help during the interview**, never preparation. No post may call
  it a practice partner, prep tool, mock interview or something to rehearse with. The daily reel
  is the rendered **demo** format (`agent/render/demo.py`, schedule `demo` every day): the
  candidate's screen, a mock call with the interviewer's tile, the Interview Sarthi panel where
  the question types in and the answer arrives one sentence at a time, then the price card. No
  Veo footage, so it looks the same every day and costs nothing to render. `film` (Veo) stays
  available for manual runs. Test locally with
  `VOICE_ENGINE=edge python -m agent create --sample --format demo`.
- **Eight posts a day and fresh Veo openings (15 Sep 2026).** Six sales reels (10:37, 12:37, 14:37, 16:37, 19:37, 21:37 IST) and two image ads (09:07, 18:07). Every reel opens on a new 8 s Veo 3.1 Fast scene from `agent/render/veo_opening.py`, capped at 1500 s a month and 2600 s in total from 15 Sep; past a cap or on any Veo error it opens on a library clip. YouTube allows six uploads a day, so six reels is the ceiling. Full Veo films (`VEO_ENABLED`) stay off.
- **Four posts a day (13 Sep 2026; was two on 12 Sep).** 09:07 IST an `image` card, 12:37 IST
  the short `sales` reel, 16:37 IST the card `reel` (real screenshot, animated cards, voice-over),
  19:37 IST the weekday format from `schedule.json` at standard length. The run step in
  `post.yml` maps each slot to its format. Since 15 Sep 2026 cron-job.org triggers the slots on time (workflow_dispatch with `slot`); the GitHub crons are a backup, and `tools/slot_already_posted.py` makes them skip a slot the outside run already posted. Not `film` on the schedule: Veo is off there and film
  would fall back to a reel. Every card reel must carry exactly one product slide with the
  screenshot; enforced in `validate()`. `strategy.py` remembers 96 posts (`RECALL_WINDOW`) so
  topics do not recur within the fortnight; raise it if the cron gains a slot.
- **The film has one fixed shape (12 Sep 2026)** so films read as a series: the question lands
  (the app's transcript line over the footage), a glance at the laptop, the answer drafts in one
  sentence at a time (the Interview Sarthi panel over the footage), then the answer card and the
  price card. Only the person, the question and the angle rotate. `knowledge/stories.json` holds
  the one shape; `agent/render/live.py` renders the overlays. The text over the footage is the
  app's own interface, which is what a muted viewer reads; it is not a caption.
- English only for the generated **film**: Veo footage with one continuous person
  (8 s clip + 7 s extension), the app's panel over the scene, then the **real interface card**
  with that day's question and answer, then the price card. About 22 to 28 s.
- Best Veo tier the credit allows (standard model, 1080p). Budget guards stay on:
  `VEO_MAX_SECONDS_PER_RUN`, `VEO_MONTHLY_SECONDS`.
- No captions or subtitles on the footage. What does go over it is the app's own interface (the
  question line, the answer panel). Because most viewers are muted, the overlays and the two
  cards must carry the whole pitch: what it is, where it runs, what it costs.
- Voice: human voices only. Chirp 3 HD first (no daily cap), Gemini TTS second (10 calls a day
  on the free tier), Edge last resort. Voice name Achird.
- Hashtags: five on Instagram (platform cap), tiered specific/mid/one broad from
  `knowledge/hashtags.json`, brand tag last, company tags only when the post is about them.
- Privacy wording, updated by the owner on 13 September: include **"hidden from supported
  screen sharing"** with a labeled local/shared-view illustration. Windows 10 (2004+) or
  Windows 11 is required; capture support varies. Since 17 Sep 2026 (owner decision, see
  knowledge/hooks.json) hooks and captions may say the interviewer did not notice, call the overlay
  invisible, say cheating, and tell disclosed fictional success stories; the product line still names
  supported screen sharing, and guarantees, statistics and real-customer claims stay out. Screen reading of shared code stays off social copy entirely
  (documented on the website instead). These are enforced in code, not only in prompts.
- Every post names Interview Sarthi and Windows and shows the app's output; enforced in
  `validate()`.

## Hard rules for working in this repo

- **Never `git add -A`.** Stage named paths. This repo is public; a 44 MB installer was once
  committed by accident. `*.exe`, `*.msi`, `.env`, `client_secret*.json`, `out/` are ignored.
- Never commit or paste tokens. `.env` holds them locally; GitHub Secrets hold them for the
  workflow. If a secret reaches a chat or a commit, rotate it.
- One voice per video. Veo's own audio is never mixed under narration; Veo speech under the
  voice-over shipped once and read as two people talking.
- Veo cannot render a real interface. Given our product card as a first frame it invented a
  chat app with garbled text. Product shots are rendered cards, always.
- Separate Veo generations give different actors; use extension for continuity.
- Veo's extension returns the WHOLE clip (base plus new seconds). Play an extended beat from
  where the previous beat ended (`offsets` in `build_film`). Playing it from zero repeated beat 1
  and never showed the answer; every film published on 11 and 12 Sep had this.
- Every video segment is converted to limited range and tagged bt709 (`TO_TV`, `COLOR_TAGS` in
  film.py and reel.py). JPEG frame sequences decode as full range, Veo clips and PNG stills as
  limited; joined as they come, decoders reinitialise at the boundary and the card renders a
  shade off.
- The `-preview` Veo model ids 404 on this Vertex project; use the GA ids
  (`veo-3.1-generate-001`, `-fast-`, `-lite-`).
- The $300 Google Cloud credit is spent only through Vertex AI. An AI Studio key answers
  "prepayment credits are depleted" regardless of the balance. Do not go back to a key for Veo.
- Instagram media cannot be deleted through the API and the YouTube token is upload-only, so a
  bad post is removed by the owner by hand. Check before publishing.
- Python heredocs through the shell mangle backslashes on this Windows setup; write patches to
  a file first.

## What does not travel with git

- `.env`: all credentials. Copy it by hand or recreate it; see `.env.example`.
- The Google Cloud identity used by the workflow is keyless (Workload Identity Federation,
  project `uniyal-video`). It exists only on GitHub. Locally, Veo and Chirp are
  unavailable unless Application Default Credentials are set up, so local test builds use the
  card fallback and the Edge voice. Published posts are unaffected.
- Claude Code's own memory and chat transcripts are per machine and contain pasted secrets;
  they are not committed. This file and `docs/DECISIONS.md` are the carrier instead. When
  something durable is learned, add it there.

## Accounts and identifiers (not secrets)

Meta app "Interview Sarthi Poster" id 28038591292508568, Facebook Page id 1402449719621710,
Instagram user id 17841443484885325, YouTube channel UCmlZKXqRv-3R8ZSd7tcEhrQ (owned by the
interviewsarthi@gmail.com Google account), Veo/voice project `uniyal-video` (ibyteai2026@gmail.com
Google account, service account veo-au-541@uniyal-video.iam.gserviceaccount.com).

## Style

No em dashes anywhere in generated text or code comments. Short sentences. Indian context.
