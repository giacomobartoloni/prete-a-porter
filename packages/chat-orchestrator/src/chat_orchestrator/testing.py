"""Test-only helpers used by the orchestrator runtime in TEST_MODE.

TEST_MODE validates the real graph/runtime contract. Do not replace this with
AsyncMock: tool binding, message types and streaming chunks are part of the
behavior being tested.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel


class ToolCapableFakeChatModel(FakeListChatModel):
    """Deterministic LangChain-compatible test model.

    The model never requests a tool. ``bind_tools`` is accepted only so the real
    orchestrator graph can run unchanged in TEST_MODE.
    """

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ToolCapableFakeChatModel":
        return self


def build_test_llm() -> ToolCapableFakeChatModel:
    """Build the fake chat model used when ``TEST_MODE=true``."""
    return ToolCapableFakeChatModel(responses=["Test response from mock LLM"])
