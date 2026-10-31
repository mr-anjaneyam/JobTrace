"""Salary and compensation parser for JobTrace.

Extracts compensation ranges (LPA, monthly INR, USD annual/hourly) from job descriptions
and structured payloads.
"""
from __future__ import annotations

import re


def extract_salary(text: str) -> tuple[float | None, float | None, str, str]:
    """Extract salary min, max, currency, and raw text snippet from text.
    
    Returns:
        (salary_min, salary_max, currency, salary_text)
    """
    if not text:
        return None, None, "", ""

    # Normalize dashes and non-breaking spaces
    clean = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", text)
    clean = clean.replace("\xa0", " ")

    # 1. LPA / Lakhs pattern (e.g. ₹4.8-5.3 LPA, ₹6.5 LPA - ₹9 LPA, 12 - 18 Lakhs, INR 6 LPA, 8 LPA)
    m = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l)?\s*(?:-|to)\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l)\b",
        clean,
        re.I,
    )
    if m:
        min_val = float(m.group(1))
        max_val = float(m.group(2))
        return min_val, max_val, "INR_LPA", f"₹{min_val:g}–{max_val:g} LPA"

    m_single_lpa = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l)\b",
        clean,
        re.I,
    )
    if m_single_lpa:
        val = float(m_single_lpa.group(1))
        return val, val, "INR_LPA", f"₹{val:g} LPA"

    # 2. USD pattern (e.g. $120k - $150k, $90,000 - $120,000, $130,000 / year)
    def _parse_usd(s: str) -> float:
        s = s.lower().replace(",", "").strip()
        if s.endswith("k"):
            return float(s[:-1]) * 1000
        val = float(s)
        if val < 500:  # e.g. 120 -> 120k
            return val * 1000
        return val

    m_usd = re.search(
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?k?)\s*(?:-|to)\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?k?)",
        clean,
        re.I,
    )
    if m_usd:
        try:
            min_val = _parse_usd(m_usd.group(1))
            max_val = _parse_usd(m_usd.group(2))
            min_k = round(min_val / 1000)
            max_k = round(max_val / 1000)
            return min_val, max_val, "USD", f"${min_k:g}k–${max_k:g}k/yr"
        except ValueError:
            pass

    m_single_usd = re.search(
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?k?)\s*(?:/|\s*per\s*)?\s*(?:year|yr|annum)\b",
        clean,
        re.I,
    )
    if m_single_usd:
        try:
            val = _parse_usd(m_single_usd.group(1))
            val_k = round(val / 1000)
            return val, val, "USD", f"${val_k:g}k/yr"
        except ValueError:
            pass

    # 3. Monthly INR pattern (e.g. ₹35,000 - ₹50,000 / month, 25k - 40k per month, ₹30,000/mo)
    m_mo = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(?:k|thousand)?\s*(?:-|to)\s*(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(?:k|thousand)?\s*(?:/|\s*per\s*)\s*(?:month|mo)\b",
        clean,
        re.I,
    )
    if m_mo:
        raw_min = m_mo.group(1).replace(",", "")
        raw_max = m_mo.group(2).replace(",", "")
        try:
            min_val = float(raw_min)
            max_val = float(raw_max)
            return min_val, max_val, "INR_MONTH", f"₹{min_val:g}–{max_val:g}/mo"
        except ValueError:
            pass

    m_single_mo = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(?:k|thousand)?\s*(?:/|\s*per\s*)\s*(?:month|mo)\b",
        clean,
        re.I,
    )
    if m_single_mo:
        raw = m_single_mo.group(1).replace(",", "")
        try:
            val = float(raw)
            return val, val, "INR_MONTH", f"₹{val:g}/mo"
        except ValueError:
            pass

    # 4. Fallback search for salary keyword line
    m_kw = re.search(
        r"(?:salary|compensation|ctc|stipend|pay\s+range)\s*:?\s*([^\n\r;,]{3,40})",
        clean,
        re.I,
    )
    if m_kw:
        snippet = m_kw.group(1).strip()
        if re.search(r"\d", snippet):
            return None, None, "UNKNOWN", snippet

    return None, None, "", ""
