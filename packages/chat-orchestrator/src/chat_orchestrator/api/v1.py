"""OpenAI-compatible routes consumed by OpenAI-compatible chat clients.

LibreChat and OpenWebUI both discover the single advertised model here and send
every chat request to ``POST /v1/chat/completions``. The request's ``model``
field is accepted but never read: the backend always uses its own configured
LLM.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from ..application import is_visible_token, run_chat, stream_chat, to_langchain_messages
from ..config import get_chat_timeout_seconds, get_llm
from ..rate_limiter import RateLimitResult, get_rate_limiter
from ..utils.logging import get_logger
from .auth import require_api_key
from .identity import CallerIdentity, get_caller_identity
from .schemas import (
    MODEL_ID,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCard,
    ModelList,
)
from .sse import DONE_FRAME, build_content_chunk, build_error_chunk, build_finish_chunk
from .tasks import classify_task

logger = get_logger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["openai-compatible"],
    dependencies=[Depends(require_api_key)],
)

INTERNAL_ERROR_MESSAGE_IT: str = (
    "Si è verificato un errore nel generare la risposta. Riprova tra qualche istante."
)
TIMEOUT_ERROR_MESSAGE_IT: str = (
    "La richiesta ha superato il tempo massimo di elaborazione. Riprova tra qualche istante."
)
RATE_LIMIT_MESSAGE_IT: str = "Hai raggiunto il limite di messaggi. Riprova più tardi."


def _new_completion_id() -> str:
    """Build a request-stable completion id."""
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


def _log_received(completion_id: str, identity: CallerIdentity, stream: bool) -> None:
    """Log the boundary fields that make one completion traceable."""
    logger.info(
        "Chat completion received",
        request_id=completion_id,
        conversation_id=identity.thread_id,
        message_id=identity.message_id,
        user_id=identity.user_id,
        stream=stream,
        model=MODEL_ID,
    )


def _log_finished(
    completion_id: str,
    identity: CallerIdentity,
    stream: bool,
    started: float,
    outcome: str,
) -> None:
    """Log duration and outcome for a completion logged by ``_log_received``."""
    logger.info(
        "Chat completion finished",
        request_id=completion_id,
        conversation_id=identity.thread_id,
        message_id=identity.message_id,
        user_id=identity.user_id,
        stream=stream,
        duration_ms=round((time.monotonic() - started) * 1000),
        outcome=outcome,
    )


async def _invoke_graph(
    request: ChatCompletionRequest,
    identity: CallerIdentity,
) -> str:
    """Run the ReAct graph through the shared application seam."""
    return await run_chat(request.messages, session_id=identity.thread_id)


async def _invoke_utility_llm(request: ChatCompletionRequest) -> str:
    """Answer a utility request with a bare LLM call.

    No homily system prompt and no tools: a utility task is a generic text
    transformation. Running it through the ReAct loop would make the LLM call
    the liturgical tools to generate a chat title.
    """
    llm = get_llm()
    async with asyncio.timeout(get_chat_timeout_seconds()):
        response = await llm.ainvoke(to_langchain_messages(request.messages))
    content = response.content
    if isinstance(content, str):
        return content
    return str(content)


async def _stream_chat(
    request: ChatCompletionRequest,
    completion_id: str,
    identity: CallerIdentity,
    started: float,
) -> AsyncIterator[str]:
    """Stream a chat completion as OpenAI-shaped SSE frames.

    A failure mid-stream is logged and the stream is terminated with
    ``[DONE]`` rather than left open, so the client never hangs. A timeout
    ends the same way, with an in-band error the client can surface.
    """
    try:
        async for chunk, metadata in stream_chat(
            request.messages,
            session_id=identity.thread_id,
        ):
            if is_visible_token(chunk, metadata):
                yield build_content_chunk(chunk.content, chunk_id=completion_id)
        yield build_finish_chunk(chunk_id=completion_id)
        outcome = "completed"
    except TimeoutError:
        logger.error("Streaming completion timed out", request_id=completion_id)
        yield build_error_chunk(TIMEOUT_ERROR_MESSAGE_IT, error_type="timeout")
        outcome = "timeout"
    except Exception:
        logger.error("Streaming completion failed", exc_info=True)
        yield build_error_chunk(INTERNAL_ERROR_MESSAGE_IT)
        outcome = "error"
    _log_finished(completion_id, identity, True, started, outcome)
    yield DONE_FRAME


async def _stream_utility_task(
    request: ChatCompletionRequest,
    completion_id: str,
    identity: CallerIdentity,
    started: float,
) -> AsyncIterator[str]:
    """Stream a utility task straight from the LLM, with no graph and no tools."""
    try:
        llm = get_llm()
        async with asyncio.timeout(get_chat_timeout_seconds()):
            async for chunk in llm.astream(to_langchain_messages(request.messages)):
                content = chunk.content
                if isinstance(content, str) and content:
                    yield build_content_chunk(content, chunk_id=completion_id)
        yield build_finish_chunk(chunk_id=completion_id)
        outcome = "completed"
    except TimeoutError:
        logger.error("Streaming utility task timed out", request_id=completion_id)
        yield build_error_chunk(TIMEOUT_ERROR_MESSAGE_IT, error_type="timeout")
        outcome = "timeout"
    except Exception:
        logger.error("Streaming utility task failed", exc_info=True)
        yield build_error_chunk(INTERNAL_ERROR_MESSAGE_IT)
        outcome = "error"
    _log_finished(completion_id, identity, True, started, outcome)
    yield DONE_FRAME


@router.get("/models")
async def list_models() -> ModelList:
    """Advertise the single available model."""
    return ModelList(
        data=[
            ModelCard(
                id=MODEL_ID,
                created=int(time.time()),
            )
        ]
    )


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    identity: CallerIdentity = Depends(get_caller_identity),
):
    """Answer a chat completion request.

    ``stream=True`` returns OpenAI-shaped SSE frames and ``stream=False`` the
    buffered payload. Both paths are bounded by ``CHAT_REQUEST_TIMEOUT_SECONDS``
    so a stuck downstream agent cannot hold the request open forever.
    """
    completion_id = _new_completion_id()
    started = time.monotonic()
    _log_received(completion_id, identity, request.stream)

    limiter = await get_rate_limiter()
    quota: RateLimitResult = await limiter.check_and_increment(identity.user_id)
    if not quota.ok:
        logger.info("Rate limit exceeded", user_id=identity.user_id)
        _log_finished(completion_id, identity, request.stream, started, "rate_limited")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": RATE_LIMIT_MESSAGE_IT,
                    "type": "rate_limit_exceeded",
                    "limits": {
                        "hour": {
                            "limit": quota.limits["hour"].limit,
                            "remaining": quota.limits["hour"].remaining,
                            "reset_at": quota.limits["hour"].reset_at,
                        },
                        "day": {
                            "limit": quota.limits["day"].limit,
                            "remaining": quota.limits["day"].remaining,
                            "reset_at": quota.limits["day"].reset_at,
                        },
                    },
                }
            },
        )

    task = classify_task(request)

    if request.stream:
        generator = (
            _stream_utility_task(request, completion_id, identity, started)
            if task is not None
            else _stream_chat(request, completion_id, identity, started)
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    if task is not None:
        logger.info("Handling utility task", task=task, request_id=completion_id)
        try:
            content = await _invoke_utility_llm(request)
        except TimeoutError:
            logger.error("Utility task timed out", request_id=completion_id)
            _log_finished(completion_id, identity, False, started, "timeout")
            return JSONResponse(
                status_code=504,
                content={"error": {"message": TIMEOUT_ERROR_MESSAGE_IT, "type": "timeout"}},
            )
        except Exception:
            logger.error("Utility task LLM call failed", exc_info=True)
            _log_finished(completion_id, identity, False, started, "error")
            return JSONResponse(
                status_code=500,
                content={"error": {"message": INTERNAL_ERROR_MESSAGE_IT, "type": "internal_error"}},
            )
        _log_finished(completion_id, identity, False, started, "completed")
        return ChatCompletionResponse(
            id=completion_id,
            created=int(time.time()),
            choices=[
                ChatCompletionChoice(
                    message={"role": "assistant", "content": content},
                )
            ],
        )

    try:
        content = await _invoke_graph(request, identity)
    except TimeoutError:
        logger.error("Graph invocation timed out", request_id=completion_id)
        _log_finished(completion_id, identity, False, started, "timeout")
        return JSONResponse(
            status_code=504,
            content={"error": {"message": TIMEOUT_ERROR_MESSAGE_IT, "type": "timeout"}},
        )
    except Exception:
        logger.error("Graph invocation failed", exc_info=True)
        _log_finished(completion_id, identity, False, started, "error")
        return JSONResponse(
            status_code=500,
            content={"error": {"message": INTERNAL_ERROR_MESSAGE_IT, "type": "internal_error"}},
        )

    _log_finished(completion_id, identity, False, started, "completed")
    return ChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        choices=[
            ChatCompletionChoice(
                message={"role": "assistant", "content": content},
            )
        ],
    )
