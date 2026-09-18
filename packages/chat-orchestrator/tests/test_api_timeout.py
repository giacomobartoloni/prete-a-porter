"""The chat-request wall-clock bound: config parsing and both transports."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from chat_orchestrator.api import v1
from chat_orchestrator.api.schemas import MODEL_ID
from chat_orchestrator.config import (
    CHAT_TIMEOUT_ENV_VAR,
    DEFAULT_CHAT_TIMEOUT_SECONDS,
    get_chat_timeout_seconds,
)

AUTH_HEADERS = {"Authorization": "Bearer test-orchestrator-key"}
TEST_TIMEOUT_SECONDS = "0.05"


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
def hanging_graph():
    """A graph whose invocation and stream never produce before the bound."""

    async def hanging_ainvoke(*args, **kwargs):
        await asyncio.sleep(30)
        return {"messages": [AIMessage(content="mai")]}

    async def hanging_astream(*args, **kwargs):
        await asyncio.sleep(30)
        yield  # pragma: no cover - the timeout fires first

    graph = MagicMock()
    graph.ainvoke = AsyncMock(side_effect=hanging_ainvoke)
    graph.astream = hanging_astream
    return graph


@pytest.fixture
def client(hanging_graph, monkeypatch):
    monkeypatch.setenv(CHAT_TIMEOUT_ENV_VAR, TEST_TIMEOUT_SECONDS)
    monkeypatch.setattr(v1, "get_graph", AsyncMock(return_value=hanging_graph))
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


class TestTimeoutConfig:
    def test_defaults_when_unset(self, monkeypatch):
        monkeypatch.delenv(CHAT_TIMEOUT_ENV_VAR, raising=False)
        assert get_chat_timeout_seconds() == DEFAULT_CHAT_TIMEOUT_SECONDS

    def test_reads_env_override(self, monkeypatch):
        monkeypatch.setenv(CHAT_TIMEOUT_ENV_VAR, "12.5")
        assert get_chat_timeout_seconds() == 12.5

    def test_rejects_non_numeric(self, monkeypatch):
        monkeypatch.setenv(CHAT_TIMEOUT_ENV_VAR, "soon")
        with pytest.raises(RuntimeError, match=CHAT_TIMEOUT_ENV_VAR):
            get_chat_timeout_seconds()

    def test_rejects_non_positive(self, monkeypatch):
        monkeypatch.setenv(CHAT_TIMEOUT_ENV_VAR, "0")
        with pytest.raises(RuntimeError, match=CHAT_TIMEOUT_ENV_VAR):
            get_chat_timeout_seconds()


class TestBufferedTimeout:
    def test_returns_504(self, client):
        response = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS)
        assert response.status_code == 504

    def test_error_is_italian_and_typed(self, client):
        body = client.post("/v1/chat/completions", json=_payload(), headers=AUTH_HEADERS).json()
        assert body["error"]["type"] == "timeout"
        assert "tempo massimo" in body["error"]["message"].lower()

    def test_utility_task_is_bounded_too(self, client, monkeypatch):
        monkeypatch.setattr(v1, "get_llm", MagicMock(return_value=_hanging_llm()))
        response = client.post(
            "/v1/chat/completions",
            json=_payload(metadata={"task": "tags_generation"}),
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 504
        assert response.json()["error"]["type"] == "timeout"


class TestStreamingTimeout:
    def test_stream_ends_with_an_error_frame_and_done(self, client):
        response = client.post(
            "/v1/chat/completions",
            json=_payload(stream=True),
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        assert response.text.rstrip().endswith("data: [DONE]")

        error_frames = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.split("\n\n")
            if line.startswith("data: {") and '"error"' in line
        ]
        assert len(error_frames) == 1
        assert error_frames[0]["error"]["type"] == "timeout"

    def test_no_content_is_emitted_before_the_timeout(self, client):
        response = client.post(
            "/v1/chat/completions",
            json=_payload(stream=True),
            headers=AUTH_HEADERS,
        )
        assert '"content"' not in response.text


def _hanging_llm():
    llm = MagicMock()

    async def hanging_ainvoke(*args, **kwargs):
        await asyncio.sleep(30)

    async def hanging_astream(*args, **kwargs):
        await asyncio.sleep(30)
        yield  # pragma: no cover - the timeout fires first

    llm.ainvoke = AsyncMock(side_effect=hanging_ainvoke)
    llm.astream = hanging_astream
    return llm
