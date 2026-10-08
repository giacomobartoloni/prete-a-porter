"""Malformed upstream shapes must become controlled ScraperError (no AttributeError)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liturgy_agent.agent import LiturgyAgent
from liturgy_agent.main import LiturgyAgentHandler
from liturgy_agent.scrapers import EvangelizeScraper, ScraperError, fetch_liturgical_data


def _complete_readings() -> list[dict]:
    return [
        {
            "book_type": "reading",
            "book": {"full_title": "Lettera di san Giacomo apostolo"},
            "reference_displayed": "4,13-17",
            "text": "Una cosa sola e necessaria",
        },
        {
            "book_type": "psalm",
            "book": {"full_title": "Salmi"},
            "reference_displayed": "48",
            "text": "Beati i poveri in spirito.",
            "chorus": "Beati",
        },
        {
            "book_type": "gospel",
            "book": {"full_title": "Dal Vangelo secondo Marco"},
            "reference_displayed": "9,38-40",
            "text": "Chi non e contro di noi e per noi.",
        },
    ]


def _payload(**data_overrides) -> dict:
    data = {
        "liturgic_title": "Mercoledi della VII settimana del Tempo Ordinario",
        "readings": _complete_readings(),
        "date_displayed": "Mercoledi 19 maggio 2026",
        "commentary": {
            "description": "Commento",
            "source": "evangelizo.ws",
            "author": {"name": "Autore"},
        },
    }
    data.update(data_overrides)
    return {"data": data}


def _scraper() -> EvangelizeScraper:
    scraper = EvangelizeScraper.__new__(EvangelizeScraper)
    scraper.TIMEOUT = 1
    scraper.MAX_RETRIES = 1
    scraper.RETRY_DELAY = 0
    scraper.API_BASE_URL = "https://example.test"
    scraper.LANG_CODE = "IT"
    return scraper


def _malformed_scraped() -> dict:
    return {
        "date": "2026-05-19",
        "sources": {
            "evangelizo.ws": {
                "source": "evangelizo.ws",
                "liturgic_title": 7,
                "first_reading": {"reference": "Gc 4,13-17", "text": "a"},
                "psalm": {"reference": "Sal 48", "text": "b"},
                "gospel": {"reference": "Mc 9,38-40", "text": "c"},
            }
        },
    }


@pytest.mark.parametrize(
    "payload,match",
    [
        (None, "payload|schema|shape"),
        ("not-a-dict", "payload|schema|shape"),
        ({"data": "x"}, "data|schema|shape"),
        ({"data": {"liturgic_title": "t", "readings": "x"}}, "readings|schema|shape"),
        (
            {
                "data": {
                    "liturgic_title": "t",
                    "readings": [
                        {
                            "book_type": "gospel",
                            "book": "not-a-dict",
                            "reference_displayed": "1,1",
                            "text": "g",
                        },
                        {
                            "book_type": "reading",
                            "book": {"full_title": "A"},
                            "reference_displayed": "1,1",
                            "text": "a",
                        },
                        {
                            "book_type": "psalm",
                            "book": {"full_title": "P"},
                            "reference_displayed": "1",
                            "text": "p",
                        },
                    ],
                }
            },
            "book|schema|shape",
        ),
        (
            {
                "data": {
                    "liturgic_title": "t",
                    "readings": _complete_readings(),
                    "commentary": "not-a-dict",
                }
            },
            "commentary|schema|shape",
        ),
        (_payload(liturgic_title=7), "liturgic_title|schema|shape|metadata"),
    ],
)
def test_parse_rejects_malformed_shapes_with_scraper_error(payload, match) -> None:
    scraper = _scraper()
    with pytest.raises(ScraperError, match=match):
        scraper._parse_daily_gospel_api(payload, "2026-05-19")


def test_build_rejects_numeric_liturgic_title(tmp_path) -> None:
    agent = LiturgyAgent(llm=MagicMock(), cache_db_path=str(tmp_path / "c.db"))
    with pytest.raises(ScraperError, match="liturgic_title|schema|shape|metadata"):
        agent._build_reading_from_scraped(_malformed_scraped(), datetime(2026, 5, 19))


@pytest.mark.asyncio
async def test_all_failed_scrapers_raise_empty_source_error() -> None:
    date = datetime(2026, 5, 19)

    with patch.object(
        EvangelizeScraper,
        "fetch_daily_gospel",
        new=AsyncMock(side_effect=ScraperError("upstream down")),
    ):
        with pytest.raises(ScraperError, match="No liturgical data|empty|source"):
            await fetch_liturgical_data(date)


@pytest.mark.asyncio
async def test_daily_tool_malformed_title_returns_controlled_error(tmp_path) -> None:
    db = str(tmp_path / "cache.db")
    agent = LiturgyAgent(llm=MagicMock(), cache_db_path=db)
    coro = agent.get_daily_readings.coroutine
    with patch(
        "liturgy_agent.agent.fetch_liturgical_data",
        new=AsyncMock(return_value=_malformed_scraped()),
    ):
        result = await coro(agent, date="2026-05-19")
    assert result["status"] == "error"
    assert "AttributeError" not in str(result.get("error", ""))
    assert agent.cache.get("2026-05-19", "mass") is None


@pytest.mark.asyncio
async def test_handler_malformed_upstream_returns_error_without_cache(tmp_path) -> None:
    db = str(tmp_path / "cache.db")
    agent = LiturgyAgent(llm=MagicMock(), cache_db_path=db)
    handler = LiturgyAgentHandler.__new__(LiturgyAgentHandler)
    handler.llm = MagicMock()
    handler.graph = MagicMock()

    with patch("liturgy_agent.agent.LiturgyAgent", return_value=agent):
        import liturgy_agent.scrapers as scrapers_mod

        with patch.object(
            scrapers_mod,
            "fetch_liturgical_data",
            new=AsyncMock(return_value=_malformed_scraped()),
        ):
            result = await handler._handle_get_readings(
                {"occasion": "mass", "date": "2026-05-19"}
            )

    assert result["status"] == "error"
    assert agent.cache.get("2026-05-19", "mass") is None
