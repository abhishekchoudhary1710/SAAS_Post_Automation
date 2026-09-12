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

## Open items for the owner

- Complete Google's "verify this account" prompt on the Cloud account that carries Veo and
  the voice.
- Instagram bio still uses "Invisible" and the old price; replacement text was provided.
- Rotate the Meta app secret at some point (it was pasted into a chat); this invalidates the
  Page token and needs the token step redone once.
