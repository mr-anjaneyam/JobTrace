import logging
import os
from datetime import date, timedelta

import pytest
import requests

from jobtrace import applog


class Resp:
    def __init__(self, status=200, text='{"ok": true}'):
        self.status_code = status
        self.text = text


def read(path):
    for h in logging.getLogger("jobtrace").handlers:
        h.flush()
    return path.read_text(encoding="utf-8")


@pytest.fixture
def logs(tmp_path):
    applog.configure({}, tmp_path)
    return tmp_path / "logs"


def daily_file(logs):
    return logs / "daily" / f"jobtrace-{date.today().isoformat()}.log"


def test_writes_continuous_and_daily_files(logs):
    logging.getLogger("jobtrace.test").info("hello")
    assert "hello" in read(logs / "jobtrace.log")
    assert "hello" in read(daily_file(logs))


def test_traced_logs_request_and_response(logs):
    def post(url, **kw):
        return Resp(200, '{"choices": [{"text": "answer"}]}')

    applog.traced("llm", post, "https://api.example.com/v1/chat", json={"prompt": "hi there"}, timeout=5)
    line = read(logs / "jobtrace.log")
    assert "jobtrace.llm" in line and "POST https://api.example.com/v1/chat -> 200" in line
    assert "hi there" in line and "answer" in line


def test_secrets_never_reach_the_log(logs, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "mock_dummy_secret_openai_value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "00000:dummyTelegramSampleTokenValue")

    def post(url, **kw):
        return Resp(200, '{"echo": "mock_dummy_secret_openai_value"}')

    applog.traced("llm", post, "https://x.test/v1?api_key=abc123&page=2", json={"auth": "Bearer mock_dummy_secret_openai_value"}, headers={"Authorization": "Bearer mock_dummy_secret_openai_value"})
    applog.traced("telegram", post, "https://api.telegram.org/bot00000:dummyTelegramSampleTokenValue/sendMessage", bodies=False)
    text = read(logs / "jobtrace.log")
    assert "mock_dummy_secret" not in text
    assert "abc123" not in text and "page=2" in text
    assert "dummyTelegramSample" not in text and "bot***" in text


def test_bodies_can_be_switched_off_and_clipped(tmp_path):
    applog.configure({"logging": {"log_bodies": False}}, tmp_path)
    applog.traced("portal", lambda url, **kw: Resp(200, "SECRET-BODY"), "https://a.test/jobs", json={"q": 1})
    assert "SECRET-BODY" not in read(tmp_path / "logs" / "jobtrace.log")

    applog.configure({"logging": {"log_bodies": True, "max_body_chars": 10}}, tmp_path)
    applog.traced("portal", lambda url, **kw: Resp(200, "x" * 500), "https://a.test/jobs")
    text = read(tmp_path / "logs" / "jobtrace.log")
    assert "truncated, 500 chars" in text and "x" * 50 not in text


def test_errors_and_exceptions_are_logged_and_passed_through(logs):
    out = applog.traced("portal", lambda url, **kw: Resp(503, "down"), "https://a.test/x")
    assert out.status_code == 503

    def boom(url, **kw):
        raise requests.ConnectionError("offline")

    with pytest.raises(requests.ConnectionError):
        applog.traced("portal", boom, "https://a.test/y")
    text = read(logs / "jobtrace.log")
    assert "WARNING" in text and "-> 503" in text and "FAILED" in text and "offline" in text


def test_logging_problems_never_break_the_call(logs):
    class Weird:
        status_code = "not a number"

        @property
        def text(self):
            raise RuntimeError("no body")

    assert isinstance(applog.traced("portal", lambda url, **kw: Weird(), "https://a.test/z"), Weird)


def test_old_daily_files_are_pruned(tmp_path):
    daily = tmp_path / "logs" / "daily"
    daily.mkdir(parents=True)
    old = daily / f"jobtrace-{(date.today() - timedelta(days=30)).isoformat()}.log"
    recent = daily / f"jobtrace-{(date.today() - timedelta(days=2)).isoformat()}.log"
    keep = daily / "notes.txt"
    for f in (old, recent, keep):
        f.write_text("x")
    applog.configure({"logging": {"retention_days": 7}}, tmp_path)
    assert not old.exists() and recent.exists() and keep.exists()

    applog.configure({"logging": {"retention_days": 1}}, tmp_path)
    assert not recent.exists()


def test_continuous_file_rolls_at_the_size_cap(tmp_path):
    handler = applog.ContinuousHandler(tmp_path / "c.log", max_bytes=200)
    logger = logging.getLogger("jobtrace.rolltest")
    logger.addHandler(handler)
    try:
        for i in range(250):
            logger.warning("line %s %s", i, "y" * 20)
    finally:
        logger.removeHandler(handler)
        handler.close()
    assert (tmp_path / "c.log.1").exists()


def test_level_follows_settings(tmp_path):
    applog.configure({"logging": {"level": "WARNING"}}, tmp_path)
    logging.getLogger("jobtrace.lvl").info("quiet")
    logging.getLogger("jobtrace.lvl").warning("loud")
    text = read(tmp_path / "logs" / "jobtrace.log")
    assert "loud" in text and "quiet" not in text


def test_unwritable_folder_does_not_crash(tmp_path):
    blocker = tmp_path / "logs"
    blocker.write_text("a file where the folder should be")
    applog.configure({}, tmp_path)  # must not raise
    logging.getLogger("jobtrace.x").info("still fine")
    assert os.path.isfile(blocker)
