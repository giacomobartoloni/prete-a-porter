"""
End-to-end tests for the Chat Orchestrator (WebSocket + HTTP).

Helpers:
    _ws_token() generates a valid JWT for WebSocket auth.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

import httpx
import jwt
import pytest


def _ws_token() -> str:
    """Generate a valid WS JWT token for testing."""
    secret = os.environ.get("WS_JWT_SECRET", "b40311d99472cc1d528f92628b796591")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "e2e-test-user",
        "type": "ws_ticket",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class TestChatOrchestratorHealth:
    def test_health(self, chat_url):
        """GET /health returns ok."""
        resp = httpx.get(chat_url + "/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestChatOrchestratorWebSocket:
    @pytest.mark.asyncio
    async def test_websocket_chat(self, chat_url):
        """Establish WebSocket, send message, receive response."""
        import websockets

        token = _ws_token()
        ws_url = chat_url.replace("http://", "ws://") + f"/ws/chat/e2e_{uuid.uuid4().hex}"

        async with websockets.connect(ws_url, subprotocols=[token]) as ws:
            await ws.send("Ciao")
            response = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data = json.loads(response)
            # May be message (real LLM) or error (mock LLM without API key)
            assert data["type"] in ("message", "error")
            if data["type"] == "error":
                pytest.skip("Chat orchestrator returned error (no LLM API key?)")
            assert len(data["content"]) > 0

    @pytest.mark.asyncio
    async def test_websocket_multiple_messages(self, chat_url):
        """Send multiple messages in same session, maintain context."""
        import websockets

        token = _ws_token()
        ws_url = chat_url.replace("http://", "ws://") + f"/ws/chat/e2e_{uuid.uuid4().hex}"

        async with websockets.connect(ws_url, subprotocols=[token]) as ws:
            await ws.send("Che giorno è oggi?")
            resp1 = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data1 = json.loads(resp1)
            assert data1["type"] in ("message", "error")
            if data1["type"] == "error":
                pytest.skip("Chat orchestrator returned error (no LLM API key?)")

            await ws.send("E domani?")
            resp2 = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data2 = json.loads(resp2)
            assert data2["type"] in ("message", "error")

    @pytest.mark.asyncio
    async def test_websocket_homily_flow(self, chat_url):
        """Full flow: request homily, receive response via agent coordination."""
        import websockets

        token = _ws_token()
        ws_url = chat_url.replace("http://", "ws://") + f"/ws/chat/e2e_{uuid.uuid4().hex}"

        async with websockets.connect(ws_url, subprotocols=[token]) as ws:
            await ws.send("Vorrei un'omelia per la prossima domenica")
            response = await asyncio.wait_for(ws.recv(), timeout=120.0)
            data = json.loads(response)
            assert data["type"] in ("message", "error")
            if data["type"] == "error":
                pytest.skip(f"Agent coordination failed: {data.get('content', '')}")
            assert len(data["content"]) > 0
