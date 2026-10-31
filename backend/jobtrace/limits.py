"""Numeric settings the user can change at runtime: defaults and allowed ranges in one place."""
from __future__ import annotations

# (section, key) -> (default, minimum, maximum)
INT_SETTINGS: dict[tuple[str, str], tuple[int, int, int]] = {
    ("llm", "daily_token_limit"): (500_000, 1_000, 1_000_000_000),
    ("llm", "max_to_score"): (5_000, 1, 100_000),
    ("llm", "batch_size"): (25, 1, 100),
    ("llm", "tokens_per_batch"): (3_400, 500, 100_000),
    ("llm", "triage_floor"): (3, 0, 10),
    ("alerts", "max_per_alert"): (15, 1, 50),
    ("digest", "max_jobs"): (35, 1, 200),
    ("storage", "retention_days"): (90, 0, 3_650),
    ("logging", "retention_days"): (14, 1, 365),
    ("logging", "max_body_chars"): (4_000, 0, 100_000),
}


def clamp(section: str, key: str, value: object) -> int | None:
    """Parse and clamp a user supplied number; None when it is not a number."""
    _, lo, hi = INT_SETTINGS[(section, key)]
    try:
        n = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return min(hi, max(lo, n))


def get(cfg: dict, section: str, key: str) -> int:
    """Current value from the config, falling back to the default when missing or invalid."""
    default = INT_SETTINGS[(section, key)][0]
    raw = (cfg.get(section) or {}).get(key)
    if raw is None:
        return default
    n = clamp(section, key, raw)
    return default if n is None else n
