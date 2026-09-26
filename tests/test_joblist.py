"""The daily jobs post (agent/joblist.py): which list it picks, what it says, and how its slot is wired.
No network and no rendering: the feed is replaced by fixed lists."""
import datetime as dt
import pathlib
import subprocess
import unittest

from agent import joblist
from agent.pipeline import compose_captions

ROOT = pathlib.Path(__file__).resolve().parents[1]


def item(id_, where="Bengaluru", new=40, **extra):
    what = id_.split(":")[1].split("@")[0].title()
    return dict({"id": id_, "kind": "skill", "what": what, "where": where, "path": "/x",
                 "url": f"https://apply.interviewsarthi.com/{id_}", "total": 300, "new_7d": new,
                 "companies": ["JPMorgan", "Amazon", "Okta"], "skills": [["AWS", 40], ["SQL", 30]]}, **extra)


class FakeHistory:
    def __init__(self, posts):
        self.posts = posts


def posted(topic, days_ago=1, today=dt.date(2026, 9, 26)):
    return {"series": joblist.SERIES, "topic": topic, "date": (today - dt.timedelta(days=days_ago)).isoformat() + " 13:40 IST"}


class ChooseTests(unittest.TestCase):
    TODAY = dt.date(2026, 9, 26)

    def test_the_list_with_most_new_jobs_wins(self):
        lists = [item("skill:java@bengaluru", new=78), item("skill:python@hyderabad", "Hyderabad", new=67)]
        self.assertEqual(joblist.choose(lists, FakeHistory([]), self.TODAY)["id"], "skill:java@bengaluru")

    def test_a_list_posted_in_the_last_three_weeks_is_skipped(self):
        lists = [item("skill:java@bengaluru", new=78), item("skill:python@hyderabad", "Hyderabad", new=67)]
        history = FakeHistory([posted("skill:java@bengaluru", 5)])
        self.assertEqual(joblist.choose(lists, history, self.TODAY)["id"], "skill:python@hyderabad")
        old = FakeHistory([posted("skill:java@bengaluru", 30)])
        self.assertEqual(joblist.choose(lists, old, self.TODAY)["id"], "skill:java@bengaluru")

    def test_every_third_jobs_post_is_remote(self):
        lists = [item("skill:java@bengaluru", new=78), item("skill:python@remote", "remote", new=900)]
        self.assertEqual(joblist.choose(lists, FakeHistory([]), self.TODAY)["where"], "Bengaluru")
        two = FakeHistory([posted("a", 3), posted("b", 2)])
        self.assertEqual(joblist.choose(lists, two, self.TODAY)["where"], "remote")

    def test_when_everything_was_posted_recently_it_still_posts(self):
        lists = [item("skill:java@bengaluru")]
        self.assertEqual(joblist.choose(lists, FakeHistory([posted("skill:java@bengaluru")]), self.TODAY)["id"],
                         "skill:java@bengaluru")

    def test_lists_without_three_named_employers_are_not_usable(self):
        self.assertFalse(joblist._usable(item("skill:java@bengaluru", companies=["Amazon"])))
        self.assertTrue(joblist._usable(item("skill:java@bengaluru")))


class ContentTests(unittest.TestCase):
    def test_every_number_and_name_comes_from_the_list(self):
        c = joblist.content_for(joblist.SAMPLE)
        self.assertEqual(c["hook"], "67 new Python jobs in Hyderabad this week")
        text = " ".join(str(s) for s in c["slides"])
        for fact in ("321", "Micron", "Analog Devices", "ServiceNow", "Sanofi", "AWS (38% of these jobs)"):
            self.assertIn(fact, text)
        self.assertEqual([s["type"] for s in c["slides"]], ["hook", "points", "points", "cta", "cta"])
        self.assertEqual(c["slides"][-1]["product"], "prep_sarthi")
        self.assertTrue(all(s.get("narration") for s in c["slides"]))

    def test_remote_lists_read_as_remote(self):
        c = joblist.content_for(item("skill:python@remote", "remote", new=888, what="Python"))
        self.assertEqual(c["hook"], "888 new remote Python jobs this week")
        self.assertEqual(c["market"], "global")
        self.assertIn("#remotejobs", c["hashtags"])

    def test_captions_send_people_to_the_profile_link_and_name_prep_sarthi(self):
        c = joblist.content_for(joblist.SAMPLE)
        plan = {"pillar": "jobs", "product": "apply_sarthi", "market": "india", "campaign_id": "t"}
        caps = compose_captions(c, "reel", plan)
        self.assertIn("link in bio, then tap Find jobs", caps["instagram"])
        self.assertIn("Prep Sarthi", caps["instagram"])
        self.assertIn("#Shorts", caps["youtube"]["title"])
        self.assertIn(joblist.SAMPLE["url"], caps["youtube"]["description"])


class SlotTests(unittest.TestCase):
    def test_the_jobs_slot_makes_a_joblist_for_applysarthi_in_its_own_series(self):
        workflow = (ROOT / ".github/workflows/post.yml").read_text()
        selection = workflow.split('          PRODUCT=""', 1)[1].split('          PRODUCT_ARG=""', 1)[0]
        out = subprocess.run(
            ["bash", "-c", 'SLOT=jobs; PRODUCT=""; FORMAT=auto; VARIANT=auto;\n' + selection
             + '\nprintf "%s %s %s" "$PRODUCT" "$FORMAT" "$CONTENT_SERIES"'],
            check=True, capture_output=True, text=True).stdout.split()
        self.assertEqual(out, ["apply_sarthi", "joblist", joblist.SERIES])
        self.assertIn('"7 8 * * *")   SLOT="jobs"', workflow)

    def test_it_is_dispatched_on_time_after_the_midday_post(self):
        chain = (ROOT / ".github/workflows/dispatch-extra-slots.yml").read_text()
        self.assertIn("'Post to social: midday'", chain)
        self.assertIn("SLOT=jobs", chain)
        self.assertIn("TARGET_UTC=08:07:00", chain)

    def test_the_duplicate_guard_knows_the_slot(self):
        from tools.slot_already_posted import SLOTS
        self.assertIn("jobs", SLOTS)


if __name__ == "__main__":
    unittest.main()
