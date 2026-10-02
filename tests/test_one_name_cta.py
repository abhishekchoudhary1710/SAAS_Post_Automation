"""One easy name in every call to action (owner's decision, 2 Oct 2026).

Reels for all three apps end by sending people to interview sarthi dot com, never to Prep Sarthi,
ApplySarthi or Live Sarthi by name: viewers remember one name, and the site's home offers all three.
"""
import datetime as dt
import re
import unittest
from collections import Counter
from unittest.mock import patch

from agent import linkedin_growth as growth
from agent.config import SAMPLES, load_json, product
from agent.copywriter import VOICE, closing_problems, validate
from agent.pipeline import compose_captions

OTHER_NAMES = re.compile(r"(?i)prep ?sarthi|apply ?sarthi|live ?sarthi")
PRODUCTS = ("interview_sarthi", "prep_sarthi", "apply_sarthi")


def closing(narration):
    return closing_problems([{"type": "cta", "narration": narration}])


class ClosingLineTests(unittest.TestCase):
    def test_umbrella_site_passes_in_any_spelling(self):
        for line in ("Free mock interview in your browser. Visit interview sarthi dot com.",
                     "Find jobs free. Visit interviewsarthi.com",
                     "Visit Interview Sarthi dot com, thirty minutes free.",
                     "मुफ़्त mock interview. इंटरव्यू सारथी डॉट कॉम पर जाइए।"):
            self.assertEqual(closing(line), [], line)

    def test_profile_link_alone_or_another_apps_name_is_sent_back(self):
        for line in ("Try Prep Sarthi free in your browser, open the profile link.",
                     "ApplySarthi is always free. Link in bio.",
                     "Try Prep Sarthi free at interview sarthi dot com.",
                     ""):
            self.assertTrue(closing(line), line)

    def test_an_earlier_sentence_may_still_name_the_app(self):
        line = "Prep Sarthi scores every answer. Free mock interview: visit interview sarthi dot com."
        self.assertEqual(closing(line), [])

    def test_every_spoken_example_the_writer_sees_passes(self):
        for pid in PRODUCTS:
            self.assertEqual(closing(VOICE[pid]["cta_spoken"]), [], pid)
            self.assertNotRegex(VOICE[pid]["cta_spoken"], OTHER_NAMES, pid)
        for fmt in ("reel", "film", "demo"):
            content = load_json(SAMPLES / f"sample_{fmt}.json")
            self.assertEqual(closing_problems(content["slides"]), [], fmt)

    def test_validate_sends_a_product_named_close_back_to_the_writer(self):
        content = load_json(SAMPLES / "sample_reel.json")
        content["slides"][-1]["narration"] = "Windows app, thirty minutes free. Open the profile link."
        _, problems = validate(content, "reel")
        self.assertTrue(any("Visit interview sarthi dot com" in p for p in problems), problems)
        _, problems = validate(load_json(SAMPLES / "sample_reel.json"), "reel")
        self.assertFalse(any("interview sarthi dot com" in p for p in problems), problems)


class CaptionTests(unittest.TestCase):
    def test_instagram_and_youtube_calls_to_action_name_only_the_umbrella_site(self):
        for pid in PRODUCTS:
            for platform in ("instagram", "youtube"):
                line = product(pid)["cta_lines"][platform]
                self.assertIn("interviewsarthi.com", line, (pid, platform))
                self.assertNotRegex(line, r"interviewsarthi\.com/", (pid, platform))
                self.assertNotRegex(line, OTHER_NAMES, (pid, platform))

    def test_facebook_keeps_each_apps_own_clickable_link(self):
        content = {"caption": "A caption long enough to stand on its own for this test.", "hook": "Hook",
                   "hashtags": ["#MockInterview"], "reel": {"youtube_title": "Title"}}
        out = compose_captions(content, "reel", {"product": "prep_sarthi", "campaign_id": "x"})
        self.assertIn("https://interviewsarthi.com/prep/?utm_source=facebook", out["facebook"])


class CardTests(unittest.TestCase):
    def drawn(self, spec):
        from PIL import ImageDraw
        from agent.render.cards import _build
        texts = []
        real = ImageDraw.ImageDraw.text

        def record(draw, xy, text, *args, **kwargs):
            texts.append(str(text))
            return real(draw, xy, text, *args, **kwargs)

        with patch.object(ImageDraw.ImageDraw, "text", record):
            _build(spec, (1080, 1920), 1, 1)
        return texts

    def test_every_card_footer_shows_the_umbrella_site(self):
        for pid in PRODUCTS:
            texts = self.drawn({"type": "hook", "title": "A hook", "product": pid})
            self.assertIn("interviewsarthi.com", texts, pid)
            self.assertFalse([t for t in texts if "interviewsarthi.com/" in t], pid)

    def test_closing_card_names_only_interview_sarthi(self):
        for pid in PRODUCTS:
            texts = self.drawn({"type": "cta", "title": "Try it free", "product": pid})
            self.assertIn("Interview Sarthi", texts, pid)
            self.assertFalse([t for t in texts if OTHER_NAMES.search(t)], (pid, texts))
        self.assertIn("Job search", self.drawn({"type": "cta", "title": "Find jobs free", "product": "apply_sarthi"}))

    def test_cards_before_the_close_still_name_the_app_shown(self):
        self.assertIn("Prep Sarthi", self.drawn({"type": "hook", "title": "A hook", "product": "prep_sarthi"}))


class LinkedInTests(unittest.TestCase):
    def test_closing_cards_send_people_to_the_umbrella_site_and_text_keeps_one_link(self):
        from agent.joblist import SAMPLE
        config = load_json(growth.CONFIG)
        state, formats = {"posts": []}, Counter()
        for offset in range(7):
            day = dt.date(2026, 9, 28) + dt.timedelta(days=offset)
            for slot in config["slots"]:
                seed = growth.choose(day, state, config, slot)
                post = growth.compose(day, seed, config, SAMPLE if seed["series"] == "jobs" else None, slot)
                state["posts"].append(post)
                for slide in post["slides"]:
                    self.assertNotIn("site", slide)
                    if slide["type"] == "cta":
                        formats[post["format"]] += 1
                        self.assertEqual(slide["note"], growth.ONE_NAME_NOTE)
                        self.assertNotRegex(slide["title"], OTHER_NAMES)
        self.assertEqual(formats, {"document": 4, "video": 3})


if __name__ == "__main__":
    unittest.main()
