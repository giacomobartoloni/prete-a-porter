"""Utility tasks bypass the graph entirely."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from chat_orchestrator import application
from chat_orchestrator.api import v1
from chat_orchestrator.api.schemas import MODEL_ID

AUTH_HEADERS = {"Authorization": "Bearer test-orchestrator-key"}


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_API_KEY", "test-orchestrator-key")


@pytest.fixture(autouse=True)
async def _isolate_rate_limiter(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DB_PATH", ":memory:")
    import chat_orchestrator.rate_limiter as limiter_mod
    limiter_mod._rate_limiter = None
    yield
    if limiter_mod._rate_limiter is not None:
        await limiter_mod._rate_limiter.close()
        limiter_mod._rate_limiter = None


@pytest.fixture
def graph_mock():
    graph = MagicMock(spec=["ainvoke"])
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="omelia")]})
    return graph


@pytest.fixture
def llm_mock():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"title": "Omelia domenicale"}'))
    return llm


@pytest.fixture
def client(graph_mock, llm_mock, monkeypatch):
    monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph_mock))
    monkeypatch.setattr(v1, "get_llm", lambda: llm_mock)
    app = FastAPI()
    app.include_router(v1.router)
    return TestClient(app)


def _payload(**overrides):
    body = {"model": MODEL_ID, "messages": [{"role": "user", "content": "genera l'omelia"}]}
    body.update(overrides)
    return body


class TestUtilityTaskRouting:
    def test_metadata_task_skips_the_graph(self, client, graph_mock, llm_mock):
        response = client.post(
            "/v1/chat/completions",
            json=_payload(metadata={"task": "title_generation"}),
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        graph_mock.ainvoke.assert_not_called()
        llm_mock.ainvoke.assert_awaited_once()

    def test_metadata_task_returns_the_llm_output(self, client):
        body = client.post(
            "/v1/chat/completions",
            json=_payload(metadata={"task": "title_generation"}),
            headers=AUTH_HEADERS,
        ).json()
        assert body["choices"][0]["message"]["content"] == '{"title": "Omelia domenicale"}'

    def test_prompt_shape_task_skips_the_graph(self, client, graph_mock):
        client.post(
            "/v1/chat/completions",
            json=_payload(messages=[{"role": "user", "content": (
                "### Task:\n"
                "Generate a concise title summarizing the chat history.\n"
                "### Output:\n"
                'JSON format: { "title": "your concise title here" }'
            )}]),
            headers=AUTH_HEADERS,
        )
        graph_mock.ainvoke.assert_not_called()

    def test_real_chat_uses_the_graph(self, client, graph_mock, llm_mock):
        client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        graph_mock.ainvoke.assert_awaited_once()
        llm_mock.ainvoke.assert_not_called()

    def test_real_chat_returns_the_graph_output(self, client):
        body = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS).json()
        assert body["choices"][0]["message"]["content"] == "omelia"

    def test_utility_path_sends_no_system_prompt(self, client, llm_mock):
        client.post(
            "/v1/chat/completions",
            json=_payload(metadata={"task": "title_generation"}),
            headers=AUTH_HEADERS,
        )
        sent = llm_mock.ainvoke.call_args[0][0]
        assert len(sent) == 1
        assert sent[0].content == "genera l'omelia"

    def test_utility_path_does_not_bind_tools(self, client, llm_mock):
        client.post(
            "/v1/chat/completions",
            json=_payload(metadata={"task": "title_generation"}),
            headers=AUTH_HEADERS,
        )
        llm_mock.bind_tools.assert_not_called()
