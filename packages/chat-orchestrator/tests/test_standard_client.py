import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "a2a-protocol" / "src"))

from a2a_protocol.client import A2AClient, A2AClientError, create_client


class TestCallAgentMethod:
    @pytest.mark.asyncio
    async def test_sends_message_send_jsonrpc(self):
        client = A2AClient(agent_url="http://test-agent:8001")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "req-1",
            "result": {
                "id": "task-1",
                "changed": False,
                "Task": {
                    "id": "task-1",
                    "contextId": "ctx-1",
                    "status": {"state": "completed"},
                    "history": [
                        {"messageId": "m1", "role": "user", "parts": [{"text": '{"method":"agent.ping","params":{}}'}]},
                        {"messageId": "m2", "role": "agent", "parts": [{"text": '{"status":"pong","agent":"test","version":"1.0"}'}]},
                    ],
                }
            }
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            result = await client.call_agent_method("agent.ping", {})

            call_args = mock_post.call_args
            body = call_args[1]["json"]
            assert body["jsonrpc"] == "2.0"
            assert body["method"] == "message/send"
            assert "id" in body["params"]
            assert "message" in body["params"]
            message_body = body["params"]["message"]
            assert message_body["role"] == "user"
            msg_text = message_body["parts"][0]["text"]
            parsed = json.loads(msg_text)
            assert parsed["method"] == "agent.ping"
            assert parsed["params"] == {}

    @pytest.mark.asyncio
    async def test_parses_agent_reply_from_history(self):
        client = A2AClient(agent_url="http://test-agent:8001")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "req-2",
            "result": {
                "id": "task-2",
                "changed": False,
                "Task": {
                    "id": "task-2",
                    "contextId": "ctx-2",
                    "status": {"state": "completed"},
                    "history": [
                        {"messageId": "m1", "role": "user", "parts": [{"text": '{"method":"test.skill","params":{}}'}]},
                        {"messageId": "m2", "role": "agent", "parts": [{"text": '{"status":"success","data":{"key":"value"}}'}]},
                    ],
                }
            }
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await client.call_agent_method("test.skill", {})
            assert result == {"status": "success", "data": {"key": "value"}}

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        client = A2AClient(agent_url="http://test-agent:8001")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with pytest.raises(A2AClientError, match="Failed to call test.skill"):
                await client.call_agent_method("test.skill", {})


class TestPing:
    @pytest.mark.asyncio
    async def test_ping_uses_health_endpoint(self):
        client = A2AClient(agent_url="http://test-agent:8001")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "agent": "test"}

        with patch("httpx.AsyncClient.get", return_value=mock_response) as mock_get:
            result = await client.ping()
            mock_get.assert_called_once()
            assert "http://test-agent:8001/health" in str(mock_get.call_args[0])
            assert result is True

    @pytest.mark.asyncio
    async def test_ping_returns_false_on_error(self):
        client = A2AClient(agent_url="http://test-agent:8001")

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with pytest.raises(A2AClientError, match="Ping failed"):
                await client.ping()
