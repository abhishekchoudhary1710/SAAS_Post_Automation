"""Deepgram Aura-2 voices English reels first (owner, 22 Oct 2026); everything else keeps Chirp.

Deepgram has no Hindi, so a Hindi or Hinglish reel must fall through to the next engine as a whole,
never a mix of two voices in one video. No network here: requests.post is patched.
"""
import os
import pathlib
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from agent.config import ROOT, brand
from agent.render import tts


def reply(status=200, body=b"\xff" * 4000, text=""):
    r = MagicMock()
    r.status_code, r.content, r.text = status, body, text
    return r


class DeepgramEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self.tmp.name) / "v.mp3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_deepgram_is_first_and_luna_is_the_voice(self):
        voices = brand()["voices"]
        self.assertEqual(voices["engine_order"][0], "deepgram")
        self.assertEqual(voices["deepgram_voice"], "aura-2-luna-en")
        self.assertIn("chirp", voices["engine_order"])

    def test_hindi_and_hinglish_are_refused_before_any_request(self):
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "k" * 40}), patch("requests.post") as post:
            for language in ("hindi", "hinglish"):
                with self.assertRaises(tts.TTSError):
                    tts._deepgram("नमस्ते", self.out, language)
            post.assert_not_called()

    def test_missing_key_is_a_clean_fallback(self):
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": ""}), self.assertRaises(tts.TTSError):
            tts._deepgram("Hello", self.out, "english")

    def test_english_request_uses_the_chosen_voice_and_writes_audio(self):
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "secret-key-value"}), \
                patch("requests.post", return_value=reply()) as post:
            tts._deepgram("Interview Sarthi tests your answers.", self.out, "english_global")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["params"]["model"], "aura-2-luna-en")
        self.assertEqual(kwargs["headers"]["Authorization"], "Token secret-key-value")
        self.assertEqual(kwargs["json"], {"text": "Interview Sarthi tests your answers."})
        self.assertGreater(self.out.stat().st_size, 1000)

    def test_an_error_never_carries_the_key(self):
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "secret-key-value"}), \
                patch("requests.post", return_value=reply(402, b"", '{"err_msg":"Insufficient credits"}')):
            with self.assertRaises(tts.TTSError) as ctx:
                tts._deepgram("Hello", self.out, "english")
        self.assertIn("402", str(ctx.exception))
        self.assertNotIn("secret-key-value", str(ctx.exception))


class OneVoicePerReelTests(unittest.TestCase):
    def test_a_hindi_reel_is_voiced_entirely_by_chirp(self):
        calls = []

        def chirp(text, out, language):
            calls.append(text)
            pathlib.Path(out).write_bytes(b"x" * 2000)
            return pathlib.Path(out)

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(tts.ENGINES, {"chirp": chirp}), patch.dict(os.environ, {"DEEPGRAM_API_KEY": "k"}):
            outs = [pathlib.Path(tmp) / f"{i}.mp3" for i in range(3)]
            paths, engine = tts.synthesize_batch(["एक", "दो", "तीन"], outs, "hindi")
        self.assertEqual(engine, "chirp")
        self.assertEqual(len(calls), 3)

    def test_deepgram_failing_mid_reel_revoices_every_line_with_the_next_engine(self):
        state = {"n": 0}

        def flaky(text, out, language):
            state["n"] += 1
            if state["n"] == 2:
                raise tts.TTSError("Deepgram HTTP 429")
            pathlib.Path(out).write_bytes(b"x" * 2000)
            return pathlib.Path(out)

        def chirp(text, out, language):
            pathlib.Path(out).write_bytes(b"c" * 2000)
            return pathlib.Path(out)

        with tempfile.TemporaryDirectory() as tmp, patch.dict(tts.ENGINES, {"deepgram": flaky, "chirp": chirp}):
            outs = [pathlib.Path(tmp) / f"{i}.mp3" for i in range(3)]
            paths, engine = tts.synthesize_batch(["a", "b", "c"], outs, "english")
            self.assertEqual(engine, "chirp")
            self.assertTrue(all(p.read_bytes().startswith(b"c") for p in paths))


class WorkflowTests(unittest.TestCase):
    def test_the_posting_workflow_passes_the_key(self):
        text = (ROOT / ".github/workflows/post.yml").read_text(encoding="utf-8")
        self.assertIn("DEEPGRAM_API_KEY: ${{ secrets.DEEPGRAM_API_KEY }}", text)


if __name__ == "__main__":
    unittest.main()
