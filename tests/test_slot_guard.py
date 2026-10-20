"""The backup GitHub schedule must skip only when the outside scheduler really posted the slot."""
import datetime as dt
import unittest

from tools.slot_already_posted import WINDOW_HOURS, decide, published_during, run_blocks, title_for

NOW = dt.datetime(2026, 9, 15, 14, 0, tzinfo=dt.timezone.utc)


def run(slot="evening", hours_ago=5, status="completed", conclusion="success",
        event="workflow_dispatch", title=None, run_id=1, minutes_long=12):
    created = NOW - dt.timedelta(hours=hours_ago)
    stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": run_id, "event": event, "status": status, "conclusion": conclusion,
            "created_at": stamp(created), "run_started_at": stamp(created + dt.timedelta(seconds=20)),
            "updated_at": stamp(created + dt.timedelta(minutes=minutes_long)),
            "display_title": title if title is not None else title_for(slot)}


def post_at(utc_time, posted=None):
    ist = utc_time + dt.timedelta(hours=5, minutes=30)
    return {"date": ist.strftime("%Y-%m-%d %H:%M IST"),
            "posted": posted if posted is not None else {"facebook": {"id": "fb1"}, "youtube": {"id": "yt1"}},
            "errors": {"instagram": "MetaError"}}


class SlotGuardTests(unittest.TestCase):
    def test_recent_successful_outside_run_blocks(self):
        self.assertTrue(run_blocks(run(), "evening", NOW))

    def test_run_still_going_blocks(self):
        self.assertTrue(run_blocks(run(status="in_progress", conclusion=None), "evening", NOW))
        self.assertTrue(run_blocks(run(status="queued", conclusion=None), "evening", NOW))

    def test_failed_outside_run_with_nothing_published_lets_the_backup_post(self):
        self.assertFalse(run_blocks(run(conclusion="failure"), "evening", NOW, posts=[]))
        self.assertFalse(run_blocks(run(conclusion="cancelled"), "evening", NOW, posts=[]))

    def test_failed_run_that_published_somewhere_blocks_the_backup(self):
        failed = run(conclusion="failure")
        during = NOW - dt.timedelta(hours=5) + dt.timedelta(minutes=8)
        self.assertTrue(run_blocks(failed, "evening", NOW, posts=[post_at(during)]))

    def test_posts_outside_the_failed_run_or_without_results_do_not_count(self):
        failed = run(conclusion="failure")
        before = NOW - dt.timedelta(hours=6)
        after = NOW - dt.timedelta(hours=4)
        during = NOW - dt.timedelta(hours=5) + dt.timedelta(minutes=8)
        self.assertFalse(published_during(failed, [post_at(before), post_at(after)]))
        self.assertFalse(published_during(failed, [post_at(during, posted={})]))

    def test_dry_run_never_blocks_a_real_post(self):
        self.assertFalse(run_blocks(run(title=title_for("evening") + " (dry run)"), "evening", NOW))

    def test_other_slot_does_not_block(self):
        self.assertFalse(run_blocks(run(slot="midday"), "evening", NOW))

    def test_yesterdays_run_does_not_block(self):
        self.assertFalse(run_blocks(run(hours_ago=WINDOW_HOURS + 1), "evening", NOW))

    def test_scheduled_runs_and_the_current_run_are_ignored(self):
        self.assertFalse(run_blocks(run(event="schedule"), "evening", NOW))
        self.assertFalse(run_blocks(run(run_id=42), "evening", NOW, current_run_id="42"))

    def test_decide_skips_only_for_a_matching_run(self):
        runs = [run(slot="midday"), run(title=title_for("evening") + " (dry run)"), run(run_id=7)]
        self.assertTrue(decide("evening", runs, NOW)[0])
        self.assertFalse(decide("morning", runs, NOW)[0])
        self.assertFalse(decide("manual", runs, NOW)[0])
        self.assertFalse(decide("evening", [], NOW)[0])

    def test_new_slot_names_are_scheduled_slots(self):
        for slot in ("late-morning", "prep-morning", "early-afternoon", "early-evening", "apply-night", "night"):
            self.assertTrue(decide(slot, [run(slot=slot)], NOW)[0])

    def test_receipt_blocks_duplicate_dispatch_or_backup(self):
        prior = {"id": "first", "slot": "prep-morning", "date": "2026-09-15 11:37 IST",
                 "posted": {"instagram": {"id": "ig1"}}}
        self.assertTrue(decide("prep-morning", [], NOW, posts=[prior])[0])
        self.assertFalse(decide("apply-night", [], NOW, posts=[prior])[0])


if __name__ == "__main__":
    unittest.main()
