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


# ---- onboarding ----

def test_onboarding_starts_incomplete_on_fresh_install(client):
    data = client.get("/api/onboarding/status").json()
    assert data["completed"] is False
    assert data["scan"]["state"] == "idle"


def test_onboarding_treats_existing_install_as_done(client, workspace):
    from jobtrace.store import Store

    s = Store(workspace / "jobtrace.db")
    s.upsert([{"id": "1", "company": "Acme", "title": "Eng", "url": "u", "location": "Remote",
               "posted_at": None, "source": "greenhouse", "description": "", "matches_filter": True}])
    assert client.get("/api/onboarding/status").json()["completed"] is True


def test_onboarding_complete_saves_name_without_scan(client, workspace):
    resp = client.post("/api/onboarding/complete", json={"name": "Ada Lovelace", "start_scan": False}).json()
    assert resp["ok"] is True and resp["started"] is False
    status = client.get("/api/onboarding/status").json()
    assert status["completed"] is True and status["name"] == "Ada Lovelace"
    assert (workspace / ".onboarding.json").exists()


def test_onboarding_background_scan_reports_progress(client, monkeypatch):
    import time

    from jobtrace.web import server

    def fake_pipeline(cfg, store, root, quiet=True, emit=None, **kw):
        emit("fetch", {"company": "Acme", "count": 3})
        emit("fetched", {"new": 3, "closed": 0, "total": 3})
        emit("scoring", {"count": 2})
        emit("scored", {"id": "a"})
        return {"new": 3, "scored": 1, "errors": []}

    monkeypatch.setattr(server, "run_pipeline", fake_pipeline)
    resp = client.post("/api/onboarding/complete", json={"name": "Ada"}).json()
    assert resp["started"] is True

    for _ in range(50):
        scan = client.get("/api/onboarding/status").json()["scan"]
        if scan["state"] != "running":
            break
        time.sleep(0.05)
    assert scan["state"] == "done" and scan["percent"] == 100 and scan["new"] == 3
    assert server._scan_state["scanning"] is False


def test_background_scan_skips_scoring_without_resume(client, monkeypatch, workspace):
    import time

    import yaml

    from jobtrace.web import server

    cfg = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    cfg["llm"] = {"provider": "openai"}
    cfg["resume_path"] = "missing.pdf"
    (workspace / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    seen = {}

    def fake_pipeline(cfg, store, root, **kw):
        seen["provider"] = cfg["llm"]["provider"]
        return {"new": 0, "scored": 0, "errors": []}

    monkeypatch.setattr(server, "run_pipeline", fake_pipeline)
    client.post("/api/onboarding/complete", json={})
    for _ in range(50):
        scan = client.get("/api/onboarding/status").json()["scan"]
        if scan["state"] != "running":
            break
        time.sleep(0.05)
    assert seen["provider"] == "none"
    assert "resume" in scan["note"].lower()


def test_settings_accepts_role_keywords(client, workspace):
    client.post("/api/settings", json={"filters": {"title_include": "Backend, Data Engineer, "}})
    cfg = load_config(workspace / "config.yaml")
    assert cfg["filters"]["title_include"] == ["backend", "data engineer"]


def test_detect_chat_endpoint(client, monkeypatch):
    from jobtrace import telegram

    seen = {}

    def fake_detect(token):
        seen["token"] = token
        return True, [{"id": "42", "name": "Ada", "type": "private"}], "Found 1 chat(s)."

    monkeypatch.setattr(telegram, "detect_chats", fake_detect)
    data = client.post("/api/telegram/detect-chat", json={"bot_token": "123456:ABCDEFGHIJKLMNOPQRSTUV"}).json()
    assert data["ok"] and data["chats"][0]["id"] == "42"
    assert seen["token"] == "123456:ABCDEFGHIJKLMNOPQRSTUV"


def test_detect_chats_validates_token_and_parses_updates(monkeypatch):
    from jobtrace import telegram

    assert telegram.detect_chats("nope")[0] is False

    class Resp:
        status_code = 200

        def json(self):
            return {"result": [{"message": {"chat": {"id": 7, "first_name": "Ada", "last_name": "L", "type": "private"}}}]}

    monkeypatch.setattr(telegram.requests, "get", lambda *a, **k: Resp())
    ok, chats, _ = telegram.detect_chats("123456:ABCDEFGHIJKLMNOPQRSTUV")
    assert ok and chats == [{"id": "7", "name": "Ada L", "type": "private"}]


def test_state_is_capped_gzipped_and_reports_total(client, workspace, monkeypatch):
    import gzip
    import json

    from jobtrace.store import Store
    from jobtrace.web import server

    s = Store(workspace / "jobtrace.db")
    s.upsert([
        {"id": f"j{i}", "company": f"C{i % 5}", "title": f"Engineer {i}", "url": "u", "location": "Remote",
         "posted_at": None, "source": "greenhouse", "description": "x" * 300, "matches_filter": True}
        for i in range(30)
    ])
    monkeypatch.setattr(server, "STATE_MAX_JOBS", 10)
    monkeypatch.setattr(server, "_trigger_background_liveness_check", lambda: None)

    raw = client.get("/api/state", headers={"Accept-Encoding": "gzip"})
    assert raw.headers["content-encoding"] == "gzip"
    data = json.loads(gzip.decompress(raw.content)) if raw.content[:2] == b"\x1f\x8b" else raw.json()
    assert len(data["jobs"]) == 10
    assert data["stats"]["open_total"] == 30

    plain = client.get("/api/state", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert len(plain.json()["jobs"]) == 10


def test_store_connection_is_reused_per_thread(workspace):
    from jobtrace.web import server

    assert server.get_store() is server.get_store()


def test_version_endpoint(client):
    data = client.get("/api/version").json()
    assert data["version"]
    assert "commit" in data

