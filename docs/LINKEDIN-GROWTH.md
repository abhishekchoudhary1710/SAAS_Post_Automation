# LinkedIn: product visits and sales

Research and implementation: 28 September 2026.

## What the audit found

The production LinkedIn Page route sent only the daily jobs reel's caption and first card.
The text asked readers to visit both a job list and Prep Sarthi, without creative-level tracking.
The marketing website and ApplySarthi deliberately remove query strings from analytics page
locations. That protects private data, but needed an explicit campaign override to preserve
this campaign's source and post ID.

A read-only Buffer check found one sent Page post, published on 28 September:
[the AWS/Bengaluru jobs post](https://www.linkedin.com/feed/update/urn:li:share:7510287540055076864).
It is too new to establish a reach or sales baseline. Buffer supplied no outbound-click metric
for it. Zero values in a new or unsupported metric are not evidence of no audience interest.

## Research and how it changes the work

1. LinkedIn says its 2026 feed changes aim to improve relevant professional content and reduce
   generic recycled material and engagement bait. The content should demonstrate a specific
   job-search or interview problem, using the actual products and clearly labelled examples.
   [LinkedIn's feed update, 12 March 2026](https://news.linkedin.com/2026/ImprovingTheFeed).
2. LinkedIn's Page guidance recommends actionable professional advice and content that is not
   excessively promotional. Each lesson here gives a usable takeaway, then explains how the
   relevant app helps the reader act on it.
   [LinkedIn Page posting guidance](https://business.linkedin.com/content/dam/lem/business/en/advertise/linkedin-pages/lms-linkedin-page-posting-best-practices-one-pager.pdf).
3. Buffer analysed more than two million posts from over 94,000 accounts and identifies two
   to five posts weekly as a sustainable starting cadence. This is observational evidence,
   not proof of growth on this specific company Page. The owner chose two posts every day,
   including Saturday and Sunday. Treat the resulting fourteen weekly posts as a measured test.
   [Buffer posting-frequency study](https://buffer.com/resources/how-often-to-post-on-linkedin/).
4. Buffer's 2026 engagement report finds stronger median engagement for LinkedIn PDF documents
   than for the other formats it examined. It also observes higher engagement where authors
   reply to comments. Neither association establishes sales lift or causality. We test four
   educational documents, three short videos and seven images weekly with clear product CTAs.
   [Buffer's 2026 report](https://buffer.com/resources/state-of-social-media-engagement-2026/).
5. LinkedIn explicitly disallows automated comments and takes action against engagement pods.
   Scheduling Page posts through Buffer is the automation here. Reply personally to useful
   questions; this campaign does not automate reactions, DMs or comments.
   [LinkedIn on authentic conversations](https://news.linkedin.com/2026/authentic-content-and-conversations).

The one-link structure, product mix, initial time, four-week review and content examples below
are recommendations for this business. They are hypotheses to measure, not algorithm rules.
There is no claim that external links must be hidden in comments, that hashtags guarantee
distribution, or that an automated Page can guarantee revenue.

## What runs

Two posts every day, including Friday, Saturday and Sunday. All times below are **IST**.

| Day | First post | Second post |
|---|---|---|
| Monday | 5:17 PM — ApplySarthi | 10:17 PM — Prep Sarthi |
| Tuesday | 4:17 PM — Prep Sarthi | 10:17 PM — Interview Sarthi |
| Wednesday | 4:17 PM — Fresh jobs | 7:17 PM — ApplySarthi |
| Thursday | 5:17 PM — Prep Sarthi | 9:17 PM — Interview Sarthi |
| Friday | 3:17 PM — Interview Sarthi | 5:17 PM — Prep Sarthi |
| Saturday | 9:17 AM — ApplySarthi | 6:17 PM — Interview Sarthi |
| Sunday | 6:17 AM — Prep Sarthi | 10:17 PM — Fresh jobs |

The starting hours draw on [Buffer's September 2026 study of 4.8 million LinkedIn posts](https://buffer.com/resources/best-time-to-post-on-linkedin/).
It reports times in the target audience's local timezone. We use India, the current campaign
market. Most chosen hours are listed daily peaks; Wednesday's second post uses the broader
late-afternoon/evening window to leave three hours after the first post. Sunday uses the
reported early-morning and late-evening options to avoid posting twice within one hour.
The 17-minute offset avoids the top of the hour; it is not a researched engagement advantage.
These are starting hypotheses, not proof of maximum reach for this Page. Compare the Page's
impressions and tracked product visits at the four-week review before changing the times.

GitHub Actions controls the schedule and calls Buffer's `shareNow` API. Buffer's saved queue
slots do not control this campaign. Cron is UTC, converted from IST in the workflow. GitHub
can delay scheduled runs, and installation, rendering and Buffer processing add latency:
the table shows trigger times, not guaranteed second-accurate publication times. A scheduled
run that starts more than three hours after its slot, or on a later IST day, skips instead of
posting (`late_start`). On 29 Sep 2026 the Monday 17:17 IST cron started at 00:16 IST Tuesday,
took Tuesday's first slot and posted at midnight. The legacy
internal slot name `midday` means the first daily post, even when that post is in the afternoon.

On 29-30 Sep 2026 GitHub started all four crons 4-6 hours late (Wednesday 16:17 at 22:01, 19:17 at
00:05), so every one skipped and the Page went two days without a post. Since 1 Oct 2026 the
ApplySarthi VM dispatches each slot on time: `tools/systemd/linkedin-post-{midday,evening}.timer`
run `gh workflow run linkedin-growth.yml -f mode=publish -f slot=...` at the IST times above. The
crons stay as the backup, and `prepare` refuses a second post for a date and slot. Install or
update on the VM with `ln -sf "$PWD"/tools/systemd/linkedin-post* ~/.config/systemd/user/`, then
`systemctl --user daemon-reload && systemctl --user enable --now linkedin-post-midday.timer
linkedin-post-evening.timer`. A test keeps the timers' times equal to `knowledge/linkedin.json`.

An extra job list can be posted by hand at any time with `gh workflow run linkedin-growth.yml -f mode=publish
-f slot=extra` (or Run workflow, mode publish, slot extra). It uses the same job-list copy as the scheduled
jobs posts, is recorded under slot `extra`, and leaves the day's two scheduled posts untouched. One per day.

Each caption names its app, explains its benefit and free entry point, and ends with one
prominent clickable destination. It uses the relevant product page rather than a generic
homepage. Paid offers explicitly apply to India. Most Prep posts are four-page PDFs. Apply
uses checklists, fictional before/after examples and labelled website illustrations; jobs
use current feed data; Interview Sarthi uses Windows interface images and useful FAQs.

At the owner's request, each post uses five distinct relevant hashtags: its audience/category,
specific topic, related context and our own product brand. Job posts use JobSearch, the
collection's role and location, Hiring and ApplySarthi; missing or duplicate role
and location tags use relevant job-search alternatives. Generic competitor-used hashtags are useful only
when relevant to our post; competitor brand tags and unrelated viral tags are excluded.
This follows [LinkedIn's Page guidance](https://business.linkedin.com/advertise/linkedin-pages/best-practices)
to use 3–5 relevant hashtags, without claiming a guaranteed reach increase. Five is the
upper end of that recommendation, not a separately established platform hashtag limit.

Wednesday and Sunday job posts now identify the employers as the hiring parties, then add
one short Prep Sarthi practice mention. Their sole tracked link still opens the job collection.
The publication receipt records `creative_version=jobs-prep-v1`, so analytics can compare
these posts with earlier job posts and product-only posts without mixing the groups.

Three slots now use native 23-second silent MP4 videos: Tuesday evening (Interview Sarthi),
Wednesday evening (ApplySarthi) and Thursday first slot (Prep Sarthi). Each combines a hook,
three seconds of existing owned illustrative footage, a product visual, a practical lesson
and a product CTA. The scene and caption disclose that this is an edited illustration,
not a customer recording or live demo. No voice or paid generation service is called.
See [asset provenance](LINKEDIN-ASSETS.md) and the
[competitor research](LINKEDIN-COMPETITOR-RESEARCH-2026-09-28.md).

Forty-eight authored product topics cover four weeks, plus eight fresh job-list posts.
The minimum product-topic reuse interval is 28 days. Jobs fetch the current feed and avoid
recent lists. Evergreen topics rotate after the initial library is used; this is authored
rotation, not unbounded AI generation. Update topics from genuine customer questions at the
monthly review. Prices and screenshots must be refreshed when the products change.

Every PDF contains a practical lesson, a Prep interface image or labelled website illustration, and a free-demo CTA. Fictional
examples are labelled; no invented customers, hiring outcomes, usage counts or ROI claims.
Windows screenshots and requirements remain specific to the live app. Prep is browser-based
practice; Apply is a free job tool. They must never borrow each other's trial or platform claims.

## Links and attribution

All three product URLs were checked live: HTTP 200, correct destinations, tracking preserved.
The scheduled preparation step repeats that check on the selected CTA and stops before posting
if a link fails or redirects away from its destination or loses tracking.

Example:

```text
https://interviewsarthi.com/prep/?utm_source=linkedin&utm_medium=social&utm_campaign=linkedin_product_growth&utm_content=li-20260929-prep-project-midday
```

The clickable caption link carries tracking; the image footer carries the readable product URL.
The website and job-page analytics accept only the exact campaign/source/medium and a bounded
creative ID. They keep arbitrary query values, email addresses and receipt keys out of GA4
page locations. The change uses Google's documented campaign configuration fields:
[GA4 configuration reference](https://developers.google.com/analytics/devguides/collection/ga4/reference/config).

GA4 exploration setup:

- Filter Session campaign to `linkedin_product_growth` and source/medium to `linkedin / social`.
- Break down Session manual ad content, landing page and date.
- Compare engaged sessions and `product_click` first.
- For Prep, compare `mock_demo_start`, `begin_checkout` and `purchase`.
- For Live, compare `download_click`, `begin_checkout` and `purchase`. Downloads are not installs.
- For Apply, check visits to the job collections and downstream usage; do not count free job
  applications as sales.

Browser purchase events are signals, not an audited payment ledger. Reconcile paid orders
with the payment system. Cross-device journeys, ad blockers, consent, Microsoft Store paths,
lost cookies and visits outside the browser session can limit attribution. This change does
not implement a payment-ledger join or claim that every sale is measurable.

The daily Buffer report reads publication status and available metrics into
`content/linkedin_growth.json`. It marks missing values as unknown and captures available
metrics in 1–3-day, 7–9-day and 28–30-day windows for age-aware comparisons, using the source
timestamp rather than the time we read the API. Reports show the source update time in IST.
Initial snapshots dated before Buffer acceptance are labelled awaiting first network refresh
and their zero values are displayed as unknown. Snapshots older than 26 hours are labelled
stale and never frozen as a milestone result. Buffer refreshes network metrics daily; new
posts can take approximately 24 hours to show impressions. A supplied
zero can also mean the source did not report that metric. Platform clicks, when supplied,
are not a substitute for GA4 website visits. There is no automatic winner selection from
likes or a small sample.
[Buffer metrics guide](https://developers.buffer.com/guides/post-metrics.html).

## Operations and failure handling

### Private campaign dashboard

The owner's [Control Room — LinkedIn](https://apply.interviewsarthi.com/admin#linkedin) joins
public Buffer publication receipts to the existing GA4 property using each `li-` creative ID.
The existing server monitor collects this every 30 minutes with its read-only Google service
account. No Google credential or private GA4 result is copied into this public repository.

It shows available Buffer impressions, reach, platform clicks, reactions, comments and shares,
with their source timestamps; GA4 visits, engaged visits, job views, employer-link clicks,
app clicks, CV uploads, match views, CV tailoring, Prep demo starts/ends, downloads, checkouts,
purchase events and reported revenue. Job-to-app links preserve only the validated campaign
fields through the owned redirect. CVs, keys, emails and job identifiers are not event payloads.

GA4 covers a rolling 30-day window and can take 24–48 hours to finish processing; Buffer
figures are lifetime snapshots on their own refresh cadence. The dashboard flags missing
tracking, stale Buffer data and GA4 sampling/thresholds. These are descriptive comparisons,
not an A/B test; compare similar post ages. It never divides GA4 visits by lifetime impressions
and calls that an outbound click-through rate.

Prep confirmations now retain the server-provided checkout amount/currency and send a hashed,
stable transaction ID after payment is confirmed, suppressing repeat purchase events on reload.
Older events or returns without the original checkout context can still lack value. Browser
purchase reports can include owner tests; the Control Room's existing Money section separately
reads payment records and excludes known owner tests. Per-post ledger attribution, Store installs
and cross-device purchases remain unavailable. No sale is inferred from a download or job click.

Sources: [GA4 dimensions and metrics](https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema),
[GA4 data freshness](https://support.google.com/analytics/answer/12233314).

`linkedin-growth.yml` is independent of the reels' creative generation. The original jobs
slot continues on its other configured destinations; its Page posting is disabled by
`LINKEDIN_PAGE_CAMPAIGN=true` in `post.yml`. The previous signed-in profile route remains
separate. The new campaign validates that its Buffer channel is a Page even when pinned by ID.

Buffer accepts publicly hosted image, document and video URLs. The campaign uses a separate
`linkedin-media` branch so another reel's upload cannot immediately replace its files.
Both workflows share `social-post` concurrency. PDFs use the documented document asset
with a thumbnail and title. Videos use only a video asset URL, without the image/document
thumbnail field. [Buffer video example](https://developers.buffer.com/examples/create-video-post.html),
[Buffer media hosting](https://developers.buffer.com/guides/hosting-media.html),
[Buffer API reference](https://developers.buffer.com/reference.html).

Before submitting, the workflow commits a reservation for that date and slot to `main`. It then calls
Buffer and saves the returned ID. A daily read checks whether the status becomes `sent`.
An accepted ID is not described as confirmed publication. On ambiguous failure or cancellation,
the reservation blocks a duplicate. Check Buffer and the Page before manually clearing a failed
reservation. A failure after reservation can skip that slot's post; avoiding duplicate public
posts takes priority over blind retries. GitHub sends normal failure notifications.

The status report runs after each publication run and at 23:47 IST daily, including weekends.
Successful posts are then checked in the day-1, day-7 and day-28 windows. Each report makes at
most 20 post-status reads and waits at least an hour between attempts for the same post.
The scheduled ceiling is 1,800 reads per 30 days plus approximately 420 requests to validate
channels and publish 60 posts, within the observed 3,000-request Free API allowance. Manual
runs and other API consumers use the same allowance; this is not a reserved quota. Buffer's
observed Page posting limit was 50/day and its Free queue capacity was 10 pending posts.
This campaign sends two posts daily using shareNow, without filling a month's queue.
 Expiring API keys and unresolved statuses
appear in its Actions summary. There are no new paid generation calls, extra service accounts,
or automated outbound messages in this campaign. GitHub/Buffer account quotas still apply.

## Preview and review

```bash
python -m agent.linkedin_growth preview --date 2026-09-29 --days 14 --out out/linkedin-preview
python -m unittest discover -s tests -p 'test_linkedin*.py' -v
```

Open `out/linkedin-preview/index.html` for captions, images, playable videos and linked PDFs.
The preview respects saved history and omits already reserved slots; a full future fortnight
has 28 posts. It does not modify history or make network calls. Jobs
previews use a sample explicitly labelled on the index; production always requests fresh data.
The workflow's default manual mode is `preview`, which does not publish or reserve a date/slot.
To publish the second slot manually (an explicit owner-authorized action):

```bash
gh workflow run linkedin-growth.yml -f mode=publish -f slot=evening
```

A later scheduled run for the same date and slot will skip it, preventing a duplicate.

For an owner-requested manual metrics read, use `python -m agent.linkedin_growth report
--post-id BUFFER_POST_ID`. This reads only that known campaign post once, even if recently
checked. It cannot force Buffer to refresh LinkedIn's counters. Save the updated history
along with routine publication receipts.

On rollout day, 28 September, the existing sent jobs post is recorded as the first slot.
The owner authorized publishing the Prep example immediately as the second slot. Neither
slot should run again that day; the normal timed cadence starts the next day.

For the first four weeks keep the format and schedule stable. Review weekly for broken links,
publication errors, useful questions, engaged visits and demo starts. Reply personally to
substantive questions. At four weeks, compare product-specific conversion signals at similar
post ages. If impressions grow without visits, adjust the app benefit and CTA. If visits grow
without starts, inspect the landing page and setup friction. If starts grow without verified
purchases, inspect the offer and product experience. Change one major variable at a time.
