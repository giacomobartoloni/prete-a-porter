"""Transport-independent chat execution shared by every adapter.

Two adapters run the same ReAct graph: the OpenAI-compatible HTTP surface
(``api/v1.py``) and the native Chainlit UI (``packages/prete-chat``). Message
conversion, reply extraction, the visible-token filter, the recursion limit and
the per-request timeout live here so the two cannot drift.

No FastAPI and no Chainlit imports: this module knows only LangGraph, LangChain
and sibling core modules. ``ChatMessage`` stays the OpenAI-shaped Pydantic model
because that is what every adapter already builds.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage

from .api.schemas import ChatMessage
from .config import get_chat_timeout_seconds
from .graph import get_graph

NO_RESPONSE: str = "No response"
RECURSION_LIMIT: int = 15
AGENT_NODE: str = "agent"


def flatten_content(content: str | list[dict[str, Any]]) -> str:
    """Reduce a message content value to plain text.

    A list of content blocks is joined on the blocks whose ``type`` is
    ``"text"``; every other block kind is skipped.
    """
    if isinstance(content, str):
        return content
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def to_langchain_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
    """Map OpenAI roles onto LangChain messages.

    Unknown roles become HumanMessage, matching the treatment the WebSocket
    loop already applies to every history entry.
    """
    converted: list[BaseMessage] = []
    for message in messages:
        text = flatten_content(message.content)
        if message.role == "assistant":
            converted.append(AIMessage(content=text))
        elif message.role == "system":
            converted.append(SystemMessage(content=text))
        else:
            converted.append(HumanMessage(content=text))
    return converted


def extract_reply_text(result: dict[str, Any]) -> str:
    """Pull the assistant's reply out of a graph invocation result."""
    messages = result.get("messages") or []
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    if not ai_messages:
        return NO_RESPONSE

    raw = ai_messages[-1].content
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        joined = "\n".join(
            block.get("text", "")
            for block in raw
            if isinstance(block, dict) and block.get("type") == "text"
        )
        return joined or str(raw)
    return str(raw)


def is_visible_token(chunk: object, metadata: dict[str, Any] | None) -> bool:
    """Decide whether a streamed chunk belongs in the user-visible answer.

    Two conditions, both verified against the installed LangGraph:

    1. The ``agent`` node binds tools, so a tool-calling turn streams chunks
       with ``tool_call_chunks`` populated and empty content. Emitting those
       would leak raw tool-call JSON into the chat. Note the empty case is
       ``[]``, not ``None``, so the check is truthiness.
    2. Accepting only ``AIMessageChunk`` is defence-in-depth. LangGraph's
       built-in dedupe already suppresses the full ``AIMessage`` that
       ``on_llm_end`` re-emits, because it carries the same message id as the
       deltas. That dedupe relies on the provider returning a stable id, which
       is convention rather than contract, so the type filter removes the
       dependency at no cost.
    """
    if not isinstance(chunk, AIMessageChunk):
        return False
    if not metadata or metadata.get("langgraph_node") != AGENT_NODE:
        return False
    if getattr(chunk, "tool_call_chunks", None):
        return False
    content = chunk.content
    return isinstance(content, str) and content != ""


async def run_chat(messages: list[ChatMessage], *, session_id: str | None = None) -> str:
    """Run the ReAct graph once and return the assistant's reply text.

    ``session_id`` is correlation metadata for the graph (an adapter passes its
    thread id); it creates no server-side conversation state. The whole
    invocation is bounded by ``CHAT_REQUEST_TIMEOUT_SECONDS``; a ``TimeoutError``
    propagates to the caller, which owns the user-facing mapping.
    """
    graph = await get_graph()
    state: dict[str, Any] = {"messages": to_langchain_messages(messages)}
    if session_id is not None:
        state["session_id"] = session_id
    async with asyncio.timeout(get_chat_timeout_seconds()):
        result = await graph.ainvoke(state, config={"recursion_limit": RECURSION_LIMIT})
    return extract_reply_text(result)


async def stream_chat(
    messages: list[ChatMessage],
    *,
    session_id: str | None = None,
    config: Mapping[str, Any] | None = None,
) -> AsyncIterator[tuple[object, dict[str, Any]]]:
    """Stream one graph run as native LangGraph ``(chunk, metadata)`` tuples.

    ``config`` is merged into the invocation config, which is how an adapter
    attaches its own callbacks (for example Chainlit's step-producing handler).
    Each adapter filters the tuples itself: ``is_visible_token`` selects answer
    text, callbacks select execution steps. The run is bounded by
    ``CHAT_REQUEST_TIMEOUT_SECONDS``; partial tokens already yielded stay valid.
    """
    graph = await get_graph()
    state: dict[str, Any] = {"messages": to_langchain_messages(messages)}
    if session_id is not None:
        state["session_id"] = session_id
    invocation_config = {"recursion_limit": RECURSION_LIMIT, **(config or {})}
    async with asyncio.timeout(get_chat_timeout_seconds()):
        async for chunk, metadata in graph.astream(state, config=invocation_config, stream_mode="messages"):
            yield chunk, metadata
