"""SQLite state engine with FTS5 search, proper presence tracking, and isolated queues."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    url             TEXT,
    location        TEXT,
    source          TEXT,
    posted_at       REAL,
    first_seen      REAL NOT NULL,
    last_seen       REAL NOT NULL,
    closed_at       REAL,
    score           INTEGER,
    reason          TEXT,
    notified        INTEGER NOT NULL DEFAULT 0,
    domain          TEXT,
    breakdown       TEXT,
    alerted         INTEGER NOT NULL DEFAULT 0,
    description     TEXT,
    matches_filter  INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score);
CREATE INDEX IF NOT EXISTS idx_jobs_closed_at ON jobs(closed_at);
CREATE INDEX IF NOT EXISTS idx_jobs_alerted ON jobs(alerted);
CREATE INDEX IF NOT EXISTS idx_jobs_notified ON jobs(notified);

CREATE TABLE IF NOT EXISTS runs (
    ts            INTEGER PRIMARY KEY,
    new_count     INTEGER,
    closed_count  INTEGER,
    errors        TEXT
);

CREATE TABLE IF NOT EXISTS spend (
    day     TEXT PRIMARY KEY,
    tokens  INTEGER NOT NULL DEFAULT 0
);
"""


class Store:
    def __init__(self, path: str | Path = "jobtrace.db"):
        self.path = Path(path)
        self.db = sqlite3.connect(str(self.path), timeout=30.0)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA journal_mode = WAL;")
            self.db.execute("PRAGMA busy_timeout = 30000;")
        except Exception:
            pass
        self.db.executescript(SCHEMA)
        self._init_fts()
        self.db.commit()
        self.last_upsert_ts = time.time()

    def _init_fts(self) -> None:
        """Initialize FTS5 virtual table for fast full-text searching if supported."""
        try:
            self.db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                    id UNINDEXED,
                    title,
                    company,
                    location,
                    description,
                    tokenize = 'porter unicode61'
                )
            """)
            self.has_fts = True
        except sqlite3.OperationalError:
            self.has_fts = False

    def sync_fts(self, job_id: str, title: str, company: str, location: str, description: str) -> None:
        if not self.has_fts:
            return
        self.db.execute("DELETE FROM jobs_fts WHERE id = ?", (job_id,))
        self.db.execute(
            "INSERT INTO jobs_fts (id, title, company, location, description) VALUES (?, ?, ?, ?, ?)",
            (job_id, title, company, location or "", description or ""),
        )

    # -- ingest -------------------------------------------------------------
    def upsert(self, jobs: list[dict], run_ts: float | None = None) -> list[dict]:
        """Insert or refresh jobs.
        
        Jobs have matches_filter flag:
        - If True, job is eligible for scoring and alerts.
        - If False, job still has last_seen updated so it is NOT falsely marked closed!
        """
        now = run_ts if run_ts is not None else time.time()
        self.last_upsert_ts = now
        fresh = []

        for j in jobs:
            jid = j["id"]
            matches_filter = 1 if j.get("matches_filter", True) else 0
            desc = (j.get("description") or "")[:2500]

            row = self.db.execute("SELECT id, closed_at FROM jobs WHERE id = ?", (jid,)).fetchone()
            if row:
                self.db.execute(
                    """UPDATE jobs SET
                           last_seen = ?,
                           closed_at = NULL,
                           matches_filter = ?,
                           url = COALESCE(?, url),
                           location = COALESCE(?, location),
                           posted_at = COALESCE(?, posted_at)
                       WHERE id = ?""",
                    (now, matches_filter, j.get("url"), j.get("location"), j.get("posted_at"), jid),
                )
            else:
                self.db.execute(
                    """INSERT INTO jobs (
                           id, company, title, url, location, source,
                           posted_at, first_seen, last_seen, domain, description, matches_filter
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        jid, j["company"], j["title"], j.get("url"), j.get("location", ""),
                        j.get("source", ""), j.get("posted_at"), now, now, j.get("domain", ""),
                        desc, matches_filter
                    ),
                )
                self.sync_fts(jid, j["title"], j["company"], j.get("location", ""), desc)
                if matches_filter:
                    fresh.append(j)

        self.db.commit()
        return fresh

    def mark_closed(self, healthy_companies: list[str], run_ts: float | None = None) -> list[sqlite3.Row]:
        """A tracked job that stopped appearing on its board is marked closed.
        
        Only applies to companies that fetched cleanly this run.
        """
        run_ts = run_ts if run_ts is not None else getattr(self, "last_upsert_ts", time.time())
        if not healthy_companies:
            return []

        marks = ",".join("?" * len(healthy_companies))
        rows = self.db.execute(
            f"""SELECT * FROM jobs
                WHERE company IN ({marks})
                  AND closed_at IS NULL
                  AND last_seen < ?""",
            (*healthy_companies, run_ts),
        ).fetchall()

        for r in rows:
            self.db.execute("UPDATE jobs SET closed_at = ? WHERE id = ?", (run_ts, r["id"]))
        self.db.commit()
        return rows

    def close_stale(self, sources: list[str], max_age_days: int) -> list[sqlite3.Row]:
        """Close jobs from sources without reliable presence signals (aggregators)."""
        if not sources:
            return []
        cutoff = time.time() - (max_age_days * 86400)
        marks = ",".join("?" * len(sources))
        rows = self.db.execute(
            f"""SELECT * FROM jobs
                WHERE source IN ({marks})
                  AND closed_at IS NULL
                  AND last_seen < ?""",
            (*sources, cutoff),
        ).fetchall()
        now = time.time()
        for r in rows:
            self.db.execute("UPDATE jobs SET closed_at = ? WHERE id = ?", (now, r["id"]))
        self.db.commit()
        return rows

    # -- scoring ------------------------------------------------------------
    def save_score(self, job_id: str, score: int, reason: str, breakdown: dict | None = None) -> None:
        self.db.execute(
            "UPDATE jobs SET score = ?, reason = ?, breakdown = ? WHERE id = ?",
            (score, reason, json.dumps(breakdown or {}), job_id),
        )
        self.db.commit()

    def unscored(self, limit: int = 5000) -> list[sqlite3.Row]:
        return self.db.execute(
            """SELECT * FROM jobs
               WHERE score IS NULL
                 AND closed_at IS NULL
                 AND matches_filter = 1
               ORDER BY first_seen DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    def unscored_count(self) -> int:
        return self.db.execute(
            """SELECT COUNT(*) FROM jobs
               WHERE score IS NULL
                 AND closed_at IS NULL
                 AND matches_filter = 1"""
        ).fetchone()[0]

    # -- reporting & queues -------------------------------------------------
    def unnotified(self, min_score: int = 0, require_scored: bool = False) -> list[sqlite3.Row]:
        """Fetch jobs pending weekly digest."""
        unscored_clause = "AND score IS NOT NULL" if require_scored else ""
        return self.db.execute(
            f"""SELECT * FROM jobs
                WHERE notified = 0
                  AND closed_at IS NULL
                  AND matches_filter = 1
                  {unscored_clause}
                  AND (score IS NULL OR score >= ?)
                ORDER BY score DESC NULLS LAST, first_seen DESC""",
            (min_score,),
        ).fetchall()

    def unalerted(self, companies: list[str] | set[str] | None = None) -> list[sqlite3.Row]:
        """Fetch jobs pending daily alerts, optionally filtered by company list."""
        if companies:
            marks = ",".join("?" * len(companies))
            return self.db.execute(
                f"""SELECT * FROM jobs
                    WHERE alerted = 0
                      AND closed_at IS NULL
                      AND matches_filter = 1
                      AND company IN ({marks})
                    ORDER BY first_seen DESC""",
                tuple(companies),
            ).fetchall()
        return self.db.execute(
            """SELECT * FROM jobs
               WHERE alerted = 0
                 AND closed_at IS NULL
                 AND matches_filter = 1
               ORDER BY first_seen DESC"""
        ).fetchall()

    def baselined_companies(self) -> set[str]:
        """Companies that have already completed an alert pass."""
        return {
            r["company"]
            for r in self.db.execute("SELECT DISTINCT company FROM jobs WHERE alerted = 1")
        }

    def mark_alerted(self, ids: list[str]) -> None:
        if not ids:
            return
        self.db.executemany("UPDATE jobs SET alerted = 1 WHERE id = ?", [(i,) for i in ids])
        self.db.commit()

    def mark_notified(self, ids: list[str]) -> None:
        if not ids:
            return
        self.db.executemany("UPDATE jobs SET notified = 1 WHERE id = ?", [(i,) for i in ids])
        self.db.commit()

    def since(self, seconds: float, min_score: int = 0) -> list[sqlite3.Row]:
        cutoff = time.time() - seconds
        return self.db.execute(
            """SELECT * FROM jobs
               WHERE first_seen >= ?
                 AND closed_at IS NULL
                 AND matches_filter = 1
                 AND (score IS NULL OR score >= ?)
               ORDER BY score DESC NULLS LAST, first_seen DESC""",
            (cutoff, min_score),
        ).fetchall()

    def closed_since(self, seconds: float) -> list[sqlite3.Row]:
        cutoff = time.time() - seconds
        return self.db.execute(
            "SELECT * FROM jobs WHERE closed_at >= ? ORDER BY closed_at DESC", (cutoff,)
        ).fetchall()

    def search(self, query: str, limit: int = 4000) -> list[str]:
        """High performance full-text search across title, company, location, and description."""
        words = [w.strip() for w in query.split() if w.strip()][:8]
        if not words:
            return []

        if self.has_fts:
            # Match all words in FTS5
            fts_query = " ".join(f'"{w}*"' for w in words)
            try:
                rows = self.db.execute(
                    """SELECT j.id FROM jobs j
                       JOIN jobs_fts f ON j.id = f.id
                       WHERE j.closed_at IS NULL
                         AND jobs_fts MATCH ?
                       LIMIT ?""",
                    (fts_query, limit),
                ).fetchall()
                return [r["id"] for r in rows]
            except sqlite3.OperationalError:
                pass  # Fallback to standard LIKE if syntax error in query

        # Fallback B-Tree LIKE
        clauses = " AND ".join(
            "(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(location) LIKE ? OR LOWER(COALESCE(description,'')) LIKE ?)"
            for _ in words
        )
        params: list[str] = []
        for w in words:
            params.extend([f"%{w.lower()}%"] * 4)
        rows = self.db.execute(
            f"SELECT id FROM jobs WHERE closed_at IS NULL AND {clauses} LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [r["id"] for r in rows]

    def log_run(self, new_count: int, closed_count: int, errors: list[str]) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO runs (ts, new_count, closed_count, errors) VALUES (?, ?, ?, ?)",
            (int(time.time()), new_count, closed_count, "\n".join(errors)),
        )
        self.db.commit()

    def stats(self) -> dict:
        row = self.db.execute(
            "SELECT COUNT(*) total, SUM(closed_at IS NULL) open FROM jobs"
        ).fetchone()
        return {"total": row["total"] or 0, "open": row["open"] or 0}
