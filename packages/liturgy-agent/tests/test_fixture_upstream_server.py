"""In-process fixture Evangelizo server drives fetch_liturgical_data happy/error."""

from __future__ import annotations

import importlib.util
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from liturgy_agent.scrapers import EvangelizeScraper, ScraperError, fetch_liturgical_data


def _load_fixture_module():
    path = (
        Path(__file__).resolve().parents[3]
        / "contracts"
        / "scripts"
        / "fixture_evangelizo_server.py"
    )
    spec = importlib.util.spec_from_file_location("fixture_evangelizo_server", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fixture_base_url(monkeypatch: pytest.MonkeyPatch):
    mod = _load_fixture_module()
    server = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("EVANGELIZO_BASE_URL", base)
    monkeypatch.setattr(EvangelizeScraper, "MAX_RETRIES", 1)
    monkeypatch.setattr(EvangelizeScraper, "RETRY_DELAY", 0)
    time.sleep(0.05)
    yield base
    server.shutdown()


@pytest.mark.asyncio
async def test_fixture_server_happy_path(fixture_base_url):
    result = await fetch_liturgical_data(datetime(2026, 5, 19))
    source = result["sources"]["evangelizo.ws"]
    assert source["first_reading"]["text"]
    assert source["gospel"]["text"]
    assert "second_reading" not in source


@pytest.mark.asyncio
async def test_fixture_server_error_date(fixture_base_url):
    with pytest.raises(ScraperError):
        await fetch_liturgical_data(datetime(2099, 12, 31))
