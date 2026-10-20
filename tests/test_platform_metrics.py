"""Facebook reel plays and YouTube watch time reach performance.json without blocking a post."""
import datetime as dt
import unittest
from types import SimpleNamespace
from unittest import mock

from agent import feedback
from agent.publish.meta import MetaError
from tools.growth_scorecard import IST, build

NOW = dt.datetime(2026, 9, 25, 12, 0, tzinfo=IST)
REEL_INSIGHTS = {'data': [
    {'name': 'blue_reels_play_count', 'values': [{'value': 120}]},
    {'name': 'post_impressions_unique', 'values': [{'value': 90}]},
    {'name': 'post_video_avg_time_watched', 'values': [{'value': 4300}]},
    {'name': 'post_video_likes_by_reaction_type', 'values': [{'value': {'like': 2}}]},
]}


def settings(**kw):
    base = dict(has_meta=True, has_instagram=False, has_youtube=False, platforms=['facebook'],
                meta_page_id='page', meta_page_token='t', ig_user_id=None, graph_version='v23.0')
    return SimpleNamespace(**{**base, **kw})


def post(fb_id, hours_old=50, yt_id=None):
    posted = {'facebook': {'id': fb_id}}
    if yt_id:
        posted['youtube'] = {'id': yt_id}
    return {'date': (NOW - dt.timedelta(hours=hours_old)).strftime('%Y-%m-%d %H:%M IST'), 'posted': posted}


def run(settings_obj, posts, meta):
    saved = {}
    with mock.patch.object(feedback, 'History', return_value=SimpleNamespace(recent=lambda n: posts)), \
         mock.patch.object(feedback, 'load_json', side_effect=FileNotFoundError), \
         mock.patch.object(feedback, 'save_json', side_effect=lambda path, data: saved.update(data)), \
         mock.patch.object(feedback, 'now_ist', return_value=NOW), \
         mock.patch('agent.publish.meta.Meta', return_value=meta):
        feedback.refresh(settings_obj)
    return saved


class PlatformMetricsTests(unittest.TestCase):
    def test_facebook_reel_values_read_plays_reach_and_watch_time(self):
        meta = mock.Mock(get=mock.Mock(return_value=REEL_INSIGHTS))
        self.assertEqual(feedback._facebook_values(meta, 'v1'),
                         {'views': 120, 'reach': 90, 'avg_watch_seconds': 4.3})
        meta.get.assert_called_once_with('v1/video_insights')

    def test_facebook_reel_gets_a_48h_snapshot_and_carousels_are_skipped(self):
        meta = mock.Mock(get=mock.Mock(return_value=REEL_INSIGHTS))
        data = run(settings(), [post('v1'), post('page_123')], meta)
        self.assertEqual(data['posts']['facebook:v1']['snapshots']['48h']['views'], 120)
        self.assertNotIn('facebook:page_123', data['posts'])
        self.assertEqual(data['unavailable'], {})

    def test_a_permission_refusal_stops_facebook_reads_and_is_reported(self):
        meta = mock.Mock(get=mock.Mock(side_effect=MetaError('OAuthException 200/None: read_insights missing')))
        data = run(settings(), [post('v1'), post('v2')], meta)
        self.assertEqual(meta.get.call_count, 1)
        self.assertEqual(data['unavailable'], {'facebook_insights': 'MetaError'})
        self.assertNotIn('facebook:v1', data['posts'])

    def test_a_single_bad_video_does_not_stop_the_others(self):
        meta = mock.Mock(get=mock.Mock(side_effect=[MetaError('GraphMethodException 100/33: no such object'),
                                                    REEL_INSIGHTS]))
        data = run(settings(), [post('v1'), post('v2')], meta)
        self.assertIn('facebook:v2', data['posts'])
        self.assertEqual(data['unavailable'], {})

    def test_youtube_watch_time_joins_the_view_counts(self):
        stats = {'items': [{'id': 'yt1', 'statistics': {'viewCount': '40', 'likeCount': '1', 'commentCount': '0'}}]}
        service = mock.Mock()
        service.videos.return_value.list.return_value.execute.return_value = stats
        watch = {'yt1': {'avg_watch_seconds': 7, 'avg_watch_percent': 41.2, 'minutes_watched': 4.7}}
        with mock.patch('agent.publish.youtube._service', return_value=service), \
             mock.patch.object(feedback, '_youtube_watch', return_value=watch):
            data = run(settings(has_meta=False, has_youtube=True, platforms=['youtube']),
                       [post('v1', yt_id='yt1')], None)
        self.assertEqual(data['posts']['youtube:yt1']['snapshots']['48h'],
                         {'checked_at': data['checked_at'], 'views': 40, 'likes': 1, 'comments': 0,
                          'avg_watch_seconds': 7, 'avg_watch_percent': 41.2, 'minutes_watched': 4.7})

    def test_youtube_analytics_refusal_keeps_the_view_counts(self):
        stats = {'items': [{'id': 'yt1', 'statistics': {'viewCount': '40'}}]}
        service = mock.Mock()
        service.videos.return_value.list.return_value.execute.return_value = stats
        with mock.patch('agent.publish.youtube._service', return_value=service), \
             mock.patch.object(feedback, '_youtube_watch', side_effect=RuntimeError('403')):
            data = run(settings(has_meta=False, has_youtube=True, platforms=['youtube']),
                       [post('v1', yt_id='yt1')], None)
        self.assertEqual(data['posts']['youtube:yt1']['views'], 40)
        self.assertEqual(data['unavailable'], {'youtube_analytics': 'RuntimeError'})

    def test_scorecard_shows_watch_time_and_keeps_missing_unknown(self):
        history = {'posts': [post('v1', yt_id='yt1')]}
        metrics = {'posts': {'youtube:yt1': {'avg_watch_seconds': 7, 'avg_watch_percent': 41.2},
                             'facebook:v1': {'views': 120, 'avg_watch_seconds': 4.3}}}
        report = build(history, metrics, NOW)
        self.assertIn('| youtube | 1 | 7 | 41.2 |', report)
        self.assertIn('| facebook | 1 | 4.3 | unknown |', report)
        self.assertIn('| instagram | 0 | unknown | unknown |', report)


if __name__ == '__main__':
    unittest.main()
