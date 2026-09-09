# Interview Sarthi social agent

An autonomous content agent for Interview Sarthi's Instagram, Facebook Page and YouTube
channel. On a schedule it decides what to post, writes it, renders the images or the
reel, publishes to the accounts you own, and remembers what it did so it never repeats
itself. Everything it relies on is free.

```
knowledge/           what the agent knows: business brief, brand, pillars, schedule, your notes
   |
   v
strategist  ->  copywriter  ->  reviewer  ->  renderer  ->  publishers  ->  history
(Gemini)        (Gemini)        (Gemini)      (Pillow,       (Graph API,     (content/history.json,
                                               edge-tts,      YouTube API)    committed back)
                                               ffmpeg)
```

One run makes one post:

| Format | What it is | Goes to |
|---|---|---|
| image | one 1080x1350 card (question and answer, myth versus fact, hook, stat) | Instagram, Facebook |
| carousel | 4 to 7 cards: hook, value slides, product moment, CTA with pricing | Instagram, Facebook |
| reel | 30 to 45 second 1080x1920 video, voice-over, slow push-in on each card | Instagram Reels, Facebook Reels, YouTube Shorts |

## What it costs

| Piece | Service | Cost |
|---|---|---|
| Scheduler and compute | GitHub Actions | free (unlimited minutes on a public repo, 2,000 a month on a private one; a run uses 3 to 6) |
| Writing | Google Gemini API free tier | free, about 4 calls per run |
| Voice-over | Microsoft Edge neural voices via edge-tts | free, no key |
| Rendering | Pillow and ffmpeg | free |
| Publishing | Meta Graph API, YouTube Data API v3 | free |
| Public URL for Instagram media | this repo's `media` branch, or Cloudinary free tier | free |

## Try it in two minutes, no accounts needed

```powershell
pip install -r requirements.txt
python -m agent create --sample --format carousel
python -m agent create --sample --format reel
```

Open the `out/` folder. `--sample` uses the posts in `samples/` instead of calling Gemini,
so you can see exactly how cards and reels look before you connect anything.

## Setup, once

### 1. Gemini key

Create a key at https://aistudio.google.com/apikey (no card). That is `GEMINI_API_KEY`.

### 2. Facebook Page and Instagram

You need a Facebook Page and an Instagram professional account (Business or Creator)
linked to that Page. Instagram: Settings > Account type and tools > Switch to professional
account; then Settings > Business tools and controls > Connect a Facebook Page.

1. Go to https://developers.facebook.com/apps and create an app. Type: **Business**.
2. In the app dashboard add the products **Facebook Login for Business** and
   **Instagram Graph API** (names vary slightly by year; add whatever mentions Instagram).
3. Open https://developers.facebook.com/tools/explorer/, select your app, click
   **Generate Access Token**, and tick these permissions:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`,
   `instagram_content_publish`, `business_management`. Approve the dialog for your Page
   and Instagram account. Copy the token.
4. Run the helper. It exchanges the token and prints the values you need:

   ```powershell
   python setup/meta_setup.py --app-id APP_ID --app-secret APP_SECRET --token PASTE_TOKEN
   ```

   App ID and App Secret are under App settings > Basic. Copy `META_PAGE_ID`,
   `META_PAGE_ACCESS_TOKEN` and `IG_USER_ID`. Page tokens obtained this way do not expire.
5. Switch the app to **Live** (toggle at the top of the dashboard). It asks for a privacy
   policy URL: use https://interviewsarthi.com/privacy.html. No App Review is needed when
   you post only to Pages and accounts you administer, which is the case here. Posts made
   while the app is still in Development mode are visible only to you.

### 3. YouTube

1. https://console.cloud.google.com: create a project, then **APIs and Services > Library**
   and enable **YouTube Data API v3**.
2. **OAuth consent screen**: User type External. Fill the app name and your email. Under
   Test users add the Google account that owns the channel. Then press **Publish app**
   so the status reads *In production*. It will say the app is unverified; that is fine
   for your own channel. (Apps left in Testing expire refresh tokens after 7 days.)
3. **Credentials > Create credentials > OAuth client ID > Desktop app**. Download the JSON.
4. Run the helper, sign in with the channel's account when the browser opens:

   ```powershell
   python setup/youtube_setup.py client_secret.json
   ```

   Copy `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

**Public uploads need one more step.** YouTube sets every video uploaded through the API to
*private* until the project passes a free compliance audit. Request it once at
https://support.google.com/youtube/contact/yt_api_form (choose the audit option, describe
the tool as "uploads Shorts to my own channel on a schedule"). Until it is approved, set the
repository variable `YT_PRIVACY` to `unlisted` or `private` and flip videos to public in
YouTube Studio, or just let them sit private. After approval set it to `public`.

### 4. Where Instagram fetches media from

Instagram's API downloads images and videos from a public URL instead of accepting an
upload. The agent picks the first of these that works, in this order:

1. **Cloudinary** if `CLOUDINARY_URL` is set (free account at https://cloudinary.com, copy
   the URL from its dashboard). Most robust, one extra signup.
2. **This repo's `media` branch** if the repo is **public**: the run force-pushes the files
   to an orphan branch and uses raw GitHub URLs. Zero signup, nothing accumulates.
3. **Facebook's copy** otherwise: the agent posts to Facebook first, then hands Instagram
   the CDN URL of the photo or video Facebook just stored. Works with a private repo and
   no extra account, as long as `facebook` stays in the platform list (it does by default).

`python -m agent verify` prints which one is in effect.

### 5. GitHub

1. Push this folder to GitHub.
2. **Settings > Actions > General > Workflow permissions**: choose *Read and write
   permissions*. The workflow commits `content/history.json` (and the media branch on a public repo).
3. **Settings > Secrets and variables > Actions > Secrets**, add:

   | Secret | From |
   |---|---|
   | `GEMINI_API_KEY` | step 1 |
   | `META_PAGE_ID`, `META_PAGE_ACCESS_TOKEN`, `IG_USER_ID` | step 2 |
   | `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | step 3 |
   | `CLOUDINARY_URL` | step 4, only for a private repo |

   Under **Variables** (not secrets) optionally add `YT_PRIVACY` (`public`, `unlisted` or
   `private`) and `GEMINI_MODELS` (comma list, default `gemini-3.6-flash,gemini-3.1-flash-lite`).

4. Check everything from your PC before the first scheduled run. Put the same values in a
   local `.env` (copy `.env.example`) and run:

   ```powershell
   python -m agent verify
   python -m agent run --dry-run --format image
   ```

   `verify` prints one line per credential. `--dry-run` writes a real, Gemini-written post
   to `out/` without publishing. Look at it. If you like it, publish that exact folder:

   ```powershell
   python -m agent publish out/<folder>
   ```

5. On GitHub open **Actions > Post to social > Run workflow**, tick *dry_run* once, read
   the job summary. Then run it once for real. After that the schedule takes over.

## Schedule

The cron in `.github/workflows/post.yml` decides **when**; `knowledge/schedule.json`
decides **what** each weekday gets.

Default: Monday, Wednesday and Friday at 19:37 IST, which maps to reel, carousel and reel
on those days, so YouTube gets two Shorts a week and Instagram gets two reels and a
carousel. Three posts a week is the right start for an automated account:
enough to look alive, few enough that every post has to be good, and well inside the free
Gemini quota. Daily posting rarely helps a new account and doubles the chance of a
repetitive feed; switch to it once the first month of data says people save the posts.

To post daily change the cron line to `"7 14 * * *"`. The weekday map already covers all
seven days: three reels, two carousels and two single images a week.
To move the time, remember GitHub cron is UTC: IST minus 5:30.

You can also run it by hand any time from the Actions tab, with a format and a topic of
your choice.

## Steering the content

Everything the agent believes lives in `knowledge/`. Edit and commit; the next run uses it.

| File | What to change there |
|---|---|
| `business_brief.md` | facts, prices, features, positioning, links. The agent may only state what is here. |
| `notes.md` | anything you want it to know this month: a launch, a season, a topic to avoid |
| `pillars.json` | content themes, their weights (long-run share) and example topics |
| `schedule.json` | weekday to format map, language rotation, slide counts, reel length |
| `brand.json` | colours, fonts, **your real Instagram and YouTube handles** (shown in the card footer), pricing rows, hashtags, CTA lines, voices, forbidden words |
| `business_brief.auto.md` | rewritten monthly from the live website by the second workflow; do not edit by hand |

Optional extras:

- **Music**: drop `.mp3` files into `assets/music/` and reels mix one in quietly. See the
  README there for free sources.
- **Screenshots**: `assets/brand/` holds the product screenshots used by product slides.
  Replace them when the app's look changes; keep the file names.
- **Refresh the brief from the app repo too**: locally run
  `python -m agent research --url https://interviewsarthi.com --repo ..\AI-Helps_SAAS`
  and it reads the repo's markdown files as well as the site.

## Rules the agent follows

These are in the prompts, checked again by the reviewer pass, and enforced in code where possible.

- Only facts, prices and links from the business brief. No invented testimonials, user
  counts, success rates or quotes. No promise of a job or a selection.
- Product framing is "assistant, guide, practice partner, in your words, from your resume".
  The words cheat, undetectable, hidden, invisible and stealth are forbidden, and screen-share
  exclusion is never mentioned in posts. A post that breaks these rules is rejected and the
  run fails rather than publishing.
- No em dashes anywhere.
- Hinglish on screen is Roman script. Reel narration for Hinglish posts is mixed script so
  the Hindi voice pronounces it correctly.
- It posts only to the Page, Instagram account and channel whose tokens you gave it.

## Commands

```
python -m agent run       [--format auto|image|carousel|reel] [--topic "..."] [--language english|hinglish]
                          [--platforms instagram,facebook,youtube] [--dry-run] [--sample]
python -m agent create    same options; renders to out/ and publishes nothing
python -m agent publish   out/<folder> [--platforms ...] [--dry-run]
python -m agent plan      print today's plan as JSON (one Gemini call)
python -m agent research  [--url ...] [--repo ...]   rewrite knowledge/business_brief.auto.md
python -m agent verify    check every credential and ffmpeg without posting
```

## When something goes wrong

GitHub emails you when a run fails. Open the run: the job summary shows the plan, the
caption and every platform's result or error, and the *Artifacts* section holds the images,
the video and `post.json` for two weeks.

| Symptom | Cause and fix |
|---|---|
| `Gemini: HTTP 429` | free-tier rate limit; the client already waits and retries, and falls back to the second model. If it persists, run less often or switch `GEMINI_MODELS`. |
| `no public host for Instagram media` | the repo is private and Facebook was not posted in this run. Keep facebook in the platforms, make the repo public, or set `CLOUDINARY_URL`. |
| Instagram error mentioning `image_url` or aspect ratio | the file must be JPEG, 4:5 to 1.91:1. The renderer already does this; check you did not change `FEED` in `agent/render/cards.py`. |
| Facebook posts exist but nobody else sees them | the Meta app is still in Development mode. Switch it to Live. |
| `OAuthException 190` | the Page token was invalidated (password change, app removed). Rerun `setup/meta_setup.py`. |
| YouTube `invalid_grant` | refresh token expired because the OAuth app was left in Testing. Publish the consent screen and rerun `setup/youtube_setup.py`. |
| YouTube video uploaded as private although `YT_PRIVACY=public` | the project has not passed the API audit yet. See step 3. |
| YouTube `quotaExceeded` | 10,000 units a day, 1,600 per upload. Wait a day. |
| Reel has no voice | edge-tts could not reach Microsoft's service; the run continues without narration. Usually transient. |
| `git push` says `refusing to allow ... without workflow scope` | your GitHub token cannot upload Actions files. Run `gh auth refresh -h github.com -s workflow` (or create a token with the `workflow` scope) and push again. |
| Post rejected by the reviewer three times | look at the run log; the issues are listed. Usually the topic asked for a claim the brief does not support. Add the fact to the brief if it is true. |

## Layout

```
agent/
  cli.py          commands
  pipeline.py     create -> publish -> remember -> report
  strategy.py     picks pillar, topic, language for today
  copywriter.py   writes the post, reviews it, validates structure and rules
  knowledge.py    assembles the prompt context from knowledge/
  llm.py          Gemini REST client with model fallback and retry
  history.py      content/history.json
  research.py     website crawler + brief synthesis
  render/cards.py slide templates (hook, stat, points, qa, myth, product, cta, quote)
  render/reel.py  frames + voice -> mp4
  render/tts.py   edge-tts wrapper
  publish/meta.py Facebook Page + Instagram
  publish/youtube.py
  publish/media_host.py  GitHub media branch or Cloudinary
setup/            one-time token helpers
knowledge/        the agent's brain, edit freely
samples/          three finished posts used for --sample and as examples in the prompts
assets/           fonts (Poppins, OFL), brand images, optional music
content/          history.json, written by runs
out/              run outputs, ignored by git
```
