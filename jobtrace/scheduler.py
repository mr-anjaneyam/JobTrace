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

    def tick(self) -> None:
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # 1. Daily Alert Check
        if (
            now.hour == self.alert_hour
            and now.minute >= self.alert_minute
            and self.last_alert_date != today_str
        ):
            print(f"[{now.strftime('%H:%M:%S')}] Triggering daily alert pass...", flush=True)
            try:
                self.alert_fn()
            except Exception as e:
                print(f"Error during scheduled alert: {e}", flush=True)
            self.last_alert_date = today_str

        # 2. Weekly Digest Check (Mondays)
        if (
            now.weekday() == self.digest_weekday
            and now.hour == self.digest_hour
            and now.minute >= self.digest_minute
            and self.last_digest_date != today_str
        ):
            print(f"[{now.strftime('%H:%M:%S')}] Triggering weekly digest pass...", flush=True)
            try:
                self.digest_fn()
            except Exception as e:
                print(f"Error during scheduled digest: {e}", flush=True)
            self.last_digest_date = today_str

    def run_forever(self, interval_seconds: int = 30) -> None:
        print("JobTrace scheduler running in background. Press Ctrl+C to stop.", flush=True)
        print(f"  Daily Alerts: Every day at {self.alert_hour:02d}:{self.alert_minute:02d}")
        print(f"  Weekly Digest: Mondays at {self.digest_hour:02d}:{self.digest_minute:02d}")
        while True:
            self.tick()
            time.sleep(interval_seconds)
