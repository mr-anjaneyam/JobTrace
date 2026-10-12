"""Tests for JobTrace Web Settings API and Resume Upload endpoints."""
import io
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace.web.server import app, ROOT, update_env_file

client = TestClient(app)


def test_get_settings():
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "telegram" in data
    assert "bot_token" in data["telegram"]
    assert "chat_ids" in data["telegram"]
    assert "llm" in data
    assert "provider" in data["llm"]
    assert "api_keys" in data
    assert "XKIRO_API_KEY" in data["api_keys"]
    print("[OK] test_get_settings passed")


def test_update_settings_and_env():
    # Save current env values
    orig_xkiro = os.environ.get("XKIRO_API_KEY", "")

    test_payload = {
        "telegram": {
            "bot_token": "test-bot-token-999",
            "chat_ids": "10001, 10002\n10003",
        },
        "llm": {
            "provider": "xkiro",
            "model": "mistralai/mistral-large-2512",
            "min_score": 7,
            "triage": True,
        },
        "candidate": {
            "seniority": "mid",
            "locations": ["Remote", "Bengaluru"],
        },
        "api_keys": {
            "XKIRO_API_KEY": "test-key-xkiro-val",
            "OPENAI_API_KEY": "test-key-openai-val",
        },
    }

    resp = client.post("/api/settings", json=test_payload)
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    # Verify os.environ updated
    assert os.environ.get("XKIRO_API_KEY") == "test-key-xkiro-val"
    assert os.environ.get("TELEGRAM_BOT_TOKEN") == "test-bot-token-999"
    assert "10001" in os.environ.get("TELEGRAM_CHAT_IDS", "")
    assert "10002" in os.environ.get("TELEGRAM_CHAT_IDS", "")
    assert "10003" in os.environ.get("TELEGRAM_CHAT_IDS", "")

    # Verify GET reflects update
    verify_resp = client.get("/api/settings")
    data = verify_resp.json()
    assert data["telegram"]["bot_token"] == "test-bot-token-999"
    assert data["telegram"]["chat_ids"] == ["10001", "10002", "10003"]
    assert data["llm"]["min_score"] == 7
    assert data["candidate"]["seniority"] == "mid"
    assert data["api_keys"]["XKIRO_API_KEY"] == "test-key-xkiro-val"

    print("[OK] test_update_settings_and_env passed")


def test_upload_resume():
    sample_cv = b"""John Doe
Senior Software Engineer
San Francisco, CA

Experience:
Acme Corp | Staff Engineer | 2021 - Present
Built distributed indexing system handling 50k RPS in Go and Python.

Beta Tech | Software Engineer | 2018 - 2021
Developed full-stack web applications using React, TypeScript, and FastAPI.
"""
    files = {"file": ("test_resume.txt", io.BytesIO(sample_cv), "text/plain")}
    resp = client.post("/api/upload-resume", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("filename") == "test_resume.txt"
    assert "profile" in data
    assert "John Doe" in data["profile"].get("name", "")

    # Clean up test resume file
    test_file = ROOT / "test_resume.txt"
    if test_file.exists():
        test_file.unlink()

    # Reset config back to resume.example.txt
    from jobtrace.web.server import get_cfg, save_config
    c = get_cfg()
    c["resume_path"] = "resume.example.txt"
    save_config(c)

    print("[OK] test_upload_resume passed")


def test_confirm_profile():
    payload = {
        "name": "Jane Developer",
        "headline": "Lead Systems Architect",
        "location": "Seattle, WA",
        "target_locations": ["Remote", "Seattle"],
        "seniority": "lead",
        "years_of_experience": 8.5,
        "seniority_reason": "Over 8 years building distributed clouds",
        "summary": "Experienced systems architect with a strong background in distributed systems.",
        "skills": ["Go", "Kubernetes", "Rust", "Distributed Systems"],
        "experience": [
          {"org": "CloudTech", "role": "Principal Engineer", "years": "2020 - Present", "highlights": "Scale infra"}
        ],
        "education": [{"degree": "M.S. in Computer Science", "institution": "UW", "year": "2018"}],
    }

    resp = client.post("/api/profile", json=payload)
    assert resp.status_code == 200
    d = resp.json()
    assert d.get("ok") is True

    # Verify GET /api/profile returns the confirmed data
    prof_resp = client.get("/api/profile")
    prof = prof_resp.json()
    assert prof["name"] == "Jane Developer"
    assert prof["seniority"] == "lead"
    assert prof["years_of_experience"] == 8.5
    assert "Kubernetes" in prof["skills"]

    # Verify config.yaml candidate seniority was updated
    from jobtrace.web.server import get_cfg
    c = get_cfg()
    assert c["candidate"]["seniority"] == "lead"
    assert "Seattle" in c["candidate"]["locations"]

    print("[OK] test_confirm_profile passed")


def test_persistence():
    from jobtrace.main import load_dotenv, load_config

    # Modify env and config
    client.post("/api/settings", json={
        "telegram": {"bot_token": "persistent-token-123", "chat_ids": "555, 666, 777"},
        "api_keys": {"XKIRO_API_KEY": "persistent-xkiro-secret"},
        "candidate": {"seniority": "senior", "locations": ["Remote"]},
    })

    # Clear memory env
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("XKIRO_API_KEY", None)

    # Re-read from disk
    load_dotenv()
    loaded_cfg = load_config(ROOT / "config.yaml")

    # Assert persistence
    assert os.environ.get("TELEGRAM_BOT_TOKEN") == "persistent-token-123"
    assert os.environ.get("XKIRO_API_KEY") == "persistent-xkiro-secret"
    assert loaded_cfg["candidate"]["seniority"] == "senior"
    assert loaded_cfg["telegram"]["chat_ids"] == ["555", "666", "777"]

    print("[OK] test_persistence passed")


if __name__ == "__main__":
    env_backup = (ROOT / ".env").read_text(encoding="utf-8") if (ROOT / ".env").exists() else None
    cfg_backup = (ROOT / "config.yaml").read_text(encoding="utf-8") if (ROOT / "config.yaml").exists() else None
    profile_backup = (ROOT / ".resume_details.json").read_text(encoding="utf-8") if (ROOT / ".resume_details.json").exists() else None
    env_vars_backup = dict(os.environ)

    try:
        test_get_settings()
        test_update_settings_and_env()
        test_upload_resume()
        test_confirm_profile()
        test_persistence()
        print("All Web Settings & Profile API tests PASSED!")
    finally:
        if env_backup is not None:
            (ROOT / ".env").write_text(env_backup, encoding="utf-8")
        if cfg_backup is not None:
            (ROOT / "config.yaml").write_text(cfg_backup, encoding="utf-8")
        if profile_backup is not None:
            (ROOT / ".resume_details.json").write_text(profile_backup, encoding="utf-8")
        os.environ.clear()
        os.environ.update(env_vars_backup)


