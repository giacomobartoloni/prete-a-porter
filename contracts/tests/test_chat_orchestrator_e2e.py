"""
End-to-end tests for the Chat Orchestrator (WebSocket + HTTP).

Mandatory WS turns must succeed (message frames). Error frames fail the test.
Each scenario uses an independent user identity to avoid quota cross-contamination.
Explicit rate-limit coverage lives in test_openai_api_boundary.py.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import jwt
import pytest


def _ws_token(user_id: str | None = None) -> str:
    """Generate a valid WS JWT token for a unique test user."""
    secret = os.environ.get("WS_JWT_SECRET", "b40311d99472cc1d528f92628b796591")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id or f"e2e-{uuid.uuid4().hex}",
        "type": "ws_ticket",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _assert_successful_message_frame(data: dict, *, turn: str) -> None:
    """Required turns must yield a non-empty message frame — never skip on error."""
    assert data.get("type") == "message", (
        f"{turn}: expected message frame, got {data!r}"
    )
    assert isinstance(data.get("content"), str) and len(data["content"]) > 0, (
        f"{turn}: empty message content: {data!r}"
    )


class TestChatOrchestratorHealth:
    def test_health(self, chat_url):
        """GET /health returns ok."""
        resp = httpx.get(chat_url + "/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestChatOrchestratorWebSocket:
    @pytest.mark.asyncio
    async def test_websocket_chat(self, chat_url):
        """Establish WebSocket, send message, receive successful response."""
        import websockets

        token = _ws_token()
        ws_url = chat_url.replace("http://", "ws://") + f"/ws/chat/e2e_{uuid.uuid4().hex}"

        async with websockets.connect(ws_url, subprotocols=[token]) as ws:
            await ws.send("Ciao")
            response = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data = json.loads(response)
            _assert_successful_message_frame(data, turn="websocket_chat")

    @pytest.mark.asyncio
    async def test_websocket_multiple_messages(self, chat_url):
        """Send multiple messages in same session; every turn must succeed."""
        import websockets

        token = _ws_token()
        ws_url = chat_url.replace("http://", "ws://") + f"/ws/chat/e2e_{uuid.uuid4().hex}"

        async with websockets.connect(ws_url, subprotocols=[token]) as ws:
            await ws.send("Che giorno è oggi?")
            resp1 = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data1 = json.loads(resp1)
            _assert_successful_message_frame(data1, turn="turn-1")

            await ws.send("E domani?")
            resp2 = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data2 = json.loads(resp2)
            _assert_successful_message_frame(data2, turn="turn-2")

    @pytest.mark.asyncio
    async def test_websocket_homily_flow(self, chat_url):
        """Homily request path returns a successful message frame."""
        import websockets

        token = _ws_token()
        ws_url = chat_url.replace("http://", "ws://") + f"/ws/chat/e2e_{uuid.uuid4().hex}"

        async with websockets.connect(ws_url, subprotocols=[token]) as ws:
            await ws.send("Vorrei un'omelia per la prossima domenica")
            response = await asyncio.wait_for(ws.recv(), timeout=120.0)
            data = json.loads(response)
            _assert_successful_message_frame(data, turn="homily_flow")


def test_error_frame_assertion_fails_instead_of_skip():
    """Focused regression: error frames must fail assertions, not skip."""
    with pytest.raises(AssertionError, match="expected message frame"):
        _assert_successful_message_frame(
            {"type": "error", "content": "boom"},
            turn="injected",
        )
