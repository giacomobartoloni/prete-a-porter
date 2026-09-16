"""OpenAI-compatible routes consumed by OpenWebUI.

OpenWebUI discovers the single advertised model here and sends every chat
request to ``POST /v1/chat/completions``. The request's ``model`` field is
accepted but never read: the backend always uses its own configured LLM.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import get_llm
from ..graph import get_graph
from ..rate_limiter import RateLimitResult, get_rate_limiter
from .auth import require_api_key
from .identity import CallerIdentity, get_caller_identity
from .messages import extract_reply_text, stream_graph_tokens, to_langchain_messages
from .sse import DONE_FRAME, build_content_chunk, build_finish_chunk
from .tasks import classify_task
from .schemas import (
    MODEL_ID,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCard,
    ModelList,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["openai-compatible"],
    dependencies=[Depends(require_api_key)],
)

RECURSION_LIMIT: int = 15
INTERNAL_ERROR_MESSAGE_IT: str = (
    "Si è verificato un errore nel generare la risposta. Riprova tra qualche istante."
)
RATE_LIMIT_MESSAGE_IT: str = "Hai raggiunto il limite di messaggi. Riprova più tardi."


def _new_completion_id() -> str:
    """Build a request-stable completion id."""
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


async def _invoke_graph(request: ChatCompletionRequest) -> str:
    """Run the ReAct graph and return the assistant's reply text."""
    graph = await get_graph()
    result = await graph.ainvoke(
        {"messages": to_langchain_messages(request.messages)},
        config={"recursion_limit": RECURSION_LIMIT},
    )
    return extract_reply_text(result)


async def _invoke_utility_llm(request: ChatCompletionRequest) -> str:
    """Answer a utility request with a bare LLM call.

    No homily system prompt and no tools: a utility task is a generic text
    transformation. Running it through the ReAct loop would make the LLM call
    the liturgical tools to generate a chat title.
    """
    llm = get_llm()
    response = await llm.ainvoke(to_langchain_messages(request.messages))
    content = response.content
    if isinstance(content, str):
        return content
    return str(content)


async def _stream_chat(
    request: ChatCompletionRequest,
    completion_id: str,
) -> AsyncIterator[str]:
    """Stream a chat completion as OpenAI-shaped SSE frames.

    A failure mid-stream is logged and the stream is terminated with
    ``[DONE]`` rather than left open, so the client never hangs.
    """
    try:
        graph = await get_graph()
        messages = to_langchain_messages(request.messages)
        async for token in stream_graph_tokens(graph, messages):
            yield build_content_chunk(token, chunk_id=completion_id)
        yield build_finish_chunk(chunk_id=completion_id)
    except Exception:
        logger.error("Streaming completion failed", exc_info=True)
    yield DONE_FRAME


async def _stream_utility_task(
    request: ChatCompletionRequest,
    completion_id: str,
) -> AsyncIterator[str]:
    """Stream a utility task straight from the LLM, with no graph and no tools."""
    try:
        llm = get_llm()
        async for chunk in llm.astream(to_langchain_messages(request.messages)):
            content = chunk.content
            if isinstance(content, str) and content:
                yield build_content_chunk(content, chunk_id=completion_id)
        yield build_finish_chunk(chunk_id=completion_id)
    except Exception:
        logger.error("Streaming utility task failed", exc_info=True)
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

    Streaming is not implemented yet: ``stream=True`` currently returns the
    same buffered payload. The SSE path is added separately.
    """
    completion_id = _new_completion_id()

    limiter = await get_rate_limiter()
    quota: RateLimitResult = await limiter.check_and_increment(identity.user_id)
    if not quota.ok:
        logger.info("Rate limit exceeded", extra={"user_id": identity.user_id})
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
            _stream_utility_task(request, completion_id)
            if task is not None
            else _stream_chat(request, completion_id)
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
        logger.info("Handling OpenWebUI utility task", extra={"task": task})
        try:
            content = await _invoke_utility_llm(request)
        except Exception:
            logger.error("Utility task LLM call failed", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": {"message": INTERNAL_ERROR_MESSAGE_IT, "type": "internal_error"}},
            )
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
        content = await _invoke_graph(request)
    except Exception:
        logger.error("Graph invocation failed", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": INTERNAL_ERROR_MESSAGE_IT, "type": "internal_error"}},
        )

    return ChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        choices=[
            ChatCompletionChoice(
                message={"role": "assistant", "content": content},
            )
        ],
    )
