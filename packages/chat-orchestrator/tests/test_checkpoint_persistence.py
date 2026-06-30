"""Tests for checkpoint persistence features in chat-orchestrator.

Covers:
  1. _message_loop checkpoint recovery (routes.py)
  2. DELETE /checkpoints/{session_id} endpoint (main.py)
  3. cleanup_old_checkpoints TTL logic (cleanup.py)
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from chat_orchestrator.cleanup import cleanup_old_checkpoints
from chat_orchestrator.routes import _message_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockCheckpoint:
    """Simulates a single checkpoint entry yielded by an async checkpointer."""

    def __init__(self, ts: str, thread_id: str):
        self.checkpoint = {"ts": ts}
        self.config = {"configurable": {"thread_id": thread_id}}

class MockCheckpointWithUser:
    """Simulates a checkpoint with channel_values containing user_id."""

    def __init__(self, user_id: str):
        self.checkpoint = {"channel_values": {"user_id": user_id}}


class RecordingCheckpointer:
    """Test double that records deletions and yields given checkpoints."""

    def __init__(self, checkpoints=None):
        self.checkpoints = checkpoints or []
        self.deleted = []

    async def alist(self):
        for cp in self.checkpoints:
            yield cp

    async def adelete_thread(self, thread_id):
        self.deleted.append(thread_id)


def _iso_days_ago(days: int) -> str:
    """Return an ISO-format UTC timestamp *days* in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# TestMessageLoop — _message_loop checkpoint recovery
# ---------------------------------------------------------------------------

class TestMessageLoop:
    """Checkpoint recovery logic inside _message_loop (routes.py)."""

    @pytest.fixture(autouse=True)
    async def _set_rate_limit_env(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_DB_PATH", ":memory:")
        import chat_orchestrator.routes as routes_mod
        routes_mod._rate_limiter = None
        yield
        if routes_mod._rate_limiter is not None:
            await routes_mod._rate_limiter.close()
            routes_mod._rate_limiter = None

    @pytest.mark.asyncio
    async def test_with_checkpoint_passes_only_new_text(self):
        """When aget_tuple returns a checkpoint, only the new text is passed."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "new message", "history": [{"content": "old msg"}]}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = MockCheckpointWithUser("user-1")
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="response")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "new message"
        ws.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_checkpoint_rebuilds_from_history(self):
        """When no checkpoint, history + new text are passed."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "latest", "history": [{"content": "first"}, {"content": "second"}]}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = None
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="ok")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 3
        assert msgs[0].content == "first"
        assert msgs[1].content == "second"
        assert msgs[2].content == "latest"
        state = graph.ainvoke.call_args[0][0]
        assert state["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_checkpointer_error_falls_back_to_history(self):
        """When aget_tuple raises, treat as no-checkpoint and rebuild."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "new", "history": [{"content": "prev"}]}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.side_effect = RuntimeError("db down")
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="ok")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 2
        assert msgs[0].content == "prev"
        assert msgs[1].content == "new"
        state = graph.ainvoke.call_args[0][0]
        assert state["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_non_json_message_uses_raw_text(self):
        """Non-JSON message falls back to raw text with empty history."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            "plain text message",
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = None
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="ok")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 1
        assert msgs[0].content == "plain text message"
        state = graph.ainvoke.call_args[0][0]
        assert state["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_with_checkpoint_ignores_client_history(self):
        """Checkpoint present → client history is ignored."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "latest", "history": [{"content": "should be ignored"}]}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = MockCheckpointWithUser("user-1")
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="resp")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 1
        assert msgs[0].content == "latest"

    @pytest.mark.asyncio
    async def test_without_checkpoint_and_no_history(self):
        """No checkpoint, no history → only new text passed."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "hello"}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = None
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="hi")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 1
        assert msgs[0].content == "hello"
        state = graph.ainvoke.call_args[0][0]
        assert state["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_non_json_with_checkpoint_uses_raw_text(self):
        """Non-JSON + live checkpoint → raw text, no history."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            "raw input",
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = MockCheckpointWithUser("user-1")
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="resp")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 1
        assert msgs[0].content == "raw input"

    @pytest.mark.asyncio
    async def test_missing_checkpointer_falls_back(self):
        """Missing checkpointer attribute → history rebuild."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "hi", "history": [{"content": "prev"}]}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()

        graph = MagicMock(spec=[])
        graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="resp")],
        })

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()
        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert len(msgs) == 2
        assert msgs[0].content == "prev"
        assert msgs[1].content == "hi"
        state = graph.ainvoke.call_args[0][0]
        assert state["user_id"] == "user-1"


    @pytest.mark.asyncio
    async def test_mismatched_user_id_closes_websocket(self):
        """When checkpoint user_id != JWT sub, close with 4003."""
        ws = MagicMock()
        ws.receive_text = AsyncMock(side_effect=[
            json.dumps({"text": "hello"}),
            WebSocketDisconnect(),
        ])
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()

        graph = MagicMock()
        graph.checkpointer = AsyncMock()
        graph.checkpointer.aget_tuple.return_value = MockCheckpointWithUser("alice")
        graph.ainvoke = AsyncMock()

        try:
            await _message_loop(ws, graph, "session-1", "bob", "corr-1")
        except WebSocketDisconnect:
            pass

        ws.close.assert_awaited_once_with(code=4003, reason="Forbidden")
        graph.ainvoke.assert_not_called()


# ---------------------------------------------------------------------------
# TestDeleteCheckpoint — DELETE /checkpoints/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteCheckpoint:
    """DELETE /checkpoints/{session_id} endpoint (main.py)."""

    @pytest.mark.asyncio
    async def test_returns_204(self):
        """Endpoint returns HTTP 204."""
        mock_graph = AsyncMock()
        mock_graph.checkpointer = AsyncMock()

        with patch("chat_orchestrator.main.get_graph", return_value=mock_graph):
            from chat_orchestrator.main import delete_checkpoint
            response = await delete_checkpoint("session-abc")
            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_calls_adelete_thread_with_session_id(self):
        """adelete_thread is called with the correct session_id."""
        mock_graph = AsyncMock()
        mock_graph.checkpointer = AsyncMock()

        with patch("chat_orchestrator.main.get_graph", return_value=mock_graph):
            from chat_orchestrator.main import delete_checkpoint
            await delete_checkpoint("session-xyz")
            mock_graph.checkpointer.adelete_thread.assert_awaited_once_with("session-xyz")

    @pytest.mark.asyncio
    async def test_does_not_crash_when_thread_missing(self):
        """Exception from adelete_thread is caught, still returns 204."""
        mock_graph = AsyncMock()
        mock_graph.checkpointer = AsyncMock()
        mock_graph.checkpointer.adelete_thread.side_effect = Exception("not found")

        with patch("chat_orchestrator.main.get_graph", return_value=mock_graph):
            from chat_orchestrator.main import delete_checkpoint
            response = await delete_checkpoint("ghost-session")
            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_handles_graph_error_gracefully(self):
        """Exception from get_graph is caught, still returns 204."""
        with patch(
            "chat_orchestrator.main.get_graph",
            side_effect=RuntimeError("connection refused"),
        ):
            from chat_orchestrator.main import delete_checkpoint
            response = await delete_checkpoint("session-1")
            assert response.status_code == 204


# ---------------------------------------------------------------------------
# TestCleanupOldCheckpoints — background TTL cleanup
# ---------------------------------------------------------------------------

class TestCleanupOldCheckpoints:
    """cleanup_old_checkpoints TTL logic (cleanup.py)."""

    @pytest.mark.asyncio
    async def test_does_not_delete_recent_checkpoints(self, monkeypatch):
        """Checkpoints within the TTL window are kept."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")
        cp = RecordingCheckpointer([
            MockCheckpoint(_iso_days_ago(0), "now"),
            MockCheckpoint(_iso_days_ago(30), "recent-1"),
            MockCheckpoint(_iso_days_ago(89), "recent-2"),
        ])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 0
        assert cp.deleted == []

    @pytest.mark.asyncio
    async def test_deletes_old_checkpoints(self, monkeypatch):
        """Checkpoints past the TTL window are deleted."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")
        cp = RecordingCheckpointer([
            MockCheckpoint(_iso_days_ago(180), "old-1"),
            MockCheckpoint(_iso_days_ago(365), "old-2"),
        ])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 2
        assert "old-1" in cp.deleted
        assert "old-2" in cp.deleted

    @pytest.mark.asyncio
    async def test_mixed_ages_only_old_deleted(self, monkeypatch):
        """Only checkpoints past the TTL are deleted; recent survive."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")
        cp = RecordingCheckpointer([
            MockCheckpoint(_iso_days_ago(180), "old"),
            MockCheckpoint(_iso_days_ago(30), "recent"),
            MockCheckpoint(_iso_days_ago(200), "very-old"),
            MockCheckpoint(_iso_days_ago(0), "now"),
        ])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 2
        assert "old" in cp.deleted
        assert "very-old" in cp.deleted
        assert "recent" not in cp.deleted
        assert "now" not in cp.deleted

    @pytest.mark.asyncio
    async def test_empty_checkpoints_returns_zero(self, monkeypatch):
        """An empty checkpointer returns 0 without error."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")
        cp = RecordingCheckpointer([])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 0
        assert cp.deleted == []

    @pytest.mark.asyncio
    async def test_skips_checkpoints_without_timestamp(self, monkeypatch):
        """Checkpoints missing the 'ts' field are silently skipped."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")

        cps = [
            MockCheckpoint(_iso_days_ago(200), "has-ts"),
            MockCheckpoint("", "no-ts"),
            MockCheckpoint(_iso_days_ago(180), "also-has-ts"),
        ]
        cps[1].checkpoint = {}

        graph = MagicMock()
        graph.checkpointer = RecordingCheckpointer(cps)

        with patch.object(graph.checkpointer, "adelete_thread", wraps=graph.checkpointer.adelete_thread) as del_spy:
            count = await cleanup_old_checkpoints(graph)

        assert count == 2
        assert del_spy.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_bad_timestamp_format(self, monkeypatch):
        """Unparseable ts strings are skipped."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")
        cp = RecordingCheckpointer([
            MockCheckpoint("not-a-date", "bad-1"),
            MockCheckpoint(_iso_days_ago(200), "good"),
        ])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 1
        assert "bad-1" not in cp.deleted
        assert "good" in cp.deleted

    @pytest.mark.asyncio
    async def test_returns_deleted_count(self, monkeypatch):
        """Return value matches the number of deleted checkpoints."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "90")
        cp = RecordingCheckpointer([
            MockCheckpoint(_iso_days_ago(180), "old"),
            MockCheckpoint(_iso_days_ago(0), "fresh"),
        ])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 1

    @pytest.mark.asyncio
    async def test_custom_ttl_from_env(self, monkeypatch):
        """TTL is read from the CHECKPOINT_TTL_DAYS env var (default 90)."""
        monkeypatch.setenv("CHECKPOINT_TTL_DAYS", "30")
        cp = RecordingCheckpointer([
            MockCheckpoint(_iso_days_ago(60), "too-old"),
            MockCheckpoint(_iso_days_ago(15), "still-fresh"),
        ])
        graph = MagicMock()
        graph.checkpointer = cp

        count = await cleanup_old_checkpoints(graph)

        assert count == 1
        assert "too-old" in cp.deleted
        assert "still-fresh" not in cp.deleted


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
        import chat_orchestrator.routes as routes_mod
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
