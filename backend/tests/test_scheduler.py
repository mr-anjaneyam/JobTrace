import datetime

from jobtrace import scheduler as sched_mod
from jobtrace.scheduler import Scheduler


class FakeDT(datetime.datetime):
    current = datetime.datetime(2026, 10, 19, 9, 0)  # a Monday

    @classmethod
    def now(cls, tz=None):
        return cls.current


def make(monkeypatch):
    calls = {"alert": 0, "digest": 0}
    monkeypatch.setattr(sched_mod.datetime, "datetime", FakeDT)
    s = Scheduler(
        alert_fn=lambda: calls.__setitem__("alert", calls["alert"] + 1),
        digest_fn=lambda: calls.__setitem__("digest", calls["digest"] + 1),
    )
    return s, calls


def test_nothing_before_slot(monkeypatch):
    s, calls = make(monkeypatch)
    FakeDT.current = datetime.datetime(2026, 10, 19, 8, 59)
    s.tick()
    assert calls == {"alert": 0, "digest": 0}


def test_fires_once_per_day(monkeypatch):
    s, calls = make(monkeypatch)
    FakeDT.current = datetime.datetime(2026, 10, 19, 9, 31)
    s.tick()
    s.tick()
    assert calls == {"alert": 1, "digest": 1}


def test_catches_up_when_started_late(monkeypatch):
    s, calls = make(monkeypatch)
    FakeDT.current = datetime.datetime(2026, 10, 19, 14, 5)
    s.tick()
    assert calls == {"alert": 1, "digest": 1}


def test_digest_only_on_digest_weekday(monkeypatch):
    s, calls = make(monkeypatch)
    FakeDT.current = datetime.datetime(2026, 10, 21, 10, 0)  # Wednesday
    s.tick()
    assert calls == {"alert": 1, "digest": 0}


def test_failure_does_not_stop_scheduler(monkeypatch):
    monkeypatch.setattr(sched_mod.datetime, "datetime", FakeDT)
    FakeDT.current = datetime.datetime(2026, 10, 19, 10, 0)

    def boom():
        raise RuntimeError("down")

    s = Scheduler(alert_fn=boom, digest_fn=boom)
    s.tick()
    assert s.last_alert_date == "2026-10-19"


def test_declined_job_is_retried_not_consumed(monkeypatch):
    monkeypatch.setattr(sched_mod.datetime, "datetime", FakeDT)
    FakeDT.current = datetime.datetime(2026, 10, 21, 10, 0)  # Wednesday
    state = {"ready": False, "runs": 0}

    def job():
        if not state["ready"]:
            return False
        state["runs"] += 1
        return True

    s = Scheduler(alert_fn=job, digest_fn=lambda: None)
    s.tick()
    s.tick()
    assert s.last_alert_date is None and state["runs"] == 0
    state["ready"] = True
    s.tick()
    s.tick()
    assert s.last_alert_date == "2026-10-21" and state["runs"] == 1
