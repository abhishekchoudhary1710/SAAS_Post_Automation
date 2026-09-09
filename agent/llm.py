"""Gemini text generation over the plain REST API.

Same pattern the product uses: try each model in order, step to the next one on a
retired (404) or busy (429/503) model, and return the first non-empty answer. The
free tier is rate limited per minute, so a 429 waits before trying again.
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

    def text(self, system: str, user: str, *, temperature: float = 0.8,
             max_tokens: int = 4096, json_mode: bool = False) -> str:
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
        for model in self.models:
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
                    text = self._text_of(response.json())
                    if text:
                        return text
                    last = f"{model}: empty reply"
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
        raw = self.text(system, user, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        return _extract_json(raw)

    @staticmethod
    def _text_of(payload) -> str:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return ""
        return "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict)).strip()
