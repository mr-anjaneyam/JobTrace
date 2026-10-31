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

