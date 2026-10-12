"""Configurable seniority gate for JobTrace.

Ensures candidate seniority fits the role, while supporting any target experience
band (intern, junior, mid, senior, lead, executive, or any).
"""
from __future__ import annotations

import re

SENIOR_TITLES = (
    r"senior", r"sr\.?", r"staff", r"principal", r"lead", r"leads",
    r"head of", r"director", r"vp", r"vice president", r"chief",
    r"architect", r"manager", r"distinguished", r"fellow", r"iii", r"iv"
)

EXECUTIVE_TITLES = (
    r"head of", r"director", r"vp", r"vice president", r"chief",
    r"partner", r"distinguished", r"fellow"
)

JUNIOR_TITLES = (
    r"intern", r"internship", r"junior", r"jr\.?", r"new ?grad",
    r"graduate", r"entry[- ]level", r"associate", r"apprentice",
    r"trainee", r"early career", r"university", r"campus", r"fresher"
)

_SENIOR_RE = re.compile(r"\b(?:" + "|".join(SENIOR_TITLES) + r")\b", re.I)
_EXEC_RE = re.compile(r"\b(?:" + "|".join(EXECUTIVE_TITLES) + r")\b", re.I)
_JUNIOR_RE = re.compile(r"\b(?:" + "|".join(JUNIOR_TITLES) + r")\b", re.I)


def is_senior_title(title: str) -> bool:
    t = title or ""
    if _JUNIOR_RE.search(t) and not _EXEC_RE.search(t):
        return False
    return bool(_SENIOR_RE.search(t))


def is_junior_title(title: str) -> bool:
    t = title or ""
    return bool(_JUNIOR_RE.search(t))


def apply_cap(
    score: int,
    title: str,
    reason: str = "",
    target_seniority: str = "junior",
    cap_value: int = 3,
) -> tuple[int, str]:
    """Apply rule-based seniority cap based on candidate's target seniority.
    
    target_seniority options:
      - 'intern' / 'junior': cap senior/lead/director roles at cap_value.
      - 'mid': cap executive/director roles; allow senior roles.
      - 'senior' / 'lead': cap intern/trainee roles; allow senior roles.
      - 'any' / 'off': no title cap.
    """
    mode = (target_seniority or "junior").lower().strip()
    if mode in ("any", "off", "none"):
        return score, reason

    t = title or ""
    if mode in ("intern", "junior", "entry"):
        if is_senior_title(t):
            if score <= cap_value:
                return score, reason
            note = f"capped at {cap_value}: senior title (senior role for {mode} target)"
            return cap_value, f"{reason}; {note}" if reason else note

    elif mode == "mid":
        if bool(_EXEC_RE.search(t)):
            if score <= cap_value:
                return score, reason
            note = f"capped at {cap_value}: executive role for mid target"
            return cap_value, f"{reason}; {note}" if reason else note

    elif mode in ("senior", "lead", "staff", "principal"):
        # For senior engineers, cap low-level internships unless requested
        if is_junior_title(t) and not _SENIOR_RE.search(t):
            if score <= cap_value:
                return score, reason
            note = f"capped at {cap_value}: intern/entry role for senior target"
            return cap_value, f"{reason}; {note}" if reason else note

    return score, reason
