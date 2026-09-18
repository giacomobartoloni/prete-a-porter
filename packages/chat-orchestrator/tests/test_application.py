"""Conversion helpers and the transport-independent chat seam.

These helpers moved here from ``api.messages`` when chat execution moved into
``chat_orchestrator.application``; the tests moved with them, and the seam
itself (``run_chat``/``stream_chat``) gained coverage for messages/session state,
config passthrough, the timeout bound and cancellation propagation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from chat_orchestrator import application
from chat_orchestrator.api.schemas import ChatMessage
from chat_orchestrator.application import (
    RECURSION_LIMIT,
    extract_reply_text,
    flatten_content,
    is_visible_token,
    run_chat,
    stream_chat,
    to_langchain_messages,
)


def _graph_mock(*, ainvoke=None, astream=None) -> MagicMock:
    """Build a graph double exposing only the methods under test."""
    graph = MagicMock()
    if ainvoke is not None:
        graph.ainvoke = ainvoke
    if astream is not None:
        graph.astream = astream
    return graph


class TestFlattenContent:
    def test_string_passes_through(self):
        assert flatten_content("ciao") == "ciao"

    def test_text_blocks_are_joined(self):
        blocks = [{"type": "text", "text": "prima"}, {"type": "text", "text": "seconda"}]
        assert flatten_content(blocks) == "prima\nseconda"

    def test_non_text_blocks_are_skipped(self):
        blocks = [{"type": "image_url", "image_url": {"url": "x"}}, {"type": "text", "text": "ok"}]
        assert flatten_content(blocks) == "ok"

    def test_empty_block_list_yields_empty_string(self):
        assert flatten_content([]) == ""


class TestToLangchainMessages:
    def test_user_becomes_human_message(self):
        msgs = to_langchain_messages([ChatMessage(role="user", content="ciao")])
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "ciao"

    def test_assistant_becomes_ai_message(self):
        msgs = to_langchain_messages([ChatMessage(role="assistant", content="risposta")])
        assert isinstance(msgs[0], AIMessage)

    def test_system_becomes_system_message(self):
        msgs = to_langchain_messages([ChatMessage(role="system", content="regole")])
        assert isinstance(msgs[0], SystemMessage)

    def test_unknown_role_becomes_human_message(self):
        """Same treatment the WebSocket loop gives every history entry."""
        msgs = to_langchain_messages([ChatMessage(role="tool", content="result")])
        assert isinstance(msgs[0], HumanMessage)

    def test_content_blocks_are_flattened(self):
        msgs = to_langchain_messages(
            [ChatMessage(role="user", content=[{"type": "text", "text": "ciao"}])]
        )
        assert msgs[0].content == "ciao"

    def test_order_is_preserved(self):
        msgs = to_langchain_messages([
            ChatMessage(role="user", content="prima"),
            ChatMessage(role="assistant", content="seconda"),
            ChatMessage(role="user", content="terza"),
        ])
        assert [m.content for m in msgs] == ["prima", "seconda", "terza"]


class TestExtractReplyText:
    def test_returns_last_ai_message(self):
        result = {"messages": [HumanMessage(content="q"), AIMessage(content="prima"), AIMessage(content="ultima")]}
        assert extract_reply_text(result) == "ultima"

    def test_joins_text_blocks(self):
        result = {"messages": [AIMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])]}
        assert extract_reply_text(result) == "a\nb"

    def test_falls_back_when_no_ai_message(self):
        assert extract_reply_text({"messages": [HumanMessage(content="q")]}) == "No response"

    def test_falls_back_when_messages_missing(self):
        assert extract_reply_text({}) == "No response"

    def test_non_text_blocks_fall_back_to_repr(self):
        """A list with no text block has no joinable text, so it is stringified."""
        result = {"messages": [AIMessage(content=[{"type": "image_url", "image_url": {"url": "x"}}])]}
        assert "image_url" in extract_reply_text(result)


class TestIsVisibleToken:
    def test_plain_content_is_visible(self):
        chunk = AIMessageChunk(content="ciao")
        assert is_visible_token(chunk, {"langgraph_node": "agent"}) is True

    def test_empty_content_is_not_visible(self):
        chunk = AIMessageChunk(content="")
        assert is_visible_token(chunk, {"langgraph_node": "agent"}) is False

    def test_full_ai_message_is_not_visible(self):
        """Defence-in-depth: the full AIMessage from on_llm_end is not a delta."""
        assert is_visible_token(AIMessage(content="testo completo"), {"langgraph_node": "agent"}) is False

    def test_tool_call_chunks_are_not_visible(self):
        """The tool-bound LLM emits tool-call chunks with empty content."""
        chunk = AIMessageChunk(content="")
        chunk.tool_call_chunks = [{"name": "get_liturgical_readings"}]
        assert is_visible_token(chunk, {"langgraph_node": "agent"}) is False

    def test_empty_tool_call_chunks_list_is_visible(self):
        """The empty case is [], not None, so truthiness is the right check."""
        chunk = AIMessageChunk(content="ciao")
        chunk.tool_call_chunks = []
        assert is_visible_token(chunk, {"langgraph_node": "agent"}) is True

    def test_content_with_tool_call_chunks_is_not_visible(self):
        chunk = AIMessageChunk(content="partial")
        chunk.tool_call_chunks = [{"name": "x"}]
        assert is_visible_token(chunk, {"langgraph_node": "agent"}) is False

    def test_tools_node_chunks_are_not_visible(self):
        chunk = AIMessageChunk(content="ciao")
        assert is_visible_token(chunk, {"langgraph_node": "tools"}) is False

    def test_missing_metadata_is_not_visible(self):
        assert is_visible_token(AIMessageChunk(content="ciao"), None) is False


class TestRunChat:
    @pytest.mark.asyncio
    async def test_returns_the_reply_text(self, monkeypatch):
        graph = _graph_mock(ainvoke=AsyncMock(return_value={"messages": [AIMessage(content="risposta")]}))
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        reply = await run_chat([ChatMessage(role="user", content="ciao")])

        assert reply == "risposta"

    @pytest.mark.asyncio
    async def test_state_carries_only_messages_without_a_session_id(self, monkeypatch):
        graph = _graph_mock(ainvoke=AsyncMock(return_value={"messages": [AIMessage(content="x")]}))
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        await run_chat([ChatMessage(role="user", content="ciao")])

        state = graph.ainvoke.await_args.args[0]
        assert list(state) == ["messages"]
        assert graph.ainvoke.await_args.kwargs["config"] == {"recursion_limit": RECURSION_LIMIT}

    @pytest.mark.asyncio
    async def test_session_id_is_added_when_provided(self, monkeypatch):
        graph = _graph_mock(ainvoke=AsyncMock(return_value={"messages": [AIMessage(content="x")]}))
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        await run_chat([ChatMessage(role="user", content="ciao")], session_id="thread-1")

        assert graph.ainvoke.await_args.args[0]["session_id"] == "thread-1"

    @pytest.mark.asyncio
    async def test_timeout_bound_is_applied_and_propagates(self, monkeypatch):
        monkeypatch.setenv("CHAT_REQUEST_TIMEOUT_SECONDS", "0.05")

        async def slow_ainvoke(payload, config=None):
            await asyncio.sleep(5)
            return {"messages": [AIMessage(content="troppo tardi")]}

        graph = _graph_mock(ainvoke=slow_ainvoke)
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        with pytest.raises(TimeoutError):
            await run_chat([ChatMessage(role="user", content="ciao")])


class TestStreamChat:
    @staticmethod
    def _streaming_graph(*, capture: dict | None = None) -> MagicMock:
        async def fake_astream(payload, config=None, stream_mode=None, **kwargs):
            if capture is not None:
                capture["state"] = payload
                capture["config"] = config
                capture["stream_mode"] = stream_mode
            yield (AIMessageChunk(content="Ecco"), {"langgraph_node": "agent"})
            yield (AIMessageChunk(content=" l'omelia."), {"langgraph_node": "agent"})

        return _graph_mock(astream=fake_astream)

    @pytest.mark.asyncio
    async def test_yields_native_langgraph_tuples(self, monkeypatch):
        graph = self._streaming_graph()
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        chunks = [item async for item in stream_chat([ChatMessage(role="user", content="ciao")])]

        assert [chunk.content for chunk, _meta in chunks] == ["Ecco", " l'omelia."]
        assert all(meta == {"langgraph_node": "agent"} for _chunk, meta in chunks)

    @pytest.mark.asyncio
    async def test_config_is_merged_into_the_invocation(self, monkeypatch):
        capture: dict = {}
        graph = self._streaming_graph(capture=capture)
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))
        handler = object()

        _ = [
            item
            async for item in stream_chat(
                [ChatMessage(role="user", content="ciao")],
                config={"callbacks": [handler]},
            )
        ]

        assert capture["config"]["callbacks"] == [handler]
        assert capture["config"]["recursion_limit"] == RECURSION_LIMIT
        assert capture["stream_mode"] == "messages"

    @pytest.mark.asyncio
    async def test_session_id_is_added_only_when_provided(self, monkeypatch):
        capture: dict = {}
        graph = self._streaming_graph(capture=capture)
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        _ = [item async for item in stream_chat([ChatMessage(role="user", content="ciao")])]
        assert "session_id" not in capture["state"]

        _ = [
            item
            async for item in stream_chat([ChatMessage(role="user", content="ciao")], session_id="thread-1")
        ]
        assert capture["state"]["session_id"] == "thread-1"

    @pytest.mark.asyncio
    async def test_cancellation_propagates_with_partial_tokens_intact(self, monkeypatch):
        async def cancelling_astream(payload, config=None, stream_mode=None, **kwargs):
            yield (AIMessageChunk(content="parziale"), {"langgraph_node": "agent"})
            raise asyncio.CancelledError

        graph = _graph_mock(astream=cancelling_astream)
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))
        collected: list[str] = []

        with pytest.raises(asyncio.CancelledError):
            async for chunk, _meta in stream_chat([ChatMessage(role="user", content="ciao")]):
                collected.append(chunk.content)

        assert collected == ["parziale"]

    @pytest.mark.asyncio
    async def test_timeout_bound_is_applied_and_propagates(self, monkeypatch):
        monkeypatch.setenv("CHAT_REQUEST_TIMEOUT_SECONDS", "0.05")

        async def slow_astream(payload, config=None, stream_mode=None, **kwargs):
            await asyncio.sleep(5)
            yield (AIMessageChunk(content="troppo tardi"), {"langgraph_node": "agent"})

        graph = _graph_mock(astream=slow_astream)
        monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph))

        with pytest.raises(TimeoutError):
            async for _chunk, _meta in stream_chat([ChatMessage(role="user", content="ciao")]):
                pass
