"""
Agent-to-Agent (A2A) Protocol Implementation.

This package implements the A2A protocol for inter-agent communication,
using HTTP/SSE transport for production microservices.

Key Components:
- protocol: Message models and JSON-RPC 2.0 serialization
- transport: HTTP/SSE transport implementation
- server: Agent server wrapper for hosting agents
- client: Client for making A2A requests

Version: 0.1.0
"""

from .protocol import (
    A2AMessage,
    A2ARequest,
    A2AResponse,
    A2AError,
    A2AErrorCode,
    A2AErrorData,
    serialize_message,
    deserialize_message,
    create_request,
    create_response,
    create_error
)

from .transport import (
    A2ATransport,
    A2ATransportError,
    HTTPTransport,
    create_transport
)

from .server import (
    A2AServer,
    AgentHandler,
    create_server
)

from .client import (
    A2AClient,
    A2AClientError,
    create_client,
    a2a_client
)

from .llm import (
    create_llm,
    LLMNotConfiguredError,
)

__all__ = [
    # Protocol
    "A2AMessage",
    "A2ARequest",
    "A2AResponse",
    "A2AError",
    "A2AErrorCode",
    "A2AErrorData",
    "serialize_message",
    "deserialize_message",
    "create_request",
    "create_response",
    "create_error",
    
    # Transport
    "A2ATransport",
    "A2ATransportError",
    "HTTPTransport",
    "create_transport",
    
    # Server
    "A2AServer",
    "AgentHandler",
    "create_server",
    
    # Client
    "A2AClient",
    "A2AClientError",
    "create_client",
    "a2a_client",

    # LLM
    "create_llm",
    "LLMNotConfiguredError",
]

__version__ = "0.1.0"
