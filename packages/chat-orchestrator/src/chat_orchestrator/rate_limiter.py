"""Sliding-window rate limiter using SQLite."""
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite


@dataclass
class RateLimitInfo:
    limit: int
    remaining: int
    reset_at: str | None


@dataclass
class RateLimitResult:
    ok: bool
    limits: dict[str, RateLimitInfo]


class RateLimiter:
    def __init__(self, db_path: str, per_hour: int, per_day: int):
        self._db_path = db_path
        self.per_hour = per_hour
        self.per_day = per_day
        self._insert_count = 0

    @classmethod
    async def create(
        cls,
        db_path: str | None = None,
        per_hour: int | None = None,
        per_day: int | None = None,
    ) -> "RateLimiter":
        if db_path is None:
            db_path = os.getenv("RATE_LIMIT_DB_PATH", "/app/data/rate_limiter.db")
        if per_hour is None:
            per_hour = int(os.getenv("RATE_LIMIT_MESSAGES_PER_HOUR", "5"))
        if per_day is None:
            per_day = int(os.getenv("RATE_LIMIT_MESSAGES_PER_DAY", "20"))
        self = cls(db_path, per_hour, per_day)
        self._conn = await aiosqlite.connect(db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS message_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_log_user_id
            ON message_log(user_id)
        """)
        await self._conn.commit()
        return self

    async def close(self):
        if hasattr(self, "_conn"):
            await self._conn.close()

    async def check_and_increment(self, user_id: str) -> RateLimitResult:
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400

        cur = await self._conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM message_log WHERE user_id = ? AND created_at > ?",
            (user_id, hour_ago),
        )
        hour_count, hour_oldest = await cur.fetchone()

        cur = await self._conn.execute(
            "SELECT COUNT(*), MIN(created_at) FROM message_log WHERE user_id = ? AND created_at > ?",
            (user_id, day_ago),
        )
        day_count, day_oldest = await cur.fetchone()

        hour_remaining = max(0, self.per_hour - hour_count)
        day_remaining = max(0, self.per_day - day_count)

        hour_exceeded = hour_count >= self.per_hour
        day_exceeded = day_count >= self.per_day

        hour_reset = (
            datetime.fromtimestamp(hour_oldest + 3600, tz=timezone.utc).isoformat()
            if hour_exceeded and hour_oldest is not None else None
        )
        day_reset = (
            datetime.fromtimestamp(day_oldest + 86400, tz=timezone.utc).isoformat()
            if day_exceeded and day_oldest is not None else None
        )

        if hour_exceeded or day_exceeded:
            return RateLimitResult(ok=False, limits={
                "hour": RateLimitInfo(limit=self.per_hour, remaining=hour_remaining, reset_at=hour_reset),
                "day": RateLimitInfo(limit=self.per_day, remaining=day_remaining, reset_at=day_reset),
            })

        await self._conn.execute(
            "INSERT INTO message_log (user_id, created_at) VALUES (?, ?)",
            (user_id, now),
        )
        self._insert_count += 1
        if self._insert_count % 100 == 0:
            await self._conn.execute(
                "DELETE FROM message_log WHERE created_at < ?",
                (now - 86400,),
            )
        await self._conn.commit()

        return RateLimitResult(ok=True, limits={
            "hour": RateLimitInfo(limit=self.per_hour, remaining=hour_remaining - 1, reset_at=None),
            "day": RateLimitInfo(limit=self.per_day, remaining=day_remaining - 1, reset_at=None),
        })
