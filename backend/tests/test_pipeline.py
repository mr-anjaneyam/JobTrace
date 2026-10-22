import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace import pipeline, sources
from jobtrace.store import Store


def test_unified_pipeline():
    tmp_dir = Path(tempfile.mkdtemp())
    db_path = tmp_dir / "pipe.db"
    store = Store(db_path)

    resume_file = tmp_dir / "resume.txt"
    resume_file.write_text("SKILLS\nPython, FastAPI, React, SQL\nEXPERIENCE\nSoftware Engineer 2023-Present\n")

    cfg = {
        "resume_path": str(resume_file),
        "companies": [{"name": "Acme", "board": "greenhouse", "slug": "acme"}],
        "discovery": {"enabled": False},
        "filters": {"title_include": ["engineer", "architect"], "title_exclude": []},
        "candidate": {"seniority": "junior"},
        "llm": {
            "provider": "local",
            "daily_token_limit": 500_000,
            "min_score": 5,
        },
    }

    # Mock fetch_company
    sources.fetch_company = lambda entry: ([
        {
            "id": "j1",
            "company": "Acme",
            "title": "Software Engineer",
            "url": "https://acme.com/1",
            "location": "Remote",
            "posted_at": None,
            "description": "Python FastAPI React Postgres",
            "source": "greenhouse",
            "domain": "acme.com",
            "matches_filter": True,
        },
        {
            "id": "j2",
            "company": "Acme",
            "title": "Senior Staff Architect",
            "url": "https://acme.com/2",
            "location": "Remote",
            "posted_at": None,
            "description": "Python Architecture",
            "source": "greenhouse",
            "domain": "acme.com",
            "matches_filter": True,
        },
        {
            "id": "j3",
            "company": "Acme",
            "title": "Account Executive",  # Filtered out by title_include
            "url": "https://acme.com/3",
            "location": "Remote",
            "posted_at": None,
            "description": "Sales calls",
            "source": "greenhouse",
            "domain": "acme.com",
            "matches_filter": True,
        },
    ], None)

    events = []
    result = pipeline.run_pipeline(
        cfg=cfg,
        store=store,
        root_dir=tmp_dir,
        quiet=True,
        emit=lambda kind, data: events.append(kind),
    )

    assert result["new"] == 2  # j1 and j2 match filter
    assert result["scored"] == 2

    # Verify j1 scored highly
    row1 = store.db.execute("SELECT score, reason FROM jobs WHERE id='j1'").fetchone()
    assert row1["score"] >= 6

    # Verify j2 (Senior Staff Architect) was properly capped at 3 by seniority gate for junior target!
    row2 = store.db.execute("SELECT score, reason FROM jobs WHERE id='j2'").fetchone()
    assert row2["score"] <= 3
    assert "senior" in row2["reason"]

    # Verify j3 exists in DB for presence diffing but has matches_filter=0
    row3 = store.db.execute("SELECT matches_filter, closed_at FROM jobs WHERE id='j3'").fetchone()
    assert row3["matches_filter"] == 0
    assert row3["closed_at"] is None

    print("[OK] unified pipeline tests pass")


if __name__ == "__main__":
    test_unified_pipeline()
    print("All pipeline tests PASSED!")


def test_scan_lock_blocks_a_second_scan_and_releases(tmp_path):
    import pytest

    with pipeline.scan_lock(tmp_path):
        with pytest.raises(pipeline.ScanBusy):
            with pipeline.scan_lock(tmp_path):
                pass
    with pipeline.scan_lock(tmp_path):
        pass  # released after the first scan
    assert not (tmp_path / pipeline.SCAN_LOCK_NAME).exists()


def test_stale_scan_lock_is_taken_over(tmp_path):
    import os
    import time

    lock = tmp_path / pipeline.SCAN_LOCK_NAME
    lock.write_text("9999")
    old = time.time() - pipeline.SCAN_LOCK_STALE_SECONDS - 60
    os.utime(lock, (old, old))
    with pipeline.scan_lock(tmp_path):
        pass


def test_run_pipeline_reports_busy_instead_of_scanning(tmp_path):
    import pytest

    store = Store(tmp_path / "t.db")
    with pipeline.scan_lock(tmp_path):
        with pytest.raises(pipeline.ScanBusy):
            pipeline.run_pipeline({"companies": []}, store, tmp_path, quiet=True)
