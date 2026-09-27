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

    def test_every_opening_is_a_professional_woman_three_in_four_white(self):
        """Owner, 27 Sep 2026: a smart, attractive woman, never sexualised; white 75%, Indian 25%."""
        prompts = [vo.opening_prompt({**SCENARIO, "id": f"fresh-{i}"}) for i in range(400)]
        white = [p for p in prompts if "young white woman" in p]
        indian = [p for p in prompts if "young Indian woman" in p]
        self.assertEqual(len(white) + len(indian), 400)
        self.assertTrue(260 <= len(white) <= 340, len(white))
        for p in prompts:
            self.assertIn("smart, attractive", p)
            self.assertNotRegex(p.lower(), r"\bsexy\b|\bhot\b|seductive|revealing|\bman\b")
        with patch.dict(os.environ, {"VEO_WHITE_FACE_SHARE": "0"}):
            self.assertTrue(all("young Indian woman" in vo.opening_prompt({**SCENARIO, "id": f"x{i}"}) for i in range(30)))
        with patch.dict(os.environ, {"VEO_WHITE_FACE_SHARE": "1"}):
            self.assertTrue(all("young white woman" in vo.opening_prompt({**SCENARIO, "id": f"x{i}"}) for i in range(30)))

    def test_both_faces_share_the_same_rooms_and_clothes(self):
        """Only the face may differ between the two arms of the test."""
        for i in range(40):
            s = {**SCENARIO, "id": f"fresh-{i}"}
            white = vo.opening_prompt({**s, "face": "white"})
            indian = vo.opening_prompt({**s, "face": "indian"})
            self.assertEqual(white.replace("white woman", "X"), indian.replace("Indian woman", "X"))

    def test_choose_face_keeps_three_in_four_without_long_runs(self):
        h = history_with([])
        picks = []
        for i in range(40):
            face = vo.choose_face(h)
            picks.append(face)
            h.posts.append({"id": f"p{i}", "face": face})
        self.assertTrue(28 <= picks.count("white") <= 32, picks.count("white"))
        self.assertLessEqual(max(len(run) for run in "".join("w" if f == "white" else "i" for f in picks).split("i")), 4)
        with patch.dict(os.environ, {"VEO_FACE": "indian"}):
            self.assertEqual(vo.choose_face(h), "indian")

    def test_candidate_action_matches_the_product(self):
        live = vo.opening_prompt({**SCENARIO, 'product': 'interview_sarthi'})
        prep = vo.opening_prompt({**SCENARIO, 'product': 'prep_sarthi'})
        apply = vo.opening_prompt({**SCENARIO, 'product': 'apply_sarthi'})
        self.assertIn('online job interview', live)
        self.assertIn('mock interview', prep)
        self.assertIn('no recruiter or live employer call', prep)
        self.assertIn('reviews job opportunities', apply)
        self.assertIn('not an interview or a job offer', apply)
        for prompt in (prep, apply):
            self.assertIn('The laptop screen faces away', prompt)
            self.assertNotIn('during an online job interview', prompt)

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
        def fake_generate(prompt, out, model, timeout_s=600, seconds=None):
            out.write_bytes(b"0" * 20000)

        def fake_smooth(raw, out):
            out.write_bytes(b"1" * 20000)

        with patch.dict(os.environ, ENV), patch.object(vo, "_generate", fake_generate), \
                patch.object(vo, "_smooth", fake_smooth):
            opening = vo.generate_opening(SCENARIO, history_with([]), self.run)
        self.assertEqual(opening["seconds"], 8.0)
        self.assertEqual(opening["clip_id"], "veo-fresh")
        self.assertIn(opening["face"], ("white", "indian"))
        self.assertIn(f"young {'white' if opening['face'] == 'white' else 'Indian'} woman", opening["prompt"])
        self.assertTrue(opening["smoothed"])
        self.assertTrue(opening["clip"].endswith("veo-opening.mp4"))

    def test_smoothing_failure_still_plays_the_paid_clip(self):
        def fake_generate(prompt, out, model, timeout_s=600, seconds=None):
            out.write_bytes(b"0" * 20000)

        with patch.dict(os.environ, ENV), patch.object(vo, "_generate", fake_generate), \
                patch.object(vo, "_smooth", side_effect=RuntimeError("ffmpeg")):
            opening = vo.generate_opening(SCENARIO, history_with([]), self.run)
        self.assertFalse(opening["smoothed"])
        self.assertTrue(opening["clip"].endswith("veo-opening-raw.mp4"))

    def test_a_shorter_opening_is_generated_and_charged_at_its_own_length(self):
        """A card reel shows a four second cold open, so it must not buy eight (24 Sep 2026)."""
        asked = {}

        def fake_generate(prompt, out, model, timeout_s=600, seconds=None):
            asked["seconds"] = seconds
            out.write_bytes(b"0" * 20000)

        with patch.dict(os.environ, ENV), patch.object(vo, "_generate", fake_generate), \
                patch.object(vo, "_smooth", lambda raw, out: out.write_bytes(b"1" * 20000)):
            opening = vo.generate_opening(SCENARIO, history_with([]), self.run, seconds=4)
        self.assertEqual(asked["seconds"], 4)
        self.assertEqual(opening["seconds"], 4.0)

    def test_a_shorter_opening_still_fits_a_budget_that_eight_would_break(self):
        """32 s of a 40 s cap leaves room for a 4 s opening but not an 8 s one."""
        h = history_with([("2026-09-19 10:00 IST", 16), ("2026-09-19 12:00 IST", 16)])
        h.posts.append({"id": "more", "date": "2026-09-19 14:00 IST",
                        "visual_clip": vo.CLIP_ID, "veo_seconds": 4})
        with patch.dict(os.environ, ENV):
            self.assertIn("monthly", vo.budget_stop(h, NOW))
            self.assertIsNone(vo.budget_stop(h, NOW, seconds=4))

    def test_footage_rejects_paths_outside_library_and_out(self):
        from agent.render.motion import footage
        with self.assertRaises(ValueError):
            footage(str(Path(tempfile.gettempdir()) / "elsewhere.mp4"))


if __name__ == "__main__":
    unittest.main()
