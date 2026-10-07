"""Live HTTP coverage of the OpenAI-compatible ``/v1`` boundary.

Requires a running chat-orchestrator with ``ORCHESTRATOR_API_KEY`` set (the
contract-tests CI job provides ``test-orchestrator-key``). Uses ``TEST_MODE``
so completions do not need a real LLM provider.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

API_KEY = os.environ.get("ORCHESTRATOR_API_KEY", "test-orchestrator-key")
AUTH = {"Authorization": f"Bearer {API_KEY}"}
HOURLY_LIMIT = int(os.environ.get("RATE_LIMIT_MESSAGES_PER_HOUR", "5"))


def _payload(**overrides):
    body = {
        "model": "prete-a-porter",
        "messages": [{"role": "user", "content": "Ciao"}],
        "stream": False,
    }
    body.update(overrides)
    return body


@pytest.fixture
def chat_base(chat_url):
    return chat_url.rstrip("/")


class TestModelsAuth:
    def test_models_without_auth_returns_401(self, chat_base):
        resp = httpx.get(f"{chat_base}/v1/models")
        assert resp.status_code == 401

    def test_models_with_valid_key(self, chat_base):
        resp = httpx.get(f"{chat_base}/v1/models", headers=AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert body["data"][0]["id"] == "prete-a-porter"

    def test_models_with_invalid_key_returns_401(self, chat_base):
        resp = httpx.get(
            f"{chat_base}/v1/models",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401


class TestBufferedCompletion:
    def test_buffered_completion_shape(self, chat_base):
        resp = httpx.post(
            f"{chat_base}/v1/chat/completions",
            headers={
                **AUTH,
                "X-OpenWebUI-User-Id": f"boundary-user-{uuid.uuid4().hex[:8]}",
                "X-OpenWebUI-Chat-Id": f"boundary-chat-{uuid.uuid4().hex[:8]}",
            },
            json=_payload(),
            timeout=60.0,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "chat.completion"
        assert body["model"] == "prete-a-porter"
        assert body["choices"]
        choice = body["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert isinstance(choice["message"]["content"], str)


class TestStreamingCompletion:
    def test_streaming_ends_with_done(self, chat_base):
        with httpx.stream(
            "POST",
            f"{chat_base}/v1/chat/completions",
            headers={
                **AUTH,
                "X-OpenWebUI-User-Id": f"stream-user-{uuid.uuid4().hex[:8]}",
                "X-OpenWebUI-Chat-Id": f"stream-chat-{uuid.uuid4().hex[:8]}",
                "Content-Type": "application/json",
            },
            json=_payload(stream=True),
            timeout=60.0,
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            text = "".join(resp.iter_text())
        assert "chat.completion.chunk" in text
        assert "data: [DONE]" in text
        assert "finish_reason" in text


class TestForwardedIdentity:
    def test_forwarded_identity_headers_are_accepted(self, chat_base):
        """Headers must not break the request; correlation is covered by unit tests."""
        resp = httpx.post(
            f"{chat_base}/v1/chat/completions",
            headers={
                **AUTH,
                "X-OpenWebUI-User-Id": "user-123",
                "X-OpenWebUI-Chat-Id": "chat-456",
                "X-OpenWebUI-User-Email": "user@example.test",
            },
            json=_payload(),
            timeout=60.0,
        )
        assert resp.status_code == 200


class TestRateLimit:
    def test_exhausted_quota_returns_429(self, chat_base):
        user = f"quota-user-{uuid.uuid4().hex}"
        headers = {**AUTH, "X-OpenWebUI-User-Id": user}
        for _ in range(HOURLY_LIMIT):
            response = httpx.post(
                f"{chat_base}/v1/chat/completions",
                headers=headers,
                json=_payload(),
                timeout=60.0,
            )
            assert response.status_code == 200, response.text

        limited = httpx.post(
            f"{chat_base}/v1/chat/completions",
            headers=headers,
            json=_payload(),
            timeout=60.0,
        )
        assert limited.status_code == 429
        body = limited.json()
        assert body["error"]["type"] == "rate_limit_exceeded"
        assert "limite" in body["error"]["message"].lower()
