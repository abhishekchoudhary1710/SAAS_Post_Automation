# LinkedIn creative asset provenance

Updated 28 September 2026. These assets are owned product/marketing materials. Example
answers, scores and people are illustrative; no customer result or testimonial is claimed.

## Fresh website captures

`tools/capture_linkedin_assets.py` renders the sibling `Interview-Sarthi` website locally
with Playwright, blocks external requests, and captures product panels at a 1440 × 1000
viewport with device scale factor 2. Website revision:
`640bd2eee4ce26de3189a4d4ece263daf1b3dc39`.

| Committed file under assets/brand | Source | Meaning |
|---|---|---|
| linkedin-apply-match.png | /apply/, match tab, .product-visual | Website illustration of CV matching with example content |
| linkedin-apply-fill.png | /apply/, fill tab, .product-visual | Website illustration of form filling with fictional data |
| linkedin-prep-preview.png | /prep/, .call | Website illustration of spoken interview practice |

These are newly captured marketing website panels, not recordings of a real applicant
using the live app. Captions identify them as website illustrations. CI uses the committed
PNGs and does not need Playwright or access to customer accounts.

## Short videos

`agent/render/linkedin_video.py` creates 720 × 900 H.264 MP4 files at 30 fps, with no audio.
The storyboard is hook (3 seconds), owned illustrative scene (3), product visual (6),
lesson (6), CTA (5). A visible label covers the scene throughout. The existing source clips
are `assets/motion/interview-project-smooth.mp4`, `interview-smooth.mp4`, and
`interview-woman-smooth.mp4`. They are rotated alongside topic-specific cards.

Existing app screenshots remain under their configured `knowledge/brand.json` keys;
rendered cards distinguish real interface captures with illustrative content from website
illustrations. Fictional before/after answers are labelled on the cards. The video is an
edited explainer, not a continuous screen recording. Refresh captures and offers when the
product changes; do not substitute customer data without separate authorization.

To refresh website images with an installed Playwright browser:

```bash
python tools/capture_linkedin_assets.py --browser /path/to/chrome
```

To generate the next fortnight's captions and media:

```bash
python -m agent.linkedin_growth preview --date 2026-09-29 --days 14 --out out/linkedin-preview
```
