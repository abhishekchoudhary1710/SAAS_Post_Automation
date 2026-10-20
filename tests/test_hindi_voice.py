"""Hindi voice (owner, 11 Oct 2026): one in four India reels speaks Hindi; the screen stays English."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import campaign, copywriter, strategy
from agent.render import tts, veo_opening


def history_with(posts):
    return SimpleNamespace(posts=list(posts))


def plan(**kw):
    return {"language": "english", "market": "india", "pillar": "prep_free", **kw}


class HindiVoiceTest(unittest.TestCase):
    def test_one_in_four_india_reels_without_bunching(self):
        h = history_with([])
        picks = []
        for i in range(40):
            language = strategy.choose_voice_language(h, plan(), "reel")
            picks.append(language)
            h.posts.append({"id": f"p{i}", "format": "reel", "market": "india", "pillar": "prep_free",
                            "language": language})
        self.assertTrue(8 <= picks.count("hindi") <= 12, picks.count("hindi"))
        self.assertNotIn("hindihindi", "".join("hindi" if p == "hindi" else "-" for p in picks))

    def test_never_abroad_films_jobs_or_other_languages(self):
        h = history_with([])
        with patch.dict(os.environ, {"HINDI_VOICE_SHARE": "1"}):
            self.assertEqual(strategy.choose_voice_language(h, plan(), "reel"), "hindi")
            self.assertEqual(strategy.choose_voice_language(h, plan(market="global"), "reel"), "english")
            self.assertEqual(strategy.choose_voice_language(h, plan(), "film"), "english")
            self.assertEqual(strategy.choose_voice_language(h, plan(), "carousel"), "english")
            self.assertEqual(strategy.choose_voice_language(h, plan(pillar="jobs"), "reel"), "english")
            self.assertEqual(strategy.choose_voice_language(h, plan(language="hinglish"), "reel"), "hinglish")
        with patch.dict(os.environ, {"HINDI_VOICE_SHARE": "0"}):
            self.assertEqual(strategy.choose_voice_language(h, plan(), "reel"), "english")

    def test_jobs_and_abroad_reels_do_not_count_toward_the_share(self):
        crowd = [{"format": "reel", "market": "global", "language": "english"},
                 {"format": "reel", "market": "india", "pillar": "jobs", "language": "english"}] * 10
        recent = [{"format": "reel", "market": "india", "pillar": "prep_free", "language": "english"}] * 3
        self.assertEqual(strategy.choose_voice_language(history_with(crowd + recent), plan(), "reel"), "hindi")

    def test_hindi_is_spoken_by_a_hindi_voice(self):
        self.assertEqual(tts.CHIRP_LOCALES["hindi"], "hi-IN")
        self.assertIn("Hindi", tts.DIRECTIONS["hindi"])

    def test_screen_text_in_a_hindi_reel_must_be_english(self):
        devanagari = "".join(chr(c) for c in (0x0939, 0x093F, 0x0902, 0x0926, 0x0940))
        post = {"language": "hindi", "hook": "Asked your greatest weakness?",
                "slides": [{"type": "hook", "title": "Asked your greatest weakness?",
                            "narration": "HR ने पूछा weakness बताइए?"},
                           {"type": "product", "image": "overlay_hinglish", "title": "Interview Sarthi"}]}
        checked, problems = copywriter.validate(post, "reel")
        self.assertEqual([p for p in problems if "Hindi-voice" in p], [])
        self.assertEqual(checked["slides"][1]["image"], "overlay_english")
        post["slides"][0]["title"] = devanagari
        self.assertTrue([p for p in copywriter.validate(post, "reel")[1] if "Hindi-voice" in p])


    def test_india_sales_clips_speak_hindi_and_global_ones_do_not(self):
        self.assertTrue(campaign.hindi_sales("india"))
        self.assertFalse(campaign.hindi_sales("global"))
        with patch.dict(os.environ, {"HINDI_SALES": "0"}):
            self.assertFalse(campaign.hindi_sales("india"))

    def test_hindi_sales_script_rules(self):
        english = campaign.authored_script(campaign.scenarios()[0], "short", 0)
        self.assertEqual(campaign.script_problems(english, "short"), [])
        problems = campaign.script_problems(english, "short", "hindi")
        self.assertTrue(any("Devanagari" in p for p in problems), problems)
        self.assertEqual(campaign.HINDI_BUDGETS.keys(), campaign.BUDGETS.keys())

    def test_india_sales_openings_do_not_steer_the_reel_face_balance(self):
        # Reels alone are one white in three, so the next reel should be Indian. Counting the twelve
        # India sales openings would fill the window with Indian faces and wrongly pick white.
        reels = [{"format": "reel", "market": "india", "face": f} for f in ("white", "indian", "indian")]
        sales = [{"format": "sales", "market": "india", "face": "indian"}] * 12
        self.assertEqual(veo_opening.choose_face(history_with(reels + sales)), "indian")


if __name__ == "__main__":
    unittest.main()
