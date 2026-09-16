"""The graph must carry no server-side conversation state.

The assertions are behavioural: a stateless graph accepts an invocation
without a thread_id and does not accumulate history across calls.

Two fixtures are load-bearing and were verified by running them against the
pre-change code:

1. ``DATABASE_PATH`` must point at a writable temp directory. Before this
   change, ``create_graph`` resolves ``DATABASE_PATH`` and creates its parent
   directory; the default ``/app/data`` does not exist outside Docker, and
   ``Path('/app/data').mkdir`` raises ``OSError: Read-only file system`` on
   macOS, which would fail the test for the wrong reason.
2. ``get_llm`` is replaced with a local fake, NOT with ``TEST_MODE=true``.
   The ``TEST_MODE`` branch of ``a2a_protocol.llm.create_llm`` returns an
   ``AsyncMock``, and ``AsyncMock().bind_tools(...)`` returns a coroutine
   rather than the mock itself — so ``graph.py``'s
   ``llm_with_tools = llm.bind_tools(...)`` followed by
   ``await llm_with_tools.ainvoke(...)`` raises
   ``AttributeError: 'coroutine' object has no attribute 'ainvoke'``.
   The fake below keeps ``bind_tools`` synchronous and returns ``self``.
"""

import tempfile
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import chat_orchestrator.graph as graph_mod
from chat_orchestrator.graph import create_graph, get_graph, reset_graph


class _FakeLLM:
    """Minimal LLM double: synchronous bind_tools, no tool calls."""

    def bind_tools(self, tools: list) -> "_FakeLLM":
        return self

    async def ainvoke(self, messages: list) -> AIMessage:
        return AIMessage(content="risposta di test")


@pytest.fixture(autouse=True)
def _writable_database_path(monkeypatch):
    """Point DATABASE_PATH at a temp dir; /app/data exists only inside Docker."""
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("DATABASE_PATH", str(Path(tmp) / "test_graph.db"))
    yield


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    monkeypatch.setattr(graph_mod, "get_llm", lambda: _FakeLLM())
    reset_graph()
    yield
    reset_graph()


class TestGraphIsStateless:
    @pytest.mark.asyncio
    async def test_create_graph_returns_a_runnable(self):
        """create_graph returns the runnable directly, not a (graph, context) tuple."""
        compiled = await create_graph()
        assert hasattr(compiled, "ainvoke")

    @pytest.mark.asyncio
    async def test_invocation_needs_no_thread_id(self):
        """A checkpointer would raise without thread_id; a stateless graph must not.

        Before this change the test fails with exactly:

            ValueError: Checkpointer requires one or more of the following
            'configurable' keys: thread_id, checkpoint_ns, checkpoint_id

        That error is the proof the graph was stateful. If this test instead
        fails with the OSError about a read-only filesystem, the DATABASE_PATH
        fixture is missing — do not weaken the assertion, fix the fixture.
        """
        compiled = await create_graph()
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content="ciao")]},
            config={"recursion_limit": 15},
        )
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_history_does_not_accumulate_across_calls(self):
        """The defining property of statelessness: no memory between invocations."""
        graph = await get_graph()

        first = await graph.ainvoke(
            {"messages": [HumanMessage(content="prima domanda")]},
            config={"recursion_limit": 15},
        )
        second = await graph.ainvoke(
            {"messages": [HumanMessage(content="seconda domanda")]},
            config={"recursion_limit": 15},
        )

        first_human = [m.content for m in first["messages"] if isinstance(m, HumanMessage)]
        second_human = [m.content for m in second["messages"] if isinstance(m, HumanMessage)]
        assert first_human == ["prima domanda"]
        assert second_human == ["seconda domanda"]
