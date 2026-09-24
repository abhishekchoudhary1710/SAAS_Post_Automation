# Ninety-day social growth experiment

Prepared and implemented 24 September 2026. The publishing schedule, duplicate guard,
product-safe fallback, age-matched metric snapshots and daily scorecard are in this repo.

## Objective and baseline

Use the remaining Google Cloud trial credit before its actual expiry while growing qualified visits and product starts. The previous schedule had eight posts per day: six videos and two ApplySarthi carousels. The new schedule has ten posts per day, with eight distinct reels and two carousels. Cross-post each suitable reel to Instagram, Facebook, and YouTube, subject to each account's publishing limits.

The 24 September account audit found 68 YouTube uploads, 70 Instagram reels and 68 Facebook videos. Sixty-seven processed public YouTube videos had 639 lifetime views and a median of three views. The strongest topics were Hindi/Hinglish interview moments and specific company questions; these are hypotheses, because samples were small and posts were different ages. Meta views and retention were unavailable due to missing insights permissions. The 14-day business funnel showed five non-owner Live Sarthi purchases, zero Prep purchases and 13 Apply accounts, with no reliable attribution from social. The audit is in `../../reports/social-reels-2026-09-24/`.

The goal is **more product starts**, measured separately for Live's first trial run, Prep's first mock interview, and Apply's account plus first application. A view is a discovery signal, not a user.

## Proposed daily publishing mix

| IST slot | Product | Format | Purpose | Veo opening |
|---|---|---|---|---|
| 09:07 | Apply | Carousel | Saveable job-search or application lesson | None |
| 10:37 | Live | Short reel | One Hindi/Hinglish interview moment | 8-second Fast clip |
| **11:37, new** | Prep | Reel | One company/role-specific practice question | Immediate hook card |
| 12:37 | Live | Reel | Actual interface demonstration with fictional CV | 4-second Fast clip |
| 14:37 | Prep | Reel | Weak answer, follow-up, improved answer | 4-second Fast clip |
| 16:37 | Live | Reel | Another persona/objection, not the morning scenario | 8-second Fast clip |
| 18:07 | Apply | Carousel | Job fit, CV, or form-filling lesson | None |
| 19:37 | Live | Reel | Real product workflow and one trial offer | 8-second Fast clip if existing sales format |
| **20:37, new** | Apply | Reel | Screen-based job match or form demo | Immediate hook card |
| 21:37 | Prep | Reel | Different company, role, or interview stage | 4-second Fast clip |

This retains every existing slot, adds two reels, and spends Veo on the six existing videos. The additions begin on rendered question/workflow cards and show the product interface, without a new generated actor. Eight reels per day means 56 videos per week, and the whole ten-post schedule means 70 posts per week. A mere change in actor or wording does not count as a new idea.

The two added reels are dispatched by `dispatch-extra-slots.yml` after the existing
on-time 10:37 and 19:37 cron-job.org runs, with a wait to 11:37 and 20:37 IST.
The `post.yml` crons are backups. A same-day publication receipt prevents a duplicate
if both triggers fire. This avoids needing access to the cron-job.org account.

The repo says YouTube tops out at six API uploads per day. That claim is outdated: Google's current API documentation states a default of 100 `videos.insert` calls per day in the upload bucket. The channel itself has a separate daily upload limit that varies by eligibility and history. Test the seventh and eighth daily upload for three days; if the channel rejects them, publish those two to Instagram/Facebook and leave YouTube at its accepted daily count. Do not retry channel-limit failures repeatedly.

## Credit ledger and guardrail

The workflow currently generates three 8-second Veo 3.1 Fast openings and three 4-second openings each successful full day, or **36 generated seconds/day**. It requests 720p video without audio. Google's listed Vertex rate is **$0.08 per generated second**, so the full-day opening estimate is **$2.88/day** or **$259.20 for 90 days**. This excludes paid writing, voice, test generations, prior films, failed-to-publish generations and other Cloud usage. It is a forecast, not the account balance. The new two reels add no Veo generation under this proposal.

The history currently records 272 generated opening seconds since 17 September, roughly $21.76 at that rate. History only records posts that reached `content/history.json`; it is not a bill. The owner estimates **$300 remaining for about 60 days**, with a later $300 top-up. Keep the later top-up separate until available. At the present six Veo openings per day, 60 days use about $172.80 for openings, leaving room for writing, voice, experiments and variance. Before raising the Veo cap, read the **actual unexpired credit balance and expiry date** in Cloud Billing. Google says the free trial ends after 90 days or when the credit is spent.

Let **B** be the credit remaining today and **R** the days left to expiry. Reserve the greater of $40 or 12% of B for Gemini writing, voice, tests and billing variance. The daily Veo allowance is at most `(B - reserve) / (0.08 × R)` generated seconds. If that is below 36, rotate some openings to existing footage while preserving the eight-reel schedule. Check the real balance every week and recalculate. Keep a separate project budget alert; an ordinary Google Cloud alert is not a hard spending limit. The existing code has a 2,600-second lifetime opening cap counted from 17 September. At 36 seconds/day it will stop after roughly 65 more full days, so adjust that cap only after confirming the billing balance and expiry, with a safety margin.

The key rule is to spend credit on footage that makes a scenario clearer. Do not lengthen a clip or add generated footage just to exhaust credit. If the credit is still substantially unspent after day 30, test better visual formats on strong topics, not more repeated ads. Never infer billing from history alone.

Sources: [Vertex Veo prices](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing), [Cloud free trial](https://cloud.google.com/signup-faqs), [YouTube API upload quota](https://developers.google.com/youtube/v3/docs/videos/insert), [YouTube channel upload limits](https://support.google.com/youtube/answer/57407), [Google Cloud budget alerts](https://docs.cloud.google.com/billing/docs/how-to/budgets).

## Creative system for high volume

Each reel must have one audience, one concrete problem, one useful example or product proof, and one product-specific action. Open on the question, screen, mistake or objection in the first two seconds. Show the answer or improvement before the sales CTA. Keep narration and on-screen text useful without sound. Clearly label fictional CVs and illustrative results; do not state guaranteed jobs, real-user outcomes or a fixed app response time.

Build a weekly idea board with at least 70 distinct briefs before scheduling ten posts/day. Each brief records product, persona, company or role, stage of job hunt, question/problem, proof to show, spoken opening, on-screen opening and landing page. Reject another brief if it repeats the same core question and product proof from the prior 30 days. One company question can become a Live answer example and a Prep practice example only when the shown experience and takeaway differ substantially.

The first four content families to test are:

1. **Specific company and role questions:** relocation, project ownership, team conflict and salary expectations. Verify any company-specific claim; do not imply a question is universal.
2. **Hindi/Hinglish switches:** the exact question and a clear sample answer, not a generic reassurance.
3. **Before and after in Prep:** spoken first answer, follow-up question, useful revision from the CV.
4. **Apply workflow:** matching job, tailored CV or autofilled form, with the user reviewing and submitting.

Retire the six-times-repeated rejection hook and four-times-repeated roti hook during the first test cycle. Keep three distinct visual structures in rotation: real interface, narrated example with cards, and a candidate scene with a product screen. The generated actor is an opening, not the proof of what the app does. Show the real product step early. Automatically check claim accuracy, duplicate concepts, media integrity, readable text, audio, platform-specific CTA and correct destination. Review a sample of finished posts every week and refresh the idea board from real user questions.

## Route viewers into the right product

Every post should name one product and one action. Put Live, Prep and Apply as clearly named links in channel profiles wherever supported. YouTube Shorts description/comment URLs are not clickable; the current `compose_captions` YouTube wording assumes they are, so the spoken and on-screen CTA should direct viewers to the appropriate profile link. Instagram captions also point to a profile link. Facebook may use the product's direct, tagged URL. Avoid burying the action under the same long feature and price block on every post.

Use tagged links that preserve product, platform, creative ID and campaign so visits can be tied to posts. Configure GA4 read access for the reporting service account, repair Meta insights permissions, enable YouTube Analytics API, and instrument product starts: Live download plus first run, Prep first mock, Apply signup plus first reviewed application. On `apply.interviewsarthi.com`, add the missing analytics coverage or equivalent privacy-conscious event recording. The scorecard marks these outcomes unknown until the data is connected. Do not claim that view counts caused purchases without linked evidence.

Google's [link guidance](https://support.google.com/youtube/answer/13748639?hl=en) confirms that Shorts URLs in descriptions and comments are not clickable. YouTube also says viewing choice, watch duration and average percentage viewed affect recommendation performance. [Shorts discovery guidance](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en).

## Measurement and decisions

Record a row per post per platform, including product, content family, hook, format, generated seconds, publication status, publish time, 48-hour views, seven-day views, engagement, profile/site visits and product starts. Compare posts at equal ages. Report separate medians for YouTube, Instagram and Facebook; do not combine their view definitions. For YouTube, add shown-in-feed, chose-to-view, engaged views, average watch duration and retention when API/Studio access is available. For Instagram and Facebook, collect views, watch time, saves/shares and profile visits when the correct permissions are granted. On the site, track product starts and paid outcomes by source where feasible.

Prepare the same one-page scorecard every seven days: posts scheduled/published by platform; top and bottom five reels at 48 hours with their first two seconds; median attention by product and content family; tagged landing visits; first product starts; paid orders excluding owner tests; generated Veo seconds; actual Cloud charges and credit left. Mark missing metrics as unknown. Use the first week to establish a 48-hour baseline because the existing audit contains lifetime snapshots only.

Use this decision matrix at each review:

| Observation | Next action |
|---|---|
| Views and watch time improve; product starts improve | Keep the distinct format and give it more of the existing slots. |
| Views improve; site visits or starts do not | Fix the CTA, profile link, matching landing page or trial setup before producing more of that format. |
| Views stay low; people who reach the site do start | Improve the first two seconds and distribution while keeping the useful product demonstration. |
| Views and starts stay low across ten or more posts of one format | Replace that format's opening and proof; test again at the same volume. |
| Fewer than ten measured posts or missing analytics | Treat results as inconclusive; fix collection or wait for comparable data. |

| Checkpoint | Decision |
|---|---|
| **Day 3** | Verify all ten slots produce distinct posts, both extra reels publish on Meta, and whether YouTube accepts uploads seven and eight. Fix failures and confirm generated-second ledger against billing. |
| **Day 7** | Review the first two seconds and audience retention of the highest and lowest posts at equal age. If most new reels still draw single-digit views and no chosen-to-view improvement, rewrite hooks and product proof; maintain the volume while changing the creative. Check landing clicks and product starts. |
| **Day 14** | Compare at least ten examples per content family where possible, using 48-hour median views, retention, qualified visits and starts. Keep a family for product starts even if its views are modest. Pause formats with repeated low attention and no starts. Reallocate slots among the three products; do not confuse age or audience differences with a proven causal win. |
| **Day 30** | Check real users, paid conversions and credit remaining. If attention rose but starts did not, fix the CTA and landing/onboarding path. If starts rose but purchases did not, inspect trial experience and pricing comprehension. If attention is still weak, redesign openings and evidence rather than raising volume further. Recalculate paid footage for the remaining trial days. |
| **Every 14 days thereafter** | Continue the best distinct topics, retire repeats, and balance remaining credit over actual days to expiry. Document each slot change and the measured reason. |

Do not use a fixed view target as the sole success condition. The existing baseline is too small and lacks retention and Meta views. The primary success measure is **qualified product starts per week**, followed by paid Live/Prep customers and meaningful Apply usage. The plan deliberately raises output now and uses the checkpoints to decide what to produce next.
