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


def apply_location_cap(
    score: int,
    location_str: str,
    target_locations: list[str] | None,
    breakdown: dict | None = None,
    reason: str = "",
    cap_value: int = DEFAULT_CAP,
) -> tuple[int, str]:
    """Cap score if candidate has target locations and job is confirmed onsite in an unapproved location."""
    if not target_locations or score <= cap_value:
        return score, reason

    loc = (location_str or "").strip().lower()
    if not loc or loc in ("n/a", "unknown", "none"):
        return score, reason

    remote_keywords = ("remote", "anywhere", "work from home", "distributed", "telecommute")
    if any(k in loc for k in remote_keywords):
        return score, reason

    import re
    cleaned_targets = [t.strip().lower() for t in target_locations if t.strip()]
    if any(re.search(rf"\b{re.escape(t)}\b", loc) for t in cleaned_targets):
        return score, reason

    if breakdown is not None and "location" in breakdown:
        breakdown["location"] = min(breakdown.get("location", 100), 15)

    note = f"capped at {cap_value}: location mismatch (onsite in {location_str})"
    return cap_value, f"{reason}; {note}" if reason else note
