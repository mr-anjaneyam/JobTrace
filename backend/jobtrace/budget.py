"""Daily token budget enforcement backed by SQLite."""
from __future__ import annotations

import sqlite3
import time


class Budget:
    def __init__(self, db: sqlite3.Connection, daily_limit: int = 500_000, reserve: int = 40_000):
        self.db = db
        self.daily_limit = daily_limit
        self.reserve = reserve
        self._ensure_table()

    def _ensure_table(self) -> None:
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS spend (
                day     TEXT PRIMARY KEY,
                tokens  INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.db.commit()

    @staticmethod
    def _today() -> str:
        # UTC date avoids local midnight skew across machines
        return time.strftime("%Y-%m-%d", time.gmtime())

    def used(self) -> int:
        row = self.db.execute("SELECT tokens FROM spend WHERE day = ?", (self._today(),)).fetchone()
        return (row[0] if row else 0) or 0

    def remaining(self) -> int:
        return max(0, self.daily_limit - self.reserve - self.used())

    def can_afford(self, tokens: int) -> bool:
        return self.remaining() >= tokens

    def record(self, tokens: int) -> None:
        if tokens <= 0:
            return
        self.db.execute(
            """INSERT INTO spend (day, tokens) VALUES (?, ?)
               ON CONFLICT(day) DO UPDATE SET tokens = tokens + excluded.tokens""",
            (self._today(), int(tokens)),
        )
        self.db.commit()

    def report(self) -> str:
        used, limit = self.used(), self.daily_limit
        pct = (100 * used // limit) if limit else 0
        return f"{used:,}/{limit:,} tokens today ({pct}%), {self.remaining():,} spendable remaining"
