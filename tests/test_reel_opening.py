"""The opening of a card reel: it has footage, and somebody is speaking over it.

Both halves were missing on 24 Sep 2026. Card reels opened on nothing, because render_media
asked generate_hook (part of the Veo film switched off on 12 Sep) instead of generate_opening.
Once footage arrived, the owner pointed out the next gap: four seconds of silence at the front.
A reel is judged in its first second, and dead air reads as a video that has not started.

Real ffmpeg, real muxing, and the audio is measured rather than assumed. Skipped where ffmpeg
is absent; CI installs it.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from agent.render import reel as R


def _sh(*args):
    subprocess.run(list(args), check=True, capture_output=True)


def _mean_dbfs(path, start, length):
    """Average level over a window. Digital silence reports about -91 dB."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-i", str(path),
                          "-t", str(length), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    raise AssertionError("ffmpeg reported no mean_volume:\n" + out[-500:])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class ReelOpeningTests(unittest.TestCase):
    def setUp(self):
        self.work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.work, True)
        self.intro = self.work / "intro.mp4"
        _sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
            "-i", "testsrc=size=720x1280:rate=30:duration=6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(self.intro))
        self.frames = []
        for i, colour in enumerate(("red", "blue"), 1):
            frame = self.work / f"frame-{i}.png"
            _sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                "-i", f"color=c={colour}:size=1080x1920:duration=1", "-frames:v", "1", str(frame))
            self.frames.append(frame)
        self._real_batch, self._real_music = R.synthesize_batch, R.pick_music
        R.pick_music = lambda: None          # music would mask whether anyone is speaking
        self.addCleanup(self._restore)

    def _restore(self):
        R.synthesize_batch, R.pick_music = self._real_batch, self._real_music

    def _voice_of(self, *lengths):
        def batch(lines, outs, language):
            made = []
            for path, secs in zip(outs, lengths):
                _sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=340:duration={secs}", "-c:a", "libmp3lame", str(path))
                made.append(pathlib.Path(path))
            return made, "test-voice"
        R.synthesize_batch = batch

    def test_the_first_line_starts_on_the_footage_and_carries_into_the_card(self):
        self._voice_of(9, 3)
        out = self.work / "reel.mp4"
        info = R.build_reel(self.frames, ["first line", "second line"], out,
                            intro=self.intro, intro_seconds=4.0)
        self.assertTrue(info["voiced"])
        self.assertGreater(_mean_dbfs(out, 0, 4), -60, "the opening four seconds are silent")
        self.assertGreater(_mean_dbfs(out, 4, 4), -60, "the first card is silent")
        # 4 opening + (9 - 4 + 0.4 tail) + (3 + 0.4): the line is split, never repeated or lost.
        self.assertAlmostEqual(info["seconds"], 12.8, delta=0.3)

    def test_a_first_line_too_short_to_split_leaves_the_opening_silent(self):
        """Better a quiet opening than a card with a syllable left on it."""
        self._voice_of(2, 3)
        out = self.work / "reel.mp4"
        info = R.build_reel(self.frames, ["short", "second line"], out,
                            intro=self.intro, intro_seconds=4.0)
        self.assertLess(_mean_dbfs(out, 0, 4), -60)
        self.assertGreater(_mean_dbfs(out, 4, 4), -60)
        # The whole 2 s line still plays, on the card, padded to the slide minimum.
        self.assertAlmostEqual(info["seconds"], 4 + R.MIN_SLIDE_SECONDS + 3 + R.TAIL, delta=0.3)

    def test_a_reel_with_no_opening_is_unchanged(self):
        self._voice_of(5, 3)
        out = self.work / "reel.mp4"
        info = R.build_reel(self.frames, ["first line", "second line"], out)
        self.assertGreater(_mean_dbfs(out, 0, 3), -60)
        self.assertAlmostEqual(info["seconds"], 5 + R.TAIL + 3 + R.TAIL, delta=0.3)


if __name__ == "__main__":
    unittest.main()
