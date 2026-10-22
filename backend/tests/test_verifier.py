import time
from contextlib import contextmanager

from jobtrace import verifier
from jobtrace.store import Store


class FakeRaw:
    def __init__(self, body):
        self.body = body

    def read(self, n, decode_content=True):
        return self.body[:n]


class FakeResponse:
    def __init__(self, status=200, url="https://boards.example.com/jobs/1", body=b"<html>open role</html>"):
        self.status_code = status
        self.url = url
        self.raw = FakeRaw(body)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_get(monkeypatch, resp=None, exc=None):
    def fake_get(*a, **k):
        if exc:
            raise exc
        return resp

    monkeypatch.setattr(verifier.requests, "get", fake_get)


def test_live_posting(monkeypatch):
    patch_get(monkeypatch, FakeResponse())
    assert verifier.check_url_liveness("https://boards.example.com/jobs/1") == (True, "Active")


def test_404_means_closed(monkeypatch):
    patch_get(monkeypatch, FakeResponse(status=404))
    active, reason = verifier.check_url_liveness("https://boards.example.com/jobs/1")
    assert active is False and "404" in reason


def test_archived_notice_means_closed(monkeypatch):
    patch_get(monkeypatch, FakeResponse(body=b"Sorry, this job listing is archived."))
    active, _ = verifier.check_url_liveness("https://boards.example.com/jobs/1")
    assert active is False


def test_remotive_redirect_to_index_means_closed(monkeypatch):
    patch_get(monkeypatch, FakeResponse(url="https://remotive.com/remote-jobs"))
    active, reason = verifier.check_url_liveness("https://remotive.com/remote-jobs/software-dev/foo-123")
    assert active is False and "archived" in reason


def test_network_errors_never_discard(monkeypatch):
    patch_get(monkeypatch, exc=verifier.requests.Timeout())
    assert verifier.check_url_liveness("https://boards.example.com/jobs/1")[0] is True


def test_forbidden_is_assumed_active(monkeypatch):
    patch_get(monkeypatch, FakeResponse(status=403))
    assert verifier.check_url_liveness("https://boards.example.com/jobs/1")[0] is True


def test_missing_url_is_skipped():
    assert verifier.check_url_liveness("")[0] is True


def job(i, source="greenhouse", posted_at=None, last_seen=None):
    return {
        "id": i, "company": "Acme", "title": f"Eng {i}", "url": f"https://boards.example.com/jobs/{i}",
        "location": "Remote", "posted_at": posted_at, "source": source, "description": "", "matches_filter": True,
    }


def test_discard_elapsed_only_hits_stale_aggregators(tmp_path):
    s = Store(tmp_path / "t.db")
    old = time.time() - 40 * 86400
    s.upsert([job("old", "remotive", posted_at=old), job("new", "remotive", posted_at=time.time()), job("gh", "greenhouse", posted_at=old)])
    assert verifier.discard_elapsed_jobs(s, max_age_days=14) == ["old"]


def test_verify_and_discard_closes_dead_jobs(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.db")
    s.upsert([job("alive"), job("dead")])

    def fake_check(url, timeout=4.0):
        return (not url.endswith("/dead"), "Listing removed (HTTP 404)")

    monkeypatch.setattr(verifier, "check_url_liveness", fake_check)
    res = verifier.verify_and_discard_jobs(s)
    assert res["checked"] == 2 and res["closed_count"] == 1
    assert [c["id"] for c in res["closed"]] == ["dead"]
    assert s.stats()["open"] == 1
