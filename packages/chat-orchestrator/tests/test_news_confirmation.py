"""News search must never run without explicit confirmation."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from chat_orchestrator.graph import _news_search_confirmed, TOOLS_REGISTRY, tools_node


def test_news_tool_registered():
    assert "search_news" in TOOLS_REGISTRY


def test_initial_request_does_not_authorize_search():
    assert not _news_search_confirmed({"messages": [HumanMessage(content="Cerca notizie sulla pace")]})


def test_confirmation_after_proposal():
    messages = [
        HumanMessage(content="Omelia sulla pace"),
        AIMessage(content="Posso cercare online notizie recenti sulla pace. Vuoi che cerchi online?"),
        HumanMessage(content="Sì, procedi"),
    ]
    assert _news_search_confirmed({"messages": messages})


def test_unrelated_yes_does_not_authorize_search():
    messages = [AIMessage(content="Vuoi preparare un'omelia?"), HumanMessage(content="Sì")]
    assert not _news_search_confirmed({"messages": messages})


def test_decline_does_not_authorize_search():
    messages = [AIMessage(content="Vuoi che cerchi online?"), HumanMessage(content="No")]
    assert not _news_search_confirmed({"messages": messages})


@pytest.mark.parametrize("reply", [
    "Sì, grazie",
    "Sì, cerca notizie sulla pace",
    "Sì, per favore, cerca notizie recenti",
    "Certo, procedi",
])
def test_natural_approval_after_real_search_proposal(reply):
    messages = [
        AIMessage(content="Posso cercare online notizie sulla pace. Vuoi che cerchi online?"),
        HumanMessage(content=reply),
    ]
    assert _news_search_confirmed({"messages": messages})


@pytest.mark.parametrize("proposal, reply", [
    ("Non posso cercare online. Vuoi procedere senza notizie?", "Sì"),
    ("Vuoi che cerchi online? Vuoi procedere senza notizie?", "Sì"),
    ("Non vuoi che cerchi online?", "Sì"),
    ("Vuoi che cerchi online?", "Sì, ma senza notizie"),
    ("Vuoi che cerchi online?", "Sì, non cercare"),
    ("Posso cercare online notizie sulla pace.", "Sì"),
])
def test_no_search_without_unequivocal_consent(proposal, reply):
    assert not _news_search_confirmed({
        "messages": [AIMessage(content=proposal), HumanMessage(content=reply)]
    })


@pytest.mark.parametrize("proposal, reply, expected_calls", [
    ("Non posso cercare online. Vuoi procedere senza notizie?", "Sì", 0),
    ("Posso cercare online notizie sulla pace. Vuoi che cerchi online?", "Sì, grazie", 1),
    ("Posso cercare online notizie sulla pace. Vuoi che cerchi online?", "Sì, cerca notizie sulla pace", 1),
    ("Vuoi che cerchi online notizie sulla pace?", "No, grazie", 0),
])
async def test_confirmation_enforced_at_news_tool_boundary(
    monkeypatch, proposal, reply, expected_calls,
):
    search = SimpleNamespace(ainvoke=AsyncMock(return_value={"articles": []}))
    monkeypatch.setitem(TOOLS_REGISTRY, "search_news", search)
    call = {"name": "search_news", "args": {"query": "pace"}, "id": "call-news", "type": "tool_call"}
    state = {"messages": [
        AIMessage(content=proposal),
        HumanMessage(content=reply),
        AIMessage(content="", tool_calls=[call]),
    ]}
    result = await tools_node(state)
    assert search.ainvoke.await_count == expected_calls
    assert len(result["messages"]) == 1
    assert result["messages"][0].name == "search_news"
