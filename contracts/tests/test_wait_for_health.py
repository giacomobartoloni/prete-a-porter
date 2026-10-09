"""Readiness helper fails on exhaustion and HTTP errors."""

from __future__ import annotations

import importlib.util
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wait_for_health.py"
_SPEC = importlib.util.spec_from_file_location("wait_for_health", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
readiness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(readiness)


class _Handler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):  # noqa: N802
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):  # noqa: A003
        return


@pytest.fixture
def health_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}/health"
    server.shutdown()


def test_wait_for_health_succeeds(health_server):
    _Handler.status = 200
    readiness.wait_for(health_server, attempts=3, sleep_seconds=0.01)


def test_wait_for_health_fails_on_http_error(health_server):
    _Handler.status = 503
    with pytest.raises(SystemExit) as exc:
        readiness.wait_for(health_server, attempts=2, sleep_seconds=0.01)
    assert exc.value.code == 1


def test_wait_for_health_fails_when_unreachable():
    with pytest.raises(SystemExit) as exc:
        readiness.wait_for("http://127.0.0.1:1/health", attempts=2, sleep_seconds=0.01)
    assert exc.value.code == 1
