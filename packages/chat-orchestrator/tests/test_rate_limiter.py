"""Rate limiter: sliding window enforcement and its use by the message loop."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect

# ---------------------------------------------------------------------------
# TestRateLimiter — sliding window rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiterDataTypes:
    """RateLimitResult and RateLimitInfo data types."""

    def test_rate_limit_info_defaults(self):
        from chat_orchestrator.rate_limiter import RateLimitInfo
        info = RateLimitInfo(limit=5, remaining=3, reset_at="2026-06-01T12:00:00Z")
        assert info.limit == 5
        assert info.remaining == 3

    def test_rate_limit_result(self):
        from chat_orchestrator.rate_limiter import RateLimitInfo, RateLimitResult
        info = RateLimitInfo(limit=5, remaining=0, reset_at="2026-06-01T12:00:00Z")
        result = RateLimitResult(ok=False, limits={"hour": info})
        assert result.ok is False
        assert result.limits["hour"].remaining == 0


class TestRateLimiterInit:
    """RateLimiter initialization and schema creation."""

    @pytest.mark.asyncio
    async def test_init_creates_table(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=5, per_day=20)
        try:
            cursor = await limiter._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='message_log'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "message_log"
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_init_creates_index(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:")
        try:
            cursor = await limiter._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_message_log_user_id'"
            )
            row = await cursor.fetchone()
            assert row is not None
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_uses_env_values_when_not_provided(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_HOUR", "10")
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_DAY", "50")
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:")
        try:
            assert limiter.per_hour == 10
            assert limiter.per_day == 50
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_uses_defaults_when_no_env(self, monkeypatch):
        monkeypatch.delenv("RATE_LIMIT_MESSAGES_PER_HOUR", raising=False)
        monkeypatch.delenv("RATE_LIMIT_MESSAGES_PER_DAY", raising=False)
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:")
        try:
            assert limiter.per_hour == 5
            assert limiter.per_day == 20
        finally:
            await limiter.close()


class TestRateLimiterCheckAndIncrement:
    """RateLimiter.check_and_increment core logic."""

    @pytest.mark.asyncio
    async def test_first_message_allowed(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:")
        try:
            result = await limiter.check_and_increment("user-1")
            assert result.ok is True
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_within_hour_limit_allowed(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=3, per_day=20)
        try:
            for _ in range(3):
                r = await limiter.check_and_increment("user-1")
                assert r.ok is True
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_exceeds_hour_limit(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=2, per_day=20)
        try:
            for _ in range(2):
                await limiter.check_and_increment("user-1")
            result = await limiter.check_and_increment("user-1")
            assert result.ok is False
            assert result.limits["hour"].remaining == 0
            assert result.limits["hour"].reset_at is not None
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_exceeds_day_limit(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=10, per_day=2)
        try:
            for _ in range(2):
                await limiter.check_and_increment("user-1")
            result = await limiter.check_and_increment("user-1")
            assert result.ok is False
            assert result.limits["day"].remaining == 0
            assert result.limits["day"].reset_at is not None
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_remaining_decreases(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=3, per_day=20)
        try:
            r1 = await limiter.check_and_increment("user-1")
            assert r1.limits["hour"].remaining == 2
            r2 = await limiter.check_and_increment("user-1")
            assert r2.limits["hour"].remaining == 1
            r3 = await limiter.check_and_increment("user-1")
            assert r3.limits["hour"].remaining == 0
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_remaining_never_negative(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=1, per_day=20)
        try:
            await limiter.check_and_increment("user-1")
            await limiter.check_and_increment("user-1")
            r = await limiter.check_and_increment("user-1")
            assert r.limits["hour"].remaining == 0
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=2, per_day=20)
        try:
            for _ in range(2):
                await limiter.check_and_increment("user-a")
            r_a = await limiter.check_and_increment("user-a")
            assert r_a.ok is False
            r_b = await limiter.check_and_increment("user-b")
            assert r_b.ok is True
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_concurrent_check_and_increment_never_exceeds_limit(self, tmp_path):
        import asyncio

        from chat_orchestrator.rate_limiter import RateLimiter

        db_path = str(tmp_path / "rate.db")
        limiter = await RateLimiter.create(db_path, per_hour=1, per_day=100)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[limiter.check_and_increment("same-user") for _ in range(10)]
                ),
                timeout=5,
            )
            assert sum(1 for result in results if result.ok) == 1
            cur = await limiter._conn.execute(
                "SELECT COUNT(*) FROM message_log WHERE user_id = ?",
                ("same-user",),
            )
            row = await cur.fetchone()
            assert row[0] == 1
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests_keep_users_independent(self, tmp_path):
        import asyncio

        from chat_orchestrator.rate_limiter import RateLimiter

        limiter = await RateLimiter.create(str(tmp_path / "rate.db"), per_hour=1, per_day=100)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    limiter.check_and_increment("user-a"),
                    limiter.check_and_increment("user-b"),
                    limiter.check_and_increment("user-a"),
                    limiter.check_and_increment("user-b"),
                ),
                timeout=5,
            )
            assert results[0].ok is True
            assert results[1].ok is True
            assert results[2].ok is False
            assert results[3].ok is False
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_reset_at_for_hour_limit(self):
        import time
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=2, per_day=20)
        try:
            now = time.time()
            await limiter.check_and_increment("user-1")
            await limiter.check_and_increment("user-1")
            result = await limiter.check_and_increment("user-1")
            assert result.ok is False
            expected_reset = now + 3600
            actual_reset = _parse_iso(result.limits["hour"].reset_at)
            assert abs(actual_reset - expected_reset) < 2
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_reset_at_null_when_not_exceeded(self):
        from chat_orchestrator.rate_limiter import RateLimiter
        limiter = await RateLimiter.create(":memory:", per_hour=5, per_day=20)
        try:
            r = await limiter.check_and_increment("user-1")
            assert r.limits["hour"].reset_at is None
            assert r.limits["day"].reset_at is None
        finally:
            await limiter.close()


class TestMessageLoopRateLimit:
    """_message_loop rate limiting via RateLimiter."""

    @pytest.fixture(autouse=True)
    async def _cleanup_rate_limiter(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_HOUR", "1")
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_DAY", "20")
        monkeypatch.setenv("RATE_LIMIT_DB_PATH", ":memory:")
        import chat_orchestrator.rate_limiter as routes_mod
        routes_mod._rate_limiter = None
        yield
        if routes_mod._rate_limiter is not None:
            await routes_mod._rate_limiter.close()
            routes_mod._rate_limiter = None

    @pytest.mark.asyncio
    async def test_rate_limited_message_returns_error(self, monkeypatch):

        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "msg 1"}),
            json.dumps({"text": "msg 2"}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()
        monkeypatch.setattr(
            "chat_orchestrator.routes.run_chat",
            AsyncMock(return_value="ok"),
        )

        from chat_orchestrator.routes import _message_loop
        try:
            await _message_loop(ws, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        # msg 1 should succeed, msg 2 should be rate-limited
        assert ws.send_json.await_count == 2
        error_call = ws.send_json.await_args_list[1]
        payload = error_call[0][0]
        assert payload["type"] == "error"
        assert payload["code"] == "rate_limit_exceeded"
        assert payload["limits"]["hour"]["remaining"] == 0
        assert payload["limits"]["day"]["remaining"] == 19


class TestGetRateLimiterSingleton:
    @pytest.mark.asyncio
    async def test_concurrent_get_rate_limiter_creates_once(self, monkeypatch):
        import asyncio

        import chat_orchestrator.rate_limiter as limiter_mod

        limiter_mod._rate_limiter = None
        create_calls = 0
        original_create = limiter_mod.RateLimiter.create

        async def counting_create(*args, **kwargs):
            nonlocal create_calls
            create_calls += 1
            await asyncio.sleep(0.01)
            return await original_create(":memory:", per_hour=5, per_day=20)

        monkeypatch.setattr(limiter_mod.RateLimiter, "create", counting_create)
        try:
            instances = await asyncio.gather(
                *[limiter_mod.get_rate_limiter() for _ in range(10)]
            )
            assert create_calls == 1
            assert all(instance is instances[0] for instance in instances)
        finally:
            if limiter_mod._rate_limiter is not None:
                await limiter_mod._rate_limiter.close()
                limiter_mod._rate_limiter = None


def _parse_iso(iso: str) -> float:
    from datetime import datetime, timezone
    return datetime.fromisoformat(iso).timestamp()
