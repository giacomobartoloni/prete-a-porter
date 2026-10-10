"""News search must never run without explicit confirmation."""
from langchain_core.messages import AIMessage, HumanMessage
from chat_orchestrator.graph import _news_search_confirmed, TOOLS_REGISTRY


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
