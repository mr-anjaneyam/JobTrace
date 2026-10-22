"""Shared fixtures: tests must never read or write the developer's real config, .env or resume."""
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SECRET_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_CHAT_IDS",
    "XKIRO_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_env():
    saved = dict(os.environ)
    for name in SECRET_ENV:
        os.environ.pop(name, None)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point the web server and dotenv loader at a throwaway project root."""
    from jobtrace import main
    from jobtrace.web import server

    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"llm": {"provider": "none"}, "candidate": {"seniority": "junior"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(main, "ROOT", tmp_path)
    return tmp_path
