"""Tests for A2A HTTP transport URL routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a_protocol.protocol import create_request


@pytest.mark.asyncio
async def test_http_transport_sends_to_root_not_a2a():
    """HTTPTransport.send() must POST to '/' not '/a2a'."""
    from a2a_protocol.transport import HTTPTransport

    transport = HTTPTransport(agent_url="http://test-agent:8001", retries=1)
    request = create_request(method="agent.ping", params={})

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": request.id,
        "result": {"status": "pong"},
    }
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.object(transport, "_get_client", return_value=mock_client):
        await transport.send(request)

    call_url = mock_client.post.call_args[0][0]
    assert call_url == "http://test-agent:8001/", (
        f"Expected POST to '/', got: {call_url}"
    )
