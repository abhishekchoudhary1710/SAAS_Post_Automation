# Interview Sarthi: business brief

This file is the agent's source of truth about the business. Every post is written
from what is here. Edit it freely; keep facts accurate, because the agent is told to
use only facts from this file and never to invent numbers, quotes or testimonials.

Last reviewed: 9 September 2026.

## One line

Interview Sarthi is a Windows app that listens to your online interview, shows what
the interviewer just asked, and drafts what to say, from your own resume, in English,
Hindi or Hinglish. Built for Indian candidates. 30 minutes free, then one-time passes
from Rs 99. Runs on your own free Google Gemini key.

Name: "Sarthi" is Hindi/Sanskrit for the charioteer who guides the warrior
(Krishna to Arjun). Pronounced "saar-thee".

## What it does, in detail

- Runs as a desktop app on Windows 10 and 11. Install from the Microsoft Store or the
  direct installer. Setup takes about a minute.
- During an online interview on Teams, Zoom, Google Meet or Webex, it listens to the
  call audio on your PC. No bot joins the call and nothing appears in the participant
  list.
- It transcribes the interviewer live and shows every question with a timestamp.
- For each question it drafts one natural, spoken-style answer the candidate can say
  as written. Each sentence sits on its own line so you can pause and find your place.
  Two to four key phrases are highlighted.
- Answers are grounded in the resume you uploaded during setup. "Walk me through your
  last project" is answered with your real project, not a template. It cannot invent
  experience you do not have.
- Languages: English, Hindi and Hinglish. It follows whichever language the
  interviewer uses, including a switch mid-sentence, which is how many Indian
  interviews actually run.
- Answers start appearing in about 1.5 seconds.
- Screen reading: if the interviewer shares a code snippet or a diagram, one key reads
  the shared screen and drafts the answer (code, output, short explanation).
- Ask box: type any question about the meeting and get an answer from the transcript.
- Session transcript and summary saved at the end of every call, useful for reviewing
  your own performance and for mock practice.
- Controls: fade, hide to a slim bar, pause listening, clear context.
- The overlay is excluded from screen capture on Windows. This is documented openly on the
  website and in the app's help. Social posts do not cover it, because it is not why people
  buy: they buy the language help and the answers drawn from their own resume.

## How it works under the hood (for "how does it work" content)

- Everything runs on the candidate's own free Google Gemini API key from
  aistudio.google.com. No credit card is needed for the key. The free tier is enough
  to run interviews, so the ongoing AI cost is Rs 0.
- Audio and resume go from the candidate's PC directly to Google Gemini and nowhere
  else. Interview Sarthi runs no servers and never sees the interview.
- The candidate's microphone is never sent to the model. Only the meeting audio is,
  so the candidate's own voice can never trigger an answer.
- Licensing is a pass key checked against the payment provider (Dodo Payments). One
  key works on up to two devices for the month and quarter passes.

## Pricing (exact, use only these numbers)

| Plan | Price | Notes |
|---|---|---|
| Free | Rs 0 | 30 minutes of answers per device, every feature, no card, no signup |
| 2-Day Pass | Rs 99 one-time | 2 days from purchase, unlimited sessions, 1 device |
| 7-Day Pass | Rs 399 one-time | 7 days, unlimited sessions, 1 device. Most popular. About Rs 57 a day |
| 1-Month Pass | Rs 999 one-time | 30 days, 2 devices. About Rs 33 a day |
| 3-Month Pass | Rs 1,999 one-time | 90 days, 2 devices. About Rs 22 a day |

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
6. Not remembering what was asked afterwards (transcript and summary solve this).

## Differentiators (what to lead with)

1. Hinglish. Answers in the language the interviewer used. This is the main
   differentiator and the thing US tools get wrong.
2. Your resume, your words. Answers about your real projects.
3. Rupees, one-time. From Rs 99. Nothing renews.
4. 30 minutes free with every feature, no card.
5. Private by design: your own free Gemini key, no vendor servers.
6. Screen reading for shared code and diagrams.
7. Session transcript and summary for self-review and practice.

## Positioning and voice

The framing is "an AI practice partner, and confidence in Hinglish interviews".

- Say: assistant, guide, practice partner, "in your words", "from your resume",
  "confidence", "never blank again", "answers in Hinglish".
- Do not use: cheat, cheating, undetectable, hidden, invisible, stealth, "hack the
  interview", "fool the interviewer". Three reasons, in order of importance. They are
  inaccurate: the app drafts from the candidate's own resume and cannot manufacture
  experience, and any interviewer who probes two levels down will find that out. They
  breach the advertising and content policies of every platform we post on. And they
  attract moderation and removals, which costs the account.
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
  Teams, Zoom, Meet, Webex.
- Mac or phone? Not yet. Windows only.
- Is it free? The first 30 minutes are free with every feature, no card. After that,
  passes from Rs 99.
- Which pass for one interview? For a single call the 2-Day Pass. Most interviews
  have 2 or 3 rounds on different days, so the 7-Day Pass covers a full loop.
- Does it need a fast internet? A normal broadband or 4G connection is fine.
- Where does my data go? From your PC to Google Gemini under your own key. There are
  no Interview Sarthi servers.
- Refunds? 7-day money-back on the first pass, no questions asked.

## Content angles that work for this audience

- "Interviewer asked X, say this" question and answer cards, in English and Hinglish.
- Company-specific HR round prep (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini).
- Myth versus fact about online interviews and AI help.
- Fresher confidence: self-introduction, strengths and weaknesses, salary expectation,
  why should we hire you, reason for job change, explaining a career gap.
- Online interview setup: audio, camera, lighting, notes, what to do when you freeze.
- Product moments: the Hinglish answer appearing, the resume-grounded project answer,
  screen reading a code snippet, the free 30 minutes, the Rs 99 pass, the transcript.
- Seasonal: placement season (July to October), NQT (February to April), appraisal
  and switching season (March to May), new year job change.
