"""Tests for JobTrace Web Settings API and Resume Upload endpoints (run against a temp project root)."""
import io
import os

import pytest
from fastapi.testclient import TestClient

from jobtrace.main import load_config, load_dotenv
from jobtrace.web.server import MASK_CHAR, app


@pytest.fixture
def client(workspace):
    return TestClient(app)


def test_get_settings(client):
    data = client.get("/api/settings").json()
    assert "chat_ids" in data["telegram"]
    assert data["llm"]["provider"] == "none"
    assert "XKIRO_API_KEY" in data["api_keys"]


def test_update_settings_and_env(client, workspace):
    payload = {
        "telegram": {"bot_token": "test-bot-token-999", "chat_ids": "10001, 10002\n10003"},
        "llm": {"provider": "xkiro", "model": "m", "min_score": 7, "triage": True},
        "candidate": {"seniority": "mid", "locations": ["Remote", "Bengaluru"]},
        "api_keys": {"XKIRO_API_KEY": "test-key-xkiro-val"},
    }
    assert client.post("/api/settings", json=payload).json()["ok"] is True
    assert os.environ["XKIRO_API_KEY"] == "test-key-xkiro-val"
    assert os.environ["TELEGRAM_CHAT_IDS"] == "10001, 10002, 10003"

    data = client.get("/api/settings").json()
    assert data["telegram"]["chat_ids"] == ["10001", "10002", "10003"]
    assert data["llm"]["min_score"] == 7
    assert data["candidate"]["seniority"] == "mid"


def test_secrets_are_masked_and_round_trip(client):
    client.post(
        "/api/settings",
        json={
            "telegram": {"bot_token": "123456:ABCDEFGHIJKLMNOP", "chat_ids": "1"},
            "api_keys": {"XKIRO_API_KEY": "sk-super-secret-value"},
        },
    )
    data = client.get("/api/settings").json()
    assert "ABCDEFGHIJ" not in data["telegram"]["bot_token"]
    assert MASK_CHAR in data["telegram"]["bot_token"]
    assert "super-secret" not in data["api_keys"]["XKIRO_API_KEY"]
    assert data["api_keys"]["XKIRO_API_KEY"].endswith("alue")

    # Saving the masked values back must not overwrite the real secrets
    client.post("/api/settings", json={"telegram": data["telegram"], "api_keys": data["api_keys"]})
    assert os.environ["XKIRO_API_KEY"] == "sk-super-secret-value"
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "123456:ABCDEFGHIJKLMNOP"


def test_unknown_env_names_are_rejected(client):
    original_path = os.environ.get("PATH")
    client.post("/api/settings", json={"api_keys": {"PATH": "/evil", "LD_PRELOAD": "x"}})
    assert os.environ.get("PATH") == original_path
    assert "LD_PRELOAD" not in os.environ


def test_env_value_with_newline_is_rejected(client, workspace):
    resp = client.post("/api/settings", json={"api_keys": {"XKIRO_API_KEY": 'a"\nEVIL=1'}}).json()
    assert resp["ok"] is False
    assert not (workspace / ".env").exists()


def test_upload_resume_txt(client, workspace):
    cv = b"John Doe\nSenior Software Engineer\nSan Francisco, CA\n\nExperience:\nAcme Corp | Staff Engineer | 2021 - Present\n"
    files = {"file": ("anything.txt", io.BytesIO(cv), "text/plain")}
    data = client.post("/api/upload-resume", files=files).json()
    assert data["ok"] is True
    assert data["filename"] == "resume.txt"
    assert (workspace / "resume.txt").exists()
    assert load_config(workspace / "config.yaml")["resume_path"] == "resume.txt"


def test_upload_cannot_overwrite_project_files(client, workspace):
    (workspace / "README.md").write_text("keep me", encoding="utf-8")
    files = {"file": ("README.md", io.BytesIO(b"pwned"), "text/markdown")}
    client.post("/api/upload-resume", files=files)
    assert (workspace / "README.md").read_text(encoding="utf-8") == "keep me"


def test_upload_rejects_bad_type_and_oversize(client):
    bad = client.post("/api/upload-resume", files={"file": ("x.exe", io.BytesIO(b"x"), "application/octet-stream")}).json()
    assert bad["ok"] is False
    big = client.post(
        "/api/upload-resume",
        files={"file": ("big.txt", io.BytesIO(b"a" * (5 * 1024 * 1024 + 10)), "text/plain")},
    ).json()
    assert big["ok"] is False


def test_confirm_profile(client, workspace):
    payload = {"name": "Jane Developer", "seniority": "lead", "target_locations": ["Remote", "Seattle"], "years_of_experience": 8.5}
    assert client.post("/api/profile", json=payload).json()["ok"] is True
    prof = client.get("/api/profile").json()
    assert prof["name"] == "Jane Developer"
    cfg = load_config(workspace / "config.yaml")
    assert cfg["candidate"]["seniority"] == "lead"
    assert "Seattle" in cfg["candidate"]["locations"]


def test_persistence(client, workspace):
    client.post(
        "/api/settings",
        json={
            "telegram": {"bot_token": "persistent-token-123", "chat_ids": "555, 666, 777"},
            "api_keys": {"XKIRO_API_KEY": "persistent-xkiro-secret"},
        },
    )
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("XKIRO_API_KEY", None)
    load_dotenv()
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "persistent-token-123"
    assert os.environ["XKIRO_API_KEY"] == "persistent-xkiro-secret"
    assert load_config(workspace / "config.yaml")["telegram"]["chat_ids"] == ["555", "666", "777"]


def test_cors_rejects_foreign_origin(client):
    r = client.get("/api/settings", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    ok = client.get("/api/settings", headers={"Origin": "http://localhost:3000"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
