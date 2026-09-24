"""Protect the 48-hour comparisons and repeat-content gate."""
import datetime as dt
import unittest

from agent.feedback import _due_snapshot, _record
from agent.pipeline import _duplicate_reason
from tools.growth_scorecard import IST, build


class GrowthMeasurementTests(unittest.TestCase):
    def test_rejects_a_nearly_identical_prep_topic_but_not_an_apply_topic(self):
        class History:
            def recent(self, count):
                return [{'id': 'old', 'product': 'prep_sarthi',
                         'topic': 'TCS project ownership in HR round',
                         'hook': 'How did you own that TCS project?'}]

        content = {'topic': 'TCS project ownership in HR round', 'hook': 'How did you own that TCS project?'}
        self.assertIn('topic resembles', _duplicate_reason(content, {'product': 'prep_sarthi'}, History()))
        self.assertIsNone(_duplicate_reason(content, {'product': 'apply_sarthi'}, History()))

    def test_missing_instagram_views_stay_unknown_and_can_be_retried(self):
        now = dt.datetime(2026, 9, 24, 12, 0, tzinfo=IST)
        post = {'date': '2026-09-22 10:00 IST', 'posted': {'instagram': {'id': 'ig1'}}}
        data = {'posts': {}}
        _record(data, 'instagram', 'ig1', {'likes': 3}, 50)
        self.assertTrue(_due_snapshot(post, 'instagram', data, now))
        _record(data, 'instagram', 'ig1', {'views': 40}, 50)
        self.assertFalse(_due_snapshot(post, 'instagram', data, now))

    def test_scorecard_uses_48h_views_and_never_treats_missing_as_zero(self):
        now = dt.datetime(2026, 9, 24, 12, 0, tzinfo=IST)
        history = {'posts': [{'id': 'p1', 'date': '2026-09-22 10:00 IST',
                              'product': 'prep_sarthi', 'hook': 'A real question',
                              'posted': {'youtube': {'id': 'yt1'}, 'instagram': {'id': 'ig1'}}}]}
        metrics = {'posts': {'youtube:yt1': {'snapshots': {'48h': {'views': 40}}},
                             'instagram:ig1': {'likes': 3}}}
        report = build(history, metrics, now)
        self.assertIn('| youtube | 1 | 1 | 40 | 0 | unknown |', report)
        self.assertIn('| instagram | 1 | 0 | unknown | 0 | unknown |', report)


if __name__ == '__main__':
    unittest.main()
