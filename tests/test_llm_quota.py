"""The writing backend: where the calls go, and what an exhausted allowance costs.

Both behaviours were bought the hard way on 24 Sep 2026. Every reel and carousel slot had
failed since 21 Sep because the writing ran on the AI Studio free tier (limit 20 a day)
while the Google Cloud credit that pays for Veo and Chirp sat unspent, and because a single
quota refusal was retried 36 times, spending the allowance the next slot needed.
"""
import unittest
from unittest import mock

from agent import llm


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


QUOTA_BODY = {"error": {"message": (
    "You exceeded your current quota, please check your plan and billing details. "
    "Quota exceeded for metric: generativelanguage.googleapis.com/"
    "generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash")}}

OK_BODY = {"candidates": [{"content": {"parts": [{"text": '{"topic": "a topic"}'}]},
                           "finishReason": "STOP"}]}


def studio(models=("m1", "m2", "m3"), **kw):
    with mock.patch.dict("os.environ", {"GEMINI_BACKEND": "studio"}, clear=False):
        return llm.Gemini("key", list(models), **kw)


class QuotaTests(unittest.TestCase):
    def test_exhausted_allowance_is_tried_once_per_model_and_never_waited_on(self):
        calls = []

        def post(url, **kw):
            calls.append(url)
            return FakeResponse(429, QUOTA_BODY)

        client = studio()
        with mock.patch.object(llm.requests, "post", post), \
                mock.patch.object(llm.time, "sleep") as slept:
            with self.assertRaises(llm.QuotaError):
                client.json("sys", "user")
        # One request per model, and not one second spent waiting for an allowance that
        # only refills tomorrow. The old code made twelve here, and plan_post made 36.
        self.assertEqual(len(calls), 3)
        slept.assert_not_called()

    def test_a_busy_model_is_still_retried_with_waits(self):
        """503 is a momentary outage, not an allowance. That retry must survive."""
        calls = []

        def post(url, **kw):
            calls.append(url)
            return FakeResponse(503, {"error": {"message": "overloaded"}})

        client = studio(models=("m1",), retry_waits=(1, 1))
        with mock.patch.object(llm.requests, "post", post), \
                mock.patch.object(llm.time, "sleep") as slept:
            with self.assertRaises(llm.LLMError) as caught:
                client.text("sys", "user")
        self.assertNotIsInstance(caught.exception, llm.QuotaError)
        self.assertEqual(len(calls), 3)
        self.assertEqual(slept.call_count, 2)

    def test_one_model_out_of_allowance_still_lets_the_next_one_answer(self):
        replies = [FakeResponse(429, QUOTA_BODY), FakeResponse(200, OK_BODY)]

        def post(url, **kw):
            return replies.pop(0)

        client = studio(models=("m1", "m2"))
        with mock.patch.object(llm.requests, "post", post), \
                mock.patch.object(llm.time, "sleep"):
            self.assertEqual(client.json("sys", "user"), {"topic": "a topic"})


class BackendTests(unittest.TestCase):
    def test_without_cloud_credentials_it_uses_the_api_key(self):
        with mock.patch.object(llm, "_vertex_credentials", return_value=(None, "")):
            client = llm.Gemini("key", ["gemini-3.6-flash"])
        self.assertEqual(client.backend, "studio")
        self.assertIn("generativelanguage.googleapis.com", client._endpoint("gemini-3.6-flash"))
        self.assertEqual(client._headers()["x-goog-api-key"], "key")

    def test_with_cloud_credentials_it_bills_the_project_that_holds_the_credit(self):
        creds = mock.Mock(valid=True, token="tok")
        with mock.patch.object(llm, "_vertex_credentials", return_value=(creds, "uniyal-video")), \
                mock.patch.dict("os.environ", {"GOOGLE_CLOUD_LOCATION": "global"}, clear=False):
            client = llm.Gemini("", ["gemini-3.6-flash"])
        self.assertEqual(client.backend, "vertex")
        url = client._endpoint("gemini-3.6-flash")
        self.assertIn("aiplatform.googleapis.com", url)
        self.assertIn("projects/uniyal-video/locations/global", url)
        self.assertEqual(client._headers()["Authorization"], "Bearer tok")
        # No API key needed at all once the project pays.
        self.assertNotIn("x-goog-api-key", client._headers())

    def test_a_region_uses_its_own_host(self):
        creds = mock.Mock(valid=True, token="tok")
        with mock.patch.object(llm, "_vertex_credentials", return_value=(creds, "uniyal-video")), \
                mock.patch.dict("os.environ", {"GOOGLE_CLOUD_LOCATION": "asia-south1"}, clear=False):
            client = llm.Gemini("", ["gemini-3.6-flash"])
        self.assertIn("asia-south1-aiplatform.googleapis.com", client._endpoint("gemini-3.6-flash"))

    def test_an_expired_token_is_refreshed_before_the_call(self):
        creds = mock.Mock(valid=False, token="stale")

        def refresh(c):
            c.valid, c.token = True, "fresh"
        with mock.patch.object(llm, "_vertex_credentials", return_value=(creds, "uniyal-video")):
            client = llm.Gemini("", ["gemini-3.6-flash"])
        with mock.patch.object(llm, "_refresh", refresh):
            self.assertEqual(client._headers()["Authorization"], "Bearer fresh")


if __name__ == "__main__":
    unittest.main()
