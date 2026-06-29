"""Integration tests for liturgy-agent scraping pipeline.

Tests the fetch_lithurgical_data and _build_reading_from_scraped
functions that were impacted by the VaticanScraper removal.
"""

import inspect
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liturgy_agent.agent import LiturgyAgent
from liturgy_agent.cache import LiturgyCache
from liturgy_agent.scrapers import (
    ScraperError,
    fetch_liturgical_data,
)
from liturgy_agent.state import LiturgicalReading

# ---------------------------------------------------------------------------
# fetch_liturgical_data signature
# ---------------------------------------------------------------------------


class TestFetchLiturgicalDataSignature:
    """Verify include_vatican param is gone and defaults are correct."""

    def test_include_vatican_no_longer_accepted(self):
        sig = inspect.signature(fetch_liturgical_data)
        assert "include_vatican" not in sig.parameters

    def test_include_evangelizo_defaults_to_true(self):
        sig = inspect.signature(fetch_liturgical_data)
        assert sig.parameters["include_evangelizo"].default is True

    def test_date_defaults_to_none(self):
        sig = inspect.signature(fetch_liturgical_data)
        assert sig.parameters["date"].default is None


# ---------------------------------------------------------------------------
# fetch_liturgical_data behaviour with mocked HTTP
# ---------------------------------------------------------------------------


def _mock_evangelizo_response(date_str: str) -> dict:
    """Build a realistic payload as returned by publication.evangelizo.ws."""
    return {
        "data": {
            "liturgic_title": "Mercoledì della VII settimana del Tempo Ordinario",
            "readings": [
                {
                    "book_type": "reading",
                    "book": {"full_title": "Lettera di san Giacomo apostolo"},
                    "reference_displayed": "4,13-17",
                    "title": "Lettera di san Giacomo apostolo",
                    "text": "«Una cosa sola è necessaria»",
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
                    "text": "Chi non è contro di noi è per noi.",
                },
            ],
            "date_displayed": "Mercoledì 19 maggio 2026",
            "commentary": {
                "description": "Il testo evangelico ci invita a riflettere...",
                "source": "evangelizo.ws",
                "author": {"name": "Commentatore"},
            },
        }
    }


def _make_async_mock_response(payload: dict, status: int = 200):
    """Return a mock that simulates httpx.AsyncClient.get()."""
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=payload)
    resp.raise_for_status = MagicMock()
    return resp


class TestFetchLiturgicalData:
    """Test fetch_liturgical_data with mocked HTTP layer."""

    @pytest.mark.asyncio
    async def test_returns_evangelizo_source_when_http_succeeds(self):
        date = datetime(2026, 5, 19)
        payload = _mock_evangelizo_response("2026-05-19")

        async def fake_get(url, **kw):
            return _make_async_mock_response(payload)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.get = AsyncMock(side_effect=fake_get)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await fetch_liturgical_data(date)

        assert "sources" in result
        assert "evangelizo.ws" in result["sources"]
        assert result["date"] == "2026-05-19"

    @pytest.mark.asyncio
    async def test_returns_defaults_date_when_not_provided(self):
        payload = _mock_evangelizo_response("2026-05-19")

        async def fake_get(url, **kw):
            return _make_async_mock_response(payload)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.get = AsyncMock(side_effect=fake_get)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await fetch_liturgical_data()

        assert "sources" in result
        assert "evangelizo.ws" in result["sources"]

    @pytest.mark.asyncio
    async def test_raises_when_evangelizo_unavailable(self):
        date = datetime(2026, 5, 19)

        with patch(
            "liturgy_agent.scrapers.EvangelizeScraper",
            side_effect=ScraperError("httpx not available"),
        ):
            with pytest.raises(ScraperError, match="No scrapers available"):
                await fetch_liturgical_data(date)

    @pytest.mark.asyncio
    async def test_skips_evangelizo_when_flag_false(self):
        date = datetime(2026, 5, 19)

        with pytest.raises(ScraperError, match="No scrapers available"):
            await fetch_liturgical_data(date, include_evangelizo=False)


# ---------------------------------------------------------------------------
# _build_reading_from_scraped
# ---------------------------------------------------------------------------


class TestBuildReadingFromScraped:
    """Verify _build_reading_from_scraped produces valid LiturgicalReading."""

    def _make_scraped_data(self, date_str: str = "2026-05-19") -> dict:
        return {
            "date": date_str,
            "sources": {
                "evangelizo.ws": {
                    "source": "evangelizo.ws",
                    "date": date_str,
                    "liturgic_title": "Mercoledì della VII settimana del Tempo Ordinario",
                    "first_reading": {
                        "reference": "Gc 4,13-17",
                        "text": "«Una cosa sola è necessaria»",
                    },
                    "psalm": {
                        "reference": "Sal 48",
                        "text": "Beati i poveri in spirito.",
                        "chorus": "Beati i poveri in spirito.",
                    },
                    "gospel": {
                        "reference": "Mc 9,38-40",
                        "text": "Chi non è contro di noi è per noi.",
                    },
                }
            },
        }

    @pytest.fixture
    def agent(self):
        with patch.object(LiturgyCache, "__init__", return_value=None):
            a = LiturgyAgent(llm=MagicMock())
            a.cache = MagicMock()
            return a

    def test_builds_reading_from_evangelizo_source(self, agent):
        scraped = self._make_scraped_data()
        date = datetime(2026, 5, 19)

        result = agent._build_reading_from_scraped(scraped, date)

        assert isinstance(result, LiturgicalReading)
        assert result.date == "2026-05-19"
        assert result.occasion == "mass"
        assert result.source == "evangelizo.ws"

        assert result.first_reading.reference == "Gc 4,13-17"
        assert result.psalm.reference == "Sal 48"
        assert result.gospel.reference == "Mc 9,38-40"

        assert result.metadata.date == "2026-05-19"
        assert result.metadata.season == "Ordinary"
        assert result.metadata.color == "Green"
        assert result.metadata.year_cycle in ("A", "B", "C")

    def test_builds_reading_with_second_reading(self, agent):
        scraped = self._make_scraped_data()
        scraped["sources"]["evangelizo.ws"]["second_reading"] = {
            "reference": "1 Cor 1,1-3",
            "text": "Paolo chiamato apostolo...",
        }
        date = datetime(2026, 5, 19)

        result = agent._build_reading_from_scraped(scraped, date)

        assert isinstance(result, LiturgicalReading)
        assert result.second_reading is not None
        assert result.second_reading.reference == "1 Cor 1,1-3"
        assert result.second_reading.type == "Second"

    def test_builds_reading_without_second_reading(self, agent):
        scraped = self._make_scraped_data()
        date = datetime(2026, 5, 19)

        result = agent._build_reading_from_scraped(scraped, date)

        assert result.second_reading is None

    def test_alleluia_verse_is_always_none(self, agent):
        scraped = self._make_scraped_data()
        date = datetime(2026, 5, 19)

        result = agent._build_reading_from_scraped(scraped, date)

        assert result.alleluia_verse is None

    def test_reading_types_are_correct(self, agent):
        scraped = self._make_scraped_data()
        date = datetime(2026, 5, 19)

        result = agent._build_reading_from_scraped(scraped, date)

        assert result.first_reading.type == "First"
        assert result.psalm.type == "Psalm"
        assert result.gospel.type == "Gospel"

    def test_sunday_sets_metadata_correctly(self, agent):
        # 2026-05-24 is a Sunday
        scraped = self._make_scraped_data("2026-05-24")
        date = datetime(2026, 5, 24)

        result = agent._build_reading_from_scraped(scraped, date)

        assert result.metadata.sunday_or_weekday == "Sunday"
        assert result.metadata.date == "2026-05-24"
