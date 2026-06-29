"""
A2A Protocol Message Models and Serialization.

Implements JSON-RPC 2.0 protocol for agent-to-agent communication.

Message Format:
- Request: {"jsonrpc": "2.0", "id": "uuid", "method": "agent_name.method", "params": {...}}
- Response: {"jsonrpc": "2.0", "id": "uuid", "result": {...}}
- Error: {"jsonrpc": "2.0", "id": "uuid", "error": {"code": -32xxx, "message": "...", "data": {...}}}
"""

import json
import uuid
from typing import Any, Dict, Optional, Union, Literal
from enum import IntEnum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class A2AErrorCode(IntEnum):
    """JSON-RPC 2.0 error codes."""
    
    # Standard JSON-RPC 2.0 errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # A2A-specific errors (-32000 to -32099)
    AGENT_NOT_FOUND = -32000
    AGENT_TIMEOUT = -32001
    AGENT_BUSY = -32002
    TRANSPORT_ERROR = -32003
    SERIALIZATION_ERROR = -32004


class A2AMessage(BaseModel):
    """Base A2A message following JSON-RPC 2.0."""
    
    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    model_config = ConfigDict(use_enum_values=True)


class A2ARequest(A2AMessage):
    """
    A2A request message.
    
    Follows JSON-RPC 2.0 request format with method and params.
    
    Attributes:
        method: Fully qualified method name (e.g., "liturgy_agent.get_daily_readings")
        params: Method parameters as dictionary
    
    Example:
        >>> request = A2ARequest(
        ...     method="liturgy_agent.get_daily_readings",
        ...     params={"date": "2024-01-15", "occasion": "Mass of the Day"}
        ... )
    """
    
    method: str = Field(..., min_length=1, description="Method to call (agent.method)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Method parameters")
    
    @field_validator("method")
    def validate_method(cls, v):
        """Validate method format (agent.method)."""
        if "." not in v:
            raise ValueError(
                f"Method must be in format 'agent.method', got: {v}"
            )
        return v


class A2AErrorData(BaseModel):
    """Error data structure."""
    
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class A2AResponse(A2AMessage):
    """
    A2A successful response message.
    
    Follows JSON-RPC 2.0 response format with result.
    
    Attributes:
        result: Method result as dictionary
    
    Example:
        >>> response = A2AResponse(
        ...     id="request-uuid",
        ...     result={"status": "success", "data": {...}}
        ... )
    """
    
    result: Dict[str, Any] = Field(..., description="Method result")


class A2AError(A2AMessage):
    """
    A2A error response message.
    
    Follows JSON-RPC 2.0 error format.
    
    Attributes:
        error: Error details (code, message, data)
    
    Example:
        >>> error = A2AError(
        ...     id="request-uuid",
        ...     error=A2AErrorData(
        ...         code=A2AErrorCode.METHOD_NOT_FOUND,
        ...         message="Method not found",
        ...         data={"method": "unknown.method"}
        ...     )
        ... )
    """
    
    error: A2AErrorData


def serialize_message(
    message: Union[A2ARequest, A2AResponse, A2AError]
) -> str:
    """
    Serialize A2A message to JSON string.
    
    Args:
        message: A2A message (request, response, or error)
        
    Returns:
        JSON string representation
        
    Raises:
        ValueError: If message cannot be serialized
    
    Example:
        >>> request = A2ARequest(method="agent.test", params={})
        >>> json_str = serialize_message(request)
        >>> '{"jsonrpc":"2.0","id":"...","method":"agent.test","params":{}}' in json_str
        True
    """
    try:
        return message.model_dump_json()
    except Exception as e:
        raise ValueError(f"Failed to serialize A2A message: {e}") from e


def deserialize_message(
    json_str: str
) -> Union[A2ARequest, A2AResponse, A2AError]:
    """
    Deserialize JSON string to A2A message.
    
    Automatically detects message type (request, response, or error)
    based on the presence of 'method', 'result', or 'error' fields.
    
    Args:
        json_str: JSON string
        
    Returns:
        Parsed A2A message
        
    Raises:
        ValueError: If JSON is invalid or message type cannot be determined
    
    Example:
        >>> json_str = '{"jsonrpc":"2.0","id":"123","method":"agent.test","params":{}}'
        >>> message = deserialize_message(json_str)
        >>> isinstance(message, A2ARequest)
        True
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    
    # Validate JSON-RPC version
    if data.get("jsonrpc") != "2.0":
        raise ValueError(
            f"Invalid JSON-RPC version: {data.get('jsonrpc')}. Expected '2.0'"
        )
    
    # Detect message type
    if "method" in data:
        return A2ARequest(**data)
    elif "result" in data:
        return A2AResponse(**data)
    elif "error" in data:
        return A2AError(**data)
    else:
        raise ValueError(
            "Invalid A2A message: must contain 'method', 'result', or 'error'"
        )


def create_request(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> A2ARequest:
    """
    Create an A2A request message.
    
    Args:
        method: Method to call (format: "agent.method")
        params: Method parameters
        request_id: Optional request ID (generated if not provided)
        
    Returns:
        A2A request message
    
    Example:
        >>> request = create_request(
        ...     method="liturgy_agent.get_daily_readings",
        ...     params={"date": "2024-01-15"}
        ... )
        >>> request.method
        'liturgy_agent.get_daily_readings'
    """
    if request_id:
        return A2ARequest(
            id=request_id,
            method=method,
            params=params or {}
        )
    return A2ARequest(method=method, params=params or {})


def create_response(
    request_id: str,
    result: Dict[str, Any]
) -> A2AResponse:
    """
    Create an A2A response message.
    
    Args:
        request_id: ID from the original request
        result: Method result
        
    Returns:
        A2A response message
    
    Example:
        >>> response = create_response(
        ...     request_id="123",
        ...     result={"status": "success", "data": {}}
        ... )
        >>> response.id
        '123'
    """
    return A2AResponse(id=request_id, result=result)


def create_error(
    request_id: str,
    code: A2AErrorCode,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> A2AError:
    """
    Create an A2A error message.
    
    Args:
        request_id: ID from the original request
        code: Error code
        message: Error message
        data: Optional additional error data
        
    Returns:
        A2A error message
    
    Example:
        >>> error = create_error(
        ...     request_id="123",
        ...     code=A2AErrorCode.METHOD_NOT_FOUND,
        ...     message="Method not found"
        ... )
        >>> error.error.code
        -32601
    """
    return A2AError(
        id=request_id,
        error=A2AErrorData(code=code, message=message, data=data)
    )
