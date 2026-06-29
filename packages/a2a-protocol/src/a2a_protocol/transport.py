"""
A2A Transport Layer.

Implements HTTP transport for agent-to-agent communication:
- HTTP: RESTful HTTP with SSE for streaming (production)

This module provides HTTP-only transport suitable for microservices deployments.
"""

import asyncio
import base64
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator
import logging

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from .protocol import (
    A2ARequest,
    A2AResponse,
    A2AError,
    A2AErrorCode,
    serialize_message,
    deserialize_message,
    create_error
)

logger = logging.getLogger(__name__)


class A2ATransportError(Exception):
    """Base exception for transport errors."""
    pass


class A2ATransport(ABC):
    """
    Abstract base class for A2A transports.
    
    All transports must implement:
    - send: Send a request and return a response
    - send_stream: Send a request and stream responses (optional)
    """
    
    @abstractmethod
    async def send(
        self,
        request: A2ARequest,
        timeout: float = 30.0
    ) -> A2AResponse:
        """
        Send a request and wait for response.
        
        Args:
            request: A2A request message
            timeout: Timeout in seconds
            
        Returns:
            A2A response message
            
        Raises:
            A2ATransportError: If transport fails
            TimeoutError: If request times out
        """
        pass
    
    async def send_stream(
        self,
        request: A2ARequest,
        timeout: float = 60.0
    ) -> AsyncGenerator[A2AResponse, None]:
        """
        Send a request and stream responses.
        
        Args:
            request: A2A request message
            timeout: Timeout in seconds
            
        Yields:
            A2A response messages
            
        Raises:
            A2ATransportError: If transport fails
            NotImplementedError: If streaming not supported
        """
        raise NotImplementedError("Streaming not supported by this transport")


class HTTPTransport(A2ATransport):
    """
    HTTP-based transport for agent communication.
    
    Uses HTTP POST for requests and Server-Sent Events (SSE) for streaming.
    Suitable for production microservices deployments.
    
    Example:
        >>> transport = HTTPTransport(agent_url="http://liturgy-agent:8001")
        >>> request = A2ARequest(method="agent.test", params={})
        >>> response = await transport.send(request)
    """
    
    def __init__(
        self,
        agent_url: str,
        timeout: float = 30.0,
        retries: int = 3,
        auth_username: Optional[str] = None,
        auth_password: Optional[str] = None,
    ):
        """
        Initialize HTTP transport.

        Args:
            agent_url: Base URL of agent (e.g., "http://liturgy-agent:8001")
            timeout: Default timeout in seconds
            retries: Number of retry attempts
            auth_username: Optional Basic Auth username.
            auth_password: Optional Basic Auth password.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx required for HTTP transport. Install with: pip install httpx"
            )
        
        self.agent_url = agent_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self._auth_username = auth_username or os.environ.get("A2A_BASIC_AUTH_USERNAME")
        self._auth_password = auth_password or os.environ.get("A2A_BASIC_AUTH_PASSWORD")
        self._client: Optional[httpx.AsyncClient] = None
    
    def _basic_auth_header(self) -> Optional[Dict[str, str]]:
        if self._auth_username and self._auth_password:
            encoded = base64.b64encode(
                f"{self._auth_username}:{self._auth_password}".encode()
            ).decode()
            return {"Authorization": f"Basic {encoded}"}
        return None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            auth_header = self._basic_auth_header()
            if auth_header:
                headers.update(auth_header)
            self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self._client
    
    async def send(
        self,
        request: A2ARequest,
        timeout: Optional[float] = None
    ) -> A2AResponse:
        """
        Send request via HTTP POST.
        
        Args:
            request: A2A request
            timeout: Timeout in seconds (uses default if not provided)
            
        Returns:
            A2A response
            
        Raises:
            A2ATransportError: If HTTP request fails
            TimeoutError: If request times out
        """
        url = f"{self.agent_url}/"
        request_json = serialize_message(request)
        timeout_val = timeout or self.timeout
        
        for attempt in range(self.retries):
            try:
                logger.debug(f"HTTP POST to {url}: {request_json[:100]}...")
                
                response = await self._get_client().post(
                    url,
                    json=json.loads(request_json),
                    timeout=timeout_val
                )
                response.raise_for_status()
                
                response_data = response.json()
                message = deserialize_message(json.dumps(response_data))
                
                if isinstance(message, A2AError):
                    raise A2ATransportError(
                        f"Agent returned error: {message.error.message}"
                    )
                
                if not isinstance(message, A2AResponse):
                    raise A2ATransportError(
                        f"Expected response, got: {type(message).__name__}"
                    )
                
                return message
                
            except httpx.TimeoutException:
                if attempt == self.retries - 1:
                    raise TimeoutError(f"Request timed out after {timeout_val}s")
                logger.warning(f"Request timed out, retrying ({attempt + 1}/{self.retries})...")
                await asyncio.sleep(1.0 * (attempt + 1))
            
            except httpx.HTTPError as e:
                if attempt == self.retries - 1:
                    raise A2ATransportError(f"HTTP error: {e}") from e
                logger.warning(f"HTTP error, retrying ({attempt + 1}/{self.retries}): {e}")
                await asyncio.sleep(1.0 * (attempt + 1))
            
            except Exception as e:
                raise A2ATransportError(f"HTTP transport error: {e}") from e
        
        raise A2ATransportError("Max retries exceeded")
    
    async def send_stream(
        self,
        request: A2ARequest,
        timeout: float = 60.0
    ) -> AsyncGenerator[A2AResponse, None]:
        """
        Send request and stream responses via SSE.
        
        Args:
            request: A2A request
            timeout: Timeout in seconds
            
        Yields:
            A2A response messages
            
        Raises:
            A2ATransportError: If streaming fails
        """
        url = f"{self.agent_url}/stream"
        request_json = serialize_message(request)
        
        try:
            async with self._get_client().stream(
                "POST",
                url,
                json=json.loads(request_json),
                timeout=timeout
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    
                    message = deserialize_message(data)
                    
                    if isinstance(message, A2AError):
                        raise A2ATransportError(
                            f"Agent returned error: {message.error.message}"
                        )
                    
                    if isinstance(message, A2AResponse):
                        yield message
        
        except httpx.HTTPError as e:
            raise A2ATransportError(f"SSE streaming error: {e}") from e
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def create_transport(
    agent_url: str,
    timeout: float = 30.0,
    retries: int = 3,
    auth_username: Optional[str] = None,
    auth_password: Optional[str] = None,
) -> A2ATransport:
    """
    Factory function to create HTTP transport.
    
    Args:
        agent_url: Base URL of agent (e.g., "http://liturgy-agent:8001")
        timeout: Default timeout in seconds
        retries: Number of retry attempts
        auth_username: Optional Basic Auth username.
        auth_password: Optional Basic Auth password.
        
    Returns:
        Configured HTTP transport
    """
    return HTTPTransport(
        agent_url=agent_url,
        timeout=timeout,
        retries=retries,
        auth_username=auth_username,
        auth_password=auth_password,
    )
