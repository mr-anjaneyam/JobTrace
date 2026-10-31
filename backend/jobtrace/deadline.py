"""Application deadline extractor and elapsed checker for JobTrace."""
from __future__ import annotations

import re
import time
from datetime import datetime

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}


def extract_deadline(text: str) -> tuple[float | None, str]:
    """Extract deadline timestamp and human-readable text from job posting text.
    
    Returns:
        (deadline_at_epoch, deadline_text)
    """
    if not text:
        return None, ""

    clean = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", text)
    current_year = datetime.now().year

    # 1. Cued regex (Deadline: ..., Last date to apply: ..., Apply before: ..., Walk-in date: ...)
    m = re.search(
        r"(?:deadline|last\s+date\s+(?:to\s+apply|for\s+application)?|apply\s+before|valid\s+(?:till|until)|closing\s+date|ends\s+on|walk-?in\s+(?:drive\s+)?(?:date|on))\s*:?\s*([^\n\r;,]{3,50})",
        clean,
        re.I,
    )
    
    target_str = m.group(1).strip() if m else clean
    clean_val = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", target_str, flags=re.I)

    # Try format: "31 Oct 2026", "31 October 2026", "31 Oct", "Oct 31, 2026"
    m_date1 = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?\b", clean_val)
    if m_date1:
        day = int(m_date1.group(1))
        mon_str = m_date1.group(2).lower()
        year = int(m_date1.group(3)) if m_date1.group(3) else current_year
        if mon_str in MONTHS and 1 <= day <= 31:
            try:
                dt = datetime(year, MONTHS[mon_str], day, 23, 59, 59)
                epoch = dt.timestamp()
                formatted = dt.strftime("%d %b %Y")
                return epoch, formatted
            except ValueError:
                pass

    m_date2 = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:,?\s+(\d{4}))?\b", clean_val)
    if m_date2:
        mon_str = m_date2.group(1).lower()
        day = int(m_date2.group(2))
        year = int(m_date2.group(3)) if m_date2.group(3) else current_year
        if mon_str in MONTHS and 1 <= day <= 31:
            try:
                dt = datetime(year, MONTHS[mon_str], day, 23, 59, 59)
                epoch = dt.timestamp()
                formatted = dt.strftime("%d %b %Y")
                return epoch, formatted
            except ValueError:
                pass

    # Try format: DD/MM/YYYY or DD-MM-YYYY
    m_num = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", clean_val)
    if m_num:
        day = int(m_num.group(1))
        month = int(m_num.group(2))
        raw_yr = m_num.group(3)
        year = int("20" + raw_yr) if len(raw_yr) == 2 else int(raw_yr)
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                dt = datetime(year, month, day, 23, 59, 59)
                epoch = dt.timestamp()
                formatted = dt.strftime("%d %b %Y")
                return epoch, formatted
            except ValueError:
                pass

    if m:
        return None, m.group(1).strip()[:40]

    return None, ""


def is_deadline_elapsed(deadline_at: float | None) -> bool:
    """Returns True if the deadline has passed."""
    if deadline_at is None:
        return False
    return time.time() > deadline_at
