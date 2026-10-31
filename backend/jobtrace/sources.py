"""Job board adapters for JobTrace.

Supports 7 ATS platforms (Greenhouse, Lever, Ashby, Workable, Workday,
Oracle Recruiting Cloud, Atlassian) and aggregators (Remotive, Arbeitnow).
Features concurrent fetching and URL tracking parameter normalization.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from . import applog

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
    from jobtrace.sanitize import clean_html_text
    url = normalize_url(raw_url)
    clean_title = (title or "").strip()
    return {
        "id": _job_id(company, clean_title, url),
        "company": company.strip(),
        "title": clean_title,
        "url": url,
        "location": (location or "").strip(),
        "posted_at": posted_at,
        "description": clean_html_text(description)[:6000],
        "source": source,
        "domain": domain,
        "matches_filter": True,
    }


def _get(url: str, params: dict | None = None) -> Any:
    r = applog.traced("portal", requests.get, url, headers=UA, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(url: str, body: dict) -> Any:
    r = applog.traced(
        "portal",
        requests.post,
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


def fetch_workday_description_by_url(raw_url: str) -> str:
    """Fetch full job description for a Workday posting from its public URL."""
    try:
        import html as html_lib
        parsed = urlparse(raw_url)
        host = parsed.netloc
        host_parts = host.split(".")
        tenant = host_parts[0]
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            site = path_parts[0]
            subpath = "/" + "/".join(path_parts[1:])
            cxs_url = f"{parsed.scheme}://{host}/wday/cxs/{tenant}/{site}{subpath}"
            data = _get(cxs_url)
            raw = (data.get("jobPostingInfo") or {}).get("jobDescription") or ""
            if raw:
                clean = html_lib.unescape(raw)
                clean = re.sub(r"<[^>]+>", " ", clean)
                return re.sub(r"\s+", " ", clean).strip()
    except Exception:
        pass
    return ""


def workday(name: str, slug: str, max_jobs: int = 600, keyword: str = "") -> list[dict]:
    """slug can be 'tenant/wdN/site' or 'tenant/site'. `keyword` narrows the search server side."""
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
            "searchText": keyword,
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


def oracle_cloud(name: str, slug: str, max_jobs: int = 800, keyword: str = "") -> list[dict]:
    """slug is 'host/siteNumber', e.g. 'eeho.fa.us2.oraclecloud.com/CX_1'."""
    if "/" not in slug:
        raise ValueError(f"Invalid Oracle slug: '{slug}'. Expected 'host/siteNumber'")
    host, site = slug.split("/", 1)
    out: list[dict] = []
    kw = f"keyword={requests.utils.quote(keyword)}," if keyword else ""

    for offset in range(0, max_jobs, 200):
        url = (
            f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
            f"?onlyData=true&expand=requisitionList.secondaryLocations"
            f"&finder=findReqs;siteNumber={site},{kw}limit=200,offset={offset}"
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
        parts = [
            j.get("overview") or "",
            j.get("responsibilities") or "",
            j.get("qualifications") or "",
        ]
        full_text = re.sub(r"<[^>]+>", " ", " ".join(p for p in parts if p))
        out.append(_norm(
            name, j.get("title"), portal.get("portalUrl"),
            "; ".join(locs[:2]), _epoch(portal.get("updatedDate")),
            full_text, "atlassian"
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

# Boards whose API can filter by a search word, used to pull only one country's roles
SEARCHABLE_BOARDS = {"workday", "oracle"}


def fetch_company(entry: dict, keyword: str = "") -> tuple[list[dict], str | None]:
    """Fetch single company. Never raises exception.

    `keyword` (e.g. a country name) is applied server side on the boards that support search.
    """
    board = entry.get("board", "greenhouse").lower()
    fn = BOARDS.get(board)
    if not fn:
        return [], f"unknown board '{board}'"
    try:
        if keyword and board in SEARCHABLE_BOARDS:
            jobs = fn(entry["name"], entry["slug"], keyword=keyword)
        else:
            jobs = fn(entry["name"], entry["slug"])
        domain = entry.get("domain", "")
        for j in jobs:
            j["domain"] = domain
        return jobs, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


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



# --------------------------------------------------------------------------
# Direct URL Ingestion & Live Scraper
# --------------------------------------------------------------------------

def fetch_job_details_from_url(raw_url: str) -> dict | None:
    """Fetch live job details (title, company, location, description) directly from the URL.

    Inspects the actual destination page/API (Workday, Greenhouse, Lever, Ashby, or generic web)
    so JobTrace does not have to rely on truncated or dirty Telegram/intermediary post summaries.
    """
    if not raw_url:
        return None
    url = normalize_url(raw_url)
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    # 1. Workday ATS
    if "myworkdayjobs.com" in host:
        try:
            import html as html_lib
            host_parts = host.split(".")
            tenant = host_parts[0]
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 2:
                if re.match(r"^[a-z]{2}(?:-[A-Z]{2})?$", path_parts[0], re.I) and len(path_parts) >= 3:
                    site = path_parts[1]
                    subpath = "/" + "/".join(path_parts[2:])
                else:
                    site = path_parts[0]
                    subpath = "/" + "/".join(path_parts[1:])
                cxs_url = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}{subpath}"
                data = _get(cxs_url)
                info = data.get("jobPostingInfo") or {}
                hiring = data.get("hiringOrganization") or {}
                raw_co = hiring.get("name") or tenant
                co = re.sub(r"^\d+\s*", "", raw_co)
                co = re.sub(r"\s*(?:com|\.com|India|Pvt|Ltd|Private|Limited).*$", "", co, flags=re.I).strip() or tenant.title()
                co = co.title() if co.islower() else co
                raw_desc = info.get("jobDescription") or ""
                clean_desc = html_lib.unescape(raw_desc)
                clean_desc = re.sub(r"<[^>]+>", " ", clean_desc)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                title = (info.get("title") or "").strip()
                loc = (info.get("location") or "").strip()
                posted_epoch = _epoch(info.get("startDate") or info.get("postedOn"))
                if title or clean_desc:
                    return {
                        "title": title or "Untitled Role",
                        "company": co,
                        "location": loc,
                        "description": clean_desc,
                        "url": url,
                        "posted_at": posted_epoch,
                        "source": "workday",
                    }
        except Exception as e:
            applog.log.warning("Workday live extraction failed for %s: %s", url, e)

    # 2. Greenhouse
    gh_match = re.search(r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if gh_match:
        try:
            import html as html_lib
            board, jid = gh_match.group(1), gh_match.group(2)
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}"
            data = _get(api_url)
            content = html_lib.unescape(data.get("content") or "")
            content = re.sub(r"<[^>]+>", " ", content)
            content = re.sub(r"\s+", " ", content).strip()
            title = (data.get("title") or "").strip()
            co = (data.get("company_name") or board.title()).strip()
            loc = ((data.get("location") or {}).get("name") or "").strip()
            if title or content:
                return {
                    "title": title or "Untitled Role",
                    "company": co,
                    "location": loc,
                    "description": content,
                    "url": url,
                    "source": "greenhouse",
                }
        except Exception as e:
            applog.log.warning("Greenhouse live extraction failed for %s: %s", url, e)

    # 3. Lever
    lever_match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9-]+)", url)
    if lever_match:
        try:
            import html as html_lib
            board, jid = lever_match.group(1), lever_match.group(2)
            api_url = f"https://api.lever.co/v0/postings/{board}/{jid}"
            data = _get(api_url)
            desc = data.get("descriptionPlain") or ""
            if not desc:
                desc = html_lib.unescape(data.get("description") or "")
                desc = re.sub(r"<[^>]+>", " ", desc)
                desc = re.sub(r"\s+", " ", desc).strip()
            title = (data.get("text") or "").strip()
            cats = data.get("categories") or {}
            loc = (cats.get("location") or "").strip()
            if title or desc:
                return {
                    "title": title or "Untitled Role",
                    "company": board.title(),
                    "location": loc,
                    "description": desc,
                    "url": url,
                    "source": "lever",
                }
        except Exception as e:
            applog.log.warning("Lever live extraction failed for %s: %s", url, e)

    # 4. Ashby
    ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([a-f0-9-]+)", url)
    if ashby_match:
        try:
            import html as html_lib
            board, jid = ashby_match.group(1), ashby_match.group(2)
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{board}/posting/{jid}"
            data = _get(api_url)
            desc = html_lib.unescape(data.get("descriptionHtml") or "")
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            title = (data.get("title") or "").strip()
            co = (data.get("companyName") or board.title()).strip()
            loc = (data.get("locationName") or "").strip()
            if title or desc:
                return {
                    "title": title or "Untitled Role",
                    "company": co,
                    "location": loc,
                    "description": desc,
                    "url": url,
                    "source": "ashby",
                }
        except Exception as e:
            applog.log.warning("Ashby live extraction failed for %s: %s", url, e)

    # 5. Generic Web / Career Page Fallback
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            },
            timeout=15,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()

            title = ""
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif soup.title and soup.title.string:
                title = soup.title.string.strip()
            elif soup.h1:
                title = soup.h1.get_text().strip()

            co = ""
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                co = og_site["content"].strip()
            else:
                co_domain = parsed.netloc.replace("www.", "").split(".")[0]
                co = co_domain.title()

            loc = ""
            og_loc = soup.find("meta", property="og:locality") or soup.find("meta", {"name": "geo.placename"})
            if og_loc and og_loc.get("content"):
                loc = og_loc["content"].strip()

            main_el = soup.find("main") or soup.find("article") or soup.find(id=re.compile(r"job|content|detail", re.I)) or soup.body
            text = main_el.get_text(separator=" ", strip=True) if main_el else soup.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()

            if title or text:
                return {
                    "title": title or "Untitled Role",
                    "company": co,
                    "location": loc,
                    "description": text[:8000],
                    "url": url,
                    "source": "web",
                }
    except Exception as e:
        applog.log.warning("Generic web live extraction failed for %s: %s", url, e)

    return None
