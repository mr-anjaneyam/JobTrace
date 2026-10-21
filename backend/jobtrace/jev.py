"""TypeSafe System One backend for JobTrace."""
from __future__ import annotations

import os
import threading
from typing import Any

FIT_LEVELS = [
    "wrong field entirely - the candidate has none of the required background",
    "adjacent field - some transferable skills but a clear stretch",
    "plausible - meets roughly half the stated requirements",
    "strong - meets most requirements with relevant direct experience",
    "excellent - meets or exceeds every requirement, an obvious match",
]

SENIORITY = {
    "under": "the role is more senior than the candidate's experience supports",
    "match": "the role's seniority matches the candidate's experience",
    "over": "the role is junior to what the candidate has already done",
}

LOCATION = {
    "ok": "the candidate could work here - remote, or a location they can reach",
    "unclear": "the posting does not state a location clearly enough to judge",
    "blocked": "onsite in a place the candidate cannot plausibly work from",
}


class JevScorer:
    provider = "jev"
    INPUT_COST_PER_MTOK = 0.042

    def __init__(self, model: str | None = None):
        try:
            from typesafe_sdk import Choice, Score, TypeSafeClient
        except ImportError as e:
            raise RuntimeError("pip install typesafe-sdk to use the Jev backend") from e

        key = (os.environ.get("TYPESAFE_API_KEY") or "").strip()
        if not key or key.startswith("paste-your"):
            raise RuntimeError("TYPESAFE_API_KEY is not set.")

        self._Score = Score
        self._Choice = Choice
        self.client = TypeSafeClient(**({"model": model} if model else {}))
        self._lock = threading.Lock()
        self.input_tokens = 0

    def _questions(self) -> dict:
        return {
            "fit": self._Score(
                instructions="How well does this candidate fit this specific job?",
                criteria=FIT_LEVELS,
            ),
            "seniority": self._Choice(
                instructions="How does the role's seniority compare to the candidate's?",
                criteria={k: v for k, v in SENIORITY.items()},
            ),
            "location": self._Choice(
                instructions="Can this candidate actually work in this role's location?",
                criteria={k: v for k, v in LOCATION.items()},
            ),
        }

    def score(self, profile: str, job: dict) -> tuple[int, str, dict]:
        state = (
            f"CANDIDATE RESUME:\n{profile[:8000]}\n\n"
            f"JOB POSTING:\n"
            f"Company: {job['company']}\n"
            f"Title: {job['title']}\n"
            f"Location: {job.get('location') or 'unspecified'}\n"
            f"Description: {(job.get('description') or 'n/a')[:4000]}"
        )
        try:
            result = self.client.system_one(state, self._questions())
        except Exception as e:
            return 0, f"scoring failed: {type(e).__name__}", {}

        usage = getattr(result, "usage", None)
        with self._lock:
            self.input_tokens += getattr(usage, "input_tokens", 0) or 0

        fit = result.scores["fit"]
        seniority = result.choices["seniority"].choice
        location = result.choices["location"].choice

        score = fit.score / (len(FIT_LEVELS) - 1) * 10
        if location == "blocked":
            score *= 0.3
        if seniority in ("under", "over"):
            score *= 0.75

        confidence = getattr(fit, "confidence", None)
        bits = [f"seniority {seniority}", f"location {location}"]
        if confidence is not None:
            bits.append(f"confidence {confidence:.0%}")

        breakdown = {
            "skills": round(fit.score / (len(FIT_LEVELS) - 1) * 100),
            "seniority": {"match": 100, "under": 35, "over": 55}.get(seniority, 50),
            "location": {"ok": 100, "unclear": 55, "blocked": 10}.get(location, 50),
            "domain": round(fit.score / (len(FIT_LEVELS) - 1) * 100),
            "recency": 100,
            "reach": round(score * 10),
        }
        return round(score), ", ".join(bits), breakdown

    def cost_usd(self) -> float:
        with self._lock:
            return self.input_tokens / 1_000_000 * self.INPUT_COST_PER_MTOK
