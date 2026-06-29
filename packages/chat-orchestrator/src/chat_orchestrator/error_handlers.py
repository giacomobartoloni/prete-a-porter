"""
Error handlers for Prete-a-porter backend.

Provides FastAPI exception handlers and error response formatting
with user-friendly Italian messages.
"""

from typing import Any, Dict

from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from .exceptions import PreteAPorterException
from .utils.logging import get_logger, get_correlation_id

logger = get_logger(__name__)


def get_error_response(exception: PreteAPorterException) -> Dict[str, Any]:
    """
    Create a standardized error response dictionary.
    
    Args:
        exception: The application exception
        
    Returns:
        Dictionary with error details
    """
    return {
        "error": {
            "code": exception.error_code,
            "message": exception.user_message_it,
            "correlation_id": get_correlation_id(),
        }
    }


async def preteaporter_exception_handler(request: Request, exc: PreteAPorterException):
    """
    Handle all custom application exceptions.
    
    Returns JSON response with user-friendly Italian error message.
    """
    logger.error(
        "Application exception occurred",
        error_code=exc.error_code,
        error_message=exc.message,
        correlation_id=get_correlation_id(),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content=get_error_response(exc)
    )


async def validation_exception_handler(request: Request, exc: PreteAPorterException):
    """
    Handle validation exceptions with 400 status code.
    """
    from .exceptions import ValidationException
    
    if isinstance(exc, ValidationException):
        logger.warning(
            "Validation error",
            error_code=exc.error_code,
            error_message=exc.message,
            correlation_id=get_correlation_id(),
            field=exc.details.get("field"),
        )
        
        return JSONResponse(
            status_code=400,
            content=get_error_response(exc)
        )
    
    # Fallback to generic handler
    return await preteaporter_exception_handler(request, exc)


async def llm_exception_handler(request: Request, exc: PreteAPorterException):
    """
    Handle LLM exceptions with 503 status code (service unavailable).
    """
    from .exceptions import LLMException, LLMRateLimitException
    
    if isinstance(exc, LLMRateLimitException):
        logger.warning(
            "LLM rate limit exceeded",
            error_code=exc.error_code,
            correlation_id=get_correlation_id(),
        )
        
        return JSONResponse(
            status_code=429,  # Too Many Requests
            content=get_error_response(exc),
            headers={"Retry-After": str(exc.details.get("retry_after", 60))}
        )
    
    if isinstance(exc, LLMException):
        logger.error(
            "LLM error",
            error_code=exc.error_code,
            error_message=exc.message,
            correlation_id=get_correlation_id(),
            exc_info=True,
        )
        
        return JSONResponse(
            status_code=503,  # Service Unavailable
            content=get_error_response(exc)
        )
    
    # Fallback to generic handler
    return await preteaporter_exception_handler(request, exc)


async def websocket_exception_handler(websocket: WebSocket, exc: Exception):
    """
    Handle WebSocket exceptions by sending error message to client.
    
    This handler should be called from within the WebSocket endpoint.
    """
    correlation_id = get_correlation_id()
    
    if isinstance(exc, PreteAPorterException):
        error_message = exc.user_message_it
        error_code = exc.error_code
        
        logger.error(
            "WebSocket exception",
            error_code=error_code,
            error_message=exc.message,
            correlation_id=correlation_id,
            session_id=getattr(websocket, "path_params", {}).get("session_id"),
            exc_info=True,
        )
    else:
        error_message = "Si è verificato un errore imprevisto. Riprova più tardi."
        error_code = "WS_ERROR"
        
        logger.error(
            "Unexpected WebSocket exception",
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )
    
    try:
        await websocket.send_json({
            "type": "error",
            "error": {
                "code": error_code,
                "message": error_message,
                "correlation_id": correlation_id,
            }
        })
    except Exception as send_error:
        logger.error(
            "Failed to send error message to WebSocket",
            error=str(send_error),
            correlation_id=correlation_id,
        )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle all unhandled exceptions.
    
    Returns generic error message to avoid leaking internal details.
    """
    correlation_id = get_correlation_id()
    
    logger.error(
        "Unhandled exception",
        error=str(exc),
        correlation_id=correlation_id,
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Si è verificato un errore imprevisto. Riprova più tardi.",
                "correlation_id": correlation_id,
            }
        }
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    from .exceptions import (
        PreteAPorterException,
        ValidationException,
        LLMException,
        DatabaseException,
        WebSocketException,
        ToolException,
        AgentException,
        A2AException,
        ExternalServiceException,
    )
    
    # Register custom exception handlers
    app.add_exception_handler(ValidationException, validation_exception_handler)
    app.add_exception_handler(LLMException, llm_exception_handler)
    app.add_exception_handler(PreteAPorterException, preteaporter_exception_handler)
    
    # Register catch-all handler for unhandled exceptions
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered")