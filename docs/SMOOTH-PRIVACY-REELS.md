# Smooth motion and screen-share privacy revision

The prior renderer decoded its interview footage at 12 FPS inside a 24 FPS export. This
caused visible stepped motion. The sales renderer now uses 60 FPS, frame-aligned scene
durations and a final constant-rate encode. The reusable 24 FPS source has been interpolated
to 60 FPS with FFmpeg motion compensation in `assets/motion/interview-smooth.mp4`.
This is interpolated footage, not a claim that the source camera recorded at 60 FPS.
The final encoded-media gate now verifies frame rate against the requested layout cadence.

Both authored scripts and model instructions include screen-share privacy. The product scene
first shows the real interface, then a clearly illustrative comparison of the user's screen
and the shared view. The narration says the overlay is hidden from supported screen sharing.
The on-screen qualification specifies Windows 10 (2004+) / 11 and varying capture support.
This description is based on `AI-Helps_SAAS/overlay.py:1345` (the app calls
`SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE`, records the result and warns on failure).
It is not a new end-to-end verification across Teams, Zoom and Meet.

Microsoft documents the API and its limitations:
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity

The preview is `out/sales-smooth-privacy-preview/reel.mp4`. It reuses the existing narration
except for a newly synthesized product/privacy sentence with the same Edge voice.
No online publishing or workflow deployment is part of this preview revision.
