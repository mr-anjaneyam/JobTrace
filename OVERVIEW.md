# JobTrace Architecture & System Overview

> **A high-reliability stateful career tracker, multi-backend LLM matcher, and Telegram notification engine.**

---

## 1. System Vision & Architecture

JobTrace is designed to solve the fundamental fatigue of manual job hunting:
- Instead of repeatedly visiting dozens of disparate career boards, JobTrace automates retrieval directly from the applicant tracking systems (ATS).
- Instead of relying on spammy email alerts and fragile SMTP configurations, JobTrace delivers notifications via **Telegram Bot API**.
- Instead of naive keyword matching, JobTrace reads job descriptions and resumes, applying algorithmic seniority and relevance gates to prioritize achievable roles.

### High-Level Architecture Diagram

```
                 [Career Portals & Aggregators]
     Greenhouse · Lever · Ashby · Workable · Workday · Oracle · Atlassian
                                │
                                ▼
                       [Sources Adapter Layer]
                 - ThreadPool concurrent scraping
                 - URL tracking normalization (UTM removal)
                 - Stable SHA256 ID generation
                                │
                                ▼
                   [Unified Orchestration Pipeline]
                                │
       ┌────────────────────────┴────────────────────────┐
       ▼                                                 ▼
[Stateful Presence Store]                       [Scoring Engine]
- SQLite + FTS5 full-text search               - Configurable Seniority Gate
- Presence tracking (preserves un-filtered)    - Multi-dimensional Relevance
- Clean board closure diffing                  - Daily token budget controls
- Alert queue isolation                        - LLM / Offline Matchers
       │                                                 │
       └────────────────────────┬────────────────────────┘
                                │
                                ▼
               [Notification & Delivery Dispatchers]
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
[Telegram Bot Engine]                          [FastAPI Web UI]
- Daily shortlist alerts                       - Real-time SSE live updates
- Weekly digest messages                       - FTS5 keyword & stack search
- Automatic 4096-char chunking                 - Profile radar breakdowns
```

---

## 2. Core Enhancements in JobTrace

| Dimension | Before | JobTrace |
|-----------|-----------------|----------|
| **Notification Channel** | SMTP Email / Gmail App Password | **Telegram Bot API** (real-time, rich HTML, chunked) |
| **Filter Presence Bug** | Filtering before upsert caused false closures | **All fetched jobs upserted**; `matches_filter` flag prevents false closures |
| **Alert Queue Isolation** | Daily alert scan baselined unwatched companies | **Unalerted query scoped** strictly to watched companies |
| **Job ID Stability** | Tracking query parameters changed job IDs | **`normalize_url` strips UTM / tracking params** before ID hashing |
| **Web UI Pipeline Parity** | Web UI lacked seniority caps & budget enforcement | **Unified Pipeline (`pipeline.py`)** executed by CLI, daemon, and Web UI |
| **Candidate Seniority** | Hardcoded junior-only logic | **Configurable bands**: *intern, junior, mid, senior, lead, any* |
| **Platform Support** | Hardcoded for macOS launchd | **Cross-platform daemon**, PowerShell runner (`run.ps1`), & launchd |

---

## 3. Data Store Schema & Presence Tracking

JobTrace uses an ACID-compliant local SQLite database (`jobtrace.db`):

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    location TEXT,
    source TEXT,
    posted_at REAL,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    closed_at REAL,
    alerted INTEGER DEFAULT 0,
    notified INTEGER DEFAULT 0,
    score INTEGER,
    reason TEXT,
    breakdown TEXT,
    domain TEXT,
    description TEXT,
    matches_filter INTEGER DEFAULT 1
);

CREATE VIRTUAL TABLE jobs_fts USING fts5(
    id UNINDEXED,
    title,
    company,
    location,
    description
);

CREATE TABLE spend (
    day TEXT PRIMARY KEY,
    tokens INTEGER DEFAULT 0
);
```

### Diffing & Closure Rules
1. **New Job:** A job with an ID not previously present in `jobs` is inserted with `first_seen = now` and `last_seen = now`.
2. **Existing Job:** `last_seen = now`, `closed_at = NULL` (reopens if previously closed).
3. **Absence-based Closure:** When a company board returns successfully without network errors, any job belonging to that company whose `last_seen < run_timestamp` is marked with `closed_at = now`.
4. **Age-based Aggregator Expiry:** Roles from aggregator feeds (e.g. Remotive) lack presence signals and expire automatically after `expire_after_days` (default: 14 days).

---

## 4. Telegram Notification Architecture

The Telegram module (`jobtrace/telegram.py`) provides:
- **Daily Alerts:** Dispatches immediately for openings detected at companies on your shortlist.
- **Weekly Digest:** Aggregates newly posted roles, categorizes them into Watched Companies and Discovered Feeds, lists recently closed roles, and includes pipeline summary notes.
- **Message Chunking:** Telegram imposes a hard 4,096 character limit per message. JobTrace cleanly splits long digests across line boundaries into sequential messages.
- **HTML Escaping:** All dynamic text (job titles, company names, reason strings) is strictly HTML-escaped to avoid parse errors.

---

## 5. Token Economy & Budget Controls

Scoring thousands of jobs with an LLM can consume significant tokens. JobTrace employs three defensive techniques:
1. **Positional Batch Arrays:** Prompts request compact positional arrays `[ref, score, skills, seniority, location, domain, recency, reach, "reason"]` instead of repetitive JSON keys, reducing token overhead by over 70%.
2. **Local Heuristic Triage:** When `triage: true`, obvious mismatches (score below `triage_floor`) are filtered out locally for 0 tokens.
3. **Token Reserve Protection:** Daily spend is tracked in the `spend` table. Scoring stops automatically before breaching `daily_token_limit`.
