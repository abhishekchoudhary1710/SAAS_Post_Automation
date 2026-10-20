"""Film personas: people and settings come from one pool, and both pools get used."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import story
from agent.history import History


class PersonaTests(unittest.TestCase):
    def test_person_and_setting_share_a_pool_and_both_pools_appear(self):
        pools = story.personas()
        regions = set()
        for day in range(40):
            h = History(Path(tempfile.mkdtemp()) / "history.json")
            when = dt.datetime(2026, 10, 1) + dt.timedelta(days=day)
            with patch("agent.story.now_ist", return_value=when):
                p = story.choose_persona(h)
            self.assertIn(p["person"], pools["people"][p["region"]])
            self.assertIn(p["setting"], pools["settings"][p["region"]])
            regions.add(p["region"])
        self.assertEqual(regions, {"india", "global"})

    def test_film_look_names_no_country(self):
        self.assertNotIn("Indian", story.stories()["look"])


if __name__ == "__main__":
    unittest.main()
