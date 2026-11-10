"""Deterministic OpenAI/Tavily stand-ins for black-box user journey E2E tests.

All network traffic stays between Docker Compose services. This is a scripted
provider, NOT a replacement for running against real LLM/Tavily environments.
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUDIT = {"llm_calls": [], "tavily_calls": []}
LOCK = threading.Lock()


def reply(content=None, *, tool_call=False):
    message = {"role": "assistant", "content": content}
    if tool_call:
        message["content"] = None
        message["tool_calls"] = [{
            "id": "call_e2e_news_1",
            "type": "function",
            "function": {
                "name": "search_news",
                "arguments": json.dumps({"query": "pace", "days_back": 7}),
            },
        }]
    return {
        "id": "chatcmpl-e2e-scripted",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "e2e-scripted-model",
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": "tool_calls" if tool_call else "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def complete(messages):
    # Deliberately adversarial: the fake model requests search_news on both
    # approvals and refusals. Only the REAL tools_node consent gate may allow it.
    if messages and messages[-1].get("role") == "tool":
        tool_result = str(messages[-1].get("content", ""))
        if "Ricerca non eseguita" in tool_result:
            return reply("Non ho cercato online, come richiesto.")
        if "https://example.org/news/pace" in tool_result:
            return reply("Notizia sulla pace: https://example.org/news/pace")
        return reply("Non sono disponibili notizie verificate.")

    user = next(
        (str(m.get("content", "")) for m in reversed(messages) if m.get("role") == "user"),
        "",
    ).casefold().strip()
    if "omelia" in user and "pace" in user and "cerca" not in user:
        return reply(
            "Posso cercare online notizie recenti sulla pace. "
            "Vuoi che cerchi online?"
        )
    if user in {"sì", "si", "sì, grazie", "no", "no, grazie"} or user.startswith("sì, cerca"):
        return reply(tool_call=True)
    if "cerca" in user or "notizie" in user:
        return reply(tool_call=True)
    return reply("Possiamo preparare un'omelia sulla pace.")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format_string, *args):
        pass

    def send_json(self, status, obj):
        encoded = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size or 0).decode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
        elif self.path == "/audit":
            with LOCK:
                snapshot = {k: list(v) for k, v in AUDIT.items()}
            self.send_json(200, snapshot)
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/reset":
            with LOCK:
                AUDIT["llm_calls"].clear()
                AUDIT["tavily_calls"].clear()
            self.send_json(200, {"status": "reset"})
            return
        try:
            payload = self.read_json()
        except (ValueError, UnicodeError):
            self.send_json(400, {"error": "invalid json"})
            return

        if self.path == "/v1/chat/completions":
            with LOCK:
                AUDIT["llm_calls"].append(payload)
            self.send_json(200, complete(payload.get("messages", [])))
            return
        if self.path == "/search":
            with LOCK:
                AUDIT["tavily_calls"].append(payload)
            fresh = datetime.now(timezone.utc) - timedelta(hours=2)
            self.send_json(200, {"results": [
                {"title": "Scheda malformata", "published_date": 123,
                 "url": "https://example.org/news/broken", "content": "bad"},
                {"title": "Pace e dialogo", "published_date": format_datetime(fresh),
                 "url": "https://example.org/news/pace", "content": "Iniziativa per la pace"},
                {"title": "Archivio", "published_date": "2000-01-01",
                 "url": "https://example.org/news/old", "content": "Vecchia notizia"},
            ]})
            return
        self.send_json(404, {"error": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
