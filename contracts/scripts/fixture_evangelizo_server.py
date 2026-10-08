#!/usr/bin/env python3
"""Minimal fixture Evangelizo publication API for deterministic liturgy integration.

Serves GET /{lang}/days/{YYYY-MM-DD} with a complete Mass payload by default.
Special dates:
  2099-12-31 → HTTP 503 (upstream failure)
  2099-12-30 → JSON missing gospel (schema/incomplete error path)
  2099-12-29 → object reference_displayed (malformed shape)

No third-party dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


COMPLETE_READINGS = [
    {
        "book_type": "reading",
        "book": {"full_title": "Lettera di san Giacomo apostolo"},
        "reference_displayed": "4,13-17",
        "title": "Prima lettura",
        "text": "Una cosa sola e necessaria.",
    },
    {
        "book_type": "psalm",
        "book": {"full_title": "Salmi"},
        "reference_displayed": "48",
        "title": "Salmo",
        "text": "Beati i poveri in spirito.",
        "chorus": "Beati i poveri in spirito.",
    },
    {
        "book_type": "gospel",
        "book": {"full_title": "Dal Vangelo secondo Marco"},
        "reference_displayed": "9,38-40",
        "title": "Vangelo",
        "text": "Chi non e contro di noi e per noi.",
    },
]


def _payload_for(date_str: str) -> dict:
    readings = [dict(r) for r in COMPLETE_READINGS]
    if date_str == "2099-12-30":
        readings = [r for r in readings if r["book_type"] != "gospel"]
    elif date_str == "2099-12-29":
        readings[0] = {**readings[0], "reference_displayed": {"bad": "shape"}}
    return {
        "data": {
            "liturgic_title": "Mercoledi della VII settimana del Tempo Ordinario",
            "readings": readings,
            "date_displayed": date_str,
            "commentary": {
                "description": "Fixture commentary",
                "source": "fixture",
                "author": {"name": "Fixture"},
            },
        }
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/health/"):
            self._json(200, {"status": "ok", "fixture": "evangelizo"})
            return
        match = re.match(r"^/([A-Za-z]+)/days/(\d{4}-\d{2}-\d{2})(?:\?.*)?$", self.path)
        if not match:
            self._json(404, {"error": "not found"})
            return
        date_str = match.group(2)
        if date_str == "2099-12-31":
            self._json(503, {"error": "fixture upstream failure"})
            return
        self._json(200, _payload_for(date_str))

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"fixture evangelizo listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
