"""Fresh Veo openings: budget caps hold, every failure falls back, and prompts keep screens and text out."""
import datetime as dt
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.config import ROOT
from agent.history import History
from agent.render import veo_opening as vo

NOW = dt.datetime(2026, 9, 20, 12, 0)
SCENARIO = {"id": "fresh-abc", "audience": "A fresher explaining their final-year project",
            "question": "What was your role in this project?"}
ENV = {"VEO_OPENING_ENABLED": "true", "VEO_OPENING_MONTHLY_SECONDS": "40",
       "VEO_OPENING_TOTAL_SECONDS": "64", "VEO_OPENING_START": "2026-09-15"}


def history_with(entries, clip=vo.CLIP_ID):
    h = History(Path(tempfile.mkdtemp()) / "history.json")
    for i, (date, seconds) in enumerate(entries):
        h.posts.append({"id": f"{clip}-{i}", "date": date, "visual_clip": clip, "veo_seconds": seconds})
    return h


class VeoOpeningTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "out").mkdir(exist_ok=True)
        self.run = Path(tempfile.mkdtemp(dir=ROOT / "out", prefix="test-veo-"))

    def tearDown(self):
        shutil.rmtree(self.run, ignore_errors=True)

    def test_prompt_keeps_text_and_screens_out_and_varies(self):
        prompt = vo.opening_prompt(SCENARIO)
        for phrase in ("9:16", "never visible", "No text", "no readable writing", "no spoken dialogue"):
            self.assertIn(phrase, prompt)
        self.assertGreater(len({vo.opening_prompt({**SCENARIO, "id": f"fresh-{i}"}) for i in range(12)}), 3)

    def test_budget_allows_under_caps_and_ignores_library_clips(self):
        h = history_with([("2026-09-19 10:00 IST", 8)])
        h.posts.append({"id": "lib", "date": "2026-09-19 11:00 IST", "visual_clip": "interview-man", "veo_seconds": 500})
        with patch.dict(os.environ, ENV):
            self.assertIsNone(vo.budget_stop(h, NOW))

    def test_monthly_cap_stops(self):
        # 32 s used + 8 s lands exactly on the 40 s cap, which is still allowed; 40 s used + 8 s is over it.
        h = history_with([("2026-09-19 10:00 IST", 16), ("2026-09-19 12:00 IST", 16)])
        with patch.dict(os.environ, ENV):
            self.assertIsNone(vo.budget_stop(h, NOW))
            h.posts.append({"id": "more", "date": "2026-09-19 14:00 IST", "visual_clip": vo.CLIP_ID, "veo_seconds": 8})
            self.assertIn("monthly", vo.budget_stop(h, NOW))

    def test_total_cap_counts_only_openings_since_the_start_date(self):
        now = dt.datetime(2026, 10, 2, 12, 0)
        h = history_with([("2026-09-10 10:00 IST", 100), ("2026-09-20 10:00 IST", 24), ("2026-09-25 10:00 IST", 32)])
        with patch.dict(os.environ, ENV):
            self.assertIsNone(vo.budget_stop(h, now))
            h.posts.append({"id": "oct", "date": "2026-10-01 10:00 IST", "visual_clip": vo.CLIP_ID, "veo_seconds": 8})
            self.assertIn("total", vo.budget_stop(h, now))

    def test_disabled_does_nothing(self):
        with patch.dict(os.environ, {"VEO_OPENING_ENABLED": "false"}), patch.object(vo, "_generate") as gen:
            self.assertIsNone(vo.generate_opening(SCENARIO, history_with([]), self.run))
            gen.assert_not_called()

    def test_budget_stop_skips_generation(self):
        h = history_with([("2026-09-19 10:00 IST", 40)])
        with patch.dict(os.environ, ENV), patch.object(vo, "now_ist", return_value=NOW), \
                patch.object(vo, "_generate") as gen:
            self.assertIsNone(vo.generate_opening(SCENARIO, h, self.run))
            gen.assert_not_called()

    def test_run_folder_outside_out_is_refused(self):
        with patch.dict(os.environ, ENV), patch.object(vo, "_generate") as gen:
            self.assertIsNone(vo.generate_opening(SCENARIO, history_with([]), Path(tempfile.mkdtemp())))
            gen.assert_not_called()

    def test_provider_failure_falls_back_to_library(self):
        with patch.dict(os.environ, ENV), patch.object(vo, "_generate", side_effect=RuntimeError("quota")):
            self.assertIsNone(vo.generate_opening(SCENARIO, history_with([]), self.run))

    def test_success_returns_smoothed_eight_second_opening(self):
        def fake_generate(prompt, out, model, timeout_s=600):
            out.write_bytes(b"0" * 20000)

        def fake_smooth(raw, out):
            out.write_bytes(b"1" * 20000)

        with patch.dict(os.environ, ENV), patch.object(vo, "_generate", fake_generate), \
                patch.object(vo, "_smooth", fake_smooth):
            opening = vo.generate_opening(SCENARIO, history_with([]), self.run)
        self.assertEqual(opening["seconds"], 8.0)
        self.assertEqual(opening["clip_id"], "veo-fresh")
        self.assertTrue(opening["smoothed"])
        self.assertTrue(opening["clip"].endswith("veo-opening.mp4"))

    def test_smoothing_failure_still_plays_the_paid_clip(self):
        def fake_generate(prompt, out, model, timeout_s=600):
            out.write_bytes(b"0" * 20000)

        with patch.dict(os.environ, ENV), patch.object(vo, "_generate", fake_generate), \
                patch.object(vo, "_smooth", side_effect=RuntimeError("ffmpeg")):
            opening = vo.generate_opening(SCENARIO, history_with([]), self.run)
        self.assertFalse(opening["smoothed"])
        self.assertTrue(opening["clip"].endswith("veo-opening-raw.mp4"))

    def test_footage_rejects_paths_outside_library_and_out(self):
        from agent.render.motion import footage
        with self.assertRaises(ValueError):
            footage(str(Path(tempfile.gettempdir()) / "elsewhere.mp4"))


if __name__ == "__main__":
    unittest.main()
