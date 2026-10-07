"""Schema tests: the request model must tolerate everything OpenWebUI sends."""

import pytest
from pydantic import ValidationError

from chat_orchestrator.api.schemas import (
    MODEL_ID,
    ChatCompletionRequest,
    ChatMessage,
)


class TestChatMessage:
    def test_accepts_string_content(self):
        msg = ChatMessage(role="user", content="ciao")
        assert msg.content == "ciao"

    def test_accepts_content_block_list(self):
        """OpenWebUI can send multimodal content blocks."""
        msg = ChatMessage(role="user", content=[{"type": "text", "text": "ciao"}])
        assert isinstance(msg.content, list)

    def test_accepts_unknown_role(self):
        """A future 'tool' role must not 422 the connection."""
        msg = ChatMessage(role="tool", content="result")
        assert msg.role == "tool"


class TestChatCompletionRequest:
    def test_minimal_request(self):
        req = ChatCompletionRequest(
            model=MODEL_ID,
            messages=[{"role": "user", "content": "ciao"}],
        )
        assert req.stream is False
        assert req.max_tokens is None

    def test_ignores_unknown_fields(self):
        """OpenWebUI sends chat_id, features, variables, files, temperature..."""
        req = ChatCompletionRequest(
            model=MODEL_ID,
            messages=[{"role": "user", "content": "ciao"}],
            chat_id="abc",
            session_id="def",
            features={"web_search": True},
            variables={"{{USER_NAME}}": "Giacomo"},
            filter_ids=[],
            files=[],
            temperature=0.7,
            top_p=0.9,
            background_tasks={"title_generation": False},
        )
        assert req.model == MODEL_ID

    def test_rejects_empty_messages(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model=MODEL_ID, messages=[])

    def test_rejects_non_positive_max_tokens(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                model=MODEL_ID,
                messages=[{"role": "user", "content": "ciao"}],
                max_tokens=0,
            )

    def test_metadata_accepts_arbitrary_keys(self):
        req = ChatCompletionRequest(
            model=MODEL_ID,
            messages=[{"role": "user", "content": "ciao"}],
            metadata={"task": "title_generation", "profile_timings": True},
        )
        assert req.metadata == {"task": "title_generation", "profile_timings": True}
