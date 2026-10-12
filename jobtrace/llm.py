"""Chat completions client for OpenAI-compatible LLM endpoints."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any

import requests

from . import batch


class RateLimited(Exception):
    """Provider throttled the request."""


ENDPOINTS = {
    "xkiro": ("https://api.xkiro.com/v1/chat/completions", "XKIRO_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
    "ollama": ("http://localhost:11434/v1/chat/completions", None),
}


class LLM:
    def __init__(self, provider: str, model: str):
        self.provider = provider.lower()
        if self.provider not in ENDPOINTS:
            raise ValueError(f"Unknown provider '{provider}'. Choose from {list(ENDPOINTS.keys())}")

        self.url, env_var = ENDPOINTS[self.provider]
        self.model = model
        self.key = os.environ.get(env_var, "") if env_var else ""
        self._lock = threading.Lock()
        self.input_tokens = 0
        self.output_tokens = 0

    def _pace(self, headers: Any) -> None:
        try:
            remaining = int(headers.get("x-ratelimit-remaining-tokens", "999999"))
        except ValueError:
            return
        if remaining > 2000:
            return
        reset = headers.get("x-ratelimit-reset-tokens", "")
        secs = 1.0
        m = re.match(r"(?:(\d+)m)?([\d.]+)s", reset)
        if m:
            secs = float(m.group(1) or 0) * 60 + float(m.group(2) or 0)
        with self._lock:
            time.sleep(min(max(secs, 1.0), 60))

    def chat(self, messages: list[dict], max_tokens: int = 1500, retries: int = 3) -> str:
        return self._post(messages, max_tokens, retries)

    def complete(self, prompt: str, max_tokens: int = 400, retries: int = 3) -> str:
        return self._post([{"role": "user", "content": prompt}], max_tokens, retries)

    def _post(self, messages: list[dict], max_tokens: int, retries: int) -> str:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

        for attempt in range(retries):
            try:
                r = requests.post(self.url, headers=headers, json=body, timeout=60)
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"{self.provider} connection failed: {e}") from e
                time.sleep(3 * (attempt + 1))
                continue

            if r.status_code == 429:
                wait = r.headers.get("retry-after")
                try:
                    delay = float(wait) if wait else 4 * (attempt + 1)
                except ValueError:
                    delay = 4 * (attempt + 1)
                time.sleep(min(delay, 30))
                continue

            if r.status_code >= 400:
                detail = r.text[:300]
                if r.status_code in (401, 403):
                    raise RuntimeError(f"{self.provider} rejected the API key: {detail}")
                if r.status_code == 404:
                    raise RuntimeError(f"Model '{self.model}' not found on {self.provider}: {detail}")
                raise RuntimeError(f"{self.provider} HTTP {r.status_code}: {detail}")

            self._pace(r.headers)
            payload = r.json()
            usage = payload.get("usage") or {}
            self.input_tokens += usage.get("prompt_tokens", 0) or 0
            self.output_tokens += usage.get("completion_tokens", 0) or 0
            text = payload["choices"][0]["message"]["content"]
            # Clean reasoning/thinking artifacts if any
            return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

        raise RateLimited(f"{self.provider} rate-limited after {retries} retries")


class ChatScorer:
    batch_size = 25

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.llm = LLM(provider, model)

    def score_batch(self, profile: str, jobs: list[dict]) -> dict[str, tuple[int, str, dict]]:
        if not jobs:
            return {}
        cap = min(4000, 150 + 65 * len(jobs))
        text = self.llm.chat(batch.build_messages(profile, jobs), max_tokens=cap)
        return batch.parse(text, jobs)

    def score(self, profile: str, job: dict) -> tuple[int, str, dict]:
        j = dict(job)
        j.setdefault("id", "single")
        return self.score_batch(profile, [j]).get(j["id"], (0, "no result", {}))

    def complete(self, prompt: str, **kw) -> str:
        return self.llm.complete(prompt, **kw)

    @property
    def tokens_used(self) -> int:
        return self.llm.input_tokens + self.llm.output_tokens


def make_scorer(
    provider: str,
    model: str = "",
    params: dict | None = None,
    resume_text: str = "",
    target_locations: list[str] | None = None,
    target_seniority: str = "junior",
):
    if not provider or provider in ("none", "off"):
        return None
    p = provider.lower()
    if p == "local":
        from .localmatch import LocalScorer
        return LocalScorer(
            resume_text=resume_text or model,
            target_locations=target_locations,
            target_seniority=target_seniority,
        )
    if p == "cursor":
        from .cursor import CursorScorer
        return CursorScorer(model=model, params=params)
    if p == "jev":
        from .jev import JevScorer
        return JevScorer(model=model)
    return ChatScorer(p, model)
