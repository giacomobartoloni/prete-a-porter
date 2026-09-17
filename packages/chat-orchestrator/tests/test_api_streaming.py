"""POST /v1/chat/completions with stream=true emits OpenAI-shaped SSE."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk

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
    async def fake_astream(payload, config=None, **kwargs):
        yield (AIMessageChunk(content="Ecco"), {"langgraph_node": "agent"})
        yield (AIMessageChunk(content=" l'omelia."), {"langgraph_node": "agent"})
        yield (AIMessage(content="Ecco l'omelia."), {"langgraph_node": "agent"})

    graph = MagicMock()
    graph.astream = fake_astream
    graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Ecco l'omelia.")]})
    return graph


@pytest.fixture
def client(graph_mock, monkeypatch):
    monkeypatch.setattr(v1, "get_graph", AsyncMock(return_value=graph_mock))
    app = FastAPI()
    app.include_router(v1.router)
    return TestClient(app)


def _payload(**overrides):
    body = {"model": MODEL_ID, "messages": [{"role": "user", "content": "genera l'omelia"}]}
    body.update(overrides)
    return body


def _frames(response) -> list[str]:
    return [line for line in response.text.split("\n\n") if line.strip()]


def _contents(response) -> list[str]:
    """Decoded content deltas; the finish frame carries no content."""
    out = []
    for frame in _frames(response):
        if frame == "data: [DONE]":
            continue
        payload = json.loads(frame[len("data: "):])
        if payload["choices"]:
            content = payload["choices"][0]["delta"].get("content")
            if content is not None:
                out.append(content)
    return out


class TestStreaming:
    def test_content_type_is_event_stream(self, client):
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_stream_ends_with_done(self, client):
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        assert response.text.rstrip().endswith("data: [DONE]")

    def test_content_deltas_are_emitted(self, client):
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        contents = _contents(response)
        assert "Ecco" in contents
        assert " l'omelia." in contents

    def test_no_duplicate_final_message(self, client):
        """Regression guard: the full AIMessage must not be emitted after the deltas."""
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        assert response.text.count("Ecco l'omelia.") == 0

    def test_finish_reason_is_set(self, client):
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        reasons = []
        for frame in _frames(response):
            if frame == "data: [DONE]":
                continue
            payload = json.loads(frame[len("data: "):])
            if payload["choices"]:
                reasons.append(payload["choices"][0]["finish_reason"])
        assert "stop" in reasons

    def test_every_frame_uses_the_advertised_model(self, client):
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        for frame in _frames(response):
            if frame == "data: [DONE]":
                continue
            assert json.loads(frame[len("data: "):])["model"] == MODEL_ID

    def test_stream_false_is_still_buffered_json(self, client):
        response = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["choices"][0]["message"]["content"] == "Ecco l'omelia."

    def test_streaming_requires_auth(self, client):
        assert client.post("/v1/chat/completions", json=_payload(stream=True)).status_code == 401

    def test_streaming_is_rate_limited(self, client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_MESSAGES_PER_HOUR", "1")
        headers = {**AUTH_HEADERS, "X-OpenWebUI-User-Id": "user-stream"}
        client.post("/v1/chat/completions", json=_payload(stream=True), headers=headers)
        second = client.post("/v1/chat/completions", json=_payload(stream=True), headers=headers)
        assert second.status_code == 429

    def test_graph_error_terminates_the_stream_and_reports_it(self, client, graph_mock):
        """A mid-stream failure must not leave the client hanging or silent.

        Emitting only [DONE] would render an empty assistant message with no
        explanation, because the HTTP status is already committed.
        """
        async def failing_astream(payload, config=None, **kwargs):
            yield (AIMessageChunk(content="Ecco"), {"langgraph_node": "agent"})
            raise RuntimeError("boom")

        graph_mock.astream = failing_astream
        response = client.post("/v1/chat/completions", json=_payload(stream=True), headers=AUTH_HEADERS)
        assert response.text.rstrip().endswith("data: [DONE]")
        assert '"error"' in response.text
        assert "errore" in response.text.lower()


@pytest.fixture
def llm_mock():
    async def fake_astream(messages, **kwargs):
        yield AIMessageChunk(content='{"title":')
        yield AIMessageChunk(content=' "Omelia"}')

    llm = MagicMock()
    llm.astream = fake_astream
    return llm


class TestUtilityTaskStreaming:
    def test_utility_task_does_not_touch_the_graph(self, client, graph_mock, llm_mock, monkeypatch):
        monkeypatch.setattr(v1, "get_llm", lambda: llm_mock)
        client.post(
            "/v1/chat/completions",
            json=_payload(stream=True, metadata={"task": "title_generation"}),
            headers=AUTH_HEADERS,
        )
        graph_mock.ainvoke.assert_not_called()

    def test_utility_task_streams_llm_output(self, client, llm_mock, monkeypatch):
        monkeypatch.setattr(v1, "get_llm", lambda: llm_mock)
        response = client.post(
            "/v1/chat/completions",
            json=_payload(stream=True, metadata={"task": "title_generation"}),
            headers=AUTH_HEADERS,
        )
        # Assert on decoded deltas: the raw SSE text JSON-escapes the quotes.
        assert "".join(_contents(response)) == '{"title": "Omelia"}'
        assert response.text.rstrip().endswith("data: [DONE]")
