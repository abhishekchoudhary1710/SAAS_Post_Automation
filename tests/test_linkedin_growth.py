import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from agent import linkedin_growth as growth
from agent.config import load_json, save_json
from agent.publish import buffer


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.config = load_json(growth.CONFIG)

    def test_five_weeks_have_unique_product_topics_and_one_matching_link(self):
        state = {"posts": []}
        topics = []
        for offset in range(35):
            day = dt.date(2026, 9, 28) + dt.timedelta(days=offset)
            seed = growth.choose(day, state, self.config)
            if day.weekday() >= 5:
                self.assertIsNone(seed)
                continue
            if seed['series'] == 'jobs':
                continue
            post = growth.compose(day, seed, self.config)
            self.assertEqual(urlsplit(post['url']).path, '/' + ('live' if seed['series'] == 'live' else seed['series']) + '/')
            self.assertLessEqual(len(post['text']), 2900)
            self.assertEqual(post['text'].count('https://'), 1)
            self.assertIn(self.config['products'][seed['series']]['name'], post['text'])
            self.assertEqual(parse_qs(urlsplit(post['url']).query)['utm_content'], [post['id']])
            state['posts'].append(post)
            topics.append(post['topic'])
        self.assertEqual(len(topics), 20)
        self.assertEqual(len(set(topics)), 20)

    def test_exhausted_library_stops_instead_of_repeating(self):
        state = {'posts': [{'topic': p['id'], 'day': '2026-09-27'} for p in self.config['posts']]}
        with self.assertRaisesRegex(RuntimeError, 'No fresh'):
            growth.choose(dt.date(2026, 9, 28), state, self.config)

    def test_link_validation_rejects_outside_hosts_and_replaces_old_utm(self):
        for url in ['https://interviewsarthi.com.evil.test/prep/', 'http://interviewsarthi.com/prep/']:
            with self.assertRaises(ValueError):
                growth.tracked_link(url, 'x')
        url = growth.tracked_link('https://interviewsarthi.com/prep/?utm_source=old&filter=x#demo', 'li-20260929-prep-project')
        self.assertEqual(parse_qs(urlsplit(url).query)['utm_source'], ['linkedin'])
        self.assertIn('filter=x', url)
        self.assertEqual(urlsplit(url).fragment, 'demo')

    def test_job_copy_uses_feed_values_and_one_job_list_link(self):
        from agent.joblist import SAMPLE
        post = growth.compose(dt.date(2026, 9, 30), {'id': 'jobs', 'series': 'jobs'}, self.config, SAMPLE)
        self.assertIn('67 new Python jobs', post['text'])
        self.assertIn('AWS (38%)', post['text'])
        self.assertEqual(urlsplit(post['url']).path, '/skills/python/hyderabad')
        self.assertNotIn('/prep', post['text'])

    def test_jobs_feed_must_be_recent(self):
        from agent.joblist import SAMPLE
        now = growth.now_ist()
        for hours, valid in [(1, True), (25, False)]:
            response = SimpleNamespace(raise_for_status=lambda: None,
                json=lambda: {'built_at': (now - dt.timedelta(hours=hours)).isoformat(), 'lists': [SAMPLE]})
            with patch('requests.get', return_value=response):
                if valid:
                    self.assertEqual(growth.fresh_jobs({'posts': []}, now.date()), SAMPLE)
                else:
                    with self.assertRaisesRegex(RuntimeError, 'stale'):
                        growth.fresh_jobs({'posts': []}, now.date())

    def test_redirect_checks_keep_destination_and_tracking(self):
        url = growth.tracked_link('https://interviewsarthi.com/prep/', 'li-20260929-prep-project')
        response = SimpleNamespace(url=url, raise_for_status=lambda: None)
        with patch('requests.get', return_value=response):
            growth.check_link(url)
        for bad in ['https://interviewsarthi.com/prep/', url.replace('/prep/', '/live/')]:
            response.url = bad
            with patch('requests.get', return_value=response), self.assertRaises(RuntimeError):
                growth.check_link(url)

    def test_preview_writes_four_page_pdf_without_network_or_state_mutations(self):
        with tempfile.TemporaryDirectory() as d, patch('requests.post') as post, patch('requests.get') as get:
            rows = growth.preview(dt.date(2026, 9, 29), 1, Path(d))
            self.assertTrue(Path(rows[0]['document']).read_bytes().startswith(b'%PDF'))
            self.assertEqual(len(rows[0]['slides']), 4)
            self.assertTrue((Path(d) / 'index.html').exists())
        post.assert_not_called()
        get.assert_not_called()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(buffer_api_key='fake', buffer_key_expires=None, dry_run=False, cloudinary_url=None)

    def seed(self, folder):
        config = load_json(growth.CONFIG)
        seed = config['posts'][0]
        manifest = growth.compose(dt.date(2026, 9, 28), seed, config)
        manifest.update(image=str(folder / 'card.jpg'), owner_run='local')
        (folder / 'card.jpg').write_bytes(b'image')
        save_json(folder / 'post.json', manifest)
        state = {'posts': [{**manifest, 'status': 'reserved'}]}
        save_json(folder / 'state.json', state)
        return manifest

    def test_duplicate_day_is_skipped_before_network(self):
        with tempfile.TemporaryDirectory() as d, patch('requests.post') as http:
            folder = Path(d)
            self.seed(folder)
            result = growth.prepare(dt.date(2026, 9, 28), self.settings, state_path=folder / 'state.json')
        self.assertIsNone(result)
        http.assert_not_called()

    def test_accepted_post_is_recorded_and_cannot_be_resubmitted(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            manifest = self.seed(folder)
            with patch('agent.publish.media_host._github_branch', return_value={manifest['image']: 'https://cdn.test/card.jpg'}), \
                    patch('agent.publish.buffer.post', return_value='b1') as submit:
                growth.publish_prepared(self.settings, folder, folder / 'state.json')
                receipt = load_json(folder / 'state.json')['posts'][0]
                self.assertEqual((receipt['status'], receipt['buffer_id']), ('accepted', 'b1'))
                with self.assertRaises(RuntimeError):
                    growth.publish_prepared(self.settings, folder, folder / 'state.json')
            submit.assert_called_once()

    def test_timeout_is_unknown_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            manifest = self.seed(folder)
            with patch('agent.publish.media_host._github_branch', return_value={manifest['image']: 'https://cdn.test/card.jpg'}), \
                    patch('agent.publish.buffer.post', side_effect=TimeoutError) as submit:
                with self.assertRaises(TimeoutError):
                    growth.publish_prepared(self.settings, folder, folder / 'state.json')
                self.assertEqual(load_json(folder / 'state.json')['posts'][0]['status'], 'unknown')
                with self.assertRaises(RuntimeError):
                    growth.publish_prepared(self.settings, folder, folder / 'state.json')
            submit.assert_called_once()

    def test_different_run_cannot_use_reservation(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {'GITHUB_RUN_ID': 'other'}):
            folder = Path(d)
            self.seed(folder)
            with patch('agent.publish.buffer.post') as submit, self.assertRaises(RuntimeError):
                growth.publish_prepared(self.settings, folder, folder / 'state.json')
            submit.assert_not_called()

    def test_unavailable_metrics_remain_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'state.json'
            save_json(path, {'posts': [{'id': 'x', 'topic': 'prep-project', 'buffer_id': 'b1', 'day': growth.now_ist().date().isoformat(), 'status': 'accepted'}]})
            with patch('agent.publish.buffer.inspect_post', return_value={'status': 'sending', 'metrics': None, 'metricsUpdatedAt': None}):
                state = growth.refresh(self.settings, path)
            self.assertEqual(state['posts'][0]['metrics'], {})
            self.assertIn('unknown', growth.report(state))

    def test_document_uses_buffer_document_asset(self):
        with patch('agent.publish.buffer.channel_id', return_value='page'), \
                patch('agent.publish.buffer._gql', return_value={'createPost': {'post': {'id': 'b'}}}) as gql:
            buffer.post(self.settings, 'Example', 'https://cdn.test/c.jpg', document_url='https://cdn.test/d.pdf', title='Lesson')
        self.assertIn('document: {url:', gql.call_args.args[1])
        self.assertIn('thumbnailUrl:', gql.call_args.args[1])

    def test_pinned_profile_id_is_rejected(self):
        settings = SimpleNamespace(buffer_api_key='fake', buffer_channel_id='profile', buffer_channel='Interview Sarthi')
        with patch('agent.publish.buffer.channels', return_value=[{'id': 'profile', 'service': 'linkedin', 'type': 'profile'}]):
            with self.assertRaises(RuntimeError):
                buffer.channel_id(settings)


if __name__ == '__main__':
    unittest.main()
