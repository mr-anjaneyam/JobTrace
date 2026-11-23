"""Tests for JobTrace External Job Ingestion API (POST /api/jobs/ingest)."""
import pytest
from fastapi.testclient import TestClient
from jobtrace.web.server import app


@pytest.fixture
def client(workspace):
    return TestClient(app)


def test_ingest_single_job_direct(client):
    payload = {
        "company": "Stripe",
        "title": "Staff Backend Engineer",
        "url": "https://stripe.com/jobs/staff-eng-1",
        "location": "Bengaluru",
        "description": "Looking for Go, distributed systems, resilient payment processing.",
        "source": "jobintel",
        "score_now": True,
        "notify": False,
    }
    res = client.post("/api/jobs/ingest", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["ingested"] == 1
    job = data["results"][0]
    assert job["company"] == "Stripe"
    assert job["title"] == "Staff Backend Engineer"
    assert job["id"] is not None


def test_ingest_batch_envelope(client):
    payload = {
        "jobs": [
            {
                "company": "Figma",
                "title": "Frontend Engineer",
                "url": "https://figma.com/jobs/frontend-1",
                "location": "Remote",
                "description": "TypeScript, WebAssembly, Canvas, rendering engine.",
                "source": "jobintel",
            },
            {
                "company": "Databricks",
                "title": "Data Platform Engineer",
                "url": "https://databricks.com/jobs/data-1",
                "location": "San Francisco",
                "description": "Spark, Scala, Python, cloud lakehouse architecture.",
                "source": "jobintel",
            },
        ],
        "score_now": False,
        "notify": False,
    }
    res = client.post("/api/jobs/ingest", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["received"] == 2
    assert data["ingested"] == 2


def test_ingest_invalid_payload(client):
    res = client.post("/api/jobs/ingest", json={"unrecognized_field": 123})
    assert res.status_code == 400


def test_elapsed_ingest_never_enters_live_state(client, workspace, monkeypatch):
    import time
    from jobtrace.web import server
    monkeypatch.setattr(server, "_trigger_background_liveness_check", lambda: None)
    res = client.post("/api/jobs/ingest", json={
        "company": "Acme", "title": "Elapsed job", "url": "https://example.com/elapsed",
        "deadline_at": time.time() - 3600, "score_now": False, "notify": False,
    })
    assert res.status_code == 200
    state = client.get("/api/state?history=true")
    assert state.status_code == 200
    assert state.json()["jobs"] == []
    assert state.json()["stats"]["closed"] == 1
    assert state.headers["cache-control"] == "no-store"


def test_poll_closes_elapsed_jobs_and_preserves_timeline(client, workspace, monkeypatch):
    from jobtrace.store import Store
    from jobtrace.web import server
    s = Store(workspace / "jobtrace.db")
    monkeypatch.setattr(server, "_trigger_background_liveness_check", lambda: None)
    monkeypatch.setattr(server.time, "time", lambda: 1000.0)
    s.upsert([
        {"id": "expires", "company": "Acme", "title": "Expiring", "deadline_at": 1100},
        {"id": "alive", "company": "Acme", "title": "Still open"},
    ], run_ts=900)
    assert len(client.get("/api/state").json()["jobs"]) == 2
    monkeypatch.setattr(server.time, "time", lambda: 1100.0)
    state = client.get("/api/state?history=true").json()
    assert [j["id"] for j in state["jobs"]] == ["alive"]
    historic = next(j for j in state["timeline"]["jobs"] if j["id"] == "expires")
    assert historic["periods"] == [{"opened_at": 900, "closed_at": 1100}]
    assert historic["expires_at"] == 1100


def test_busy_ingest_returns_retryable_error(client, workspace, monkeypatch):
    import sqlite3
    from jobtrace.store import Store
    from jobtrace.web import server
    s = Store(workspace / "jobtrace.db")
    s.db.execute("PRAGMA busy_timeout = 20")
    monkeypatch.setattr(server, "get_store", lambda: s)
    blocker = sqlite3.connect(str(s.path))
    blocker.execute("BEGIN IMMEDIATE")
    try:
        res = client.post("/api/jobs/ingest", json={"title": "Blocked", "score_now": False})
        assert res.status_code == 503 and res.headers["retry-after"] == "5"
        assert not s.db.in_transaction
    finally:
        blocker.rollback()
        blocker.close()
    assert client.post("/api/jobs/ingest", json={"title": "Retry", "score_now": False}).status_code == 200


def test_replayed_webhook_does_not_resurrect_discarded_job(client, monkeypatch):
    from jobtrace.web import server
    monkeypatch.setattr(server, "_trigger_background_liveness_check", lambda: None)
    payload = {"title": "Engineer", "company": "Acme", "url": "https://example.com/replay", "score_now": False}
    result = client.post("/api/jobs/ingest", json=payload).json()
    job_id = result["results"][0]["id"]
    assert client.post(f"/api/jobs/{job_id}/discard").status_code == 200
    assert client.post("/api/jobs/ingest", json=payload).status_code == 200
    assert client.get("/api/state").json()["jobs"] == []


def test_ingest_invalid_json_preserves_bad_request_status(client):
    assert client.post("/api/jobs/ingest", content="{", headers={"Content-Type": "application/json"}).status_code == 400


def test_history_reports_limit_and_keeps_old_still_open_jobs(client, workspace, monkeypatch):
    from jobtrace.store import Store
    from jobtrace.web import server
    monkeypatch.setattr(server, "_trigger_background_liveness_check", lambda: None)
    monkeypatch.setattr(server, "STATE_MAX_JOBS", 2)
    s = Store(workspace / "jobtrace.db")
    s.upsert([{"id": str(i), "title": "Engineer", "company": "Acme"} for i in range(3)], run_ts=1)
    timeline = client.get("/api/state?history=true").json()["timeline"]
    assert timeline["truncated"] is True and len(timeline["jobs"]) == 2
    assert all(j["periods"][0]["opened_at"] == 1 for j in timeline["jobs"])

