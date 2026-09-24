"""Protect the 48-hour comparisons and repeat-content gate."""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from agent.copywriter import validate
from agent.feedback import _due_snapshot, _record
from agent.pipeline import _duplicate_reason, render_media
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

    def test_extra_reel_starts_on_the_readable_hook_without_paid_or_library_intro(self):
        content = {'slides': [{'type': 'hook', 'title': 'A concrete question',
                               'narration': 'Here is the interview question.'}], 'language': 'english'}
        with tempfile.TemporaryDirectory() as folder, \
             mock.patch.dict(os.environ, {'REEL_START_ON_HOOK': 'true', 'VEO_OPENING_ENABLED': 'false'}), \
             mock.patch('agent.pipeline.render_stages', return_value=[Image.new('RGB', (16, 16))]), \
             mock.patch('agent.pipeline.build_reel', return_value={'seconds': 5, 'voiced': True, 'music': None}) as reel, \
             mock.patch('agent.pipeline._library_intro') as library:
            media = render_media(content, 'reel', Path(folder), history=object(), plan={})
        self.assertIsNone(reel.call_args.kwargs['intro'])
        library.assert_not_called()
        self.assertEqual(media['opening'], 'hook-card')
        self.assertEqual(media['veo_seconds'], 0)

    def test_apply_sample_cv_needs_visible_disclosure_and_no_invented_percentage(self):
        content = {'product': 'apply_sarthi', 'caption': 'A CV tailored to the job.',
                   'slides': [{'type': 'hook', 'title': 'ApplySarthi matches jobs'},
                              {'type': 'qa', 'question': 'What did you do?',
                               'answer': 'I improved speed by forty percent.', 'tag': 'CV example'},
                              {'type': 'product', 'title': 'Review then submit', 'image': 'apply_jobs'}]}
        _, problems = validate(content, 'reel')
        self.assertTrue(any('disclose a fictional CV' in p for p in problems))
        self.assertTrue(any('visibly labeled Fictional CV' in p for p in problems))
        self.assertTrue(any('percentage achievement' in p for p in problems))


if __name__ == '__main__':
    unittest.main()
