"""One name in the whole reel (owner's decision, 22 Oct 2026).

Instagram and YouTube are for reach and recall, so every post names Interview Sarthi and nothing else:
spoken in the first words, on screen for the whole reel, first in the caption and in the spoken close.
Prep Sarthi and ApplySarthi are described by what they do, never by their own names.
"""
import copy
import pathlib
import re
import tempfile
import unittest

from agent import joblist
from agent.config import SAMPLES, load_json, pillars, product, product_label
from agent.copywriter import one_name_problems, says_name_early, validate
from agent.knowledge import context_pack
from agent.pipeline import brand_first_line, compose_captions

OTHER_NAMES = re.compile(r"(?i)prep ?sarthi|apply ?sarthi|live ?sarthi")
PRODUCTS = ("interview_sarthi", "prep_sarthi", "apply_sarthi")


class NameTests(unittest.TestCase):
    def test_every_product_is_shown_as_interview_sarthi(self):
        for pid in PRODUCTS:
            self.assertEqual(product(pid)["name"], "Interview Sarthi", pid)
            self.assertNotRegex(product(pid)["product_block"], OTHER_NAMES, pid)
        self.assertEqual(product_label("prep_sarthi"), "Interview Sarthi's free mock interview")
        self.assertEqual(product_label("apply_sarthi"), "Interview Sarthi's free job search")
        self.assertEqual(product_label("interview_sarthi"), "Interview Sarthi")

    def test_the_writer_is_told_the_rule_and_which_brief_section_to_use(self):
        pack = context_pack({"pillar": "prep_free"})
        self.assertIn("ONE NAME IN THE WHOLE POST", pack)
        self.assertIn("THE PRODUCT THIS POST SELLS: Interview Sarthi's free mock interview (the brief's Prep Sarthi", pack)

    def test_reach_weights_keep_every_product_in_the_mix(self):
        weights = {p["id"]: p["weight"] for p in pillars()}
        self.assertLess(weights["feature_demo"], weights["say_this"])
        self.assertGreaterEqual(weights["prep_free"], weights["prep_report"])
        self.assertTrue(all(w >= 1 for w in weights.values()))


class SpokenEarlyTests(unittest.TestCase):
    def test_name_in_the_first_ten_words(self):
        self.assertTrue(says_name_early("Mind gone blank on a video call? Interview Sarthi shows what to say."))
        self.assertTrue(says_name_early("इंटरव्यू सारथी पर free mock interview दीजिए।"))
        self.assertTrue(says_name_early("Interview Sarthi ka free mock interview aapka CV padhta hai."))
        self.assertFalse(says_name_early("You claimed Kafka on your CV and the interviewer asked how you "
                                         "scaled it. Interview Sarthi helps."))
        self.assertFalse(says_name_early(""))

    def test_reel_without_the_name_up_front_goes_back_to_the_writer(self):
        content = load_json(SAMPLES / "sample_reel.json")
        self.assertEqual(one_name_problems(content, "reel"), [])
        late = copy.deepcopy(content)
        late["slides"][0]["narration"] = "Your mind goes blank on a video call and the silence gets longer. Not again."
        _, problems = validate(late, "reel")
        self.assertTrue(any("first 10 words" in p for p in problems), problems)


class SubBrandTests(unittest.TestCase):
    def test_another_apps_name_anywhere_a_viewer_sees_it_is_sent_back(self):
        base = load_json(SAMPLES / "sample_reel.json")
        for where in ("caption", "hook", "slide", "narration", "youtube_title", "hashtag"):
            content = copy.deepcopy(base)
            if where == "caption":
                content["caption"] += "\nTry Prep Sarthi today."
            elif where == "hook":
                content["hook"] = "ApplySarthi fills job forms for you."
            elif where == "slide":
                content["slides"][1]["title"] = "Apply Sarthi ranked these"
            elif where == "narration":
                content["slides"][1]["narration"] = "Live Sarthi drafts the answer."
            elif where == "youtube_title":
                content.setdefault("reel", {})["youtube_title"] = "Prep Sarthi demo #Shorts"
            else:
                content["hashtags"] = ["#PrepSarthi"]
            problems = one_name_problems(content, "reel")
            self.assertTrue(any("names only Interview Sarthi" in p for p in problems), (where, problems))

    def test_internal_plan_fields_may_keep_the_brief_names(self):
        content = load_json(SAMPLES / "sample_reel.json")
        content["topic"] = "Prep Sarthi pushback on a Kafka claim"
        content["angle"] = "ApplySarthi angle"
        self.assertEqual(one_name_problems(content, "reel"), [])


class CaptionTests(unittest.TestCase):
    def test_first_line_names_interview_sarthi(self):
        self.assertEqual(brand_first_line("Tired of retyping marks?\n\nMore."),
                         "Interview Sarthi: Tired of retyping marks?\n\nMore.")
        kept = "Interview Sarthi's mock interview asks about your CV.\nMore."
        self.assertEqual(brand_first_line(kept), kept)
        self.assertEqual(brand_first_line(""), "")

    def test_instagram_and_youtube_captions_lead_with_the_name(self):
        content = {"caption": "Claimed Kafka on your CV? Expect follow-ups.\n\nPractise first.", "hook": "Hook",
                   "hashtags": ["#MockInterview"], "reel": {"youtube_title": "Title"}}
        for pid in PRODUCTS:
            out = compose_captions(copy.deepcopy(content), "reel", {"product": pid})
            self.assertTrue(out["instagram"].startswith("Interview Sarthi: Claimed Kafka"), pid)
            self.assertIn("Interview Sarthi: Claimed Kafka", out["youtube"]["description"], pid)


class JobsReelTests(unittest.TestCase):
    def test_jobs_reel_says_the_name_first_and_never_another_apps_name(self):
        content = joblist.content_for(joblist.SAMPLE)
        self.assertTrue(says_name_early(content["slides"][0]["narration"]))
        self.assertEqual(one_name_problems({k: v for k, v in content.items() if k != "linkedin"}, "reel"), [])


class BadgeTests(unittest.TestCase):
    def test_opening_badge_renders_the_name(self):
        from PIL import Image
        from agent.render.reel import brand_badge

        with tempfile.TemporaryDirectory() as tmp:
            img = Image.open(brand_badge(pathlib.Path(tmp) / "badge.png"))
            self.assertEqual(img.mode, "RGBA")
            self.assertEqual(img.height, 88)
            self.assertGreater(img.width, 300)


if __name__ == "__main__":
    unittest.main()
