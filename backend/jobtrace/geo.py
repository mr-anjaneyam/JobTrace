"""Country-aware location matching, so a scan can be limited to one country.

A posting's location is free text ("Bengaluru, Karnataka, India", "IND Pune", "2 Locations",
"Remote - US"), so we match known place names rather than parse it.
"""
from __future__ import annotations

import re

_INDIA_PLACES = (
    "india", "bharat",
    # cities
    "bengaluru", "bangalore", "hyderabad", "secunderabad", "pune", "mumbai", "navi mumbai", "thane",
    "chennai", "gurugram", "gurgaon", "noida", "greater noida", "ghaziabad", "faridabad", "delhi",
    "new delhi", "ncr", "kolkata", "calcutta", "ahmedabad", "gandhinagar", "kochi", "cochin",
    "trivandrum", "thiruvananthapuram", "kozhikode", "coimbatore", "madurai", "chandigarh", "mohali",
    "panchkula", "jaipur", "indore", "bhopal", "lucknow", "kanpur", "nagpur", "nashik", "vadodara",
    "surat", "visakhapatnam", "vizag", "vijayawada", "bhubaneswar", "mysuru", "mysore", "mangalore",
    "mangaluru", "hubli", "pondicherry", "puducherry", "guwahati", "patna", "ranchi", "dehradun",
    "raipur", "jamshedpur",
    # states
    "karnataka", "maharashtra", "telangana", "tamil nadu", "kerala", "haryana", "uttar pradesh",
    "west bengal", "gujarat", "rajasthan", "andhra pradesh", "odisha", "madhya pradesh",
)

# country key -> aliases accepted in config, place names, upper-case codes seen in feeds
# ("IN" is left out on purpose: in US addresses it means Indiana)
COUNTRIES: dict[str, dict] = {
    "india": {"aliases": ("india", "ind"), "places": _INDIA_PLACES, "codes": ("IND",)},
}

COUNTRY_LABELS = {"india": "India"}

_REMOTE_WORDS = re.compile(r"\b(remote|anywhere|worldwide|global|work from home|wfh|distributed|hybrid|flexible)\b")
_REGION_WORDS = {"apac", "asia", "pacific", "asia pacific", "and", "or", "the", "of", "only", "based"}
_UNKNOWN = re.compile(r"^(\d+\s+locations?|multiple locations?|various( locations)?|n/?a|unknown|none|tbd)$")


def normalize_country(value: str | None) -> str:
    """Return the preset key for a configured country, or the lowercase text when there is no preset."""
    v = (value or "").strip().lower()
    for key, spec in COUNTRIES.items():
        if v == key or v in spec["aliases"]:
            return key
    return v


def _place_regex(country: str) -> re.Pattern[str]:
    spec = COUNTRIES.get(country)
    names = spec["places"] if spec else (country,)
    return re.compile(r"\b(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")


_PLACE_CACHE: dict[str, re.Pattern[str]] = {}


def _has_country(location: str, country: str) -> bool:
    pat = _PLACE_CACHE.get(country) or _PLACE_CACHE.setdefault(country, _place_regex(country))
    if pat.search(location.lower()):
        return True
    return any(re.search(rf"\b{code}\b", location) for code in COUNTRIES.get(country, {}).get("codes", ()))


def is_unknown_location(location: str | None) -> bool:
    text = (location or "").strip().lower()
    return not text or bool(_UNKNOWN.match(text))


def is_generic_remote(location: str) -> bool:
    """Remote or global text that does not tie the role to any single country."""
    text = location.lower()
    if not _REMOTE_WORDS.search(text):
        return False
    rest = _REMOTE_WORDS.sub(" ", text)
    tokens = [t for t in re.split(r"[^a-z]+", rest) if t]
    return all(t in _REGION_WORDS for t in tokens)


def location_in_country(location: str | None, country: str, include_remote: bool = False) -> bool:
    """True if the posting can be worked from `country`.

    Unknown locations (blank, "2 Locations") are kept: we cannot prove they are elsewhere.
    Global remote roles are kept only when `include_remote` is set.
    """
    key = normalize_country(country)
    if not key:
        return True
    if is_unknown_location(location):
        return True
    text = location or ""
    if _has_country(text, key):
        return True
    return include_remote and is_generic_remote(text)


def matches_target(target: str, location: str) -> bool:
    """A target location is either a country (India) or any text found as a whole word (Pune)."""
    t = (target or "").strip()
    if not t:
        return False
    key = normalize_country(t)
    if key in COUNTRIES and t.lower() == key:
        return _has_country(location, key)
    return bool(re.search(rf"\b{re.escape(t.lower())}\b", (location or "").lower()))


def target_locations(cfg: dict) -> list[str]:
    """Locations the candidate can work from, with the filter country always included."""
    cand = list((cfg.get("candidate") or {}).get("locations") or [])
    filters = cfg.get("filters") or {}
    country = (filters.get("country") or "").strip()
    if not cand:
        cand = list(filters.get("locations") or [])
    if country and country.lower() not in {c.lower() for c in cand}:
        cand.append(COUNTRY_LABELS.get(normalize_country(country), country))
    return cand
