"""The graph must carry no server-side conversation state.

The assertions are behavioural: a stateless graph accepts an invocation
without a thread_id and does not accumulate history across calls.

The ``get_llm`` fixture is load-bearing and was verified by running it against
the pre-change code: ``get_llm`` is replaced with a local fake, NOT with
``TEST_MODE=true``. The ``TEST_MODE`` branch of ``a2a_protocol.llm.create_llm``
returns an ``AsyncMock``, and ``AsyncMock().bind_tools(...)`` returns a
coroutine rather than the mock itself — so ``graph.py``'s
``llm_with_tools = llm.bind_tools(...)`` followed by
``await llm_with_tools.ainvoke(...)`` raises
``AttributeError: 'coroutine' object has no attribute 'ainvoke'``.
The fake below keeps ``bind_tools`` synchronous and returns ``self``.
"""

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
        """A checkpointer would raise without thread_id; a stateless graph must not."""
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
