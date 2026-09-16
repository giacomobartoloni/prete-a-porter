"""SSE frames must be well-formed OpenAI chunks."""

import json

from chat_orchestrator.api.schemas import MODEL_ID
from chat_orchestrator.api.sse import DONE_FRAME, build_content_chunk, build_finish_chunk


def _parse(frame: str) -> dict:
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    return json.loads(frame[len("data: "):-2])


class TestContentChunk:
    def test_frame_terminator(self):
        assert build_content_chunk("ciao", chunk_id="chatcmpl-abc").endswith("\n\n")

    def test_payload_shape(self):
        payload = _parse(build_content_chunk("ciao", chunk_id="chatcmpl-abc"))
        assert payload["id"] == "chatcmpl-abc"
        assert payload["object"] == "chat.completion.chunk"
        assert payload["model"] == MODEL_ID
        assert isinstance(payload["created"], int)

    def test_delta_carries_content(self):
        payload = _parse(build_content_chunk("ciao", chunk_id="chatcmpl-abc"))
        choice = payload["choices"][0]
        assert choice["index"] == 0
        assert choice["delta"] == {"content": "ciao"}
        assert choice["finish_reason"] is None

    def test_unicode_is_not_escaped(self):
        """Italian accents must survive as UTF-8, not \\u escapes."""
        frame = build_content_chunk("però è così", chunk_id="chatcmpl-abc")
        assert "però è così" in frame

    def test_empty_text_is_still_a_valid_frame(self):
        payload = _parse(build_content_chunk("", chunk_id="chatcmpl-abc"))
        assert payload["choices"][0]["delta"] == {"content": ""}


class TestFinishChunk:
    def test_finish_reason_is_stop(self):
        payload = _parse(build_finish_chunk(chunk_id="chatcmpl-abc"))
        assert payload["choices"][0]["finish_reason"] == "stop"

    def test_delta_is_empty(self):
        payload = _parse(build_finish_chunk(chunk_id="chatcmpl-abc"))
        assert payload["choices"][0]["delta"] == {}

    def test_same_chunk_id(self):
        payload = _parse(build_finish_chunk(chunk_id="chatcmpl-abc"))
        assert payload["id"] == "chatcmpl-abc"


class TestDoneFrame:
    def test_exact_literal(self):
        assert DONE_FRAME == "data: [DONE]\n\n"
