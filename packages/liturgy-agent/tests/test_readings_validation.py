"""Reject incomplete Mass readings and gospel-only HTML fallback."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from liturgy_agent.agent import LiturgyAgent
from liturgy_agent.cache import LiturgyCache
from liturgy_agent.scrapers import (
    EvangelizeScraper,
    ScraperError,
    assert_complete_mass_reading,
)
from liturgy_agent.state import LiturgicalMetadata, LiturgicalReading, Reading


def _reading(ref: str = "Gn 1:1", text: str = "In the beginning", typ: str = "First") -> Reading:
    return Reading(reference=ref, text=text, type=typ)  # type: ignore[arg-type]


def _complete_mass(date: str = "2026-05-19", *, second: Reading | None = None) -> LiturgicalReading:
    return LiturgicalReading(
        date=date,
        occasion="mass",
        metadata=LiturgicalMetadata(
            date=date,
            occasion="mass",
            season="Ordinary",
            color="Green",
            year_cycle="A",
            sunday_or_weekday="Weekday",
        ),
        first_reading=_reading("Gc 4,13-17", "text1", "First"),
        psalm=_reading("Sal 48", "textps", "Psalm"),
        second_reading=second,
        gospel=_reading("Mc 9,38-40", "textg", "Gospel"),
        cached_at=datetime(2026, 5, 19, 10, 0, 0),
        source="evangelizo.ws",
    )


def test_assert_complete_mass_accepts_weekday_without_second() -> None:
    assert_complete_mass_reading(_complete_mass())


def test_assert_complete_mass_rejects_sunday_without_second() -> None:
    reading = _complete_mass("2026-10-11")
    reading.metadata.sunday_or_weekday = "Sunday"
    with pytest.raises(ScraperError, match="second_reading"):
        assert_complete_mass_reading(reading)


def test_assert_complete_mass_accepts_sunday_with_second() -> None:
    reading = _complete_mass("2026-10-11", second=_reading("2 Tm 2,8-13", "second", "Second"))
    reading.metadata.sunday_or_weekday = "Sunday"
    assert_complete_mass_reading(reading)


@pytest.mark.parametrize("occasion", ["marriage", "baptism", "funeral"])
def test_ritual_readings_on_sunday_do_not_require_second(occasion) -> None:
    reading = _complete_mass("2026-10-11")
    reading.occasion = occasion
    reading.metadata.occasion = occasion
    reading.metadata.sunday_or_weekday = "Sunday"
    assert_complete_mass_reading(reading)


def test_sunday_cache_without_second_is_invalidated(tmp_path) -> None:
    cache = LiturgyCache(db_path=str(tmp_path / "cache.db"))
    reading = _complete_mass("2026-10-11")
    reading.metadata.sunday_or_weekday = "Sunday"
    cache.conn.execute(
        """INSERT INTO liturgical_cache (date, occasion, data, expires_at)
        VALUES (?, ?, ?, datetime('now', '+1 day'))""",
        (reading.date, "mass", reading.model_dump_json()),
    )
    cache.conn.commit()
    assert cache.get(reading.date, "mass") is None
    assert cache.conn.execute("SELECT COUNT(*) FROM liturgical_cache").fetchone()[0] == 0
    cache.conn.close()


def test_assert_complete_mass_rejects_blank_required_text() -> None:
    reading = _complete_mass()
    reading.first_reading.text = "   "
    with pytest.raises(ScraperError, match="first_reading|required"):
        assert_complete_mass_reading(reading)


def test_assert_complete_mass_rejects_missing_gospel_reference() -> None:
    reading = _complete_mass()
    reading.gospel.reference = ""
    with pytest.raises(ScraperError, match="gospel|required"):
        assert_complete_mass_reading(reading)


def test_assert_complete_mass_rejects_present_incomplete_second() -> None:
    reading = _complete_mass(second=_reading("1 Cor 1,1", "  ", "Second"))
    with pytest.raises(ScraperError, match="second_reading"):
        assert_complete_mass_reading(reading)


@pytest.mark.asyncio
async def test_api_failure_does_not_use_html_fallback() -> None:
    scraper = EvangelizeScraper.__new__(EvangelizeScraper)
    scraper.TIMEOUT = 1
    scraper.MAX_RETRIES = 1
    scraper.RETRY_DELAY = 0
    scraper.BASE_URL = "https://example.test"
    scraper.LANG_CODE = "IT"

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))

    with patch("liturgy_agent.scrapers.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ScraperError, match="Failed to fetch|Unexpected error"):
            await scraper.fetch_daily_gospel(datetime(2026, 5, 19))
        # HTML fallback entrypoint must be gone from the complete-Mass path.
        assert not hasattr(EvangelizeScraper, "_fetch_daily_gospel_html")


def test_build_rejects_fallback_shaped_gospel_only(tmp_path) -> None:
    agent = LiturgyAgent(llm=MagicMock(), cache_db_path=str(tmp_path / "c.db"))
    scraped = {
        "date": "2026-05-19",
        "sources": {
            "evangelizo.ws": {
                "source": "vangelodelgiorno.org",
                "gospel_reference": "Mc 1,1",
                "gospel_text": "Only gospel",
                "gospel": {"reference": "Mc 1,1", "text": "Only gospel"},
            }
        },
    }
    with pytest.raises(ScraperError):
        agent._build_reading_from_scraped(scraped, datetime(2026, 5, 19))


def test_poisoned_cache_hit_is_discarded(tmp_path) -> None:
    db = str(tmp_path / "cache.db")
    cache = LiturgyCache(db_path=db)
    poisoned = _complete_mass()
    poisoned.first_reading.text = ""
    cache.conn.execute(
        """
        INSERT INTO liturgical_cache (date, occasion, data, cached_at, expires_at, source)
        VALUES (?, ?, ?, datetime('now'), datetime('now', '+1 day'), 'cache')
        """,
        ("2026-05-19", "mass", poisoned.model_dump_json()),
    )
    cache.conn.commit()

    assert cache.get("2026-05-19", "mass") is None
    # Poisoned row removed so a later fetch can store a clean value.
    row = cache.conn.execute(
        "SELECT COUNT(*) FROM liturgical_cache WHERE date=? AND occasion=?",
        ("2026-05-19", "mass"),
    ).fetchone()
    assert row[0] == 0


@pytest.mark.asyncio
async def test_upstream_failure_returns_controlled_error_without_cache_insert(
    tmp_path,
) -> None:
    db = str(tmp_path / "cache.db")
    agent = LiturgyAgent(llm=MagicMock(), cache_db_path=db)
    coro_fn = agent.get_daily_readings.coroutine

    with patch(
        "liturgy_agent.agent.fetch_liturgical_data",
        new=AsyncMock(side_effect=ScraperError("upstream down")),
    ):
        result = await coro_fn(agent, date="2026-05-19")

    assert result["status"] == "error"
    assert agent.cache.get("2026-05-19", "mass") is None
