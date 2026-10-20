import unittest

from tools.merge_run_records import merge_history, merge_performance


class MergeRunRecordsTests(unittest.TestCase):
    def test_concurrent_posts_and_partial_platform_retries_are_preserved(self):
        remote = {'posts': [{'id': 'a', 'date': '2026-09-24 11:37 IST',
                             'posted': {'facebook': {'id': 'fb1'}}, 'errors': {'youtube': 'quota'}},
                            {'id': 'b', 'date': '2026-09-24 12:37 IST',
                             'posted': {'instagram': {'id': 'ig2'}}}]}
        local = {'posts': [{'id': 'a', 'date': '2026-09-24 12:00 IST',
                            'posted': {'youtube': {'id': 'yt1'}}, 'errors': {}},
                           {'id': 'c', 'date': '2026-09-24 14:37 IST',
                            'posted': {'instagram': {'id': 'ig3'}}}]}
        posts = merge_history(remote, local)['posts']
        self.assertEqual([p['id'] for p in posts], ['a', 'b', 'c'])
        self.assertEqual(set(posts[0]['posted']), {'facebook', 'youtube'})
        self.assertEqual(posts[0]['errors'], {})
        self.assertEqual(posts[0]['date'], '2026-09-24 11:37 IST')

    def test_newer_metrics_keep_the_first_age_matched_snapshot(self):
        remote = {'checked_at': '2026-09-24T12:00:00+05:30',
                  'posts': {'youtube:1': {'checked_at': '2026-09-24T12:00:00+05:30', 'views': 40,
                                          'snapshots': {'48h': {'views': 40}}}}}
        local = {'checked_at': '2026-09-24T13:00:00+05:30',
                 'posts': {'youtube:1': {'checked_at': '2026-09-24T13:00:00+05:30', 'views': 43},
                           'youtube:2': {'views': 5}}}
        posts = merge_performance(remote, local)['posts']
        self.assertEqual(posts['youtube:1']['views'], 43)
        self.assertEqual(posts['youtube:1']['snapshots']['48h']['views'], 40)
        self.assertEqual(posts['youtube:2']['views'], 5)


if __name__ == '__main__':
    unittest.main()
