"""Intelligent job liveness, content closure, and deadline verifier.

Detects closed, archived, elapsed, and full job postings across Remotive, Arbeitnow,
Greenhouse, Ashby, Lever, Workday, Oracle, and generic web boards.
Uses deterministic content parsing (0 AI tokens) to detect closed postings even on HTTP 200 OK.
"""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests

from . import applog
from .deadline import is_deadline_elapsed

if TYPE_CHECKING:
    from .store import Store

logger = logging.getLogger("jobtrace.verifier")

# Substring and regex patterns indicating a job posting has been archived, closed, filled, or does not exist
# Checked against response text on HTTP 200 OK to catch silent redirects / soft-404s without wasting AI tokens.
ARCHIVED_PATTERNS = [
    re.compile(r"this\s+job\s+listing\s+is\s+archived", re.IGNORECASE),
    re.compile(r"is\s+archived,?\s*sorry", re.IGNORECASE),
    re.compile(r"job\s+listing\s+is\s+archived", re.IGNORECASE),
    re.compile(r"this\s+job\s+opening\s+has\s+been\s+archived", re.IGNORECASE),
    re.compile(r"no\s+longer\s+available", re.IGNORECASE),
    re.compile(r"position\s+has\s+been\s+(?:filled|closed)", re.IGNORECASE),
    re.compile(r"this\s+position\s+is\s+closed", re.IGNORECASE),
    re.compile(r"this\s+(?:position|role|job|requisition)\s+is\s+(?:currently\s+)?full", re.IGNORECASE),
    re.compile(r"this\s+is\s+currently\s+full", re.IGNORECASE),
    re.compile(r"job\s+(?:has\s+)?expired", re.IGNORECASE),
    re.compile(r"listing\s+(?:has\s+)?expired", re.IGNORECASE),
    re.compile(r"no\s+longer\s+accepting\s+applications", re.IGNORECASE),
    re.compile(r"this\s+role\s+is\s+no\s+longer\s+open", re.IGNORECASE),
    re.compile(r"this\s+posting\s+has\s+been\s+removed", re.IGNORECASE),
    re.compile(r"job\s+not\s+found", re.IGNORECASE),
    re.compile(r"we\s+couldn't\s+find\s+the\s+job", re.IGNORECASE),
    re.compile(r"requisition\s+is\s+(?:closed|inactive)", re.IGNORECASE),
    re.compile(r"this\s+page\s+(?:doesn't|does\s+not)\s+exist", re.IGNORECASE),
    re.compile(r"the\s+page\s+you\s+are\s+looking\s+for\s+does\s+not\s+exist", re.IGNORECASE),
    re.compile(r"page\s+not\s+found", re.IGNORECASE),
    re.compile(r"applications?\s+(?:for\s+this\s+(?:role|job)\s+)?are\s+closed", re.IGNORECASE),
    re.compile(r"application\s+window\s+is\s+closed", re.IGNORECASE),
    re.compile(r"\"jobPostingInfo\"\s*:\s*null", re.IGNORECASE),
]

# Browser headers to ensure job boards respond with real content rather than 403 Bot blocks
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def check_url_liveness(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Check if a job posting URL is live and accepting applications.
    
    Checks both HTTP status code and response content (first 64KB) for closure phrases.
    Uses 0 AI tokens.

    Returns:
        (is_active: bool, reason: str)
    """
    if not url or not url.startswith("http"):
        return True, "No URL to verify"

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    try:
        # Use stream=True to read only the initial 64KB
        with applog.traced(
            "verify",
            requests.get,
            url,
            bodies=False,
            headers=BROWSER_HEADERS,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        ) as resp:
            # 1. HTTP Status Code Checks
            if resp.status_code in (404, 410):
                return False, f"Listing removed (HTTP {resp.status_code})"

            final_url = resp.url.lower()

            # 2. Redirect-based archival checks
            if "remotive.com" in domain:
                original_path = parsed.path.rstrip("/")
                final_path = urlparse(final_url).path.rstrip("/")
                if original_path != final_path and (
                    final_path in ("", "/remote-jobs", "/remote-jobs/software-development")
                    or not re.search(r"-\d+$", final_path)
                ):
                    return False, "Redirected to category index - listing archived"

            if "greenhouse.io" in domain or "lever.co" in domain:
                # If redirected to main careers index without job token
                orig_slug = parsed.path.strip("/").split("/")[-1]
                if orig_slug and orig_slug not in final_url and ("careers" in final_url or "jobs" in final_url):
                    return False, "Redirected away from job posting"

            # 3. Read first 64KB of content to scan for archival and closure notices (0 AI tokens)
            try:
                chunk = resp.raw.read(65536, decode_content=True)
                text = chunk.decode("utf-8", errors="ignore")
            except Exception:
                text = resp.text[:65536] if hasattr(resp, "text") else ""

            for pattern in ARCHIVED_PATTERNS:
                m = pattern.search(text)
                if m:
                    snippet = m.group(0).strip()
                    return False, f"Closed notice: '{snippet}'"

            # 4. If status code is valid and no archived patterns found
            if 200 <= resp.status_code < 400:
                return True, "Active"

            # If 403 or other rate limit, don't falsely discard valid listings
            return True, f"HTTP {resp.status_code} (assumed active)"

    except (requests.Timeout, requests.ConnectionError):
        # On network timeout or connection error, do not discard (prevent false positives if offline)
        return True, "Connection timeout (preserved)"
    except Exception as e:
        logger.debug(f"Liveness check exception for {url}: {e}")
        return True, "Unchecked"


def verify_and_discard_jobs(
    store: Store,
    job_ids: list[str] | None = None,
    max_workers: int = 8,
    limit: int = 60,
    cadence_hours: float = 12.0,
) -> dict:
    """Check active jobs:
    
    1. Instantly discards jobs whose application deadline has elapsed.
    2. Pings active jobs without a deadline every `cadence_hours` (default 12 hrs).
    3. Scans content for closures (e.g. 'position filled', 'currently full', 'page doesn't exist') with 0 AI tokens.
    
    Returns:
        {"checked": int, "closed_count": int, "closed": list[dict]}
    """
    closed_results: list[dict] = []
    now = time.time()

    # Step 1: Immediately close elapsed deadlines
    elapsed = store.close_elapsed_deadlines(now=now)
    for el in elapsed:
        reason = f"Application deadline elapsed ({el.get('deadline_text') or 'passed'})"
        closed_results.append({
            "id": el["id"],
            "company": el["company"],
            "title": el["title"],
            "reason": reason,
        })
        logger.info("Discarded expired deadline job: %s - %s (%s)", el["company"], el["title"], reason)

    # Step 2: Select candidate jobs to ping
    if job_ids:
        marks = ",".join("?" * len(job_ids))
        rows = store.db.execute(
            f"SELECT id, company, title, url, source, deadline_at FROM jobs WHERE id IN ({marks}) AND closed_at IS NULL",
            tuple(job_ids),
        ).fetchall()
        jobs_to_check = [dict(r) for r in rows if r["url"]]
    else:
        # Check active jobs without deadline that haven't been checked in cadence_hours (12h)
        jobs_to_check = store.get_jobs_for_liveness_check(limit=limit, cadence_hours=cadence_hours)

    if not jobs_to_check:
        return {
            "checked": len(elapsed),
            "closed_count": len(closed_results),
            "closed": closed_results,
        }

    # Step 3: Check liveness concurrently
    live_ids: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(check_url_liveness, j["url"]): j
            for j in jobs_to_check
        }

        for future in as_completed(future_map):
            job = future_map[future]
            try:
                is_active, reason = future.result()
                if not is_active:
                    store.db.execute(
                        "UPDATE jobs SET closed_at = ?, reason = ? WHERE id = ?",
                        (now, reason, job["id"]),
                    )
                    closed_results.append({
                        "id": job["id"],
                        "company": job["company"],
                        "title": job["title"],
                        "url": job["url"],
                        "reason": reason,
                    })
                    logger.info("Discarded archived job: %s - %s (%s)", job["company"], job["title"], reason)
                else:
                    live_ids.append(job["id"])
            except Exception as e:
                logger.debug("Error checking job %s: %s", job["id"], e)
                live_ids.append(job["id"])

    # Update last_verified_at timestamp on checked live jobs so they won't be pinged again for 12 hours
    if live_ids:
        store.touch_liveness_verified(live_ids, timestamp=now)

    if closed_results:
        store.db.commit()

    return {
        "checked": len(jobs_to_check) + len(elapsed),
        "closed_count": len(closed_results),
        "closed": closed_results,
    }
