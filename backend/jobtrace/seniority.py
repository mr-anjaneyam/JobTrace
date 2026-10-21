"""Configurable seniority gate for JobTrace.

Ensures candidate seniority fits the role, while supporting any target experience
band (intern, junior, mid, senior, lead, executive, or any).
"""
from __future__ import annotations

import html
import re

SENIOR_TITLES = (
    r"senior", r"sr\.?", r"staff", r"principal", r"lead", r"leads",
    r"head of", r"director", r"vp", r"vice president", r"chief",
    r"architect", r"manager", r"distinguished", r"fellow",
    r"\b(?:iii|iv|v|vi)\b",
    r"\b(?:smts|pmts|lmts)\b",
    r"(?:sde|swe|mts|engineer|developer|software\s+development\s+engineer|member\s+of\s+technical\s+staff)[- ]*(?:[3-6]|iii|iv|v|vi)\b",
    r"\b(?:level|tier|grade)[- ]*[3-6]\b",
    r"\b(?:l[5-8]|ic[5-8]|e[5-8])\b",
)

EXECUTIVE_TITLES = (
    r"head of", r"director", r"vp", r"vice president", r"chief",
    r"partner", r"distinguished", r"fellow"
)

MID_TITLES = (
    r"\b(?:ii|2|mid|mid-level|intermediate)\b",
    r"(?:sde|swe|mts|engineer|developer|software\s+development\s+engineer)[- ]*(?:2|ii)\b",
    r"\b(?:level|tier|grade)[- ]*2\b",
    r"\b(?:l4|ic4|e4)\b",
)

JUNIOR_TITLES = (
    r"intern", r"internship", r"junior", r"jr\.?", r"new ?grad",
    r"graduate", r"entry[- ]level", r"associate", r"apprentice",
    r"trainee", r"early career", r"university", r"campus", r"fresher",
    r"(?:sde|swe|mts|engineer|developer|software\s+development\s+engineer)[- ]*(?:1|i\b)",
    r"\b(?:level|tier|grade)[- ]*1\b",
    r"\b(?:l3|ic3|e3)\b",
)

_SENIOR_RE = re.compile(r"\b(?:" + "|".join(SENIOR_TITLES) + r")\b", re.I)
_EXEC_RE = re.compile(r"\b(?:" + "|".join(EXECUTIVE_TITLES) + r")\b", re.I)
_MID_RE = re.compile(r"(?:" + "|".join(MID_TITLES) + r")", re.I)
_JUNIOR_RE = re.compile(r"\b(?:" + "|".join(JUNIOR_TITLES) + r")\b", re.I)


def is_senior_title(title: str) -> bool:
    t = title or ""
    if _JUNIOR_RE.search(t) and not _EXEC_RE.search(t):
        return False
    return bool(_SENIOR_RE.search(t))


def is_mid_title(title: str) -> bool:
    t = title or ""
    if is_senior_title(t) or is_junior_title(t):
        return False
    return bool(_MID_RE.search(t))


def is_junior_title(title: str) -> bool:
    t = title or ""
    return bool(_JUNIOR_RE.search(t))


def extract_required_years(text: str, title: str = "") -> float | None:
    """Extract minimum years of required experience from description or title.
    
    Handles formats like '4+ years experience', 'minimum 3 years of experience',
    '4-6 years', 'at least 5 yrs', etc.
    Avoids company history boilerplate (e.g. 'founded in 2012, with 12 years of history').
    """
    blob = f"{title} {text}".strip()
    if not blob:
        return None

    # Unescape HTML entities & strip tags
    clean = html.unescape(blob)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    # Prioritize scanning requirements/qualifications section if present
    req_match = re.search(
        r"(?:minimum\s+qualifications?|basic\s+qualifications?|qualifications?|requirements?|what\s+you(?:'ll|\s+will)\s+need|who\s+you\s+are|what\s+we(?:'re|\s+are)\s+looking\s+for|what\s+you\s+bring)\s*:?\s*(.*?)(?=(?:preferred\s+qualifications?|bonus\s+points?|nice\s+to\s+have|benefits?|what\s+we\s+offer|about\s+(?:us|the\s+company)|our\s+values)|\Z)",
        clean,
        re.I | re.S,
    )
    target_text = req_match.group(1) if (req_match and len(req_match.group(1).strip()) > 40) else clean

    # Strip company history / age / founding boilerplate from candidate text
    target_text = re.sub(
        r"\b(?:founded\s+in|for\s+over|over|for|past|last|celebrating|more\s+than|with)\s+\d+\s+(?:years?|yrs?)\s+of\s+(?:history|presence|growth|success|innovation|excellence|service|business)\b",
        " ",
        target_text,
        flags=re.I,
    )
    target_text = re.sub(
        r"\b(?:founded\s+in|for\s+over|over|for|past|last|celebrating|more\s+than)\s+\d+\s+(?:years?|yrs?)(?:\s+of)?(?:\s+[\w-]+){0,4}",
        " ",
        target_text,
        flags=re.I,
    )

    # Normalize ranges like '5-7 years' or '5 to 7 years' into '5+ years'
    target_text = re.sub(
        r"\b(\d+(?:\.\d+)?)\s*(?:to|-)\s*\d+(?:\.\d+)?\s*(years?|yrs?)\b",
        r"\1+ \2",
        target_text,
        flags=re.I,
    )

    patterns = [
        # 1. "minimum of 4 years", "at least 4 years", "requires 4+ years"
        r"(?:minimum\s+(?:of\s+)?|at\s+least\s+|requires?\s+|require\s+)(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:to|-)?\s*(?:\d+(?:\.\d+)?)?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+[\w-]+){0,3}\s*(?:experience|exp|working|building|developing|programming)?",
        # 2. "with 4+ years of experience" (must explicitly state experience/exp/working)
        r"\b(?:candidate\s+with|seeking\s+[\w\s]{1,20}\s+with|with)\s+(\d+(?:\.\d+)?)\s*(?:\+|plus)?\s*(?:to|-)?\s*(?:\d+(?:\.\d+)?)?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+[\w-]+){0,3}\s+(?:experience|exp|hands-on|industry\s+experience|professional\s+experience|working\s+with|building|developing|programming)",
        # 3. "4+ years of experience", "4+ yrs experience", "4-6 years experience"
        r"(\d+(?:\.\d+)?)\s*(?:\+|plus)\s*(?:years?|yrs?)(?:\s+of)?(?:\s+[\w-]+){0,3}\s*(?:experience|exp)",
        # 4. "4+ years in/with/building"
        r"(\d+(?:\.\d+)?)\s*(?:\+|plus)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience\s+with|experience\s+in|working\s+with|building|developing|designing|using|programming|in\s+[a-z]+)",
        # 5. Standard "4 years of experience"
        r"(\d+(?:\.\d+)?)\s+(?:years?|yrs?)\s+of(?:\s+[\w-]+){0,3}\s*(?:experience|exp)\b",
        # 6. "4+ years experience"
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:experience|exp)\b",
    ]

    found_years: list[float] = []
    for pat in patterns:
        for m in re.finditer(pat, target_text, re.I):
            val = float(m.group(1))
            if 0.5 <= val <= 18.0:
                found_years.append(val)

    if not found_years:
        return None
    return max(found_years)


def apply_cap(
    score: int,
    title: str,
    reason: str = "",
    target_seniority: str = "junior",
    cap_value: int = 3,
    description: str = "",
    candidate_years: float | None = None,
    breakdown: dict | None = None,
) -> tuple[int, str]:
    """Apply rule-based seniority and experience requirement cap.
    
    target_seniority options:
      - 'intern' / 'junior': cap senior/lead roles at cap_value, 4+ yr reqs at 2, 3+ yr reqs at 3, Level II roles at 5.
      - 'mid': cap executive roles / 7+ yr reqs; allow senior roles.
      - 'senior' / 'lead': cap intern/trainee roles; allow senior roles.
      - 'any' / 'off': no title or experience cap.
    """
    mode = (target_seniority or "junior").lower().strip()
    if mode in ("any", "off", "none"):
        return score, reason

    t = title or ""
    req_years = extract_required_years(description, title=t)

    cand_years_str = f"{candidate_years:g}" if candidate_years is not None else "<2"

    if mode in ("intern", "junior", "entry"):
        # 1. Hard experience mismatch from description
        if req_years is not None and req_years >= 4.0:
            target_cap = min(2, cap_value)
            if breakdown is not None:
                breakdown["seniority"] = min(breakdown.get("seniority", 100), 15)
            if score <= target_cap:
                return score, reason
            note = f"capped at {target_cap}: requires {req_years:g}+ yrs experience (candidate has {cand_years_str} yrs)"
            return target_cap, f"{reason}; {note}" if reason else note

        if req_years is not None and req_years >= 3.0:
            target_cap = min(3, cap_value)
            if breakdown is not None:
                breakdown["seniority"] = min(breakdown.get("seniority", 100), 25)
            if score <= target_cap:
                return score, reason
            note = f"capped at {target_cap}: requires {req_years:g}+ yrs experience (candidate has {cand_years_str} yrs)"
            return target_cap, f"{reason}; {note}" if reason else note

        # 2. Senior / Staff / Principal / Lead titles
        if is_senior_title(t):
            if breakdown is not None:
                breakdown["seniority"] = min(breakdown.get("seniority", 100), 20)
            if score <= cap_value:
                return score, reason
            note = f"capped at {cap_value}: senior title (senior role for {mode} target)"
            return cap_value, f"{reason}; {note}" if reason else note

        # 3. Level II / Mid-level roles (e.g. Software Engineer, II)
        if is_mid_title(t):
            mid_cap = 4 if (req_years is not None and req_years > 2.0) else 5
            if breakdown is not None:
                breakdown["seniority"] = min(breakdown.get("seniority", 100), 45)
            if score <= mid_cap:
                return score, reason
            note = f"capped at {mid_cap}: mid-level II role for {mode} target"
            return mid_cap, f"{reason}; {note}" if reason else note

    elif mode == "mid":
        if (req_years is not None and req_years >= 7.0) or bool(_EXEC_RE.search(t)):
            if breakdown is not None:
                breakdown["seniority"] = min(breakdown.get("seniority", 100), 20)
            if score <= cap_value:
                return score, reason
            note = f"capped at {cap_value}: executive / 7+ yrs role for mid target"
            return cap_value, f"{reason}; {note}" if reason else note

    elif mode in ("senior", "lead", "staff", "principal"):
        # For senior engineers, cap low-level internships unless requested
        if (is_junior_title(t) and not _SENIOR_RE.search(t)) or (req_years is not None and req_years <= 1.0):
            if breakdown is not None:
                breakdown["seniority"] = min(breakdown.get("seniority", 100), 20)
            if score <= cap_value:
                return score, reason
            note = f"capped at {cap_value}: intern/entry role for senior target"
            return cap_value, f"{reason}; {note}" if reason else note

    return score, reason
