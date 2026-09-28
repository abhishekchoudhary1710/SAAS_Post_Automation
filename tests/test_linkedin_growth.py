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

    def test_four_weeks_have_56_posts_and_48_unique_product_topics(self):
        from agent.joblist import SAMPLE
        state = {"posts": []}
        topics = []
        for offset in range(28):
            day = dt.date(2026, 9, 28) + dt.timedelta(days=offset)
            for slot in self.config['slots']:
                seed = growth.choose(day, state, self.config, slot)
                post = growth.compose(day, seed, self.config, SAMPLE if seed['series'] == 'jobs' else None, slot)
                self.assertEqual(post['slot'], slot)
                self.assertLessEqual(len(post['text']), 2900)
                self.assertEqual(post['text'].count('https://'), 1)
                self.assertEqual(parse_qs(urlsplit(post['url']).query)['utm_content'], [post['id']])
                state['posts'].append(post)
                if seed['series'] != 'jobs':
                    self.assertEqual(urlsplit(post['url']).path, '/' + seed['series'] + '/')
                    self.assertIn(self.config['products'][seed['series']]['name'], post['text'])
                    topics.append(post['topic'])
        self.assertEqual(len(state['posts']), 56)
        self.assertEqual(len({p['id'] for p in state['posts']}), 56)
        self.assertEqual(len(topics), 48)
        self.assertEqual(len(set(topics)), 48)

    def test_rotation_can_continue_for_twelve_weeks_without_early_repeats(self):
        state, previous = {'posts': []}, {}
        for offset in range(84):
            day = dt.date(2026, 9, 28) + dt.timedelta(days=offset)
            for slot in self.config['slots']:
                seed = growth.choose(day, state, self.config, slot)
                if seed['series'] == 'jobs':
                    continue
                if seed['id'] in previous:
                    self.assertGreaterEqual((day - previous[seed['id']]).days, 28)
                previous[seed['id']] = day
                state['posts'].append(growth.compose(day, seed, self.config, slot=slot))

    def test_workflow_covers_exactly_two_correctly_timed_slots_every_day(self):
        import re
        workflow = Path('.github/workflows/linkedin-growth.yml').read_text()
        actual = re.findall(r'- cron: "([^"]+)"', workflow)
        expected = []
        for slot, settings in self.config['slots'].items():
            self.assertEqual(len(settings['times_ist']), 7)
            self.assertEqual(len(settings['weekday_series']), 7)
            for weekday, time in enumerate(settings['times_ist']):
                cron = growth.schedule_cron(weekday, time)
                expected.append(cron)
                self.assertEqual(growth.scheduled_slot(cron, self.config), slot)
        self.assertEqual(len(set(expected)), 14)
        self.assertCountEqual(actual, expected + ['17 18 * * *'])
        self.assertEqual(growth.schedule_cron(5, '09:17'), '47 3 * * 6')
        self.assertEqual(growth.schedule_cron(6, '22:17'), '47 16 * * 0')
        with self.assertRaises(ValueError):
            growth.scheduled_slot('17 18 * * *', self.config)

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
            self.assertEqual(len(rows), 2)
            self.assertTrue(Path(rows[0]['document']).read_bytes().startswith(b'%PDF'))
            self.assertEqual(len(rows[0]['slides']), 4)
            self.assertTrue((Path(d) / 'index.html').exists())
        post.assert_not_called()
        get.assert_not_called()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        run_env = patch.dict('os.environ', {'GITHUB_RUN_ID': 'local'})
        run_env.start()
        self.addCleanup(run_env.stop)
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

    def test_duplicate_day_and_slot_is_skipped_before_network(self):
        with tempfile.TemporaryDirectory() as d, patch('requests.post') as http:
            folder = Path(d)
            self.seed(folder)
            result = growth.prepare(dt.date(2026, 9, 28), self.settings, state_path=folder / 'state.json')
        self.assertIsNone(result)
        http.assert_not_called()

    def test_second_slot_is_allowed_on_same_day_but_cannot_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            first = self.seed(folder)
            with patch.object(growth, 'render'), patch.object(growth, 'check_link'), \
                    patch('agent.publish.buffer.channel_id', return_value='page'):
                second = growth.prepare(dt.date(2026, 9, 28), self.settings,
                                        state_path=folder / 'state.json', folder=folder, slot='evening')
                self.assertIsNotNone(second)
                self.assertNotEqual(first['id'], second['id'])
                self.assertIsNone(growth.prepare(dt.date(2026, 9, 28), self.settings,
                                                state_path=folder / 'state.json', slot='evening'))
            self.assertEqual(len(load_json(folder / 'state.json')['posts']), 2)

    def test_legacy_reservation_blocks_only_first_slot(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'state.json'
            save_json(path, {'posts': [{'day': '2026-09-28', 'topic': 'apply-fit'}]})
            with patch('requests.post') as http:
                self.assertIsNone(growth.prepare(dt.date(2026, 9, 28), self.settings, state_path=path))
            http.assert_not_called()

    def test_metrics_snapshots_and_retries_respect_request_budget(self):
        now = growth.now_ist()
        entry = {'buffer_id': 'b', 'status': 'sent', 'day': now.date().isoformat()}
        self.assertFalse(growth.metrics_due(entry, now))
        for age, key in [(1, 'one_day_metrics'), (7, 'seven_day_metrics'), (28, 'month_metrics')]:
            entry['day'] = (now.date() - dt.timedelta(days=age)).isoformat()
            self.assertTrue(growth.metrics_due(entry, now))
            entry[key] = {'impressions': 1}
            self.assertFalse(growth.metrics_due(entry, now))
        entry.update(status='sending', last_check_attempt_at=(now - dt.timedelta(minutes=59)).isoformat())
        self.assertFalse(growth.metrics_due(entry, now))
        entry['last_check_attempt_at'] = (now - dt.timedelta(hours=2)).isoformat()
        self.assertTrue(growth.metrics_due(entry, now))

    def test_refresh_caps_requests_even_when_buffer_fails(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'state.json'
            save_json(path, {'posts': [{'buffer_id': str(n), 'day': growth.now_ist().date().isoformat(),
                                      'status': 'accepted'} for n in range(25)]})
            with patch('agent.publish.buffer.inspect_post', side_effect=TimeoutError) as inspect:
                state = growth.refresh(self.settings, path)
            self.assertEqual(inspect.call_count, 20)
            self.assertEqual(sum('last_check_attempt_at' in p for p in state['posts']), 20)
            self.assertEqual(sum('metrics_error' in p for p in state['posts']), 20)

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
