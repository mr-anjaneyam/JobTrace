"""Shared batch-scoring prompt builder and resilient output parser."""
from __future__ import annotations

import json
from typing import Any

from .seniority import extract_required_years

KEYS = ("skills", "seniority", "location", "domain", "recency", "reach")

SYSTEM_TEMPLATE = """You score job postings against a candidate's profile.

CANDIDATE:
{profile}

For each job, output one compact array positionally:
[ref, score, skills, seniority, location, domain, recency, reach, "reason"]

- score is an integer 0-10 (10 = perfect match, 0 = completely irrelevant).
- The six sub-scores (skills, seniority, location, domain, recency, reach) are integers 0-100.
- reason must be at most 10 words.
- STRICT SENIORITY & EXPERIENCE GATES:
  * Seniority is a hard gate. If a job specifies more years of experience than the candidate has (e.g. requires 3+, 4+, 5+ yrs while candidate has < 2 yrs), score MUST NOT exceed 3/10 and the 'seniority' subscore MUST be <= 25.
  * Level II / 2 roles (e.g. 'Software Engineer II', 'SDE 2') typically require 3-5 years. For an early-career / junior candidate, cap score at 4/10 max, NEVER 9 or 10.
  * A 9 or 10 score is reserved ONLY for roles where the candidate meets ALL tech stack requirements AND matches or exceeds the experience level.
- LOCATION COMPATIBILITY:
  * If a job is strictly onsite in a location outside the candidate's target locations, score MUST NOT exceed 3/10 and the 'location' subscore MUST be <= 20. Remote roles or matching locations should be scored normally.

Reply with ONLY a JSON array of arrays. No markdown fence, no commentary."""

USER_TEMPLATE = """Jobs, one per line (ref|company|title|location|description):
{jobs}"""


def _extract_key_excerpt(desc: str, max_chars: int = 420) -> str:
    """Extract informative qualifications or requirements from job description."""
    if not desc:
        return ""
    import re
    # Try finding the qualifications or requirements section
    m = re.search(
        r"(?:minimum\s+qualifications?|basic\s+qualifications?|qualifications?|requirements?|what\s+you(?:'ll|\s+will)\s+need|who\s+you\s+are|what\s+we(?:'re|\s+are)\s+looking\s+for|what\s+you\s+bring)\s*:?\s*(.*?)(?=(?:preferred\s+qualifications?|bonus\s+points?|benefits?|what\s+we\s+offer)|\Z)",
        desc,
        re.I | re.S,
    )
    if m and len(m.group(1).strip()) > 60:
        target = m.group(1).strip()
    else:
        target = desc
        if re.match(r"^\s*(?:about\s+(?:us|the\s+company|our\s+team)|\b(?:we\s+are|at\s+[A-Z][\w\s]+,\s+we))\b", desc, re.I) and len(desc) > 400:
            target = desc[200:]
    return " ".join(target[:max_chars].split())


def build_messages(profile: str, jobs: list[dict]) -> list[dict]:
    lines = []
    for i, j in enumerate(jobs):
        desc = j.get("description") or ""
        req_years = extract_required_years(desc, title=j.get("title") or "")
        req_tag = f"[Req: {req_years:g}+ yrs exp] " if req_years else ""
        clean_desc = _extract_key_excerpt(desc, max_chars=420)
        lines.append(f"{i}|{j['company']}|{j['title']}|{j.get('location') or '?'}|{req_tag}{clean_desc}")

    return [
        {"role": "system", "content": SYSTEM_TEMPLATE.format(profile=profile[:1400])},
        {"role": "user", "content": USER_TEMPLATE.format(jobs="\n".join(lines))},
    ]


def build_prompt(profile: str, jobs: list[dict]) -> str:
    msgs = build_messages(profile, jobs)
    return f"{msgs[0]['content']}\n\n{msgs[1]['content']}"


def clean_breakdown(raw: Any) -> dict[str, int]:
    if isinstance(raw, dict):
        src = [raw.get(k, 0) for k in KEYS]
    elif isinstance(raw, (list, tuple)):
        src = list(raw)
    else:
        src = []

    out = {}
    padded = src + [0] * 6
    for k, v in zip(KEYS, padded[:6]):
        try:
            out[k] = max(0, min(100, int(v)))
        except (TypeError, ValueError):
            out[k] = 0
    return out


def _salvage(blob: str) -> list:
    """Extract individual JSON objects or arrays that survived malformed output."""
    out = []
    for opener, closer in (("[", "]"), ("{", "}")):
        depth = 0
        start = -1
        for i, ch in enumerate(blob):
            if ch == opener:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == closer and depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        item = json.loads(blob[start : i + 1])
                        if isinstance(item, (list, dict)) and item:
                            out.append(item)
                    except json.JSONDecodeError:
                        pass
                    start = -1
        if out:
            break
    return out


def _row(item: Any, jobs: list[dict]) -> tuple | None:
    if isinstance(item, dict):
        ref = item.get("ref", -1)
        score = item.get("score", 0)
        reason = item.get("reason", "")
        bd = item.get("breakdown")
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        ref = item[0]
        score = item[1]
        bd = item[2:8] if len(item) >= 8 else []
        reason = item[8] if len(item) > 8 else ""
    else:
        return None

    try:
        ref_idx = int(ref)
    except (TypeError, ValueError):
        return None

    if not 0 <= ref_idx < len(jobs):
        return None

    try:
        norm_score = max(0, min(10, int(score)))
    except (TypeError, ValueError):
        norm_score = 0

    return jobs[ref_idx]["id"], norm_score, str(reason)[:200], clean_breakdown(bd)


def parse(text: str, jobs: list[dict]) -> dict[str, tuple[int, str, dict]]:
    open_idx = text.find("[")
    if open_idx == -1:
        raise ValueError(f"no JSON array in reply: {text[:160]}")

    close_idx = text.rfind("]")
    blob = text[open_idx : close_idx + 1] if close_idx > open_idx else text[open_idx:]

    try:
        items = json.loads(blob)
        if not isinstance(items, list):
            raise ValueError("Reply was not a list")
        if items and not isinstance(items[0], (list, dict)):
            items = [items]
    except (json.JSONDecodeError, ValueError):
        items = _salvage(blob)
        if not items:
            raise ValueError(f"Unparseable reply: {text[:160]}")

    out: dict[str, tuple[int, str, dict]] = {}
    for item in items:
        res = _row(item, jobs)
        if res:
            job_id, sc, rsn, bd = res
            out[job_id] = (sc, rsn, bd)
    return out
