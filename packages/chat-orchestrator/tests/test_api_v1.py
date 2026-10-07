"""OpenAI-compatible routes: models, buffered completions, auth, and quota."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

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
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Ecco l'omelia.")]})
    return graph


@pytest.fixture
def client(graph_mock, monkeypatch):
    monkeypatch.setattr(application, "get_graph", AsyncMock(return_value=graph_mock))
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
        response = client.get("/v1/models", headers=AUTH_HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["object"] == "list"
        assert len(body["data"]) == 1

    def test_model_id_matches_constant(self, client):
        body = client.get("/v1/models", headers=AUTH_HEADERS).json()
        assert body["data"][0]["id"] == MODEL_ID

    def test_model_card_shape(self, client):
        card = client.get("/v1/models", headers=AUTH_HEADERS).json()["data"][0]
        assert card["object"] == "model"
        assert card["owned_by"] == "prete-a-porter"
        assert isinstance(card["created"], int)


class TestBufferedCompletion:
    def test_returns_200(self, client):
        assert client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS).status_code == 200

    def test_response_shape(self, client):
        body = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS).json()
        assert body["object"] == "chat.completion"
        assert body["model"] == MODEL_ID
        assert body["id"].startswith("chatcmpl-")
        assert isinstance(body["created"], int)

    def test_content_and_finish_reason(self, client):
        choice = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS).json()["choices"][0]
        assert choice["index"] == 0
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == "Ecco l'omelia."
        assert choice["finish_reason"] == "stop"

    def test_usage_is_present_and_zeroed(self, client):
        usage = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS).json()["usage"]
        assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_graph_receives_converted_messages(self, client, graph_mock):
        client.post("/v1/chat/completions", json=_payload(
            messages=[
                {"role": "user", "content": "prima"},
                {"role": "assistant", "content": "seconda"},
                {"role": "user", "content": "terza"},
            ]
        ), headers=AUTH_HEADERS)
        msgs = graph_mock.ainvoke.call_args[0][0]["messages"]
        assert [m.content for m in msgs] == ["prima", "seconda", "terza"]
        assert isinstance(msgs[0], HumanMessage)
        assert isinstance(msgs[1], AIMessage)

    def test_no_thread_id_is_passed_in_config(self, client, graph_mock):
        client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        assert graph_mock.ainvoke.call_args[1]["config"] == {"recursion_limit": 15}

    def test_forwarded_chat_id_becomes_graph_session_id(self, client, graph_mock):
        client.post(
            "/v1/chat/completions",
            json=_payload(),
            headers={**AUTH_HEADERS, "X-OpenWebUI-Chat-Id": "chat-123"},
        )
        state = graph_mock.ainvoke.call_args[0][0]
        assert state["session_id"] == "chat-123"

    def test_generated_thread_id_is_passed_when_chat_header_absent(self, client, graph_mock):
        client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        state = graph_mock.ainvoke.call_args[0][0]
        assert "session_id" in state
        assert isinstance(state["session_id"], str)
        assert len(state["session_id"]) > 0

    def test_ignores_unknown_openwebui_fields(self, client):
        response = client.post("/v1/chat/completions", json=_payload(
            chat_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            features={"web_search": True},
            temperature=0.7,
        ), headers=AUTH_HEADERS)
        assert response.status_code == 200

    def test_rejects_empty_messages(self, client):
        response = client.post("/v1/chat/completions", json=_payload(messages=[]), headers=AUTH_HEADERS)
        assert response.status_code == 422

    def test_returns_500_with_italian_message_on_graph_failure(self, client, graph_mock):
        graph_mock.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        response = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        assert response.status_code == 500
        body = response.json()
        assert "errore" in body["error"]["message"].lower()


class TestBoundaryLogging:
    def test_completion_event_carries_the_librechat_correlation_fields(self, client):
        from structlog.testing import capture_logs

        with capture_logs() as logs:
            client.post(
                "/v1/chat/completions",
                json=_payload(),
                headers={
                    **AUTH_HEADERS,
                    "X-User-ID": "lc-user-7",
                    "X-Conversation-ID": "lc-conversation-7",
                    "X-Message-ID": "lc-message-7",
                },
            )
        received = [entry for entry in logs if entry.get("event") == "Chat completion received"]
        assert len(received) == 1
        assert received[0]["user_id"] == "lc-user-7"
        assert received[0]["conversation_id"] == "lc-conversation-7"
        assert received[0]["message_id"] == "lc-message-7"
        assert received[0]["stream"] is False
        assert received[0]["request_id"].startswith("chatcmpl-")

    def test_finished_event_reports_the_outcome(self, client):
        from structlog.testing import capture_logs

        with capture_logs() as logs:
            client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        finished = [entry for entry in logs if entry.get("event") == "Chat completion finished"]
        assert len(finished) == 1
        assert finished[0]["outcome"] == "completed"
        assert isinstance(finished[0]["duration_ms"], int)


class TestAuthentication:
    def test_rejects_missing_key(self, client):
        assert client.post("/v1/chat/completions", json=_payload()).status_code == 401

    def test_accepts_valid_key(self, client):
        response = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        assert response.status_code == 200

    def test_models_route_also_requires_key(self, client):
        assert client.get("/v1/models").status_code == 401


class TestPerUserQuota:
    def test_quota_is_keyed_on_forwarded_user_id(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_HOUR", "1")
        headers = {**AUTH_HEADERS, "X-OpenWebUI-User-Id": "user-a"}
        assert client.post("/v1/chat/completions", json=_payload(), headers=headers).status_code == 200
        second = client.post("/v1/chat/completions", json=_payload(), headers=headers)
        assert second.status_code == 429

    def test_different_users_have_independent_quotas(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_HOUR", "1")
        a = {**AUTH_HEADERS, "X-OpenWebUI-User-Id": "user-a"}
        b = {**AUTH_HEADERS, "X-OpenWebUI-User-Id": "user-b"}
        client.post("/v1/chat/completions", json=_payload(), headers=a)
        assert client.post("/v1/chat/completions", json=_payload(), headers=b).status_code == 200

    def test_429_body_is_italian(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_HOUR", "1")
        headers = {**AUTH_HEADERS, "X-OpenWebUI-User-Id": "user-c"}
        client.post("/v1/chat/completions", json=_payload(), headers=headers)
        body = client.post("/v1/chat/completions", json=_payload(), headers=headers).json()
        assert "limite" in body["error"]["message"].lower()
