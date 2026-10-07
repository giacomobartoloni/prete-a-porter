"""The message loop rebuilds history from the request and passes no thread_id.

There is no server-side conversation state: every turn supplies its own history,
and the graph is invoked without a thread_id.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

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


def _graph():
    graph = MagicMock(spec=["ainvoke"])
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="ok")]})
    return graph


class TestMessageLoopHistory:
    @pytest.mark.asyncio
    async def test_history_is_replayed_then_new_text(self):
        ws = _ws([json.dumps({"text": "latest", "history": [{"content": "first"}, {"content": "second"}]})])
        graph = _graph()

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert [m.content for m in msgs] == ["first", "second", "latest"]
        # Missing role defaults to user.
        assert all(isinstance(m, HumanMessage) for m in msgs)

    @pytest.mark.asyncio
    async def test_no_thread_id_in_config(self):
        """The graph is stateless, so no thread_id may be passed."""
        ws = _ws([json.dumps({"text": "hi", "history": []})])
        graph = _graph()

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        config = graph.ainvoke.call_args[1]["config"]
        assert config == {"recursion_limit": 15}

    @pytest.mark.asyncio
    async def test_no_checkpointer_attribute_is_read(self):
        """A graph without a checkpointer must not cause an AttributeError path."""
        ws = _ws([json.dumps({"text": "hi"})])
        graph = _graph()

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        graph.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_json_message_uses_raw_text(self):
        ws = _ws(["plain text message"])
        graph = _graph()

        try:
            await _message_loop(ws, graph, "session-1", "user-1", "corr-1")
        except WebSocketDisconnect:
            pass

        msgs = graph.ainvoke.call_args[0][0]["messages"]
        assert [m.content for m in msgs] == ["plain text message"]
