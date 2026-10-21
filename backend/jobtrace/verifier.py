"""Intelligent job liveness and archival verifier.

Detects closed, archived, and elapsed job postings across Remotive, Arbeitnow,
Greenhouse, Ashby, Lever, Workday, Oracle, and other boards.
"""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests

if TYPE_CHECKING:
    from .store import Store

logger = logging.getLogger("jobtrace.verifier")

# Substring and regex patterns indicating a job posting has been archived, closed, or filled
ARCHIVED_PATTERNS = [
    re.compile(r"this job listing is archived", re.IGNORECASE),
    re.compile(r"is archived,?\s*sorry", re.IGNORECASE),
    re.compile(r"job listing is archived", re.IGNORECASE),
    re.compile(r"no longer available", re.IGNORECASE),
    re.compile(r"position has been (filled|closed)", re.IGNORECASE),
    re.compile(r"this position is closed", re.IGNORECASE),
    re.compile(r"job (has )?expired", re.IGNORECASE),
    re.compile(r"listing (has )?expired", re.IGNORECASE),
    re.compile(r"no longer accepting applications", re.IGNORECASE),
    re.compile(r"this role is no longer open", re.IGNORECASE),
    re.compile(r"this posting has been removed", re.IGNORECASE),
    re.compile(r"job not found", re.IGNORECASE),
    re.compile(r"requisition is (closed|inactive)", re.IGNORECASE),
    re.compile(r"the page you are looking for does not exist", re.IGNORECASE),
]

# Browser headers to ensure job boards respond with real content rather than 403 Bot blocks
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def check_url_liveness(url: str, timeout: float = 4.0) -> tuple[bool, str]:
    """Check if a job posting URL is live and accepting applications.
    
    Returns:
        (is_active: bool, reason: str)
    """
    if not url or not url.startswith("http"):
        return True, "No URL to verify"

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    try:
        # Use stream=True to avoid loading large media or whole pages into memory
        with requests.get(
            url,
            headers=BROWSER_HEADERS,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        ) as resp:
            # 1. HTTP Status Code Checks
            if resp.status_code in (404, 410):
                return False, f"Listing removed (HTTP {resp.status_code})"

            final_url = resp.url.lower()

            # 2. Redirect-based archival checks (e.g. Remotive redirects dead job URLs to category index)
            if "remotive.com" in domain:
                # If original URL had a specific job slug, but redirected to root or general search
                original_path = parsed.path.rstrip("/")
                final_path = urlparse(final_url).path.rstrip("/")
                if original_path != final_path and (
                    final_path in ("", "/remote-jobs", "/remote-jobs/software-development")
                    or not re.search(r"-\d+$", final_path)
                ):
                    return False, "Redirected to category index - listing archived"

            # 3. Read first 32KB of HTML to scan for archival and closure notices
            try:
                chunk = resp.raw.read(32768, decode_content=True)
                text = chunk.decode("utf-8", errors="ignore")
            except Exception:
                text = resp.text[:32768] if hasattr(resp, "text") else ""

            for pattern in ARCHIVED_PATTERNS:
                m = pattern.search(text)
                if m:
                    snippet = m.group(0).strip()
                    return False, f"Job board notice: '{snippet}'"

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


def discard_elapsed_jobs(store: Store, max_age_days: int = 14) -> list[str]:
    """Discard aggregator jobs whose posted_at or last_seen exceeds the maximum allowed age.
    
    Returns list of closed job IDs.
    """
    cutoff = time.time() - (max_age_days * 86400)
    now = time.time()

    # Query all open jobs from aggregators or unmonitored feeds where posted_at or last_seen is elapsed
    rows = store.db.execute(
        """SELECT id, company, title, posted_at, last_seen, source
           FROM jobs
           WHERE closed_at IS NULL
             AND source IN ('remotive', 'arbeitnow')
             AND (
                 (posted_at IS NOT NULL AND posted_at < ?)
                 OR (posted_at IS NULL AND last_seen < ?)
             )""",
        (cutoff, cutoff),
    ).fetchall()

    closed_ids = []
    for r in rows:
        jid = r["id"]
        store.db.execute(
            "UPDATE jobs SET closed_at = ?, reason = ? WHERE id = ?",
            (now, f"Elapsed posting: older than {max_age_days} days", jid),
        )
        closed_ids.append(jid)

    if closed_ids:
        store.db.commit()
        logger.info(f"Discarded {len(closed_ids)} elapsed jobs older than {max_age_days} days.")

    return closed_ids


def verify_and_discard_jobs(
    store: Store,
    job_ids: list[str] | None = None,
    max_workers: int = 8,
    limit: int = 80,
) -> dict:
    """Check a batch of active jobs and discard any that are confirmed archived/closed.
    
    Returns:
        {"checked": int, "closed": list[dict]}
    """
    if job_ids:
        marks = ",".join("?" * len(job_ids))
        rows = store.db.execute(
            f"SELECT id, company, title, url, source FROM jobs WHERE id IN ({marks}) AND closed_at IS NULL",
            tuple(job_ids),
        ).fetchall()
    else:
        # Prioritize aggregators (Remotive, Arbeitnow) and highest scoring roles
        rows = store.db.execute(
            """SELECT id, company, title, url, source FROM jobs
               WHERE closed_at IS NULL AND url IS NOT NULL AND length(url) > 5
               ORDER BY 
                 CASE WHEN source IN ('remotive', 'arbeitnow') THEN 0 ELSE 1 END,
                 score DESC NULLS LAST
               LIMIT ?""",
            (limit,),
        ).fetchall()

    jobs_to_check = [dict(r) for r in rows if r["url"]]
    if not jobs_to_check:
        return {"checked": 0, "closed": []}

    closed_results: list[dict] = []
    now = time.time()

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
                    logger.info(f"Discarded archived job: {job['company']} - {job['title']} ({reason})")
            except Exception as e:
                logger.debug(f"Error checking job {job['id']}: {e}")

    if closed_results:
        store.db.commit()

    return {
        "checked": len(jobs_to_check),
        "closed_count": len(closed_results),
        "closed": closed_results,
    }
