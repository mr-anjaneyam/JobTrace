import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace.store import Store


def make_job(i, company="Acme", matches_filter=True, source="greenhouse", desc=""):
    return {
        "id": i,
        "company": company,
        "title": f"Engineer {i}",
        "url": f"https://example.com/jobs/{i}",
        "location": "Remote",
        "posted_at": None,
        "source": source,
        "description": desc,
        "matches_filter": matches_filter,
    }


def test_upsert_and_diffing():
    tmp = os.path.join(tempfile.mkdtemp(), "test_diff.db")
    s = Store(tmp)

    # 1. New jobs
    fresh = s.upsert([make_job("j1"), make_job("j2")])
    assert len(fresh) == 2
    assert s.stats() == {"total": 2, "open": 2}

    # 2. Existing jobs must not be reported fresh
    assert len(s.upsert([make_job("j1"), make_job("j2")])) == 0

    # 3. Job closure when missing from healthy board
    time.sleep(0.02)
    s.upsert([make_job("j1")])  # j2 fell off board
    closed = s.mark_closed(["Acme"])
    assert [r["id"] for r in closed] == ["j2"]
    assert s.stats()["open"] == 1

    # 4. Reopen previously closed job
    time.sleep(0.02)
    s.upsert([make_job("j1"), make_job("j2")])
    assert s.mark_closed(["Acme"]) == []
    assert s.stats()["open"] == 2
    print("[OK] upsert and diffing tests pass")


def test_presence_vs_filter_bug_fix():
    """Verify that jobs failing search filters still update last_seen and are not falsely closed."""
    tmp = os.path.join(tempfile.mkdtemp(), "test_filter_fix.db")
    s = Store(tmp)

    # Ingest role originally matching filter
    s.upsert([make_job("eng1", "Acme", matches_filter=True)])
    time.sleep(0.02)

    # Later run: user tightened filter so role has matches_filter=False
    # But because Acme is healthy and the job is still on board, it must NOT be closed!
    s.upsert([make_job("eng1", "Acme", matches_filter=False)])
    closed = s.mark_closed(["Acme"])
    assert closed == [], f"Job must not be marked closed when still on board! Got: {closed}"
    row = s.db.execute("SELECT closed_at, matches_filter FROM jobs WHERE id='eng1'").fetchone()
    assert row["closed_at"] is None
    assert row["matches_filter"] == 0
    print("[OK] presence vs filter bug fix passes")


def test_alert_queue_isolation():
    """Verify that unalerted query can be strictly scoped to watched companies."""
    tmp = os.path.join(tempfile.mkdtemp(), "test_alert_queue.db")
    s = Store(tmp)

    s.upsert([
        make_job("a1", "WatchedCo"),
        make_job("b1", "UnwatchedCo"),
        make_job("d1", "DiscoveryCo", source="remotive"),
    ])

    # Unscoped unalerted returns all 3
    assert len(s.unalerted()) == 3

    # Scoped unalerted returns ONLY WatchedCo
    watched_unalerted = s.unalerted(companies=["WatchedCo"])
    assert [r["id"] for r in watched_unalerted] == ["a1"]

    # Mark only watched alerted
    s.mark_alerted(["a1"])
    assert [r["id"] for r in s.unalerted(companies=["WatchedCo"])] == []
    # UnwatchedCo and DiscoveryCo still preserved as unalerted!
    assert {r["id"] for r in s.unalerted()} == {"b1", "d1"}
    print("[OK] alert queue isolation test passes")


def test_fts5_search():
    tmp = os.path.join(tempfile.mkdtemp(), "test_fts.db")
    s = Store(tmp)

    s.upsert([
        make_job("j1", "Stripe", desc="Python, Distributed Systems, Redis"),
        make_job("j2", "Figma", desc="React, TypeScript, WebGL canvas"),
        make_job("j3", "Anthropic", desc="AI Alignment, PyTorch, LLM research"),
    ])

    assert s.search("Python") == ["j1"]
    assert s.search("TypeScript") == ["j2"]
    assert s.search("Stripe") == ["j1"]
    assert s.search("AI Alignment PyTorch") == ["j3"]
    assert s.search("NonexistentStack") == []
    print("[OK] FTS5 search tests pass")


if __name__ == "__main__":
    test_upsert_and_diffing()
    test_presence_vs_filter_fix = test_presence_vs_filter_bug_fix()
    test_alert_queue_isolation()
    test_fts5_search()
    print("All store tests PASSED!")


def test_prune_removes_only_long_closed_jobs_and_their_search_rows():
    tmp = os.path.join(tempfile.mkdtemp(), "test_prune.db")
    s = Store(tmp)
    s.upsert([make_job("old", desc="python backend role"), make_job("recent"), make_job("open")])
    now = time.time()
    s.db.execute("UPDATE jobs SET closed_at = ? WHERE id = 'old'", (now - 200 * 86400,))
    s.db.execute("UPDATE jobs SET closed_at = ? WHERE id = 'recent'", (now - 5 * 86400,))
    s.db.commit()

    assert s.prune(90) == 1
    ids = {r[0] for r in s.db.execute("SELECT id FROM jobs")}
    assert ids == {"recent", "open"}
    assert s.search("python") == []
    assert s.prune(0) == 0  # retention disabled


def test_prune_vacuum_runs_without_error():
    tmp = os.path.join(tempfile.mkdtemp(), "test_vacuum.db")
    s = Store(tmp)
    s.upsert([make_job("x")])
    s.db.execute("UPDATE jobs SET closed_at = ?", (time.time() - 400 * 86400,))
    s.db.commit()
    assert s.prune(30, vacuum=True) == 1


def test_upsert_commits_in_chunks_and_keeps_existing_descriptions():
    tmp = os.path.join(tempfile.mkdtemp(), "test_chunks.db")
    s = Store(tmp)
    long_desc = "Build reliable backend systems and APIs. " * 5
    s.upsert([make_job(f"j{i}", desc=long_desc) for i in range(600)])
    before = s.db.execute("SELECT description FROM jobs WHERE id = 'j1'").fetchone()[0]
    assert len(before) >= 50

    # A rescan with a different description must not rewrite rows that already have one
    s.upsert([make_job(f"j{i}", desc="replacement text that is also long enough to count " * 3) for i in range(600)])
    assert s.db.execute("SELECT description FROM jobs WHERE id = 'j1'").fetchone()[0] == before
    assert s.stats()["total"] == 600


def test_failed_upsert_rolls_back_and_releases_writer(tmp_path):
    import pytest
    s = Store(tmp_path / "rollback.db")
    other = Store(s.path)
    other.db.execute("PRAGMA busy_timeout = 50")
    with pytest.raises(KeyError):
        s.upsert([make_job("first"), {"id": "broken"}])
    assert not s.db.in_transaction
    assert s.stats()["total"] == 0
    other.upsert([make_job("recovered")])
    assert s.stats()["total"] == 1


def test_expired_reingest_stays_closed_and_history_tracks_reopen(tmp_path):
    s = Store(tmp_path / "history.db")
    j = {**make_job("deadline"), "deadline_at": 200, "deadline_text": "test deadline"}
    s.upsert([j], run_ts=100)
    s.close_elapsed_deadlines(now=200)
    s.upsert([make_job("deadline")], run_ts=300)
    assert s.stats()["open"] == 0
    periods = s.db.execute("SELECT opened_at, closed_at FROM job_periods").fetchall()
    assert [tuple(p) for p in periods] == [(100, 200)]
    s.upsert([{**j, "deadline_at": 500}], run_ts=400)
    s.close_elapsed_deadlines(now=500)
    assert [tuple(p) for p in s.db.execute(
        "SELECT opened_at, closed_at FROM job_periods ORDER BY opened_at"
    )] == [(100, 200), (400, 500)]
    assert s.prune(1, now=100000) == 1
    assert s.db.execute("SELECT COUNT(*) FROM job_periods").fetchone()[0] == 0


def test_legacy_history_backfill_is_idempotent(tmp_path):
    import sqlite3
    from jobtrace.store import SCHEMA
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute(
            "INSERT INTO jobs(id, company, title, first_seen, last_seen, closed_at) VALUES (?,?,?,?,?,?)",
            ("old", "Acme", "Engineer", 100, 150, 200),
        )
    for _ in range(2):
        s = Store(path)
        assert [tuple(p) for p in s.db.execute("SELECT opened_at, closed_at FROM job_periods")] == [(100, 200)]
        s.db.close()


def test_score_metadata_closes_deadline_and_persists_salary(tmp_path):
    from datetime import datetime
    s = Store(tmp_path / "scored.db")
    s.upsert([make_job("old")], run_ts=1)
    s.save_score("old", 8, "Matched", {
        "salary_min": 50000, "salary_max": 70000, "salary_currency": "USD",
        "salary_text": "$50k-$70k", "deadline_text": "Nov 1, 2020",
    })
    row = s.db.execute("SELECT * FROM jobs").fetchone()
    assert row["salary_min"] == 50000 and row["salary_max"] == 70000
    assert row["salary_currency"] == "USD" and row["salary_text"] == "$50k-$70k"
    assert row["closed_at"] == datetime(2020, 11, 1, 23, 59, 59).timestamp()
    assert not s.unnotified()


def test_upgrade_recovers_deadline_text_from_old_scoring(tmp_path):
    s = Store(tmp_path / "legacy-deadline.db")
    s.upsert([make_job("old")], run_ts=1)
    s.db.execute("UPDATE jobs SET deadline_text = '1 November 2020', deadline_at = NULL")
    s.db.commit()
    s.db.close()
    upgraded = Store(s.path)
    assert len(upgraded.close_elapsed_deadlines()) == 1
    assert upgraded.stats()["open"] == 0
