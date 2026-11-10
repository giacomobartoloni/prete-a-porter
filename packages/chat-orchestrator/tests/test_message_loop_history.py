"""The message loop rebuilds history from the request and passes no thread_id.

There is no server-side conversation state: every turn supplies its own history,
and execution goes through application.run_chat.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect

from chat_orchestrator.routes import _message_loop


@pytest.fixture(autouse=True)
async def _isolate_rate_limiter(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DB_PATH", ":memory:")
    import chat_orchestrator.rate_limiter as routes_mod
    routes_mod._rate_limiter = None
    yield
    if routes_mod._rate_limiter is not None:
        await routes_mod._rate_limiter.close()
        routes_mod._rate_limiter = None


def _ws(payloads):
    ws = MagicMock()
    ws.receive_text = AsyncMock(side_effect=[*payloads, WebSocketDisconnect()])
    ws.send_json = AsyncMock()
    return ws


class TestMessageLoopHistory:
    @pytest.mark.asyncio
    async def test_history_is_replayed_then_new_text(self, monkeypatch):
        run_chat = AsyncMock(return_value="ok")
        monkeypatch.setattr("chat_orchestrator.routes.run_chat", run_chat)
        ws = _ws([json.dumps({"text": "latest", "history": [{"content": "first"}, {"content": "second"}]})])

        try:
            await _message_loop(ws, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        msgs = run_chat.await_args.args[0]
        assert [m.content for m in msgs] == ["first", "second", "latest"]
        assert all(m.role == "user" for m in msgs)

    @pytest.mark.asyncio
    async def test_run_chat_receives_session_id_only(self, monkeypatch):
        """run_chat gets session_id; routes must not invent thread_id/checkpointer."""
        run_chat = AsyncMock(return_value="ok")
        monkeypatch.setattr("chat_orchestrator.routes.run_chat", run_chat)
        ws = _ws([json.dumps({"text": "hi", "history": []})])

        try:
            await _message_loop(ws, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        assert run_chat.await_args.kwargs == {"session_id": "session-1"}

    @pytest.mark.asyncio
    async def test_non_json_message_uses_raw_text(self, monkeypatch):
        run_chat = AsyncMock(return_value="ok")
        monkeypatch.setattr("chat_orchestrator.routes.run_chat", run_chat)
        ws = _ws(["plain text message"])

        try:
            await _message_loop(ws, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        msgs = run_chat.await_args.args[0]
        assert [m.content for m in msgs] == ["plain text message"]
