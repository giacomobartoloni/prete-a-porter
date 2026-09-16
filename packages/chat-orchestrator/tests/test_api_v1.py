"""GET /v1/models advertises exactly one model, and the buffered completion path."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from chat_orchestrator.api import v1
from chat_orchestrator.api.schemas import MODEL_ID


@pytest.fixture
def graph_mock():
    graph = MagicMock(spec=["ainvoke"])
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Ecco l'omelia.")]})
    return graph


@pytest.fixture
def client(graph_mock, monkeypatch):
    monkeypatch.setattr(v1, "get_graph", AsyncMock(return_value=graph_mock))
    app = FastAPI()
    app.include_router(v1.router)
    return TestClient(app)


def _payload(**overrides):
    body = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "genera l'omelia"}],
    }
    body.update(overrides)
    return body


class TestListModels:
    def test_returns_one_model(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        body = response.json()
        assert body["object"] == "list"
        assert len(body["data"]) == 1

    def test_model_id_matches_constant(self, client):
        body = client.get("/v1/models").json()
        assert body["data"][0]["id"] == MODEL_ID

    def test_model_card_shape(self, client):
        card = client.get("/v1/models").json()["data"][0]
        assert card["object"] == "model"
        assert card["owned_by"] == "prete-a-porter"
        assert isinstance(card["created"], int)


class TestBufferedCompletion:
    def test_returns_200(self, client):
        assert client.post("/v1/chat/completions", json=_payload()).status_code == 200

    def test_response_shape(self, client):
        body = client.post("/v1/chat/completions", json=_payload()).json()
        assert body["object"] == "chat.completion"
        assert body["model"] == MODEL_ID
        assert body["id"].startswith("chatcmpl-")
        assert isinstance(body["created"], int)

    def test_content_and_finish_reason(self, client):
        choice = client.post("/v1/chat/completions", json=_payload()).json()["choices"][0]
        assert choice["index"] == 0
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == "Ecco l'omelia."
        assert choice["finish_reason"] == "stop"

    def test_usage_is_present_and_zeroed(self, client):
        usage = client.post("/v1/chat/completions", json=_payload()).json()["usage"]
        assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_graph_receives_converted_messages(self, client, graph_mock):
        client.post("/v1/chat/completions", json=_payload(
            messages=[
                {"role": "user", "content": "prima"},
                {"role": "assistant", "content": "seconda"},
                {"role": "user", "content": "terza"},
            ]
        ))
        msgs = graph_mock.ainvoke.call_args[0][0]["messages"]
        assert [m.content for m in msgs] == ["prima", "seconda", "terza"]
        assert isinstance(msgs[0], HumanMessage)
        assert isinstance(msgs[1], AIMessage)

    def test_no_thread_id_is_passed(self, client, graph_mock):
        client.post("/v1/chat/completions", json=_payload())
        assert graph_mock.ainvoke.call_args[1]["config"] == {"recursion_limit": 15}

    def test_ignores_unknown_openwebui_fields(self, client):
        response = client.post("/v1/chat/completions", json=_payload(
            chat_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            features={"web_search": True},
            temperature=0.7,
        ))
        assert response.status_code == 200

    def test_rejects_empty_messages(self, client):
        assert client.post("/v1/chat/completions", json=_payload(messages=[])).status_code == 422

    def test_returns_500_with_italian_message_on_graph_failure(self, client, graph_mock):
        graph_mock.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        response = client.post("/v1/chat/completions", json=_payload())
        assert response.status_code == 500
        body = response.json()
        assert "errore" in body["error"]["message"].lower()
