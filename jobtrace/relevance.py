"""Multi-dimensional relevance gate for JobTrace.

Ensures roles in the wrong field don't score highly purely on seniority or location.
Requires both skills and domain sub-scores to be weak before capping.
"""
from __future__ import annotations

SKILLS_FLOOR = 60
DOMAIN_FLOOR = 60
DEFAULT_CAP = 3
CAP = DEFAULT_CAP


def is_irrelevant(breakdown: dict | None, skills_floor: int = SKILLS_FLOOR, domain_floor: int = DOMAIN_FLOOR) -> bool:
    if not breakdown:
        return False
    try:
        skills = int(breakdown.get("skills", 0))
        domain = int(breakdown.get("domain", 0))
    except (TypeError, ValueError):
        return False

    # All zeros indicates no model breakdown was produced, not a bad fit
    if skills == 0 and domain == 0 and not any(breakdown.values()):
        return False

    return skills < skills_floor and domain < domain_floor


def apply_cap(
    score: int,
    breakdown: dict | None,
    reason: str = "",
    skills_floor: int = SKILLS_FLOOR,
    domain_floor: int = DOMAIN_FLOOR,
    cap_value: int = DEFAULT_CAP,
) -> tuple[int, str]:
    if score <= cap_value:
        return score, reason
    if is_irrelevant(breakdown, skills_floor, domain_floor):
        note = f"capped at {cap_value}: wrong field (skills & domain mismatch)"
        return cap_value, f"{reason}; {note}" if reason else note
    return score, reason
