"""Conversion between OpenAI messages and LangChain messages, and token filtering."""

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from chat_orchestrator.api.messages import (
    extract_reply_text,
    flatten_content,
    is_visible_token,
    stream_graph_tokens,
    to_langchain_messages,
)
from chat_orchestrator.api.schemas import ChatMessage


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
