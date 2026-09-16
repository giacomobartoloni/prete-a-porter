"""Rate limiter: sliding window enforcement and its use by the message loop."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect
from langchain_core.messages import AIMessage

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
    async def test_rate_limited_message_returns_error(self):

        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "msg 1"}),
            json.dumps({"text": "msg 2"}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = None
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="ok")],
        })

        from chat_orchestrator.routes import _message_loop
        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
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


def _parse_iso(iso: str) -> float:
    from datetime import datetime, timezone
    return datetime.fromisoformat(iso).timestamp()
