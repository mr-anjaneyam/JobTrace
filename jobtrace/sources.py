"""Job board adapters for JobTrace.

Supports 7 ATS platforms (Greenhouse, Lever, Ashby, Workable, Workday,
Oracle Recruiting Cloud, Atlassian) and aggregators (Remotive, Arbeitnow).
Features concurrent fetching and URL tracking parameter normalization.
"""
from __future__ import annotations

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

UA = {"User-Agent": "JobTrace/2.0 (personal career tracker)"}
TIMEOUT = 25

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_jid", "gh_src", "lever-source", "ashby_jid", "ref", "source", "fbclid", "gclid"
}


def normalize_url(raw_url: str | None) -> str:
    """Strip tracking query parameters and standardise trailing slashes."""
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        if not parsed.netloc:
            return raw_url.strip()
        filtered_q = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in TRACKING_PARAMS
        ]
        clean_query = urlencode(filtered_q)
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, clean_query, ""))
    except Exception:
        return raw_url.strip()


def _job_id(company: str, title: str, clean_url: str) -> str:
    seed = f"{company.strip().lower()}|{title.strip().lower()}|{clean_url}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _norm(
    company: str,
    title: str,
    raw_url: str,
    location: str = "",
    posted_at: float | None = None,
    description: str = "",
    source: str = "",
    domain: str = "",
) -> dict:
    url = normalize_url(raw_url)
    clean_title = (title or "").strip()
    return {
        "id": _job_id(company, clean_title, url),
        "company": company.strip(),
        "title": clean_title,
        "url": url,
        "location": (location or "").strip(),
        "posted_at": posted_at,
        "description": (description or "")[:6000],
        "source": source,
        "domain": domain,
        "matches_filter": True,
    }


def _get(url: str, params: dict | None = None) -> Any:
    r = requests.get(url, headers=UA, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(url: str, body: dict) -> Any:
    r = requests.post(
        url,
        headers={**UA, "Content-Type": "application/json", "Accept": "application/json"},
        json=body,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _epoch(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else float(value)
    try:
        from datetime import datetime
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


# --------------------------------------------------------------------------
# Board Adapters
# --------------------------------------------------------------------------

def greenhouse(name: str, slug: str) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        out.append(_norm(
            name, j.get("title"), j.get("absolute_url"), loc,
            _epoch(j.get("updated_at") or j.get("first_published")),
            j.get("content", ""), "greenhouse"
        ))
    return out


def lever(name: str, slug: str) -> list[dict]:
    data = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for j in data:
        cats = j.get("categories") or {}
        out.append(_norm(
            name, j.get("text"), j.get("hostedUrl"),
            cats.get("location", ""), _epoch(j.get("createdAt")),
            j.get("descriptionPlain", ""), "lever"
        ))
    return out


def ashby(name: str, slug: str) -> list[dict]:
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false")
    out = []
    for j in data.get("jobs", []):
        out.append(_norm(
            name, j.get("title"), j.get("jobUrl"), j.get("location", ""),
            _epoch(j.get("publishedAt")), j.get("descriptionPlain", ""), "ashby"
        ))
    return out


def workable(name: str, slug: str) -> list[dict]:
    data = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true")
    out = []
    for j in data.get("jobs", []):
        out.append(_norm(
            name, j.get("title"), j.get("url") or j.get("application_url"),
            j.get("location", ""), _epoch(j.get("published_on")),
            j.get("description", ""), "workable"
        ))
    return out


def workday(name: str, slug: str, max_jobs: int = 600) -> list[dict]:
    """slug can be 'tenant/wdN/site' or 'tenant/site'."""
    parts = slug.split("/")
    if len(parts) >= 3:
        tenant, wd, site = parts[0], parts[1], "/".join(parts[2:])
        base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    elif len(parts) == 2:
        tenant, site = parts
        base = f"https://{tenant}.myworkdayjobs.com"
    else:
        raise ValueError(f"Invalid Workday slug: '{slug}'. Expected 'tenant/wdN/site'")

    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    out: list[dict] = []

    for offset in range(0, max_jobs, 20):
        data = _post(api, {
            "appliedFacets": {},
            "limit": 20,
            "offset": offset,
            "searchText": "",
        })
        postings = data.get("jobPostings") or []
        if not postings:
            break
        for j in postings:
            path = j.get("externalPath") or ""
            bullet = " ".join(j.get("bulletFields") or [])
            posted = _epoch(j.get("postedOn"))
            out.append(_norm(
                name, j.get("title"), f"{base}/{site}{path}",
                j.get("locationsText", ""), posted, bullet, "workday"
            ))
        if len(postings) < 20:
            break
    return out


def oracle_cloud(name: str, slug: str, max_jobs: int = 800) -> list[dict]:
    """slug is 'host/siteNumber', e.g. 'eeho.fa.us2.oraclecloud.com/CX_1'."""
    if "/" not in slug:
        raise ValueError(f"Invalid Oracle slug: '{slug}'. Expected 'host/siteNumber'")
    host, site = slug.split("/", 1)
    out: list[dict] = []

    for offset in range(0, max_jobs, 200):
        url = (
            f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
            f"?onlyData=true&expand=requisitionList.secondaryLocations"
            f"&finder=findReqs;siteNumber={site},limit=200,offset={offset}"
        )
        items = (_get(url).get("items") or [{}])[0]
        reqs = items.get("requisitionList") or []
        if not reqs:
            break
        for j in reqs:
            rid = j.get("Id") or ""
            out.append(_norm(
                name, j.get("Title"),
                f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}",
                j.get("PrimaryLocation") or "", _epoch(j.get("PostedDate")),
                j.get("ShortDescriptionStr") or "", "oracle"
            ))
        if len(reqs) < 200:
            break
    return out


def atlassian_board(name: str, slug: str) -> list[dict]:
    data = _get("https://www.atlassian.com/endpoint/careers/listings")
    out = []
    for j in data:
        portal = j.get("portalJobPost") or {}
        locs = j.get("locations") or []
        out.append(_norm(
            name, j.get("title"), portal.get("portalUrl"),
            "; ".join(locs[:2]), _epoch(portal.get("updatedDate")),
            re.sub(r"<[^>]+>", " ", j.get("overview") or ""), "atlassian"
        ))
    return out


BOARDS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
    "workday": workday,
    "oracle": oracle_cloud,
    "atlassian": atlassian_board,
}


def fetch_company(entry: dict) -> tuple[list[dict], str | None]:
    """Fetch single company. Never raises exception."""
    board = entry.get("board", "greenhouse").lower()
    fn = BOARDS.get(board)
    if not fn:
        return [], f"unknown board '{board}'"
    try:
        jobs = fn(entry["name"], entry["slug"])
        domain = entry.get("domain", "")
        for j in jobs:
            j["domain"] = domain
        return jobs, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def fetch_all_companies(companies: list[dict], max_workers: int = 8) -> tuple[list[dict], list[str], list[str]]:
    """Concurrently fetch all watched companies.
    
    Returns: (all_jobs, healthy_companies, errors)
    """
    all_jobs: list[dict] = []
    healthy_companies: list[str] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(fetch_company, entry): entry for entry in companies}
        for fut in as_completed(future_map):
            entry = future_map[fut]
            try:
                jobs, err = fut.result()
                if err:
                    errors.append(f"{entry['name']}: {err}")
                else:
                    healthy_companies.append(entry["name"])
                    all_jobs.extend(jobs)
            except Exception as e:
                errors.append(f"{entry['name']}: {type(e).__name__}: {e}")

    return all_jobs, healthy_companies, errors


# --------------------------------------------------------------------------
# Aggregators (Remote & Discovery)
# --------------------------------------------------------------------------

def remotive(query: str, limit: int = 40) -> list[dict]:
    data = _get(f"https://remotive.com/api/remote-jobs?search={requests.utils.quote(query)}&limit={limit}")
    return [
        _norm(
            j.get("company_name", "?"), j.get("title"), j.get("url"),
            j.get("candidate_required_location", "Remote"),
            _epoch(j.get("publication_date")), j.get("description", ""), "remotive"
        )
        for j in data.get("jobs", [])[:limit]
    ]


def arbeitnow(query: str, limit: int = 40) -> list[dict]:
    data = _get("https://www.arbeitnow.com/api/job-board-api")
    q = query.lower()
    out = []
    for j in data.get("data", []):
        hay = f"{j.get('title','')} {' '.join(j.get('tags') or [])}".lower()
        if q in hay:
            out.append(_norm(
                j.get("company_name", "?"), j.get("title"), j.get("url"),
                j.get("location", ""), _epoch(j.get("created_at")),
                j.get("description", ""), "arbeitnow"
            ))
        if len(out) >= limit:
            break
    return out


def discover(queries: list[str], max_per_query: int = 40) -> tuple[list[dict], list[str]]:
    jobs, errors = [], []
    for q in queries:
        for fn in (remotive, arbeitnow):
            try:
                jobs.extend(fn(q, max_per_query))
            except Exception as e:
                errors.append(f"{fn.__name__}({q}): {type(e).__name__}: {e}")
            time.sleep(0.4)
    return jobs, errors
