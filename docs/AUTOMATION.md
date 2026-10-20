# Production sales automation

The owner approved the 60 FPS motion advertisement and explicitly authorized publication to
Instagram, Facebook and YouTube, plus unattended daily operation on 13 September 2026.

The eight daily slots (15 September 2026) are 09:07 and 18:07 IST for product image advertisements, 10:37, 12:37, 16:37 and 21:37 IST for short motion reels, and 14:37 and 19:37 IST for standard motion reels. Each reel opens on a fresh Veo 3.1 Fast scene generated for that post, paid from the Google Cloud credit and capped in agent/render/veo_opening.py; the reusable clips are the fallback. The workflow runs independently of the owner's PC. The approved
privacy comparison, real interface imagery, readable answer, narration and trial offer remain.

Every run rotates the audience category, asks Gemini for a fresh fictional resume/question/answer,
checks it against recent topics, checks the text layout and separately reviews its grounding.
Script writing and creative review follow. Failed generation/review uses checked authored
examples. There are three reusable 60 FPS footage clips, three coordinated color themes, and
language-specific real screenshots. Clips avoid the previous two and themes avoid the previous
one. Resume cards and answer panels are rendered from that post's scenario. Reusable footage
will recur; the system does not promise never to reuse an asset or guarantee improved sales.
Recent exact creative hashes are blocked. Model work has a six-minute budget.

Instagram sales reels upload directly through Meta's supported resumable-file route. Video is
H.264 at 1080x1920 and 60 FPS, with 128 kbps AAC and no MP4 edit lists. The final file must pass
audio, duration, typography metadata, frame-rate and hash checks before publication.

Successful-platform receipts prevent repeating successful uploads during retries. Instagram
container state and YouTube resumable state persist within the output folder; the CLI retries
the same approved file twice. Upload-session files are excluded from public workflow artifacts.
History and available performance counts are committed after runs. Platform errors remain
visible as workflow failures; permanent credential outages cannot be repaired without renewed
access. No daily manual content approval or editing is required.

Available YouTube and Instagram counts are collected locally for performance comparison.
They do not establish retention or sales lift, and are not sent to the script provider.
Duplicate comparisons also stay local. Facebook links carry a per-post campaign ID.
Sales attribution through Instagram/YouTube profile navigation is limited.

## Product allocation — 23 September 2026

The eight existing daily times remain. ApplySarthi gets carousels at 09:07, 16:37 and
18:07 IST; Prep Sarthi gets reels at 12:37, 14:37 and 21:37; Interview Sarthi keeps
the sales slots at 10:37 and 19:37. This supersedes the older format mix above.
Pillar weights choose topics within a product; the workflow assigns products to slots.
