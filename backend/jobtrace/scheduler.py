"""Cross-platform background scheduler for JobTrace.

Supports standalone daemon execution without requiring macOS launchd,
running daily alert checks and weekly Telegram digests on schedule.
"""
from __future__ import annotations

import datetime
import time
from typing import Callable


class Scheduler:
    def __init__(
        self,
        alert_fn: Callable[[], None],
        digest_fn: Callable[[], None],
        alert_hour: int = 9,
        alert_minute: int = 30,
        digest_weekday: int = 0,  # Monday = 0
        digest_hour: int = 9,
        digest_minute: int = 0,
    ):
        self.alert_fn = alert_fn
        self.digest_fn = digest_fn
        self.alert_hour = alert_hour
        self.alert_minute = alert_minute
        self.digest_weekday = digest_weekday
        self.digest_hour = digest_hour
        self.digest_minute = digest_minute

        self.last_alert_date: str | None = None
        self.last_digest_date: str | None = None

    def _attempt(self, key: str, label: str, fn: Callable[[], object], now: datetime.datetime) -> None:
        """Run a job; a job that returns False declined to run and is retried on the next tick."""
        today = now.strftime("%Y-%m-%d")
        if getattr(self, f"_announced_{key}", None) != today:
            print(f"[{now.strftime('%H:%M:%S')}] Triggering {label}...", flush=True)
            setattr(self, f"_announced_{key}", today)
        try:
            ran = fn()
        except Exception as e:
            print(f"Error during scheduled {label}: {e}", flush=True)
            ran = True
        if ran is not False:
            setattr(self, f"last_{key}_date", today)

    def tick(self) -> None:
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # 1. Daily Alert Check (catches up if the process started after the slot)
        if (
            (now.hour, now.minute) >= (self.alert_hour, self.alert_minute)
            and self.last_alert_date != today_str
        ):
            self._attempt("alert", "daily alert pass", self.alert_fn, now)

        # 2. Weekly Digest Check (Mondays)
        if (
            now.weekday() == self.digest_weekday
            and (now.hour, now.minute) >= (self.digest_hour, self.digest_minute)
            and self.last_digest_date != today_str
        ):
            self._attempt("digest", "weekly digest pass", self.digest_fn, now)

    def run_forever(self, interval_seconds: int = 30) -> None:
        print("JobTrace scheduler running in background. Press Ctrl+C to stop.", flush=True)
        print(f"  Daily Alerts: Every day at {self.alert_hour:02d}:{self.alert_minute:02d}")
        print(f"  Weekly Digest: Mondays at {self.digest_hour:02d}:{self.digest_minute:02d}")
        while True:
            self.tick()
            time.sleep(interval_seconds)
