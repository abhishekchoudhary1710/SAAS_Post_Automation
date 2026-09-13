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

## Open items for the owner

- Complete Google's "verify this account" prompt on the Cloud account that carries Veo and
  the voice.
- Instagram bio still uses "Invisible" and the old price; replacement text was provided.
- Rotate the Meta app secret at some point (it was pasted into a chat); this invalidates the
  Page token and needs the token step redone once.
