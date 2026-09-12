# Interview Sarthi social agent, working notes for Claude Code

Read this first on any machine. It replaces the chat history: what this repo is, what the owner
has decided, what must never happen again, and what does not travel with `git pull`.
Details and dates are in `docs/DECISIONS.md`. Setting up a new PC is `docs/SETUP-ANOTHER-PC.md`.

## What this is

A fully unattended promoter for **Interview Sarthi** (interviewsarthi.com, a Windows app that
listens to an online interview and shows what to say, from the candidate's own resume, in
English, Hindi or Hinglish). It writes, renders, voices and publishes a short video every day to
the owner's own Instagram (@interviewsarthi), Facebook Page (Interview Sarthi) and YouTube
channel (@InterviewSarthi). Nothing else, nobody else's accounts.

It runs on **GitHub Actions**, not on any PC. `.github/workflows/post.yml` fires daily at
14:07 UTC (19:37 IST). A laptop being off changes nothing. Local runs are for editing and
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

- Daily, English only, one generated **film** per day: Veo footage with one continuous person
  (8 s clip + 7 s extension), the app shown inside the scene, then the **real interface card**
  with that day's question and answer, then the price card. About 20 to 30 s.
- Best Veo tier the credit allows (standard model, 1080p). Budget guards stay on:
  `VEO_MAX_SECONDS_PER_RUN`, `VEO_MONTHLY_SECONDS`.
- No captions on the footage. Because most viewers are muted, the two cards must carry the
  whole pitch: what it is, where it runs, what it costs.
- Voice: human voices only. Chirp 3 HD first (no daily cap), Gemini TTS second (10 calls a day
  on the free tier), Edge last resort. Voice name Achird.
- Hashtags: five on Instagram (platform cap), tiered specific/mid/one broad from
  `knowledge/hashtags.json`, brand tag last, company tags only when the post is about them.
- Privacy wording: **"On your screen. Not in the meeting."** Never invisible, hidden,
  undetectable, stealth, cheat. Screen reading of shared code stays off social copy entirely
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
  project `video-generation-uniyal`). It exists only on GitHub. Locally, Veo and Chirp are
  unavailable unless Application Default Credentials are set up, so local test builds use the
  card fallback and the Edge voice. Published posts are unaffected.
- Claude Code's own memory and chat transcripts are per machine and contain pasted secrets;
  they are not committed. This file and `docs/DECISIONS.md` are the carrier instead. When
  something durable is learned, add it there.

## Accounts and identifiers (not secrets)

Meta app "Interview Sarthi Poster" id 28038591292508568, Facebook Page id 1402449719621710,
Instagram user id 17841443484885325, YouTube channel UCmlZKXqRv-3R8ZSd7tcEhrQ (owned by the
interviewsarthi@gmail.com Google account), Veo/voice project `video-generation-uniyal`.

## Style

No em dashes anywhere in generated text or code comments. Short sentences. Indian context.
