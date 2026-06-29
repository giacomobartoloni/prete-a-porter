"""
HTTP and WebSocket route handlers for Chat Orchestrator.
"""

import json
import os
import uuid
from urllib.parse import parse_qs

import jwt
from fastapi import Request, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from .exceptions import WebSocketConnectionException, WebSocketMessageException
from .graph import get_graph
from .rate_limiter import RateLimiter
from .utils.logging import get_logger, set_correlation_id, clear_correlation_id

logger = get_logger(__name__)

_rate_limiter: RateLimiter | None = None


async def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = await RateLimiter.create()
    return _rate_limiter


def _get_ws_jwt_secret() -> str:
    secret = os.environ.get("WS_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "WS_JWT_SECRET environment variable is required. "
            "Set it in .env or docker-compose environment."
        )
    return secret


def _get_ws_token(websocket: WebSocket) -> str | None:
    """Extract JWT token from sub-protocol header or query param."""
    protocol = websocket.headers.get("sec-websocket-protocol", "")
    if protocol and protocol != "":
        return protocol.split(",")[0].strip()
    params = parse_qs(websocket.url.query)
    tokens = params.get("token", [])
    return tokens[0] if tokens else None


def _verify_ws_token(token: str) -> dict | None:
    """Verify WebSocket JWT token, return payload or None."""
    try:
        payload = jwt.decode(token, _get_ws_jwt_secret(), algorithms=["HS256"])
        if payload.get("type") != "ws_ticket":
            logger.warning("Invalid token type", token_type=payload.get("type"))
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.info("WebSocket token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid WebSocket token", error=str(e))
        return None


async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to each request for tracing."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)

    logger.debug("Request started", method=request.method, url=str(request.url))

    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.debug("Request completed", status_code=response.status_code)
        return response
    except Exception as e:
        logger.error("Request failed", error=str(e), exc_info=True)
        raise
    finally:
        clear_correlation_id()


async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "chat-orchestrator"}


async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for chat."""
    correlation_id = set_correlation_id()

    try:
        from .main import check_ws_rate_limit

        token = _get_ws_token(websocket)
        await websocket.accept(subprotocol=token)

        payload = _verify_ws_token(token) if token else None
        if not payload:
            logger.warning("Unauthorized WebSocket connection", session_id=session_id)
            try:
                await websocket.close(code=4001, reason="Unauthorized")
            except Exception:
                pass
            return

        if not check_ws_rate_limit(websocket):
            logger.warning("Rate limit exceeded", session_id=session_id)
            try:
                await websocket.close(code=4001, reason="Rate limit exceeded")
            except Exception:
                pass
            return

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("JWT payload missing 'sub' claim", session_id=session_id)
            try:
                await websocket.close(code=4001, reason="Invalid token payload")
            except Exception:
                pass
            return

        graph = await get_graph()
        await _message_loop(websocket, graph, session_id, user_id, correlation_id)
    except WebSocketDisconnect:
        logger.info("Client disconnected", session_id=session_id, correlation_id=correlation_id)
    except Exception as e:
        logger.error("WebSocket error", session_id=session_id, error=str(e), exc_info=True)
        await _send_error_and_close(websocket, e)
    finally:
        clear_correlation_id()


async def _message_loop(websocket: WebSocket, graph, session_id: str, user_id: str, correlation_id: str) -> None:
    """Main message receive/respond loop."""
    message_count = 0

    while True:
        try:
            data = await websocket.receive_text()
        except WebSocketDisconnect:
            raise

        message_count += 1

        # Parse JSON payload with optional history
        try:
            payload = json.loads(data)
            text = payload.get("text", data)
            history = payload.get("history", [])
        except json.JSONDecodeError:
            text = data
            history = []

        try:
            # Check if checkpointer has state for this thread
            try:
                checkpointer = graph.checkpointer
                checkpoint = await checkpointer.aget_tuple(
                    {"configurable": {"thread_id": session_id}}
                )
                has_checkpoint = checkpoint is not None
            except Exception:
                has_checkpoint = False

            if has_checkpoint:
                stored_user_id = (
                    checkpoint.checkpoint.get("channel_values", {}).get("user_id")
                )
                if stored_user_id != user_id:
                    logger.warning(
                        "Session owner mismatch",
                        session_id=session_id,
                        expected=stored_user_id,
                        actual=user_id,
                    )
                    try:
                        await websocket.close(code=4003, reason="Forbidden")
                    except Exception:
                        pass
                    return
                msgs = [HumanMessage(content=text)]
            else:
                # Checkpointer lost — rebuild from history
                msgs = [HumanMessage(content=h["content"]) for h in history if h.get("content")]
                msgs.append(HumanMessage(content=text))

            limiter = await get_rate_limiter()
            result = await limiter.check_and_increment(user_id)
            if not result.ok:
                await websocket.send_json({
                    "type": "error",
                    "code": "rate_limit_exceeded",
                    "limits": {
                        "hour": {
                            "limit": result.limits["hour"].limit,
                            "remaining": result.limits["hour"].remaining,
                            "reset_at": result.limits["hour"].reset_at,
                        },
                        "day": {
                            "limit": result.limits["day"].limit,
                            "remaining": result.limits["day"].remaining,
                            "reset_at": result.limits["day"].reset_at,
                        },
                    },
                })
                continue

            result = await graph.ainvoke(
                {"messages": msgs, "session_id": session_id, "user_id": user_id},
                config={"configurable": {"thread_id": session_id}, "recursion_limit": 15},
            )

            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            raw_content = ai_messages[-1].content if ai_messages else "No response"
            if isinstance(raw_content, list):
                ai_message = "\n".join(
                    b.get("text", "") for b in raw_content if isinstance(b, dict) and b.get("type") == "text"
                ) or str(raw_content)
            elif not isinstance(raw_content, str):
                ai_message = str(raw_content)
            else:
                ai_message = raw_content

            await websocket.send_json({
                "type": "message",
                "content": ai_message,
                "session_id": session_id,
            })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error("Error processing message", error=str(e), exc_info=True)
            await websocket.send_json({
                "type": "error",
                "error": {
                    "code": "MESSAGE_PROCESSING_ERROR",
                    "message": "Si è verificato un errore nel processare il messaggio. Riprova.",
                    "correlation_id": correlation_id,
                },
            })


async def _send_error_and_close(websocket: WebSocket, error: Exception) -> None:
    """Send error response and close WebSocket connection."""
    from .error_handlers import websocket_exception_handler

    try:
        await websocket_exception_handler(websocket, error)
    except Exception:
        pass
    try:
        await websocket.close()
    except Exception:
        pass
