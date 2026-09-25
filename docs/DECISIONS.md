# Decision log

Dated, newest last. Each entry says what was decided or learned and why, so the reasoning
survives a change of machine or a fresh Claude session. No credentials here.

## 9 September 2026, built and first posts

- Separate repo from the product (AI-Helps_SAAS). Free stack: GitHub Actions cron, Gemini
  free tier, Pillow + ffmpeg. Own accounts only.
- Pipeline: strategist -> copywriter -> reviewer (Gemini JSON) -> code validation -> render ->
  publish -> history committed back.
- Instagram needs public media URLs. Facebook's CDN copy works for photos but **not for reels**:
  Facebook re-encodes to HE-AAC, Instagram accepts only AAC-LC (error 2207076). The owner made
  the repo public so the `media` branch route serves video.
- Before going public, the positioning section of `knowledge/business_brief.md` was reworded
  so the banned-word rule reads as accuracy and platform policy, not concealment.
- Meta wiring lessons: the Graph API Explorer only offers permissions the app's use cases were
  customised to include; Instagram had been linked to another Page and needed "Switch Page" in
  Business Suite. The app stayed in Development mode and posts still went public.
- YouTube: the OAuth consent screen is now "Google Auth Platform"; publishing needs home,
  privacy and terms URLs plus the authorised domain; do not upload a logo there (forces
  verification). API uploads were NOT forced private.

## 10 September 2026, quality pass

- Reels animate (elements arrive in turn) instead of static cards with a zoom.
- Length target 25 to 32 s. Measured delivery is about 1.96 words per second; narration budget
  lives in one place (`copywriter.py`) and is read by writer, reviewer and validator.
- Hashtags: Instagram capped at 5 in December 2025; we were sending 15. Now 5 / 3 / 5 for
  IG / FB / YT, topic-specific, generic tags stripped in code.
- Links: Shorts descriptions and IG captions are never clickable, so they carry the bare domain.
- Every post is a product demonstration: names Interview Sarthi, shows the app's output,
  ends on price. Enforced in `validate()`.
- Screen reading of shared code removed from social copy at all four stages.
- A malformed or truncated model reply retries instead of killing the run; an unwritable topic
  is replaced, up to three tries.
- Meta blocked the app for part of the day and lifted it; the stored tokens survived, no
  re-authorisation was needed.
- Veo cold open wired through Vertex AI with keyless auth from GitHub. Three silent bugs fixed:
  the clip was generated, billed and discarded (wrong download call); Veo audio was on and
  paid for; with audio off the splice failed the whole run. The opener is now inside a
  try/except so it can never cost the post.

## 11 September 2026, the daily generated film

Owner decisions, taken one option at a time:
- Product appears inside the Veo footage, with the real interface card cut in right after.
- The whole story is generated fresh every day, one continuous actor via extension, new person
  and setting each time. No clip library.
- Daily, seven days, 19:37 IST. Carousel and image days retired.
- English only. No captions on footage.
- Best Veo tier; budget guards kept.
- Privacy line "On your screen. Not in the meeting." approved.
- "Viral" hashtags requested; agreed approach is a tiered, refreshed tag bank plus keywords in
  the first caption line and YouTube title, because broad tags bury a small account.

Lessons the same day:
- Veo native audio produced the candidate speaking; under narration it read as two voices. Veo
  audio is off and the assembler never mixes clip audio under narration. The extension beat
  returned an audio stream even with audio off, so that assembler rule is load-bearing.
- Veo image-to-video destroyed a real interface (invented app, garbled text). Product shots
  stay rendered cards.
- Separate generations give different actors; extension keeps one.
- The `-preview` Veo ids 404 on this project; GA ids work.
- The $300 credit spends only through Vertex AI, never through an AI Studio key.
- Gemini TTS free tier is 10 requests a day per model; a reel uses 4, so one local test can
  starve the evening post. Chirp 3 HD (billed to the Veo project, keyless) became the first
  voice; the owner had to enable the Text-to-Speech API in the console once, on the right
  project.
- The planner drifted a film to Hinglish on a language-switch story; films are now forced to
  English in code.
- Never `git add -A`: a 44 MB installer was committed to the public repo by accident.
- The OneDrive folder went read-only once (an accidental attribute); `attrib -r -h` fixed it.

## 12 September 2026, the reels were bad, and the product was being sold as prep

- Owner verdict on the Veo films: the scripts were fine, the video was not. Half of every film
  was a generated stranger making faces at an unreadable laptop, the product was never seen
  working, and every day looked different. The owner wants consistent reels.
- Second correction: the scripts said the app helps you *prepare*. It does not. It helps during
  the interview itself. The brief, the voice rules, the planner prompt, the story angles and the
  tag bank all carried prep framing (practice partner, night before, transcript review,
  #MockInterview, #InterviewPreparation) and were rewritten to the live moment.
- New daily format `demo`: rendered entirely in Pillow, no video model. A phone-shaped cut of
  the candidate's screen: the call window with the interviewer's tile (camera off, audio bars
  move while they ask), and the Interview Sarthi panel drawn in the app's own dark style. Phases:
  headline fades in, the question types into the transcript, a 1.3 s drafting pause, the answer
  arrives one sentence per line with the key phrases highlighted, then the price card. About 24 s.
  Four narration lines (hook, question, answer, price), one engine per video as before.
- Why rendered rather than footage: the demonstration IS the product doing its job, every word
  on screen is exact, the look is identical every day, and a day's reel costs no Veo seconds.
- Veo lesson found the same day: extension returns the whole clip, base plus new seconds, so the
  extended beat has to be played from where the first beat ended. Films on 11 and 12 September
  showed the first eight seconds twice. Fixed in `build_film` (offsets) for manual film runs.
- `VOICE_ENGINE=edge` in the environment skips the human voices for a local test build.
- The Veo `film` was also fixed to one shape, for the days the owner wants footage: the question
  lands (beat 1) with the app's transcript line composited over it, a glance and the answer
  (beat 2, the extension played from second 8) with the Interview Sarthi panel drafting one
  sentence per line over the footage, then the answer card and the price card. Eight rotating
  story shapes became one (`knowledge/stories.json`), overlays live in `agent/render/live.py`.
  This revisits the 11 Sep "no captions on the footage" decision: the overlays are the product's
  interface, not captions, and they are the only thing a muted viewer reads. The cover frame is
  taken at 2.5 s so the thumbnail shows the question.
- The owner asked for the card reel (screenshot, animated cards, voice-over) back, daily, on all
  three platforms, well apart from the video. Two crons in `post.yml`: 12:37 IST maps to
  `--format reel`, 19:37 IST follows `schedule.json`. Every reel must carry exactly one product
  slide with the real screenshot (`validate()`).
- Found while checking frames: JPEG frame sequences encode as full-range yuvj420p, Veo clips and
  PNG stills as limited range, so the joined file changed parameters at the card boundary and
  decoders reinitialised there. Every segment now goes through `scale=out_range=tv,setsar=1`
  and carries bt709 tags, in both `film.py` and `reel.py`.
- Positioning is enforced in `validate()` by `PREP_FRAMINGS` on everything except the
  interviewer's question and the candidate's answer; `company_prep` became `company_round`;
  `online_setup` is images and carousels only.

## 13 September 2026, four posts a day

- Analytics for the 28 days to 12 September (GA4, `ga4_report.py` in the product repo): 20
  users in the first fortnight, 225 in the second. The only thing that changed in between was
  this agent starting to post on 9 September. Instagram sent 49 sessions, Facebook 17, and the
  first ever purchase landed. The owner chose to scale posting before anything else, and to keep
  the live-help framing from the brief rather than the "practice partner" framing the traffic
  research suggested.
- `post.yml` goes from two crons to four: 09:07 IST `image` (Instagram and Facebook only, no
  YouTube quota), 12:37 IST `sales` short, 16:37 IST `reel` standard, 19:37 IST the weekday
  format from `schedule.json` at standard length. Three uploads a day is 4,800 of YouTube's
  10,000 daily units, so a manual run still fits.
- Not `film` for the new video slot: the scheduled path runs with `VEO_ENABLED=false`, and
  `_render_film` catches the missing footage and posts the card reel anyway, so scheduling film
  would just be a slower reel. The reel format skips its Veo hook cleanly when Veo is off (the
  9 to 11 September reels all carry `veo_seconds` 0).
- `strategy.py` now remembers 96 posts instead of 40 when it plans a topic, and balances pillars
  over 24 posts instead of 12. Forty posts was three weeks of memory at two a day and only ten
  days at four; a topic would come back while it was still on the feed. The constants sit at the
  top of the file with a note to raise them if the cron gains another slot.
- Known limit, per the README's warning: the constraint is distinct things to say, not compute.
  Seven pillars, eight demo scenarios and an eight-line `notes.md` are roughly ten days of
  genuinely different angles at this rate. Top up `knowledge/notes.md` and `demos.json` within
  a fortnight, or run the brief refresh, and judge on reach per post rather than follower count.
- Also found: everything since the 12 September decisions (the sales format, the quality gate,
  the prep-framing guard, Veo off) was still uncommitted, so the remote had been running the old
  once-a-day schedule. This commit ships all of it together; the new cron is live from the push.

## 15 September 2026, posting on time

- GitHub started the scheduled runs 3 to 7 hours late on 13 and 14 September. The 19:37 post
  went out around midnight and three posts landed within five hours, missing the evening window.
  No slot was dropped and every post published.
- cron-job.org (free) now calls the workflow_dispatch API at 09:07, 12:37, 16:37 and 19:37 IST with
  `slot` set to morning, midday, afternoon or evening. The workflow maps a slot to its format in
  one place, so a slot means the same thing whichever scheduler starts it.
- The GitHub crons stay as a backup rather than being removed. A new `guard` job runs first on a
  scheduled trigger: `tools/slot_already_posted.py` looks for a dispatch run titled
  "Post to social: <slot>" in the last 12 hours and skips if it succeeded or is still running.
  If it failed or never came, the backup posts, late but not lost. Dry runs are titled
  "(dry run)" and never count, and if the API cannot be read the backup posts (an extra post is
  a smaller problem than a missing one). Twelve hours covers the observed delay without matching
  the previous day's run.
- The token cron-job.org uses is fine-grained: this repository only, Actions read and write,
  nothing else. It expires; renew it before the date or on-time posting stops and only the late
  backup remains.

## 15 September 2026, fresh Veo openings and eight posts a day

- The owner wants to spend the $300 Google Cloud credit on better content and post as much as the
  automation allows. Veo had been off since 12 September, when the owner judged the full Veo films
  bad: a generated stranger at an unreadable laptop, the product never seen working. Veo also
  garbles interfaces. Evidence on the small sample: YouTube views per post were Veo films 11.5,
  current sales reels 4.7, older card reels 27.7; too few posts to call.
- Decision: every sales reel opens on a fresh 8 s Veo 3.1 Fast scene (720p, no audio) generated
  for that post; the product, answer and price stay rendered by code. This replaces the three
  library clips that repeated all week, without Veo drawing the app. The prompt keeps the laptop
  screen out of shot and bans text; setting and clothing rotate by scenario.
- Cost and caps: about $0.10 a second, $0.80 a reel. 1500 s a month (about $150) and 2600 s in
  total from 15 September (about $260, what the credit has after the September films, which used
  about 60 s of Veo 3.1 and 23 s of Veo 3.1 Fast). Counted from history (`visual_clip`
  "veo-fresh"); dry runs and runs that publish nothing are not counted, hence the margin. Past a cap
  or on any Veo error the reel opens on a library clip. A clip that is paid for but fails to
  smooth is played unsmoothed rather than wasted.
- The first six seconds are smoothed to 60 FPS with motion-compensated interpolation, as the library
  clips were. Locally that took about 100 s for six seconds of 720p.
- Eight posts a day: six reels (YouTube allows six uploads, 9,600 of 10,000 units) and two image ads
  on Instagram and Facebook. The account's Instagram API limit is 100 posts a day. New slots:
  late-morning 10:37, early-afternoon 14:37, early-evening 18:07, night 21:37; the four existing
  cron-job.org jobs are unchanged and four new ones call the new slots.
- Image run folders are now named "-image" instead of "-sales-short".

## 25 September 2026, reels for viewers outside India

- Why: of about 196 non-India visitors to the site in 28 days, about 171 were data-centre bots, and
  every reel spoke to Indian freshers in rupees with an Indian face. Nothing invited anyone abroad.
- Decision: every video is made for one market, `india` or `global`, chosen before a word is written
  (`agent/market.py`, data in `knowledge/markets.json`). A global post gets an international face,
  plain international English (no Hinglish, no Indian companies, no "fresher"), the US dollar prices
  Dodo charges abroad, a neutral `en-US` voice, international hashtags and engagement questions.
- Shares: Prep Sarthi 0.67 (it works on a phone and is practice, the easier sell abroad), Live Sarthi
  0.34 (its buyers are in India), ApplySarthi 0 (its jobs are Indian). `choose()` balances each product
  against its own recent posts, so markets alternate rather than run in streaks. `POST_MARKET=india|global`
  forces one for a manual run or a preview.
- Dollar prices are in the business brief's international tables and must match the live site: Live
  $9.99 / $19.99 / $39.99 / $69.99, Prep $4.99 / $9.99. The owner will not lower them further: Dodo
  takes about Rs 36 a sale.
- Fixed on the way: the price card showed the Windows app's ladder and "Windows 10 and 11" on every
  product's reel; each product now shows its own passes and its own footnote.

## 25 September 2026, two Live passes and one Prep pass

- Owner's new price plan. Live Sarthi (Interview Sarthi, the Windows app) sells only two passes:
  the 2-Day Pass at Rs 99 / $9.99 (2 days, 1 device, about Rs 50 a day) and the 1-Month Pass at
  Rs 299 / $29.99 (30 days, 2 devices, about Rs 10 or $1 a day; it was Rs 999 / $39.99). The 7-Day
  Pass (Rs 399 / $19.99) and the 3-Month Pass (Rs 1,999 / $69.99) are gone and no post may name them.
  The 30 free minutes are unchanged.
- Prep Sarthi sells one pass: the 30-Day Pass at Rs 99 / $9.99, unlimited mock interviews, one
  payment, never renews. The 7-Day Pass (Rs 99 / $4.99) and the old Rs 249 price are gone. The
  free-trial wording is unchanged until the owner decides it. ApplySarthi stays free.
- The sales reel's closing card now sells the month as its second line: "Rs 299 covers the whole
  month." in India and "$29.99 covers the whole month." abroad. This replaces the older dollar
  ladder in the entry above.

## Open items for the owner

- Complete Google's "verify this account" prompt on the Cloud account that carries Veo and
  the voice.
- Instagram bio still uses "Invisible" and the old price; replacement text was provided.
- Rotate the Meta app secret at some point (it was pasted into a chat); this invalidates the
  Page token and needs the token step redone once.
