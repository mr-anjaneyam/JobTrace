"""Cursor Cloud Agents scoring backend for JobTrace."""
from __future__ import annotations

import os
import logging
import time

import requests

from . import applog, batch

log = logging.getLogger("jobtrace.llm")

BASE = "https://api.cursor.com/v1"


class CursorError(RuntimeError):
    """Cursor API configuration or execution error."""


class CursorScorer:
    provider = "cursor"

    def __init__(self, model: str = "", params: dict | None = None):
        self.key = (os.environ.get("CURSOR_API_KEY") or "").strip()
        if not self.key or self.key.startswith("paste-your"):
            raise CursorError(
                "CURSOR_API_KEY is not set or placeholder. Set it in your environment or secrets."
            )
        self.model = model or "gemini-3.8-flash"
        self.params = params if params is not None else {"reasoning_effort": "low"}
        self.batch_size = 25
        self.poll_seconds = 3
        self.timeout_seconds = 360

    def _model_selection(self) -> dict:
        sel: dict = {"id": self.model}
        if self.params:
            sel["params"] = [{"id": k, "value": v} for k, v in self.params.items()]
        return sel

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    def _run_agent(self, prompt: str) -> str:
        r = applog.traced(
            "llm",
            requests.post,
            f"{BASE}/agents",
            headers=self._headers(),
            timeout=60,
            json={"prompt": {"text": prompt}, "model": self._model_selection()},
        )
        if r.status_code == 401:
            raise CursorError("Cursor rejected the API key.")
        if r.status_code >= 400:
            raise CursorError(f"Cursor HTTP {r.status_code}: {r.text[:250]}")

        agent = r.json()
        agent_id = agent.get("id")
        run_id = agent.get("latestRunId") or (agent.get("latestRun") or {}).get("id")
        if not agent_id or not run_id:
            raise CursorError(f"Cursor returned no agent run to poll: {str(agent)[:180]}")

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            time.sleep(self.poll_seconds)
            rr = applog.traced(
                "llm",
                requests.get,
                f"{BASE}/agents/{agent_id}/runs/{run_id}",
                bodies=False,
                headers=self._headers(),
                timeout=60,
            )
            if rr.status_code >= 400:
                raise CursorError(f"Cursor poll HTTP {rr.status_code}: {rr.text[:200]}")
            run = rr.json()
            status = (run.get("status") or "").upper()
            if status in ("FINISHED", "COMPLETED", "SUCCEEDED"):
                log.info("cursor run %s finished: %s", run_id, applog.clip(run.get("result")))
                return run.get("result") or ""
            if status in ("FAILED", "CANCELLED", "ERROR", "EXPIRED"):
                raise CursorError(f"Cursor run {status}: {str(run.get('error'))[:200]}")
        raise CursorError(f"Cursor run timed out after {self.timeout_seconds}s")

    def score_batch(self, profile: str, jobs: list[dict]) -> dict[str, tuple[int, str, dict]]:
        if not jobs:
            return {}
        text = self._run_agent(batch.build_prompt(profile, jobs))
        try:
            return batch.parse(text, jobs)
        except Exception as e:
            raise CursorError(f"Failed to parse Cursor output: {e}") from e

    def score(self, profile: str, job: dict) -> tuple[int, str, dict]:
        j = dict(job)
        j.setdefault("id", "single")
        got = self.score_batch(profile, [j])
        return got.get(j["id"], (0, "no result", {}))

    def complete(self, prompt: str, max_tokens: int = 300) -> str:
        return self._run_agent(prompt + "\n\nAnswer directly. Do not browse or run shell commands.")
