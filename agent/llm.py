"""Gemini text generation over the plain REST API.

Same pattern the product uses: try each model in order, step to the next one on a
retired (404) or busy (429/503) model, and return the first non-empty answer. The
free tier is rate limited per minute, so a 429 waits before trying again.

JSON calls go one step further: a reply that cannot be parsed is treated like a busy model,
and the next model gets the same prompt. A thinking model can spend its whole token budget
before closing the object, and on 11 Sep 2026 one such reply killed a production dry run.
"""

from __future__ import annotations

import json
import re
import time

import requests

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_WAITS = (15, 35, 60)


class LLMError(RuntimeError):
    pass


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
    def __init__(self, api_key: str, models: list[str], timeout: float = 120.0):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.models = list(models)
        self.timeout = timeout
        self.calls = 0
        self.last_finish = ""

    def text(self, system: str, user: str, *, temperature: float = 0.8,
             max_tokens: int = 4096, json_mode: bool = False, models: list[str] | None = None) -> str:
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
        last = "no model answered"
        for model in (models or self.models):
            for attempt in range(len(RETRY_WAITS) + 1):
                self.calls += 1
                try:
                    response = requests.post(
                        URL.format(model=model), params={"key": self.api_key}, json=body,
                        timeout=self.timeout, headers={"User-Agent": "sarthi-social-agent/1.0"})
                except requests.RequestException as exc:
                    last = f"{model}: network error ({exc})"
                    break
                if response.status_code == 200:
                    payload = response.json()
                    self.last_finish = self._finish_of(payload)
                    text = self._text_of(payload)
                    if text:
                        return text
                    last = f"{model}: empty reply (finishReason={self.last_finish or 'none'})"
                    break
                detail = ""
                try:
                    detail = response.json()["error"]["message"]
                except Exception:
                    detail = response.text[:200]
                last = f"{model}: HTTP {response.status_code} {detail}"
                if response.status_code in (429, 503) and attempt < len(RETRY_WAITS):
                    time.sleep(RETRY_WAITS[attempt])
                    continue
                if response.status_code in (404, 429, 500, 503):
                    break  # next model
                raise LLMError(last)
        raise LLMError(last)

    def json(self, system: str, user: str, *, temperature: float = 0.8, max_tokens: int = 6144):
        """First parseable JSON reply across the models, in order.

        An unreadable reply no longer ends the call: the next model gets the same prompt, and
        the error says so when the token limit is what cut the reply off.
        """
        last: Exception | None = None
        for model in self.models:
            try:
                raw = self.text(system, user, temperature=temperature, max_tokens=max_tokens,
                                json_mode=True, models=[model])
            except LLMError as exc:
                last = exc
                continue
            try:
                return _extract_json(raw)
            except LLMError as exc:
                note = " (cut off at the token limit)" if self.last_finish == "MAX_TOKENS" else ""
                print(f"[llm] {model} reply was not valid JSON{note}; trying the next model")
                last = LLMError(f"{model}{note}: {exc}")
        raise last or LLMError("no model answered")

    @staticmethod
    def _text_of(payload) -> str:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return ""
        return "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict)).strip()

    @staticmethod
    def _finish_of(payload) -> str:
        try:
            return str(payload["candidates"][0].get("finishReason") or "")
        except (KeyError, IndexError, TypeError, AttributeError):
            return ""
