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
    def test_fresh_scenario_rejects_recent_question(self):
        from agent.creative import validate_scenario
        h=Mock()
        h.recent.return_value=[{'topic':scenarios()[0]['question']}]
        self.assertIn('question too similar to a recent ad',validate_scenario(scenarios()[0],h))

    def test_visual_rotation_avoids_previous_two_clips(self):
        from agent.creative import select_visual
        with tempfile.TemporaryDirectory() as folder:
            h=History(Path(folder)/'history.json')
            seen=[]
            for i in range(6):
                v=select_visual(h)
                self.assertNotIn(v['clip_id'],seen[-2:])
                seen.append(v['clip_id'])
                if h.posts:
                    self.assertNotEqual(v['theme'],h.posts[-1]['visual_theme'])
                h.add({'id':str(i),'visual_clip':v['clip_id'],'visual_theme':v['theme']})

    def test_reviewer_failure_uses_evidence_fallback(self):
        from agent.creative import fresh_scenario
        h=Mock()
        h.recent.return_value=[]
        llm=Mock()
        llm.json.side_effect=RuntimeError('provider unavailable')
        seed=scenarios()[0]
        result,receipt=fresh_scenario(llm,seed,h)
        self.assertEqual(result,seed)
        self.assertEqual(receipt['source'],'authored')

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

    def test_all_feed_ads_fit_and_image_gate_detects_changes(self):
        from agent.render.poster import build_poster
        with tempfile.TemporaryDirectory() as folder:
            for s in scenarios():
                for index in range(len(s['hooks'])):
                    media = build_poster(s, authored_script(s, 'short', index), Path(folder) / 'poster.jpg')
                    path = Path(media['images'][0])
                    m = {'format': 'image', 'media': media,
                         'quality': {'kind': 'image', 'passed': True, 'sha256': file_hash(path)}}
                    require_publishable(m)
                    path.write_bytes(b'changed')
                    with self.assertRaises(RuntimeError):
                        require_publishable(m)

    def test_image_create_uses_reviewed_advertisement_pipeline(self):
        from agent.pipeline import create
        with tempfile.TemporaryDirectory() as folder:
            m = create(Settings.from_env(), fmt='image', sample=True, out_dir=folder)
            self.assertEqual(m['format'], 'image')
            self.assertTrue(m['quality']['passed'])
            self.assertIsNone(m['captions']['youtube'])
            self.assertIn('resume', m['captions']['instagram'])
            require_publishable(m)

    def test_promo_variant_fits_and_has_valid_fallback(self):
        from agent.campaign import PROMO_HOOKS
        from agent.render.motion import MotionScene
        for scenario in scenarios():
            for hook in range(len(PROMO_HOOKS)):
                with self.subTest(scenario=scenario['id'], hook=hook):
                    script = authored_script(scenario, 'promo', hook)
                    self.assertEqual(script_problems(script, 'promo'), [])
                    self.assertNotIn(scenario['question'], ' '.join(script['narrations']))
                    # Every headline has to fit the hook layout, not just the first one.
                    self.assertEqual(MotionScene(scenario, script, 'hook', 'promo').frame(2.6, 8).size, (1080, 1920))
            script = authored_script(scenario, 'promo', 0)
            for kind in ('features', 'product', 'cta'):
                with self.subTest(scenario=scenario['id'], kind=kind):
                    self.assertEqual(MotionScene(scenario, script, kind, 'promo').frame(2.6, 8).size, (1080, 1920))

    def test_promo_scenes_move_and_hook_drops_the_interviewer_panel(self):
        from agent.render.motion import MotionScene
        from PIL import ImageChops
        scenario = scenarios()[0]
        script = authored_script(scenario, 'promo', 0)
        for kind in ('hook', 'features', 'product', 'cta'):
            scene = MotionScene(scenario, script, kind, 'promo')
            a = scene.frame(.2, 8).crop((50, 240, 960, 1530))
            b = scene.frame(2.8, 8).crop((50, 240, 960, 1530))
            self.assertIsNotNone(ImageChops.difference(a, b).getbbox(), kind)
        sales_hook = MotionScene(scenario, authored_script(scenario, 'short', 0), 'hook', 'short')
        promo_hook = MotionScene(scenario, script, 'hook', 'promo')
        self.assertIsNotNone(ImageChops.difference(sales_hook.frame(2.6, 8), promo_hook.frame(2.6, 8)).getbbox())

    def test_promo_durations_keep_narration_and_budget(self):
        durations = scene_durations([4, 7, 5, 6], scenarios()[0], 'promo')
        self.assertEqual(len(durations), 4)
        self.assertTrue(all(a >= b + .35 for a, b in zip(durations, [4, 7, 5, 6])))
        with self.assertRaises(ValueError):
            scene_durations([8, 12, 10, 10], scenarios()[0], 'promo')


if __name__ == '__main__':
    unittest.main()
