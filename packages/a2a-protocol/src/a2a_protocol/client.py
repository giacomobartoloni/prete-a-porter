"""
A2A Client Implementation.

Client for making A2A protocol requests to agents.
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Optional, Dict, Any, AsyncGenerator
from pathlib import Path

from .protocol import (
    A2ARequest,
    A2AResponse,
    A2AError,
    create_request
)
from .transport import A2ATransport, create_transport

logger = logging.getLogger(__name__)


class A2AClient:
    """
    Client for making A2A requests to agents.
    
    Provides high-level interface for agent communication.
    Handles request creation, transport management, and error handling.
    
    Example:
        >>> client = A2AClient(
        ...     transport_type="http",
        ...     agent_url="http://liturgy-agent:8001"
        ... )
        >>> result = await client.call("liturgy_agent.get_readings", {"date": "2024-01-15"})
    """
    
    def __init__(
        self,
        transport_type: str = "http",
        **transport_kwargs
    ):
        """
        Initialize A2A client.
        
        Args:
            transport_type: "http" (only supported transport)
            **transport_kwargs: Transport-specific parameters
                For http: agent_url (str), timeout (float), retries (int)
        """
        transport_kwargs.pop('transport_type', None)
        self.transport: A2ATransport = create_transport(**transport_kwargs)
        self.transport_type = transport_type
    
    def _get_auth_headers(self) -> Dict[str, str]:
        auth_user = getattr(self.transport, '_auth_username', None) or os.environ.get("A2A_BASIC_AUTH_USERNAME")
        auth_pass = getattr(self.transport, '_auth_password', None) or os.environ.get("A2A_BASIC_AUTH_PASSWORD")
        if auth_user and auth_pass:
            encoded = base64.b64encode(f"{auth_user}:{auth_pass}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        return {}

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Call an agent method.
        
        Args:
            method: Agent method name (e.g., "liturgy_agent.get_readings")
            params: Method parameters
            timeout: Timeout in seconds
            
        Returns:
            Method result dictionary
            
        Raises:
            A2AClientError: If request fails
            TimeoutError: If request times out
        
        Example:
            >>> result = await client.call(
            ...     method="liturgy_agent.get_readings",
            ...     params={"date": "2024-01-15", "calendar": "roman"}
            ... )
            >>> print(result["readings"])
        """
        try:
            # Create request
            request = create_request(method=method, params=params)
            
            logger.info(f"Calling {method} (timeout={timeout}s)")
            
            # Send request
            response = await self.transport.send(request, timeout=timeout)
            
            logger.info(f"Call to {method} completed")
            
            return response.result
            
        except Exception as e:
            logger.error(f"Error calling {method}: {e}")
            raise A2AClientError(f"Failed to call {method}: {e}") from e
    
    async def call_stream(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call an agent method with streaming response.
        
        Args:
            method: Agent method name
            params: Method parameters
            timeout: Timeout in seconds
            
        Yields:
            Response result dictionaries
            
        Raises:
            A2AClientError: If request fails
            NotImplementedError: If transport doesn't support streaming
        
        Example:
            >>> async for chunk in client.call_stream(
            ...     method="liturgy_agent.stream_commentary",
            ...     params={"reading_id": "123"}
            ... ):
            ...     print(chunk["text"], end="", flush=True)
        """
        try:
            # Create request
            request = create_request(method=method, params=params)
            
            logger.info(f"Streaming call to {method} (timeout={timeout}s)")
            
            # Send streaming request
            async for response in self.transport.send_stream(request, timeout=timeout):
                yield response.result
            
            logger.info(f"Stream from {method} completed")
            
        except NotImplementedError:
            raise NotImplementedError(
                f"{self.transport_type} transport does not support streaming"
            )
        except Exception as e:
            logger.error(f"Error streaming from {method}: {e}")
            raise A2AClientError(f"Failed to stream from {method}: {e}") from e

    async def call_agent_method(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Call an agent method via standard Google A2A message/send protocol.

        Embeds the method call as JSON text in a message/send request
        and parses the agent's reply from the task history.

        Args:
            method: Agent method name (e.g., "liturgy_agent.get_readings")
            params: Method parameters
            timeout: Timeout in seconds

        Returns:
            Parsed result dictionary from the agent's reply

        Raises:
            A2AClientError: If request fails
        """
        import httpx

        cmd_text = json.dumps({"method": method, "params": params or {}})
        body = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "id": str(uuid.uuid4()),
                "message": {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "parts": [{"text": cmd_text}],
                },
            },
        }

        url = f"{self.transport.agent_url}/"
        headers = self._get_auth_headers()
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.post(url, json=body)

        if response.status_code >= 400:
            raise A2AClientError(
                f"Failed to call {method}: HTTP {response.status_code}"
            )

        data = response.json()

        if "error" in data:
            raise A2AClientError(f"Agent error: {data['error']}")

        result = data.get("result", {})
        task = result.get("Task", result)
        history = task.get("history", [])

        agent_messages = [m for m in history if m.get("role") == "agent"]
        if not agent_messages:
            raise A2AClientError(f"No agent reply in task {task.get('id', 'unknown')}")

        reply_text = agent_messages[-1]["parts"][0]["text"]
        return json.loads(reply_text)

    async def ping(self, timeout: float = 5.0) -> bool:
        """
        Ping the agent to check connectivity via GET /health.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if agent is reachable

        Raises:
            A2AClientError: If ping fails
        """
        try:
            import httpx
            url = f"{self.transport.agent_url}/health"
            headers = self._get_auth_headers()
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                response = await client.get(url)
                if response.status_code >= 400:
                    raise A2AClientError(
                        f"Ping failed: HTTP {response.status_code}"
                    )
                data = response.json()
                return data.get("status") in ("healthy", "ok", "pong")
        except A2AClientError:
            raise
        except Exception as e:
            raise A2AClientError(f"Ping failed: {e}") from e
    

    
    async def close(self) -> None:
        """
        Close transport and clean up resources.
        
        Always call this when done with the client.
        """
        try:
            await self.transport.close()
            logger.info("A2A client closed")
        except Exception as e:
            logger.error(f"Error closing client: {e}")
    
    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()


class A2AClientError(Exception):
    """Exception raised by A2A client."""
    pass


def create_client(
    transport_type: str = "http",
    **transport_kwargs
) -> A2AClient:
    """
    Factory function to create A2A client.
    
    Args:
        transport_type: "http" (only supported transport)
        **transport_kwargs: Transport-specific parameters
        
    Returns:
        Configured A2A client
    
    Example:
        >>> client = create_client(
        ...     transport_type="http",
        ...     agent_url="http://liturgy-agent:8001"
        ... )
    """
    return A2AClient(transport_type=transport_type, **transport_kwargs)


# Convenience context manager
class a2a_client:
    """
    Context manager for A2A client.
    
    Example:
        >>> async with a2a_client(
        ...     transport_type="http",
        ...     agent_url="http://liturgy-agent:8001"
        ... ) as client:
        ...     result = await client.call("agent.ping")
        ...     print(result)
    """
    
    def __init__(self, transport_type: str = "http", **transport_kwargs):
        self.client = create_client(transport_type, **transport_kwargs)
    
    async def __aenter__(self):
        return self.client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
