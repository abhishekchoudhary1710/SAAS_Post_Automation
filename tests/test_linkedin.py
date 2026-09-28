"""LinkedIn (agent/publish/linkedin.py): the post text LinkedIn receives, which posts go there, and that a
LinkedIn problem can never fail a run. No network: the API calls are replaced."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import joblist
from agent.config import Settings
from agent.pipeline import compose_captions, publish
from agent.publish import linkedin

PLAN = {"pillar": "jobs", "product": "apply_sarthi", "market": "india", "campaign_id": "t"}


def settings(token="token", expires=None):
    s = Settings.from_env()
    s.dry_run = False
    s.linkedin_access_token, s.linkedin_token_expires = token, expires
    s.linkedin_author_urn = "urn:li:organization:123"
    s.meta_page_id = s.meta_page_token = s.yt_client_id = None
    return s


def jobs_manifest(folder):
    content = joblist.content_for(joblist.SAMPLE)
    image = Path(folder) / "linkedin-01.jpg"
    image.write_bytes(b"card")
    return {"id": "t", "format": "reel", "plan": PLAN, "content": content,
            "media": {"video": str(Path(folder) / "reel.mp4"), "linkedin_image": str(image)},
            "captions": compose_captions(content, "reel", PLAN)}


class TextTests(unittest.TestCase):
    def test_reserved_characters_are_escaped_but_links_are_not(self):
        text = linkedin.escape("AWS (38%) #1 in_house https://apply.interviewsarthi.com/skills/python_x/a?b=c")
        self.assertEqual(text, "AWS \\(38%\\) \\#1 in\\_house https://apply.interviewsarthi.com/skills/python_x/a?b=c")

    def test_hashtags_become_real_hashtags(self):
        self.assertEqual(linkedin.hashtag("#hyderabadjobs"), "{hashtag|\\#|hyderabadjobs}")
        self.assertTrue(linkedin.commentary("Hi", ["#a", "#"]).endswith("\n\n{hashtag|\\#|a}"))

    def test_the_jobs_post_links_straight_to_the_list_and_to_prep_sarthi(self):
        text = compose_captions(joblist.content_for(joblist.SAMPLE), "reel", PLAN)["linkedin"]
        self.assertTrue(text.startswith("67 new Python jobs in Hyderabad this week."))
        self.assertIn("\n" + joblist.SAMPLE["url"] + "\n", text)
        self.assertIn("https://interviewsarthi.com/prep", text)
        self.assertIn("AWS \\(38% of these jobs\\)", text)
        self.assertNotIn("link in bio", text)
        self.assertIn("{hashtag|\\#|pythonjobs}", text)

    def test_only_posts_with_their_own_linkedin_text_go_there(self):
        caps = compose_captions({"caption": "A product reel", "hook": "Hook"}, "reel", {"pillar": "x"})
        self.assertNotIn("linkedin", caps)


class PublishTests(unittest.TestCase):
    def test_the_jobs_post_goes_to_linkedin_with_its_card(self):
        with tempfile.TemporaryDirectory() as folder:
            m = jobs_manifest(folder)
            with patch("agent.publish.linkedin.post", return_value="urn:li:share:1") as post:
                outcome = publish(m, settings(), ["instagram", "linkedin"])
            post.assert_called_once()
            self.assertEqual(post.call_args.args[2], m["media"]["linkedin_image"])
            self.assertEqual(outcome["results"]["linkedin"]["url"], "https://www.linkedin.com/feed/update/urn:li:share:1/")

    def test_a_linkedin_failure_is_a_warning_not_an_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("agent.publish.linkedin.post", side_effect=RuntimeError("HTTP 401")):
                outcome = publish(jobs_manifest(folder), settings(), ["linkedin"])
        self.assertEqual(outcome["errors"], {})
        self.assertIn("HTTP 401", outcome["warnings"]["linkedin"])

    def test_without_a_token_linkedin_is_skipped_quietly(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("agent.publish.linkedin.post") as post:
                outcome = publish(jobs_manifest(folder), settings(token=None), ["linkedin"])
            post.assert_not_called()
        self.assertEqual((outcome["errors"], outcome["warnings"], outcome["results"]), ({}, {}, {}))

    def test_a_posted_linkedin_post_is_not_posted_again_on_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            m = jobs_manifest(folder)
            with patch("agent.publish.linkedin.post", return_value="urn:li:share:1") as post:
                publish(m, settings(), ["linkedin"])
                publish(m, settings(), ["linkedin"])
            post.assert_called_once()

    def test_it_never_posts_on_a_personal_profile(self):
        s = settings()
        s.linkedin_author_urn = "urn:li:person:abc"
        with tempfile.TemporaryDirectory() as folder:
            with patch("requests.post") as http:
                outcome = publish(jobs_manifest(folder), s, ["linkedin"])
            http.assert_not_called()
        self.assertIn("personal profile is switched off", outcome["warnings"]["linkedin"])
        self.assertEqual(linkedin.author(settings()), "urn:li:organization:123")

    def test_the_run_warns_ten_days_before_the_token_expires(self):
        today = dt.date(2026, 9, 28)
        self.assertIsNone(linkedin.expiry_warning(settings(expires="2026-11-27"), today))
        self.assertIn("2026-10-08", linkedin.expiry_warning(settings(expires="2026-10-08"), today))


if __name__ == "__main__":
    unittest.main()
