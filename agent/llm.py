"""Gemini text generation over the plain REST API.

Same pattern the product uses: try each model in order, step to the next one on a
retired (404) or busy (429/503) model, and return the first non-empty answer.

**Two backends, and which one runs decides whether writing works at all.** Vertex AI
bills the Google Cloud project, which is where the $300 trial credit lives and where Veo
and Chirp already run. AI Studio takes a bare API key and is metered on its own free tier:
on 24 Sep 2026 that tier was `generate_content_free_tier_requests, limit: 20` for
gemini-3.6-flash, which is not enough to write eight posts a day. Every reel and carousel
slot had been failing since 21 Sep because of it, while the credit sat unspent. So Vertex
is preferred whenever Cloud credentials and a project are present, and the API key is the
fallback for a laptop with no `gcloud`. Force either with GEMINI_BACKEND=vertex|studio.

A quota refusal is not a busy model: waiting will not refill a daily allowance. It raises
QuotaError, which skips the per-model waits and tells the callers above to stop retrying
rather than spend the rest of the allowance discovering the same thing 36 times.

JSON calls go one step further: a reply that cannot be parsed is treated like a busy model,
and the next model gets the same prompt. A thinking model can spend its whole token budget
before closing the object, and on 11 Sep 2026 one such reply killed a production dry run.
"""

from __future__ import annotations

import json
import os
import re
import time

import requests

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Vertex serves the "global" location off the bare host and every other one off a
# regional host, which is the same split veo.py works with.
VERTEX_GLOBAL = ("https://aiplatform.googleapis.com/v1/projects/{project}/locations/global"
                 "/publishers/google/models/{model}:generateContent")
VERTEX_REGION = ("https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
                 "/locations/{location}/publishers/google/models/{model}:generateContent")
RETRY_WAITS = (15, 35, 60)


class LLMError(RuntimeError):
    pass


class QuotaError(LLMError):
    """The allowance is spent. Another attempt in this run cannot succeed."""


def _is_quota(status: int, detail: str) -> bool:
    """A 429 that is an exhausted allowance rather than a momentary rate limit."""
    if status != 429:
        return False
    text = (detail or "").lower()
    return ("quota exceeded" in text or "exceeded your current quota" in text
            or "free_tier" in text or "billing" in text)


def _refresh(creds) -> None:
    """Mint a fresh access token. Its own function so it can be stubbed without the SDK."""
    from google.auth.transport.requests import Request
    creds.refresh(Request())


def _vertex_credentials():
    """Application Default Credentials for Vertex, or None when this machine has none."""
    try:
        import google.auth
    except ImportError:
        return None, ""
    try:
        creds, detected = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        _refresh(creds)
    except Exception:  # noqa: BLE001 - a laptop without gcloud is not an error here
        return None, ""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip() or (detected or "")
    return (creds, project) if project else (None, "")


def _extract_json(text: str):
    """Parse a JSON object or array out of a model reply, tolerating code fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError("model reply was not valid JSON:\n" + text[:800])


class Gemini:
    def __init__(self, api_key: str, models: list[str], timeout: float = 120.0,
                 retry_waits: tuple = RETRY_WAITS, budget_seconds: float | None = None):
        want = os.environ.get("GEMINI_BACKEND", "auto").strip().lower()
        self.creds, self.project = (None, "")
        if want in ("auto", "vertex"):
            self.creds, self.project = _vertex_credentials()
        if want == "vertex" and not self.creds:
            raise LLMError("GEMINI_BACKEND=vertex but this machine has no Google Cloud credentials")
        self.backend = "vertex" if self.creds else "studio"
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"
        if self.backend == "studio" and not api_key:
            raise LLMError("no Google Cloud credentials and GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.models = list(models)
        self.timeout = timeout
        self.calls = 0
        self.last_finish = ""
        self.last_model = ""
        self.retry_waits = retry_waits
        self.deadline = time.monotonic()+budget_seconds if budget_seconds else None
        print(f"[llm] writing through {self.backend}"
              + (f" ({self.project}/{self.location})" if self.backend == "vertex" else " (free tier)"),
              flush=True)

    def _endpoint(self, model: str) -> str:
        if self.backend != "vertex":
            return URL.format(model=model)
        template = VERTEX_GLOBAL if self.location == "global" else VERTEX_REGION
        return template.format(project=self.project, location=self.location, model=model)

    def _headers(self) -> dict:
        if self.backend != "vertex":
            return {"User-Agent": "sarthi-social-agent/1.0", "x-goog-api-key": self.api_key}
        # A token lives an hour and a render can run longer, so refresh when it has expired.
        if not self.creds.valid:
            _refresh(self.creds)
        return {"User-Agent": "sarthi-social-agent/1.0",
                "Authorization": f"Bearer {self.creds.token}"}

    def text(self, system: str, user: str, *, temperature: float = 0.8,
             max_tokens: int = 4096, json_mode: bool = False, models: list[str] | None = None,
             schema: dict | None = None) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if schema:
            body["generationConfig"]["responseJsonSchema"] = schema
        last = "no model answered"
        quota_hit = False
        for model in (models or self.models):
            for attempt in range(len(self.retry_waits) + 1):
                remaining = self.deadline-time.monotonic() if self.deadline else self.timeout
                if remaining <= 0:
                    raise LLMError('Model time budget exhausted; use checked fallback')
                self.calls += 1
                try:
                    response = requests.post(
                        self._endpoint(model), json=body, timeout=min(self.timeout, remaining),
                        headers=self._headers())
                except requests.RequestException as exc:
                    last = f"{model}: network error ({type(exc).__name__})"
                    quota_hit = False
                    break
                if response.status_code == 200:
                    payload = response.json()
                    self.last_finish = self._finish_of(payload)
                    text = self._text_of(payload)
                    if text:
                        self.last_model = model
                        return text
                    last = f"{model}: empty reply (finishReason={self.last_finish or 'none'})"
                    quota_hit = False
                    break
                detail = ""
                try:
                    detail = response.json()["error"]["message"]
                except Exception:
                    detail = response.text[:200]
                last = f"{model}: HTTP {response.status_code} {detail}"
                quota_hit = _is_quota(response.status_code, detail)
                # An exhausted allowance does not refill inside one run. Waiting three times
                # per model, across three models, three times over, is 36 requests spent to
                # learn the same thing -- and on a 20-request allowance those are the very
                # requests the next slot needed. Step to the next model at once instead.
                if quota_hit:
                    break
                if response.status_code in (429, 503) and attempt < len(self.retry_waits):
                    time.sleep(self.retry_waits[attempt])
                    continue
                if response.status_code in (404, 429, 500, 503):
                    # Say so out loud. Vertex and AI Studio do not always publish a model
                    # under the same name, and a silent 404 on every model would look
                    # exactly like an outage while actually being a typo in the model list.
                    print(f"[llm] {model} unavailable (HTTP {response.status_code}); "
                          "trying the next model", flush=True)
                    break  # next model
                raise LLMError(last)
        raise (QuotaError(last) if quota_hit else LLMError(last))

    def json(self, system: str, user: str, *, temperature: float = 0.8, max_tokens: int = 6144,
             schema: dict | None = None):
        """First parseable JSON reply across the models, in order.

        An unreadable reply no longer ends the call: the next model gets the same prompt, and
        the error says so when the token limit is what cut the reply off.
        """
        last: Exception | None = None
        # Each model carries its own allowance, so a quota refusal on one is still worth
        # trying the next. Only when every model refuses is the run out of road, and the
        # callers above need to hear that as QuotaError rather than retry into it.
        all_quota = True
        for model in self.models:
            try:
                raw = self.text(system, user, temperature=temperature, max_tokens=max_tokens,
                                json_mode=True, models=[model], schema=schema)
            except QuotaError as exc:
                last = exc
                continue
            except LLMError as exc:
                all_quota = False
                last = exc
                continue
            all_quota = False
            try:
                return _extract_json(raw)
            except LLMError as exc:
                note = " (cut off at the token limit)" if self.last_finish == "MAX_TOKENS" else ""
                print(f"[llm] {model} reply was not valid JSON{note}; trying the next model")
                last = LLMError(f"{model}{note}: {exc}")
        if all_quota and last is not None:
            raise QuotaError(str(last))
        raise last or LLMError("no model answered")

    @staticmethod
    def _text_of(payload) -> str:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return ""
        return "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict) and not p.get("thought")).strip()

    @staticmethod
    def _finish_of(payload) -> str:
        try:
            return str(payload["candidates"][0].get("finishReason") or "")
        except (KeyError, IndexError, TypeError, AttributeError):
            return ""
