"""EVANGELIZO_BASE_URL seam for fixture-backed upstream HTTP."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liturgy_agent.scrapers import EvangelizeScraper, ScraperError, fetch_liturgical_data


def test_scraper_uses_evangelizo_base_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVANGELIZO_BASE_URL", "http://127.0.0.1:18080/")
    scraper = EvangelizeScraper()
    assert scraper.API_BASE_URL == "http://127.0.0.1:18080"


def test_scraper_default_api_base_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVANGELIZO_BASE_URL", raising=False)
    scraper = EvangelizeScraper()
    assert scraper.API_BASE_URL == "https://publication.evangelizo.ws"


@pytest.mark.asyncio
async def test_fetch_uses_configured_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVANGELIZO_BASE_URL", "http://fixture.test")
    seen: list[str] = []

    async def fake_get(url, **kwargs):
        seen.append(url)
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(
            return_value={
                "data": {
                    "liturgic_title": "Fixture title",
                    "readings": [
                        {
                            "book_type": "reading",
                            "book": {"full_title": "A"},
                            "reference_displayed": "1,1",
                            "text": "first",
                        },
                        {
                            "book_type": "psalm",
                            "book": {"full_title": "P"},
                            "reference_displayed": "1",
                            "text": "psalm",
                            "chorus": "c",
                        },
                        {
                            "book_type": "gospel",
                            "book": {"full_title": "G"},
                            "reference_displayed": "1,1",
                            "text": "gospel",
                        },
                    ],
                }
            }
        )
        return resp

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)

    with patch("liturgy_agent.scrapers.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_liturgical_data(datetime(2026, 5, 19))

    assert seen
    assert seen[0].startswith("http://fixture.test/IT/days/2026-05-19")
    assert "evangelizo.ws" in result["sources"]
