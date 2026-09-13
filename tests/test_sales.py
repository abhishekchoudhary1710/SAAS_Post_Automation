import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.campaign import authored_script, choose_scenario, scenarios, script_problems, write_script
from agent.history import History
from agent.quality import file_hash, require_publishable
from agent.render.sales import SalesScene, scene_durations
from agent.pipeline import compose_captions, publish
from agent.config import Settings, save_json


class SalesTests(unittest.TestCase):
    def test_screen_sharing_feature_is_required_and_qualified(self):
        script = authored_script(scenarios()[0], 'short', 0)
        self.assertIn('supported screen sharing', script['narrations'][-2])
        script['narrations'][-2] = 'Its overlay is always invisible to everyone during your Windows interview.'
        self.assertTrue(script_problems(script, 'short'))

    def test_scene_budgets_land_on_sixty_fps_boundaries(self):
        from agent.render.sales import FPS
        self.assertEqual(FPS, 60)
        durations = scene_durations([4.017, 7.021, 5.001, 6.033], scenarios()[0], 'short')
        for duration in durations:
            self.assertAlmostEqual(duration*FPS, round(duration*FPS))

    def test_motion_layout_fits_all_scenarios(self):
        from agent.render.motion import MotionScene
        for scenario in scenarios():
            for kind in ('hook', 'answer', 'evidence', 'product', 'cta'):
                with self.subTest(scenario=scenario['id'], kind=kind):
                    scene = MotionScene(scenario, authored_script(scenario, 'standard', 0), kind)
                    self.assertEqual(scene.frame(2.6, 8).size, (1080, 1920))

    def test_motion_changes_content_area_beyond_progress_line(self):
        from agent.render.motion import MotionScene
        from PIL import ImageChops
        scenario = scenarios()[0]
        for kind in ('hook', 'answer', 'evidence', 'product', 'cta'):
            scene = MotionScene(scenario, authored_script(scenario, 'standard', 0), kind)
            a = scene.frame(.2, 8).crop((50, 240, 960, 1530))
            b = scene.frame(2.8, 8).crop((50, 240, 960, 1530))
            self.assertIsNotNone(ImageChops.difference(a, b).getbbox(), kind)

    def test_scene_transition_starts_with_previous_scene(self):
        from agent.render.motion import MotionScene
        from PIL import ImageChops
        scenario = scenarios()[0]
        script = authored_script(scenario, 'standard', 0)
        previous = MotionScene(scenario, script, 'answer')
        current = MotionScene(scenario, script, 'product')
        current.previous = (previous, 8)
        self.assertIsNone(ImageChops.difference(current.frame(0, 7), previous.raw_frame(7.99, 8)).getbbox())

    def test_every_supported_scenario_fits_and_has_valid_fallback(self):
        for scenario in scenarios():
            for variant in ('short', 'standard'):
                for hook in range(len(scenario['hooks'])):
                    with self.subTest(scenario=scenario['id'], variant=variant, hook=hook):
                        script = authored_script(scenario, variant, hook)
                        self.assertEqual(script_problems(script, variant), [])
                        for kind in ('hook', 'answer', 'evidence', 'product', 'cta'):
                            frame = SalesScene(scenario, script, kind).frame(2.8, 8)
                            self.assertEqual(frame.size, (1080, 1920))

    def test_review_outage_cannot_accept_model_draft(self):
        s = scenarios()[0]
        draft = authored_script(s, 'standard', 1)
        llm = Mock(last_model='test-model')
        llm.json.side_effect = [draft, RuntimeError('review unavailable')]
        result, receipt = write_script(llm, s, 'standard', 0)
        self.assertEqual(result, authored_script(s, 'standard', 0))
        self.assertEqual(receipt['source'], 'authored')

    def test_approved_script_is_used(self):
        s = scenarios()[0]
        draft = authored_script(s, 'short', 1)
        llm = Mock(last_model='test-model')
        llm.json.side_effect = [draft, {'approved': True, 'clarity': 5, 'hook': 4, 'evidence': 5, 'issues': []}]
        result, receipt = write_script(llm, s, 'short', 0)
        self.assertEqual(result, draft)
        self.assertEqual(receipt['source'], 'model')

    def test_bad_claims_rejected(self):
        script = authored_script(scenarios()[0], 'short', 0)
        script['caption'] += ' Guaranteed selection.'
        self.assertTrue(script_problems(script, 'short'))

    def test_narration_never_truncated(self):
        durations = scene_durations([4, 7, 5, 6], scenarios()[0], 'short')
        self.assertTrue(all(a >= b + .35 for a, b in zip(durations, [4, 7, 5, 6])))
        with self.assertRaises(ValueError):
            scene_durations([5, 15, 10, 15], scenarios()[0], 'short')

    def test_rotation_and_history_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            h = History(Path(folder) / 'history.json')
            for i in range(8):
                scenario, hook = choose_scenario(h)
                self.assertNotIn(scenario['id'], [x['scenario'] for x in h.posts])
                h.add({'id': str(i), 'scenario': scenario['id'], 'posted': {'youtube': {'id': 'yt'}}})
            h.add({'id': '0', 'posted': {'instagram': {'id': 'ig'}}})
            self.assertEqual(len(h.posts), 8)
            self.assertEqual(set(h.posts[0]['posted']), {'youtube', 'instagram'})

    def test_gate_rejects_modified_video(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'video.mp4'
            video.write_bytes(b'checked file')
            m = {'format': 'sales', 'media': {'video': str(video)},
                 'quality': {'passed': True, 'sha256': file_hash(video)}}
            require_publishable(m)
            video.write_bytes(b'changed file')
            with self.assertRaises(RuntimeError):
                require_publishable(m)

    def test_completed_platform_not_published_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'video.mp4'
            video.write_bytes(b'checked file')
            m = {'id': 'test', 'format': 'sales', 'media': {'video': str(video)}, 'captions': {},
                 'quality': {'passed': True, 'sha256': file_hash(video)}}
            save_json(Path(folder) / 'published.json', {'id': 'test', 'results': {'youtube': {'id': 'already-posted'}}})
            settings = Settings.from_env()
            settings.dry_run = False
            with patch('agent.publish.youtube.upload_short') as upload:
                outcome = publish(m, settings, ['youtube'])
                upload.assert_not_called()
            self.assertEqual(outcome['results']['youtube']['id'], 'already-posted')

    def test_facebook_campaign_url_encoded(self):
        captions = compose_captions({'caption': 'An example', 'hook': 'A specific hook'}, 'sales', {'campaign_id': 'a b&c'})
        self.assertIn('utm_content=a+b%26c', captions['facebook'])
        self.assertNotIn('utm_content=', captions['instagram'])


if __name__ == '__main__':
    unittest.main()
