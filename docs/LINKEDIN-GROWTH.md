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
   not proof that five posts will cause growth on this specific company Page. We start with
   five weekday posts and evaluate the actual audience.
   [Buffer posting-frequency study](https://buffer.com/resources/how-often-to-post-on-linkedin/).
4. Buffer's 2026 engagement report finds stronger median engagement for LinkedIn PDF documents
   than for the other formats it examined. It also observes higher engagement where authors
   reply to comments. Neither association establishes sales lift or causality. We test two
   educational documents weekly and keep the rest as readable images with clear product CTAs.
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

| Day | Reader need | Product and destination | Format |
|---|---|---|---|
| Monday | Match experience to a role and submit a stronger application | ApplySarthi, `/apply/` | Checklist image |
| Tuesday | Explain a project or answer a follow-up | Prep Sarthi, `/prep/` | Four-page PDF |
| Wednesday | Find current openings | A specific collection on `apply.interviewsarthi.com` | Jobs image |
| Thursday | Practise an answer and improve it | Prep Sarthi, `/prep/` | Four-page PDF |
| Friday | Evaluate live assistance on Windows | Interview Sarthi, `/live/` | Actual interface image |

The initial time is 12:17 IST, Monday to Friday. It is a test slot for an India-focused audience,
not a researched universal best time. English copy makes the use cases understandable more
broadly, but quoted paid offers explicitly apply to India. The user prioritised endorsement
of the apps and website. Each caption therefore names its app, explains its benefit and free
entry point, and ends with one prominent clickable destination. It does not send people to
a generic homepage when a relevant product page exists.

Twenty authored product posts supply five weeks without repeating a product topic. There is
a 28-day minimum reuse interval. Job posts fetch the current feed and avoid recent lists.
Evergreen topics rotate after the initial library is used; this is authored rotation, not
unbounded AI generation. Update the library from genuine customer questions at the monthly
review. Prices and screenshots must be refreshed when the products change.

Every PDF contains a practical lesson, the real Prep interface, and a free-demo CTA. Fictional
examples are labelled; no invented customers, hiring outcomes, usage counts or ROI claims.
Windows screenshots and requirements remain specific to the live app. Prep is browser-based
practice; Apply is a free job tool. They must never borrow each other's trial or platform claims.

## Links and attribution

All three product URLs were checked live: HTTP 200, correct destinations, tracking preserved.
The scheduled preparation step repeats that check on the selected CTA and stops before posting
if a link fails or redirects away from its destination or loses tracking.

Example:

```text
https://interviewsarthi.com/prep/?utm_source=linkedin&utm_medium=social&utm_campaign=linkedin_product_growth&utm_content=li-20260929-prep-project
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
`content/linkedin_growth.json`. It marks missing values as unknown and retains a first
7-to-9-day snapshot for age-aware comparisons. Buffer's source metrics may lag; a supplied
zero can also mean the source did not report that metric. Platform clicks, when supplied,
are not a substitute for GA4 website visits. There is no automatic winner selection from
likes or a small sample.

## Operations and failure handling

`linkedin-growth.yml` is independent of the reels' creative generation. The original jobs
slot continues on its other configured destinations; its Page posting is disabled by
`LINKEDIN_PAGE_CAMPAIGN=true` in `post.yml`. The previous signed-in profile route remains
separate. The new campaign validates that its Buffer channel is a Page even when pinned by ID.

Buffer accepts publicly hosted image and document URLs. The campaign uses a separate
`linkedin-media` branch so another reel's upload cannot immediately replace its files.
Both workflows share `social-post` concurrency. PDFs use the documented document asset
with a thumbnail and title. [Buffer media hosting](https://developers.buffer.com/guides/hosting-media.html),
[Buffer API reference](https://developers.buffer.com/reference.html).

Before submitting, the workflow commits a reservation for that date to `main`. It then calls
Buffer and saves the returned ID. A daily read checks whether the status becomes `sent`.
An accepted ID is not described as confirmed publication. On ambiguous failure or cancellation,
the reservation blocks a duplicate. Check Buffer and the Page before manually clearing a failed
reservation. A failure after reservation can skip that day's post; avoiding duplicate public
posts takes priority over blind retries. GitHub sends normal failure notifications.

The evening report runs daily, including weekends. Expiring API keys and unresolved statuses
appear in its Actions summary. There are no new paid generation calls, extra service accounts,
or automated outbound messages in this campaign. GitHub/Buffer account quotas still apply.

## Preview and review

```bash
python -m agent.linkedin_growth preview --date 2026-09-28 --days 14 --out out/linkedin-preview
python -m unittest discover -s tests -p 'test_linkedin*.py' -v
```

Open `out/linkedin-preview/index.html` for ten captions, images and linked PDFs. Wednesday
previews use a sample explicitly labelled on the index; production always requests fresh data.
The workflow's default manual mode is `preview`, which does not publish or reserve a date.

For the first four weeks keep the format and schedule stable. Review weekly for broken links,
publication errors, useful questions, engaged visits and demo starts. Reply personally to
substantive questions. At four weeks, compare product-specific conversion signals at similar
post ages. If impressions grow without visits, adjust the app benefit and CTA. If visits grow
without starts, inspect the landing page and setup friction. If starts grow without verified
purchases, inspect the offer and product experience. Change one major variable at a time.
