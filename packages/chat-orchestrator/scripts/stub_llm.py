"""A minimal OpenAI-compatible server used to exercise the agent chain.

Level 3 verification (see ``docs/verification-levels.md``): the orchestrator,
graph, tool execution, A2A transport and the downstream agents can all be tested
without a reachable model. This stub answers ``/v1/chat/completions`` and, on the
first turn of a conversation, asks for a liturgical tool call — so a single
request traverses:

    orchestrator -> graph -> agent_node -> tools_node -> A2A client
                 -> liturgy-agent -> evangelizo.org -> back -> response

Run it and point the orchestrator at it:

    uv run python scripts/stub_llm.py                     # terminal 1
    OPENAI_BASE_URL=http://host.docker.internal:9099/v1 \\
    OPENAI_API_KEY=stub OPENAI_MODEL_NAME=stub \\
    uv run uvicorn chat_orchestrator.main:app --port 8000 # terminal 2

It is a diagnostic, not part of the product. It makes no model decisions: it
always requests the same tool, then always returns a fixed acknowledgement.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 9099
TOOL_NAME = "get_liturgical_readings"


def _envelope() -> dict:
    return {"id": "chatcmpl-stub", "created": 0, "model": "stub"}


def _tool_call_body() -> dict:
    """A completion whose only choice is a tool call."""
    return {
        **_envelope(),
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_stub_1",
                            "type": "function",
                            "function": {
                                "name": TOOL_NAME,
                                "arguments": json.dumps({"occasion": "sunday"}),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _text_body(tool_result: str) -> dict:
    """A completion that reports how much the tool returned."""
    return {
        **_envelope(),
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "STUB: chain complete. The liturgical tool returned "
                        f"{len(tool_result)} characters."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _chunk(text: str, *, finish: str | None = None) -> bytes:
    payload = {
        **_envelope(),
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {"content": text} if text else {},
                "finish_reason": finish,
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


def _tool_call_chunk() -> bytes:
    payload = {
        **_envelope(),
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_stub_1",
                            "type": "function",
                            "function": {
                                "name": TOOL_NAME,
                                "arguments": json.dumps({"occasion": "sunday"}),
                            },
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    return f"data: {json.dumps(payload)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        """Silence per-request logging; the caller's console is the output."""
        return

    def do_POST(self) -> None:  # noqa: N802 — required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        messages = body.get("messages", [])

        tool_messages = [m for m in messages if m.get("role") == "tool"]
        if body.get("stream"):
            self._stream(tool_messages)
            return

        payload = _text_body(str(tool_messages[-1].get("content", ""))) if tool_messages else _tool_call_body()
        self._send_json(payload)

    def _stream(self, tool_messages: list[dict]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        if tool_messages:
            for piece in ("STUB", ": chain", " complete", " in streaming."):
                self.wfile.write(_chunk(piece))
                self.wfile.flush()
            self.wfile.write(_chunk("", finish="stop"))
        else:
            self.wfile.write(_tool_call_chunk())

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"stub LLM listening on 0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
