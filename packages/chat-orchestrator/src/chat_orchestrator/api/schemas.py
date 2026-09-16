"""Request and response models for the OpenAI-compatible surface.

The request model deliberately ignores unknown fields: OpenWebUI sends far more
than the OpenAI minimum (chat_id, session_id, features, variables, files,
temperature, background_tasks) and rejecting any of them would break the
connection. ``role`` is a plain string rather than a Literal so that a future
``tool`` role cannot turn into an HTTP 422.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MODEL_ID: str = "prete-a-porter"


class ChatMessage(BaseModel):
    """A single conversation message.

    ``content`` accepts either a plain string or a list of content blocks,
    because OpenWebUI may send multimodal payloads.
    """

    model_config = ConfigDict(extra="ignore")

    role: str
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    """An OpenAI-shaped chat completion request.

    ``model`` is accepted but never read: the backend always uses its own
    configured LLM.
    """

    model_config = ConfigDict(extra="ignore")

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    max_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] | None = None


class ModelCard(BaseModel):
    """One entry of the ``GET /v1/models`` response."""

    id: str
    object: str = "model"
    created: int
    owned_by: str = "prete-a-porter"


class ModelList(BaseModel):
    """The ``GET /v1/models`` response envelope."""

    object: str = "list"
    data: list[ModelCard]


class ChatCompletionChoice(BaseModel):
    """One completion choice."""

    index: int = 0
    message: dict[str, Any]
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    """Token accounting.

    The graph does not surface token counts, so these are reported as zero
    rather than fabricated.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """A buffered (non-streaming) completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str = MODEL_ID
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage = Field(default_factory=ChatCompletionUsage)
