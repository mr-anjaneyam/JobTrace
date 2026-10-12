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


if __name__ == "__main__":
    test_get_settings()
    test_update_settings_and_env()
    test_upload_resume()
    print("All Web Settings API tests PASSED!")
