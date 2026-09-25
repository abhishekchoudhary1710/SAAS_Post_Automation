# Interview Sarthi: business brief

This file is the agent's source of truth about the business. Every post is written
from what is here. Edit it freely; keep facts accurate, because the agent is told to
use only facts from this file and never to invent numbers, quotes or testimonials.

Last reviewed: 13 September 2026.

## One line

Interview Sarthi is a Windows app that helps you during your online interview, live:
it listens to the call, shows what the interviewer just asked, and drafts what to say,
from your own resume, in English, Hindi or Hinglish. Built for Indian candidates. 30
minutes free, then one-time passes from Rs 99. Runs on your own free Google Gemini key.

## Three products, and which one a post is about

There are three, and every post sells exactly one of them. The post's pillar says which.
Never mix two in one post beyond a single closing line.

1. **Interview Sarthi**, the Windows app described above. Live help during the real
   interview. Most posts.
2. **Prep Sarthi**, at interviewsarthi.com/mock. A voice mock interview in the browser,
   before the real one. See its own section below.
3. **ApplySarthi**, at interviewsarthi.com/apply. Finds jobs and fills applications.
   See its own section below.

## What Interview Sarthi is not (read this before writing an Interview Sarthi post)

Interview Sarthi is not a preparation tool. It has no mock interviews, no question banks,
no courses, no coaching and nothing to rehearse. Its help arrives while the real interview
is on, on the candidate's own screen. An Interview Sarthi post that says it helps you
"prepare", "practise" or "get ready" describes a different product, and the code rejects
it. The right picture is always the same: the interviewer asks, and the answer appears.

Practice is Prep Sarthi's job, and a Prep Sarthi post is free to use those words, because
there the words are true. Keep the two apart: one is before, the other is during.

Name: "Sarthi" is Hindi/Sanskrit for the charioteer who guides the warrior
(Krishna to Arjun). Pronounced "saar-thee".

## What it does, in detail

- Runs as a desktop app on Windows 10 and 11. Install from the Microsoft Store or the
  direct installer. Setup takes about a minute.
- During an online interview on Teams, Zoom, Google Meet, Webex or any other call app, it listens to the
  call audio on your PC. No bot joins the call and nothing appears in the participant
  list.
- It transcribes the interviewer live and shows every question with a timestamp.
- For each question it drafts one natural, spoken-style answer the candidate can say
  as written. Each sentence sits on its own line so you can pause and find your place.
  Two to four key phrases are highlighted.
- Answers are grounded in the resume you uploaded during setup. "Walk me through your
  last project" is answered with your real project, not a template. The app is instructed to avoid inventing experience; suggestions still need checking.
- Languages: English, Hindi and Hinglish. It follows whichever language the
  interviewer uses, including a switch mid-sentence, which is how many Indian
  interviews actually run.
- Answers stream onto the screen. Do not advertise a fixed response time; latency varies.
- Screen reading: if the interviewer shares a code snippet or a diagram, one key reads
  the shared screen and drafts the answer (code, output, short explanation).
- Ask box: type any question about the meeting and get an answer from the transcript.
- Session transcripts are saved. The current product does not produce a post-call AI summary.
- Controls: fade, hide to a slim bar, pause listening, clear context.
- Screen-share privacy: on Windows 10 (2004+) and Windows 11 the overlay requests capture
  exclusion, so it remains visible locally and is omitted from supported screen sharing.
  Include this benefit in sales reels with a labeled local/shared-view illustration.
  Capture support varies; failures are possible and the app warns when detected.
  Do not promise that the app is always invisible or undetectable.

## How it works under the hood (for "how does it work" content)

- Everything runs on the candidate's own free Google Gemini API key from
  aistudio.google.com. No credit card is needed for the key. The free tier is enough
  to run interviews, so the ongoing AI cost is Rs 0.
- Audio and resume go from the candidate's PC directly to Google Gemini and nowhere
  else. Interview Sarthi runs no servers and never sees the interview.
- The candidate's microphone is never sent to the model. Only the meeting audio is,
  so the candidate's own voice can never trigger an answer.
- Licensing is a pass key checked against the payment provider (Dodo Payments). One
  key works on up to two devices for the 1-Month Pass.

## Pricing (exact, use only these numbers)

| Plan | Price | Notes |
|---|---|---|
| Free | Rs 0 | 30 minutes of answers per device, every feature, no card, no signup |
| 2-Day Pass | Rs 99 one-time | 2 days from purchase, unlimited sessions, 1 device. About Rs 50 a day |
| 1-Month Pass | Rs 299 one-time | 30 days, unlimited sessions, 2 devices. About Rs 10 a day |

These are the only two passes (since 25 September 2026). There is no 7-day or 3-month pass;
never mention one.

Outside India (US dollars, checkout by Dodo Payments, shown in the buyer's own currency at
checkout). Use these, and only these, in a post made for viewers outside India:

| Plan | Price outside India |
|---|---|
| Free | $0, the same 30 minutes |
| 2-Day Pass | $9.99 one-time, 1 device |
| 1-Month Pass | $29.99 one-time, 2 devices. About $1 a day |

- Nothing auto-renews. A pass just ends. Nothing is charged again.
- Paid by UPI (GPay, PhonePe, Paytm) or card, checkout by Dodo Payments.
- The first pass has a 7-day money-back guarantee, no questions asked.
- When the free minutes run out mid-call the app does not stop: the transcript
  continues, only the answers pause, and a pass key can be pasted in the overlay
  without a restart.
- Market context that may be stated: other Indian tools sell minutes (around Rs 99 for
  30 minutes) and global tools charge monthly subscriptions that renew on their own.
  Do not name competitors in social posts.

## Who it is for

Primary: Indian job seekers who interview online.

- Freshers and final-year students in campus placements at TCS, Infosys, Wipro,
  Accenture, Cognizant, Capgemini, HCL. Campus season peaks July to October; TCS NQT
  runs February to April.
- Early-career professionals (0 to 5 years) switching jobs, doing 2 or 3 online
  rounds on different days.
- Candidates whose problem is recall and language, not knowledge: people who freeze
  on a question they know the answer to, or who lose an interview because it switched
  to Hindi halfway through.
- People who are more comfortable in Hinglish than in polished English.

Devices: they interview on a Windows laptop. Many browse from a phone, so posts should
say "Windows app" clearly and send phone viewers to the website.

## The problems it solves

1. Blanking on a question you know the answer to.
2. Interviews that switch between Hindi and English, where English-only tools break.
3. Generic template answers that do not mention your actual projects.
4. Expensive, dollar-priced, auto-renewing subscriptions built for US salaries.
5. Privacy worries about uploading your resume and interview audio to a vendor.
6. Not remembering what was asked afterwards (the transcript helps with this).

## Differentiators (what to lead with)

1. Hinglish. Answers in the language the interviewer used. This is the main
   differentiator and the thing US tools get wrong.
2. Your resume, your words. Answers about your real projects.
3. Rupees, one-time. From Rs 99. Nothing renews.
4. 30 minutes free with every feature, no card.
5. Private by design: your own free Gemini key, no vendor servers.
6. Screen reading for shared code and diagrams.
7. Session transcript of what was asked.

## What every social post must convey

A stranger scrolling past has never heard of us. Every post, in every pillar, must leave them
able to answer three questions: what is it, where does it run, what does it cost.

- What it is, in the first slide or first caption line: a Windows app that listens to your
  online interview and shows you what to say, from your own resume, in English, Hindi or
  Hinglish.
- What it looks like doing that: one real interviewer question and the answer that appeared
  on screen, labelled as Interview Sarthi's output. This is the demonstration, and it is also
  the useful part the viewer saves.
- What it costs, on the closing card: 30 minutes free with every feature, no card, then
  one-time passes from Rs 99. Link in bio.

Tips without the product are wasted reach. Product without the tip is an advert nobody
watches. Each post is one interview moment, handled on screen by the app.

## Positioning and voice

The framing is "live help during your online interview, from your own resume, in
Hinglish too". Sarthi is the charioteer beside the warrior in the battle itself, not
the coach before it.

- Say: "live", "during the interview", "while the interview is on", "on your screen",
  "the answer appears", "crack the round", "clear the interview with Interview Sarthi
  beside you", assistant, guide, "in your words", "from your resume", "never blank
  again", "answers in Hinglish".
- Never say: prepare, preparation, prep, practise, practice, practice partner, mock
  interview, rehearse, revise, coaching, training, "get ready". The app is not a prep
  tool, and these words are rejected in code wherever they describe the product.
- Do not claim cheating, undetectability, universal invisibility, or guaranteed interview
  outcomes. The permitted privacy wording is "hidden from supported screen sharing";
  capture support varies. The app drafts from the candidate's own resume and does not
  manufacture experience. Screen-share exclusion does not establish permission to use
  an assistant in a particular interview.
- Never write a social post about the screen-reading feature: the interviewer sharing a
  screen, a shared code snippet, or answering an on-screen technical question. It is a real
  feature and it is documented on the website, but in a fifteen-second video with no context
  it reads as helping someone through a live coding test, which is the fastest way to lose
  the accounts. Write about language, recall and resume-grounded answers instead.
- Social posts lead with the recall and language problem, because that is what this
  audience actually searches for. Technical capabilities are documented on the website,
  which is the right place for them.
- Never promise a job, an offer or a selection. Never invent testimonials, user
  counts, success rates or quotes.
- Be direct and warm. Short sentences. Talk like a helpful senior who has sat in
  these interviews. Indian context: campus placements, HR round, TR round, service
  companies, notice period, LPA, "tell me about yourself".
- Hinglish posts use Roman script (Latin letters) on screen, e.g. "Interviewer ne
  Hindi mein pooch liya? Ab ghabrana nahi."
- No em dashes in any text. Use a comma or a full stop.
- The ethics question, if it ever comes up: Interview Sarthi is direct about what it
  is. The site publishes a guide on which uses are fine, which break rules you agreed
  to, and which are grey. It drafts from your own resume and cannot manufacture
  experience. Link the guide rather than argue:
  https://interviewsarthi.com/guides/ai-in-interviews-rules.html

## Links

- Website: https://interviewsarthi.com
- Pricing: https://interviewsarthi.com/#pricing
- Microsoft Store: https://apps.microsoft.com/detail/9NMKQPSQ1KS8
- Free Gemini key guide: https://interviewsarthi.com/free-gemini-api-key-guide.html
- Hinglish interview help: https://interviewsarthi.com/hinglish-interview-help.html
- Help: https://interviewsarthi.com/help.html
- Guides index: https://interviewsarthi.com/guides/

Guides that posts can point to (topic in brackets):

- guides/self-introduction-interview-hinglish.html (tell me about yourself, Hinglish)
- guides/hinglish-interview-answers.html (Hinglish answers)
- guides/hr-interview-questions-hinglish.html (HR round in Hinglish)
- guides/why-should-we-hire-you.html
- guides/strengths-and-weaknesses-interview.html
- guides/salary-expectation-answer.html
- guides/reason-for-job-change.html
- guides/career-gap-explanation-interview.html
- guides/first-job-interview-guide-freshers.html
- guides/tcs-interview-questions-freshers.html
- guides/infosys-interview-questions-freshers.html
- guides/wipro-interview-questions-freshers.html
- guides/accenture-interview-questions-freshers.html
- guides/cognizant-interview-questions-freshers.html
- guides/capgemini-interview-questions-freshers.html
- guides/tcs-infosys-wipro-hr-interview-questions.html
- guides/accenture-cognizant-capgemini-hr-interview.html
- online-interview-tips.html (online interview setup tips)
- can-interviewer-see-my-screen.html

## Frequently asked questions (answer these the same way every time)

- Which platforms? Windows 10 and 11. Any call app that plays through the speakers:
  Teams, Zoom, Meet, Webex and others.
- Mac or phone? Not yet. Windows only.
- Is it free? The first 30 minutes are free with every feature, no card. After that,
  passes from Rs 99.
- Which pass for one interview? For a single call the 2-Day Pass. Most interviews
  have 2 or 3 rounds on different days, so the 1-Month Pass (Rs 299, about Rs 10 a day)
  covers the whole loop and the rest of the job hunt.
- Does it need a fast internet? A normal broadband or 4G connection is fine.
- Where does my data go? From your PC to Google Gemini under your own key. There are
  no Interview Sarthi servers.
- Refunds? 7-day money-back on the first pass, no questions asked.

## Content angles that work for this audience

- "Interviewer asked X, say this" question and answer cards, in English and Hinglish.
- A question a specific company's HR round actually asks (TCS, Infosys, Wipro, Accenture,
  Cognizant, Capgemini), and the answer that appeared on screen for it.
- Myth versus fact about online interviews and AI help.
- Fresher confidence: self-introduction, strengths and weaknesses, salary expectation,
  why should we hire you, reason for job change, explaining a career gap.
- Online interview setup: audio, camera, lighting, notes, what to do when you freeze.
- Product moments: the Hinglish answer appearing, the resume-grounded project answer,
  the answer streaming onto the screen, the free 30 minutes, the Rs 99 pass.
- Seasonal: placement season (July to October), NQT (February to April), appraisal
  and switching season (March to May), new year job change.

---

# Prep Sarthi (interviewsarthi.com/mock)

Use this section, and not the Interview Sarthi facts above, when the post's pillar names
prep_sarthi. Last reviewed: 20 September 2026.

## One line

Prep Sarthi is a mock interview you speak to, in your browser. It reads your CV, asks
about your own projects out loud, asks again when an answer is vague, and scores every
answer at the end with a stronger version of it.

## What it does, in detail

- Opens in a phone or laptop browser. Nothing to install, no account for the free part.
- You upload a CV, or paste it. You may add a job description, and the questions target
  that role.
- Pick 8, 12 or 18 minutes, and a voice.
- The interviewer speaks first and waits. You answer out loud. You can interrupt her and
  she can interrupt you, as in a real call.
- Questions come from lines in your own CV: the project you named, the number you claimed,
  the gap in your dates. If an answer is thin she asks again for the specific thing missing.
- At the end: a score out of 100, every question marked out of 10, what was missing from
  each answer, and a stronger version written from your own CV and your own words.
- It also measures how you sounded, from your microphone: speaking pace, filler words,
  the pause before each answer, the longest silence inside one.
- Any language. English, Hinglish and Hindi are one tap; any other language can be typed in.
- It never coaches during the interview. She is an interviewer, not a tutor. The teaching
  is in the report.

## Pricing (exact, use only these numbers)

- Free: 20 minutes, no card and no sign-up. Invite a friend and, when they finish their
  first mock, you both get 20 more minutes.
- 30-Day Pass: Rs 99, one payment, unlimited mock interviews for 30 days. This is the only
  paid pass (since 25 September 2026); there is no 7-day pass.
- Outside India, in US dollars (Dodo Payments): 30-Day Pass $9.99. Use this, and only this, in a
  post made for viewers outside India.
- Nothing renews by itself. Pay by UPI, card or netbanking.
- It runs on the candidate's own free Google Gemini key, which is why practice is
  unlimited rather than counted in sessions.

## What it is not

It is not the live help. It never runs during a real interview. It is not a question bank
or a course: there is no list to read, only a conversation to have. It does not promise a
job, and the score is a practice score, not a hiring decision.

## What a Prep Sarthi post must convey

The interviewer has read your CV, so the questions are about your work and not generic.
It listens and pushes back. You get a score and a better answer. Twenty minutes free,
in a browser, in your language.

## Numbers in a Prep Sarthi post

Any score, pause or words-a-minute shown is an example, written to illustrate, never a
real user's result. Say so when it could be mistaken for one. No testimonials, no user
counts, no success rates.

---

# ApplySarthi (interviewsarthi.com/apply)

Use this section when the post's pillar names apply_sarthi. Last reviewed: 20 September 2026.

## One line

ApplySarthi finds the jobs that fit your CV and fills the application form for you, in
your own Chrome, for you to check and submit.

## What it does, in detail

- Collects jobs that are open right now from Naukri, LinkedIn, Indeed, Foundit, Shine,
  Internshala, Wellfound, remote boards and 750+ company career pages.
- Ranks every job against your CV, so the list is yours rather than everyone's.
- Rewrites your CV for each job, using only your real experience.
- Fills the application form inside your own Chrome and stops. You read it, fix anything,
  solve the CAPTCHA and press the site's own submit button.
- Duplicate listings across sites are merged.

## What it will not do

- It never invents a fact about you. Names, employers, titles, dates, degrees and numbers
  are copied from your CV; the AI only rewords.
- It never answers what only you can answer: salary, notice period, visa, relocation, or
  any legal declaration.
- It never submits behind your back. Autopilot exists, but only if you switch it on.
- It never sees your job-site passwords. You sign in to Naukri or LinkedIn yourself.

## Pricing

Always free, with no paid plan planned. It runs on the candidate's own free Google Gemini key.

## What it needs

A CV as PDF or Word, a free Google Gemini key, and Google Chrome on a computer for the
form filling. Browsing matches and downloading tailored CVs works on any device.

