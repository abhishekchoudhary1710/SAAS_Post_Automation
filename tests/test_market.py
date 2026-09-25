"""Posts for viewers outside India: chosen by share, then dollars, plain English and a neutral voice throughout."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from agent import market as mk
from agent.campaign import authored_script, choose_scenario, for_abroad, scenarios, script_problems
from agent.config import ROOT, SAMPLES, load_json
from agent.copywriter import validate
from agent.history import History
from agent.pipeline import compose_captions
from agent.render import veo_opening as vo
from agent.render.tts import CHIRP_LOCALES, DIRECTIONS

RUPEES = re.compile(r"₹|\bRs\b|rupee", re.I)


def empty_history():
    return History(Path(tempfile.mkdtemp()) / "history.json")


def run_of(pid, n):
    """The markets choose() picks for n posts in a row, each recorded as it would be after posting."""
    h, out = empty_history(), []
    for i in range(n):
        m = mk.choose(pid, h)
        out.append(m)
        h.posts.append({"id": str(i), "product": pid, "market": m})
    return out


class ChoiceTests(unittest.TestCase):
    def test_each_product_keeps_near_its_share_without_long_runs(self):
        for pid in ("prep_sarthi", "interview_sarthi"):
            run = run_of(pid, 12)
            share = run.count("global") / len(run)
            self.assertAlmostEqual(share, mk.share(pid), delta=0.1, msg=(pid, run))
            self.assertNotIn(["global"] * 4, [run[i:i + 4] for i in range(len(run) - 3)])
        self.assertGreater(mk.share("prep_sarthi"), mk.share("interview_sarthi"))   # Prep leads abroad

    def test_apply_stays_indian_because_its_jobs_are(self):
        self.assertEqual(set(run_of("apply_sarthi", 6)), {"india"})

    def test_posts_from_before_markets_do_not_force_a_run_abroad(self):
        h = empty_history()
        h.posts += [{"id": str(i), "product": "prep_sarthi"} for i in range(12)]
        run = []
        for i in range(6):
            m = mk.choose("prep_sarthi", h)
            run.append(m)
            h.posts.append({"id": f"n{i}", "product": "prep_sarthi", "market": m})
        self.assertIn("india", run)


class SalesReelTests(unittest.TestCase):
    def test_abroad_seed_is_english_with_an_international_name(self):
        seed, _ = choose_scenario(empty_history(), market="global")
        self.assertEqual(seed["language"], "english")
        s = for_abroad({**seed, "market": "global"})
        self.assertNotIn(seed["name"], s["profile"])
        self.assertIn(s["name"], mk.data()["global"]["names"])
        self.assertNotRegex(json.dumps(s), r"\bfreshers?\b")

    def test_abroad_script_speaks_dollars_and_still_passes_the_script_rules(self):
        for seed in [x for x in scenarios() if x["language"] == "english"][:4]:
            s = for_abroad({**copy.deepcopy(seed), "market": "global"})
            for variant in ("short", "standard", "promo"):
                script = authored_script(s, variant, 0)
                self.assertEqual(script_problems(script, variant), [], (seed["id"], variant))
                self.assertNotRegex(json.dumps(script), RUPEES)
            self.assertIn("nine ninety-nine", authored_script(s, "standard", 0)["narrations"][-1])

    def test_indian_script_is_unchanged(self):
        seed = scenarios()[0]
        self.assertIn("ninety-nine rupees", authored_script(seed, "standard", 0)["narrations"][-1])

    def test_abroad_facts_drop_rupees_and_add_dollars(self):
        from agent.campaign import FACTS
        text = mk.facts("interview_sarthi", "global", FACTS)
        self.assertNotRegex(text, RUPEES)
        self.assertIn("$9.99", text)
        self.assertEqual(mk.facts("interview_sarthi", "india", FACTS), FACTS)


class WrittenPostTests(unittest.TestCase):
    def sample(self, market):
        content = load_json(SAMPLES / "sample_reel.json")
        content["market"] = market
        return content

    def test_validate_stamps_every_slide_with_the_market(self):
        content, _ = validate(self.sample("global"), "reel")
        self.assertEqual({s["market"] for s in content["slides"]}, {"global"})
        self.assertEqual(validate(self.sample(None), "reel")[0]["market"], "india")

    def test_abroad_post_that_mentions_rupees_or_hinglish_is_sent_back(self):
        content = self.sample("global")
        content["slides"][-1]["narration"] = "Passes from 99 rupees. Open the profile link."
        _, problems = validate(content, "reel")
        self.assertTrue(any("outside India" in p for p in problems), problems)
        _, problems = validate(self.sample("india"), "reel")
        self.assertFalse(any("outside India" in p for p in problems), problems)

    def test_abroad_hashtags_carry_nothing_indian(self):
        content = self.sample("global")
        content["hashtags"] = ["#TCSNQT", "#FresherJobs", "#MockInterview"]
        content, _ = validate(content, "reel")
        self.assertTrue(content["hashtags"])
        for tag in content["hashtags"]:
            self.assertNotRegex(tag.lower(), r"tcs|fresher|india|placement")

    def test_captions_abroad_quote_dollars_and_ask_a_global_question(self):
        for pid in ("interview_sarthi", "prep_sarthi"):
            content = {"caption": "A caption long enough to stand on its own for this test.", "hook": "Hook",
                       "hashtags": ["#MockInterview"], "market": "global", "product": pid,
                       "reel": {"youtube_title": "Title"}}
            out = compose_captions(content, "reel", {"product": pid, "campaign_id": "x", "market": "global"})
            for text in (out["facebook"], out["youtube"]["description"]):
                self.assertNotRegex(text, RUPEES, pid)
                self.assertNotIn("Hinglish", text)
            self.assertIn("$", out["facebook"])

    def test_cta_card_prices_follow_product_and_market(self):
        # Since 25 Sep 2026: Live has a 2-day and a 1-month pass, Prep one 30-day pass.
        self.assertEqual([r["price"] for r in mk.pricing("interview_sarthi", "india")], ["₹0", "₹99", "₹299"])
        self.assertEqual([r["price"] for r in mk.pricing("interview_sarthi", "global")], ["$0", "$9.99", "$29.99"])
        # Prep's card used to show the Windows app's ladder; now it shows its own passes.
        self.assertEqual([r["price"] for r in mk.pricing("prep_sarthi", "india")], ["₹0", "₹99"])
        self.assertEqual([r["price"] for r in mk.pricing("prep_sarthi", "global")], ["$0", "$9.99"])
        self.assertEqual(mk.pricing("prep_sarthi", "india")[1]["label"], "30-Day Pass")

    def test_closing_card_sells_the_month_in_each_market(self):
        self.assertEqual(mk.card_price("interview_sarthi", "global", ("x", "y")),
                         ("Then $9.99 for 2 days.", "$29.99 covers the whole month."))
        self.assertIn("Rs 299 covers the whole month.", (ROOT / "agent/render/motion.py").read_text(encoding="utf-8"))

    def test_no_retired_pass_is_mentioned(self):
        retired = re.compile(r"7-Day Pass|3-Month Pass|₹399|Rs 399|₹999|Rs 999|1,999|₹249|Rs 249|"
                             r"\$19\.99|\$39\.99|\$69\.99|\$4\.99|covers a week")
        for name in ("knowledge/brand.json", "knowledge/markets.json", "agent/campaign.py",
                     "agent/copywriter.py", "agent/render/motion.py"):
            self.assertNotRegex((ROOT / name).read_text(encoding="utf-8"), retired, name)


class FaceAndVoiceTests(unittest.TestCase):
    def test_face_follows_the_post_market(self):
        for i in range(20):
            s = {"id": f"fresh-{i}", "audience": "A new graduate explaining their project", "question": "Why?"}
            self.assertIn("A young Indian adult", vo.opening_prompt({**s, "market": "india"}))
            self.assertNotIn("Indian", vo.opening_prompt({**s, "market": "global"}))

    def test_abroad_voice_is_neutral_english(self):
        self.assertEqual(mk.voice_language("english", "global"), "english_global")
        self.assertEqual(mk.voice_language("english", "india"), "english")
        self.assertEqual(mk.voice_language("hinglish", "global"), "hinglish")
        self.assertNotIn("Indian", DIRECTIONS["english_global"])
        self.assertEqual(CHIRP_LOCALES["english_global"], "en-US")


if __name__ == "__main__":
    unittest.main()
