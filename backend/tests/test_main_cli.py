import sys
import zipfile

import pytest

from jobtrace import main, resume
from jobtrace.store import Store


def test_watched_names_prefers_alert_list():
    cfg = {"alerts": {"companies": ["A"]}, "companies": [{"name": "A"}, {"name": "B"}]}
    assert main.watched_names(cfg) == {"A"}
    assert main.watched_names({"companies": [{"name": "A"}, {"name": "B"}]}) == {"A", "B"}


def test_load_config_missing_exits(tmp_path):
    with pytest.raises(SystemExit):
        main.load_config(tmp_path / "nope.yaml")


def test_load_dotenv_sets_only_missing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# c\nFOO_JT="bar"\nKEEP_JT=new\nbad line\n', encoding="utf-8")
    monkeypatch.setenv("KEEP_JT", "old")
    monkeypatch.delenv("FOO_JT", raising=False)
    main.load_dotenv(env)
    import os
    assert os.environ["FOO_JT"] == "bar"
    assert os.environ["KEEP_JT"] == "old"  # real environment wins over .env
    monkeypatch.delenv("FOO_JT", raising=False)
    monkeypatch.delenv("KEEP_JT", raising=False)


def test_cmd_web_binds_loopback_by_default(monkeypatch):
    seen = {}
    import types

    fake = types.SimpleNamespace(run=lambda app, **kw: seen.update(kw))
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    monkeypatch.delenv("JOBTRACE_HOST", raising=False)
    monkeypatch.delenv("JOBTRACE_RELOAD", raising=False)
    main.cmd_web(port=9999)
    assert seen["host"] == "127.0.0.1" and seen["reload"] is False and seen["port"] == 9999


def test_cmd_list_handles_empty(tmp_path, capsys):
    main.cmd_list(Store(tmp_path / "t.db"))
    assert "No recent openings" in capsys.readouterr().out


def test_cmd_digest_dry_run_sends_nothing(tmp_path, monkeypatch, capsys):
    s = Store(tmp_path / "t.db")
    s.upsert([{"id": "1", "company": "Acme", "title": "Eng", "url": "u", "location": "Remote",
               "posted_at": None, "source": "greenhouse", "description": "", "matches_filter": True}])
    sent = []
    monkeypatch.setattr(main.telegram, "send_digest", lambda *a, **k: sent.append(1))
    main.cmd_digest({"llm": {"provider": "none"}}, s, dry_run=True)
    assert not sent and "DRY RUN" in capsys.readouterr().out


def test_docx_extraction(tmp_path):
    path = tmp_path / "cv.docx"
    xml = (
        '<w:document xmlns:w="x"><w:body>'
        "<w:p><w:r><w:t>Jane Doe</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>R&amp;D Engineer</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)
    text = resume.extract_text(path)
    assert text.splitlines() == ["Jane Doe", "R&D Engineer"]


def test_bad_docx_raises(tmp_path):
    path = tmp_path / "cv.docx"
    path.write_text("not a zip", encoding="utf-8")
    with pytest.raises(RuntimeError):
        resume.extract_text(path)
