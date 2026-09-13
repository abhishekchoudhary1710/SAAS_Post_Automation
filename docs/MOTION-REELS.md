# Motion creative revision

The owner rejected the initial sales previews as static slides. `sales` now renders with
`agent/render/motion.py`: moving illustrative footage in the opening, animated question and
answer panels, a resume detail moving into focus, a floating laptop with a slow camera move
over the real screenshot, an animated trial offer and 340 ms slide/dissolve transitions.
Transitions fit inside scene durations so narration is not shortened or overlapped.

The music bed is generated locally with sine-wave chords, pulses and soft transition sweeps.
It contains no downloaded music or samples. Voice is normalized before a quiet music mix.
The final file still passes the encoded-media publication gate. No paid generation is required.

`assets/motion/interview.mp4` is a silent six-second crop of the owner's existing AI-generated
`out/veo-continuous/base.mp4`. It is illustrative footage, not a customer testimonial or real
interview recording. The visible answer uses the fictional scenario; the real screenshot is
labeled separately. Footage is reusable on scheduled runners and does not depend on `out/`.
If the footage asset is absent, the renderer uses animated native graphics instead.

The old previews remain in `out/sales-short-preview` and `out/sales-standard-preview` for
comparison. `out/sales-motion-preview/reel.mp4` is the motion revision using the same standard
narration, so the visual changes can be judged directly. The online workflow has not been
deployed or run by this preview revision.
