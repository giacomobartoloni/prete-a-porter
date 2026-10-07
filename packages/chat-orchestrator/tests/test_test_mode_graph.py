"""Full-graph regression: TEST_MODE must drive the real LangGraph path."""

import pytest

from chat_orchestrator.api.schemas import ChatMessage
from chat_orchestrator.application import is_visible_token, run_chat, stream_chat
from chat_orchestrator.graph import reset_graph


@pytest.fixture(autouse=True)
def _reset_graph_singleton():
    reset_graph()
    yield
    reset_graph()


@pytest.mark.asyncio
async def test_test_mode_runs_real_graph(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    reset_graph()

    reply = await run_chat(
        [ChatMessage(role="user", content="Ciao")],
        session_id="test-thread",
    )

    assert reply == "Test response from mock LLM"


@pytest.mark.asyncio
async def test_test_mode_streams_visible_tokens(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    reset_graph()

    visible: list[str] = []
    async for chunk, metadata in stream_chat(
        [ChatMessage(role="user", content="Ciao")],
        session_id="stream-thread",
    ):
        if is_visible_token(chunk, metadata):
            visible.append(chunk.content)

    assert "".join(visible) == "Test response from mock LLM"
