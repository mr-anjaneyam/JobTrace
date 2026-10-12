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
    print("✓ upsert and diffing tests pass")


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
    print("✓ presence vs filter bug fix passes")


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
    print("✓ alert queue isolation test passes")


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
    print("✓ FTS5 search tests pass")


if __name__ == "__main__":
    test_upsert_and_diffing()
    test_presence_vs_filter_fix = test_presence_vs_filter_bug_fix()
    test_alert_queue_isolation()
    test_fts5_search()
    print("All store tests PASSED!")
