"""Server-Sent Event frames for the OpenAI-compatible streaming path.

OpenWebUI consumes ``chat.completion.chunk`` frames terminated by
``data: [DONE]``. Every frame carries the advertised model id, not the upstream
provider's model name, so the stream matches what ``GET /v1/models`` advertised.
"""

import json
import time

from .schemas import MODEL_ID

DONE_FRAME: str = "data: [DONE]\n\n"


def _frame(payload: dict) -> str:
    """Encode one payload as an SSE data frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _envelope(chunk_id: str) -> dict:
    """Build the fields shared by every chunk."""
    return {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_ID,
    }


def build_content_chunk(text: str, *, chunk_id: str) -> str:
    """Build a frame carrying one content delta."""
    payload = _envelope(chunk_id)
    payload["choices"] = [
        {"index": 0, "delta": {"content": text}, "finish_reason": None}
    ]
    return _frame(payload)


def build_finish_chunk(*, chunk_id: str) -> str:
    """Build the frame that closes the stream.

    The reference implementation never sets ``finish_reason``; clients that
    rely on it would hang until ``[DONE]``. This frame sets it correctly.
    """
    payload = _envelope(chunk_id)
    payload["choices"] = [
        {"index": 0, "delta": {}, "finish_reason": "stop"}
    ]
    return _frame(payload)


def build_error_chunk(message: str, *, error_type: str = "internal_error") -> str:
    """Build a frame carrying an error instead of content.

    A stream that fails after the response has started cannot change its HTTP
    status. Emitting only ``[DONE]`` would leave the client with an empty
    assistant message and no explanation, so the failure travels in-band as a
    top-level ``error`` object, which OpenAI-compatible clients surface.
    """
    return _frame({"error": {"message": message, "type": error_type}})
