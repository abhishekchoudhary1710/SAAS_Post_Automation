"""Every caption sends the viewer somewhere GA4 can see, and asks them something (16 Sep 2026)."""
import unittest

from agent.config import VIDEO_FORMATS, brand
from agent.pipeline import compose_captions, engagement_question

CONTENT = {"caption": "Your project. But what did YOU build?", "hook": "Your project. But what did YOU build?",
           "hashtags": ["#TCSNQT", "#HRRound"], "reel": {"youtube_title": "What was your role? | Interview Sarthi",
                                                          "youtube_description": "A fictional example answer."}}
PLAN = {"campaign_id": "20260916-1937-sales-standard", "guide_link": "https://interviewsarthi.com/guides/why-should-we-hire-you.html"}


class CaptionTests(unittest.TestCase):
    def setUp(self):
        self.fmt = "sales" if "sales" in VIDEO_FORMATS else next(iter(VIDEO_FORMATS))
        self.out = compose_captions(CONTENT, self.fmt, PLAN)

    def test_instagram_names_the_site_and_the_bio_link_without_a_dead_url(self):
        text = self.out["instagram"]
        self.assertIn("interviewsarthi.com", text)
        self.assertIn("bio", text.lower())
        self.assertIn("laptop", text.lower())
        self.assertNotIn("http", text)

    def test_youtube_opens_with_a_tagged_link_and_gives_the_store_url(self):
        description = self.out["youtube"]["description"]
        first = description.splitlines()[0]
        self.assertIn("https://interviewsarthi.com/?utm_source=youtube", first)
        self.assertIn("utm_content=20260916-1937-sales-standard", first)
        self.assertIn(brand()["store_url"], description)
        self.assertNotIn("search Interview Sarthi", description)
        self.assertIn(PLAN["guide_link"], description)

    def test_facebook_keeps_its_tagged_link(self):
        self.assertIn("utm_source=facebook", self.out["facebook"])

    def test_every_platform_asks_the_same_question_and_it_is_stable(self):
        question = engagement_question(PLAN, CONTENT)
        self.assertTrue(question.endswith("?") or question.endswith("."))
        for platform in ("instagram", "facebook"):
            self.assertIn(question, self.out[platform])
        self.assertIn(question, self.out["youtube"]["description"])
        self.assertEqual(question, engagement_question(PLAN, CONTENT))
        # A different post gets a question of its own often enough to rotate.
        others = {engagement_question({"campaign_id": f"post-{i}"}, CONTENT) for i in range(30)}
        self.assertGreater(len(others), 1)

    def test_questions_never_use_banned_words(self):
        banned = [w.lower() for w in brand()["forbidden_words"]]
        for q in brand()["engagement_questions"]:
            self.assertFalse(any(w in q.lower() for w in banned), q)


if __name__ == "__main__":
    unittest.main()
