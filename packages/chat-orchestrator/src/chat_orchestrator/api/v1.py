"""OpenAI-compatible routes consumed by OpenWebUI.

OpenWebUI discovers the single advertised model here and sends every chat
request to ``POST /v1/chat/completions``. The request's ``model`` field is
accepted but never read: the backend always uses its own configured LLM.
"""

import logging
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..graph import get_graph
from ..rate_limiter import RateLimitResult, get_rate_limiter
from .auth import require_api_key
from .identity import CallerIdentity, get_caller_identity
from .messages import extract_reply_text, to_langchain_messages
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
