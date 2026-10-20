# Interview Sarthi: auto brief
Generated 01 October 2026 from 40 pages of interviewsarthi.com.

## One line
Interview Sarthi provides three apps to help job seekers find jobs across multiple portals, practise AI mock interviews, and receive live interview assistance during calls.

## What it does, in detail
Interview Sarthi offers three standalone tools for different stages of the job search:
* **Apply Sarthi:** Aggregates job postings from multiple sources (including Naukri, LinkedIn, Indeed, Foundit, Shine, Internshala, Wellfound, and company career boards) into one search. It ranks jobs against a candidate's CV, generates tailored CVs and cover letters, tracks applications, and uses a Chrome browser extension to autofill application forms.
* **Prep Sarthi:** A browser-based AI mock interview tool. It conducts voice interviews with questions grounded in the candidate's CV and target job description, asks follow-up questions on weak answers, and generates feedback reports reviewing answer content, speaking pace, pauses, and filler words.
* **Live Sarthi:** A Windows desktop application that transcribes call audio during live interview calls (such as Teams, Zoom, Google Meet, or Webex) and shows answer suggestions grounded in the user's CV on screen.

## How it works (technology, privacy, requirements)
* **Requirements:** Apply Sarthi runs in a web browser, with form autofill requiring Chrome on desktop and a PDF or Word CV. Prep Sarthi runs in a browser on desktop or mobile and requires a microphone. Live Sarthi requires Windows 10 (version 2004+) or Windows 11 and an internet connection.
* **Technology:** Live Sarthi transcribes audio and generates answer suggestions starting in approximately 1.5 seconds under suitable conditions. It uses the Windows `WDA_EXCLUDEFROMCAPTURE` API to hide its overlay panel from supported screen shares. Apply Sarthi operates inside a real Chromium browser window to access sites like Naukri and Foundit that block headless browsers or plain HTTP requests.
* **AI Keys & Quotas:** AI features use the candidate's own Google Gemini API key from Google AI Studio (Apply's first tailored CV and Prep's free demo require no key). Google usage limits and API costs are separate from Interview Sarthi passes.
* **Privacy:** Apply Sarthi requires sign-in for personalized matching, but job-board login credentials stay in the candidate's own browser and are not shared with vendor servers. Live Sarthi stores transcripts locally on the PC. Audio and resume context travel directly from the user's computer to Google under their own key. On Google's free Gemini tier, Google states it may review content to improve services; paid Gemini tiers provide strict privacy terms.

## Pricing (exact numbers and terms as published)
The site publishes pricing for India in Indian Rupees (₹). It notes that international USD ($) pricing exists but details are listed separately.

* **Apply Sarthi:**
  * Free always. No paid plan or subscription required.
  * First tailored CV is free. Later tailoring and AI form assistance use the user's own free Gemini API key.

* **Prep Sarthi:**
  * Free 7-minute demo interview (no sign-up or Gemini key required).
  * 30-day pass: ₹99 for 30 days (one-time payment, no auto-renewal). Requires the user's Gemini key.

* **Live Sarthi:**
  * Free trial: 30 minutes free per Windows device (all features included, no card or account required). Reinstalling does not reset the trial allowance.
  * 2-Day Pass: ₹99 for 2 days on 1 device.
  * 1-Month Pass: ₹299 for 30 days on 2 devices.
  * Pass terms: Passes are one-time purchases and do not auto-renew. Passes provide unlimited sessions during their validity. Validity days begin when the key is first activated in the app, and keys must be activated within 30 days of purchase.
  * Refer-a-friend offer: Every pass includes an invite code. When a friend buys and activates a pass using the code, both get a Free Interview Day (a 24-hour key for 1 device, valid for activation within 30 days). There is no cap on referrals.

## Who it is for
* Job seekers in India applying across multiple job boards and corporate career sites.
* Freshers rehearsing project explanations, technical basics, or entry-level HR rounds for companies like TCS, Infosys, Wipro, Accenture, Cognizant, and Capgemini.
* Experienced professionals organizing accomplishments, career transitions, backlogs, or career gaps.
* Candidates who need interview practice or call assistance in English, Hindi, or Hinglish.

## Problems it solves
* Time wasted checking multiple job portals and retyping standard details into long application forms.
* Low application response rates caused by using a single generic CV or applying to closed job postings.
* Lack of a practice partner to run realistic mock interviews and catch weak answers, filler words, or pacing issues.
* Difficulty recalling relevant experience or structuring answers under pressure on live call rounds.
* Unexpected recurring software charges and expensive monthly subscriptions.

## Differentiators and proof points (only what the site states)
* Built and supported directly by independent developer Abhishek Choudhary in India, with Live Sarthi releases published openly on GitHub.
* Designed specifically for the Indian job market, including explicit support for Hinglish questions and answers.
* Form autofill works directly inside the user's own browser, reaching sites like Naukri, Foundit, Shine, and Internshala that block external server bots.
* Built-in safeguard against CV hallucination: Apply Sarthi discards any rewritten line that introduces a figure absent from the original source CV.
* Hides the Live Sarthi overlay from supported Windows screen captures using Windows native API controls.
* No auto-renewing subscriptions; all passes are fixed one-time payments.

## Voice, tone and words the site uses
* **Tone:** Plainspoken, practical, transparent, direct, and realistic.
* **Key Words and Phrases:** "Sarthi" (meaning charioteer or guide), "grounded in your CV", "resume-grounded", "less typing", "no monthly commitment", "no auto-renew", "no bot joins your meeting", "preserves facts", "your career, your call".

## Words and claims the site avoids or warns about
* Does not guarantee job offers, interview calls, or selection.
* Avoids unverified comparative rankings, success rates, or detection statistics.
* Warns against bulk auto-apply tools that send hundreds of applications a day, submit generic CVs, or harvest job-board passwords on vendor servers.
* Warns against AI tools that fabricate resume facts, numbers, employment dates, or qualifications.
* Warns candidates not to use live AI assistance where employer, interviewer, or proctored test rules prohibit it.

## Links worth pointing to (URL: what it is)
* https://interviewsarthi.com : Main homepage describing all three apps.
* https://interviewsarthi.com/about.html : Developer background, business model, and contact email.
* https://interviewsarthi.com/facts.html : Live Sarthi facts, system requirements, pricing, and official downloads.
* https://interviewsarthi.com/apply/ : Apply Sarthi portal for job search, matching, and form filling.
* https://interviewsarthi.com/free-gemini-api-key-guide.html : Step-by-step setup guide for a Google Gemini API key.
* https://interviewsarthi.com/apply/auto-apply-jobs-india.html : Analysis of auto-apply tools and technical constraints of Indian job boards.
* https://interviewsarthi.com/best-ai-interview-assistant-india.html : Comparison guide reviewing 7 AI interview assistants.
* https://interviewsarthi.com/can-interviewer-see-my-screen.html : Technical guide on screen sharing and capture exclusion.
* https://interviewsarthi.com/guides/ai-in-interviews-rules.html : Operational rules and guidance on obtaining permission for AI tools.

## Frequently asked questions (as answered on the site)
* **Is ApplySarthi free?** Yes, ApplySarthi is free with no paid plan or credit card required.
* **Does ApplySarthi cover Naukri?** Yes, it covers Naukri, Foundit, Shine, Internshala, LinkedIn, Indeed, and company career sites by running inside your own browser session.
* **Does ApplySarthi automatically submit applications?** By default, no. It fills the form so you can review it before pressing submit. It contains an optional Autopilot switch that can press submit if turned on by the user.
* **Can an interviewer see Live Sarthi during a screen share?** No, on supported Windows 10 (2004+) and Windows 11 capture setups, the panel remains hidden. Users are advised to test their setup on a mock call and follow interviewer rules.
* **Does a bot join the call for Live Sarthi?** No, no bot joins your meeting.
* **Do paid passes renew automatically?** No, all passes are one-time purchases for fixed durations and never auto-renew.
* **What key is required for AI features?** A free Google Gemini API key set up via Google AI Studio.

## Content angles suggested by the site's own pages
* "Why 200 generic job applications lead to silence (and the five-step fix)."
* "How auto-apply tools actually work in India: Why server bots miss Naukri and Foundit."
* "How to answer HR interview questions naturally in Hinglish."
* "What Zoom, Teams, and Google Meet actually transmit when you share your screen."
* "Fresher interview preparation guides for TCS, Infosys, Accenture, Cognizant, and Capgemini."

## Open questions the owner should confirm
* Are international USD ($) pricing structures published on a separate page, or provided only upon direct inquiry?
* Are there plans to bring Live Sarthi to macOS or Linux, or will it remain Windows-only?
* Does the desktop app notify users in real time if their personal Gemini API key hits Google rate limits during an active call?
