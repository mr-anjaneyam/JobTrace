"""Shared batch-scoring prompt builder and resilient output parser."""
from __future__ import annotations

import json
from typing import Any

from .seniority import extract_required_years

KEYS = ("skills", "seniority", "location", "domain", "recency", "reach")

SYSTEM_TEMPLATE = """You are a senior technical hiring partner matching software engineering roles to a candidate profile.

CANDIDATE:
{profile}

For each job, output one compact array positionally:
[
  ref,
  score,
  skills,
  seniority,
  location,
  domain,
  recency,
  reach,
  "reason",
  ["matched_skill_1", "matched_skill_2"],
  ["missing_skill_1", "missing_skill_2"],
  "seniority_fit",
  "recruiter_advice",
  "salary_text_if_any",
  "deadline_text_if_any"
]

- score is an integer 0-10 (10 = ideal match, 0 = completely irrelevant).
- The six sub-scores (skills, seniority, location, domain, recency, reach) MUST BE INTEGERS 0-100.
- reason: at most 10 words stating the genuine fit or blocker.
- matched_skills: array of strings with top 2-5 technical skills present in both candidate and JD.
- missing_skills: array of strings with key technical skills requested by JD that candidate does not emphasize.
- seniority_fit: one sentence evaluating experience alignment (e.g. "Candidate has 1 yr vs 0-2 yrs required: Optimal sweet spot").
- recruiter_advice: 1-2 actionable sentences on why to apply, which resume project (e.g. Lumen microservices, CoreTrace) to highlight, and interview focus.
- salary_text_if_any: compensation mentioned in JD (e.g. "₹4.8–5.3 LPA", "$120k-$140k"), or empty string "" if not mentioned.
- deadline_text_if_any: application deadline or walk-in date mentioned in JD (e.g. "31 Oct 2026"), or empty string "" if not mentioned.

STRICT EVALUATION & CALIBRATION RULES:
1. SENIORITY & EXPERIENCE MATCHING:
   - TARGET SWEET SPOT (Eligible for 8-10/10):
     * Roles asking for 1-3 years, 0-2 years, "fresher - 2 yrs", or early-career (SDE 1, Junior/Associate Software Engineer, AMTS).
   - STRICT FRESHER / CAMPUS (Score MUST NOT exceed 2/10, seniority subscore <= 20):
     * If the candidate already has full-time industry experience (~1 year), do NOT recommend roles strictly reserved for college students, campus recruitment drives, student internships, or "batch of 2024/2025 freshers only". The candidate is an active professional engineer, not a campus fresher.
   - SENIOR / LEAD (Score MUST NOT exceed 2/10, seniority subscore <= 20):
     * Roles requiring 3+, 4+, 5+ years experience, or titled Senior, Lead, Staff, Principal, Architect.
   - LEVEL II / MID (Score capped at 4/10):
     * Roles explicitly titled SDE 2 / Software Engineer II or asking for 3-5 years.

2. AVOID "HAMMERING" MEDIOCRE (50%) ROLES:
   - Do NOT give 5/10 or 6/10 to generic postings merely because they mention basic tools (Git, Linux, SQL).
   - If the core domain or tech stack is misaligned (e.g. PHP/WordPress, Mobile iOS/Swift, Embedded C, Tech Support, SAP), score MUST be 1-3/10.
   - A score of 7-10 is strictly reserved for genuine matches where primary stack (e.g. Java/Spring Boot, Python backend, APIs, Cloud) and experience level cleanly overlap.

3. LOCATION COMPATIBILITY:
   - If strictly onsite in an unapproved location outside candidate preferences, score MUST NOT exceed 3/10 and location subscore <= 20. Remote or matching cities scored normally.

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
    matched_skills = []
    missing_skills = []
    seniority_fit = ""
    advice = ""
    salary_text = ""
    deadline_text = ""

    if isinstance(item, dict):
        ref = item.get("ref", -1)
        score = item.get("score", 0)
        reason = item.get("reason", "")
        bd = item.get("breakdown")
        matched_skills = item.get("matched_skills") or []
        missing_skills = item.get("missing_skills") or []
        seniority_fit = item.get("seniority_fit") or ""
        advice = item.get("recruiter_advice") or item.get("advice") or ""
        salary_text = item.get("salary_text_if_any") or item.get("salary") or ""
        deadline_text = item.get("deadline_text_if_any") or item.get("deadline") or ""
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        ref = item[0]
        score = item[1]
        bd = item[2:8] if len(item) >= 8 else []
        reason = item[8] if len(item) > 8 else ""
        if len(item) > 9 and isinstance(item[9], list):
            matched_skills = [str(x) for x in item[9]]
        if len(item) > 10 and isinstance(item[10], list):
            missing_skills = [str(x) for x in item[10]]
        if len(item) > 11 and item[11]:
            seniority_fit = str(item[11])
        if len(item) > 12 and item[12]:
            advice = str(item[12])
        if len(item) > 13 and item[13]:
            salary_text = str(item[13])
        if len(item) > 14 and item[14]:
            deadline_text = str(item[14])
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

    clean_bd = clean_breakdown(bd)
    clean_bd["matched_skills"] = matched_skills
    clean_bd["missing_skills"] = missing_skills
    clean_bd["seniority_fit"] = seniority_fit
    clean_bd["advice"] = advice
    if salary_text:
        clean_bd["salary_text"] = salary_text
    if deadline_text:
        clean_bd["deadline_text"] = deadline_text

    return jobs[ref_idx]["id"], norm_score, str(reason)[:200], clean_bd


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
        # A reply cut off by max_tokens leaves the outer array unclosed, so retry without it
        items = _salvage(blob) or _salvage(blob[1:])
        if not items:
            raise ValueError(f"Unparseable reply: {text[:160]}")

    out: dict[str, tuple[int, str, dict]] = {}
    for item in items:
        res = _row(item, jobs)
        if res:
            job_id, sc, rsn, bd = res
            out[job_id] = (sc, rsn, bd)
    return out
