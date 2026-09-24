"""Exercise the actual workflow's slot selection without running or publishing posts."""
import collections
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductScheduleTests(unittest.TestCase):
    def test_eight_slots_have_the_intended_products_and_supported_formats(self):
        workflow = (ROOT / ".github/workflows/post.yml").read_text()
        selection = workflow.split('          PRODUCT=""', 1)[1].split('          PRODUCT_ARG=""', 1)[0]
        pillars = json.loads((ROOT / "knowledge/pillars.json").read_text())["pillars"]
        counts = collections.Counter()
        slots = ("morning", "late-morning", "midday", "early-afternoon",
                 "afternoon", "early-evening", "evening", "night")
        for slot in slots:
            result = subprocess.run(
                ["bash", "-c", 'SLOT="$1"; PRODUCT=""; FORMAT=auto; VARIANT=auto;\n' + selection
                 + '\nprintf "%s %s" "${PRODUCT:-interview_sarthi}" "$FORMAT"', "schedule-test", slot],
                check=True, capture_output=True, text=True)
            product, fmt = result.stdout.split()
            counts[product] += 1
            if product != "interview_sarthi":
                self.assertIn(fmt, ("reel", "carousel"))
                self.assertTrue(any(p.get("product") == product and fmt in p["formats"] for p in pillars))
        # 24 Sep 2026: the Windows app is the only one of the three with paying
        # customers, so it holds three of the eight slots.
        self.assertEqual(counts, {"interview_sarthi": 3, "prep_sarthi": 3, "apply_sarthi": 2})
