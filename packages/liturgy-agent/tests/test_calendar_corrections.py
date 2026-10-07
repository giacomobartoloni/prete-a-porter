"""Bounded Advent cycle and supported feast-color corrections."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from liturgy_agent.agent import LiturgyAgent


@pytest.fixture
def agent(tmp_path):
    return LiturgyAgent(MagicMock(), cache_db_path=str(tmp_path / "c.db"))


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2024-12-01", "C"),  # First Advent 2024 (Dec 1) starts C
        ("2025-11-29", "C"),  # day before Advent 2025 still C
        ("2025-11-30", "A"),  # First Advent 2025 starts A
        ("2025-12-01", "A"),
        ("2026-11-28", "A"),  # day before Advent 2026 still A
        ("2026-11-29", "B"),  # pinned: First Advent 2026 → B
        ("2026-12-01", "B"),
        ("2027-01-10", "B"),  # civil rollover still B until Advent 2027
        ("2027-11-27", "B"),  # day before Advent 2027
        ("2027-11-28", "C"),  # First Advent 2027 starts C
    ],
)
def test_liturgical_year_cycle_literal_cases(agent, iso, expected):
    d = date.fromisoformat(iso)
    assert agent.liturgical_year_cycle(d) == expected


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2024-12-01", date(2024, 12, 1)),
        ("2025-11-30", date(2025, 11, 30)),
        ("2026-11-29", date(2026, 11, 29)),
        ("2027-11-28", date(2027, 11, 28)),
    ],
)
def test_first_advent_sunday_nov_dec_range(agent, iso, expected):
    year = date.fromisoformat(iso).year
    assert agent.first_advent_sunday(year) == expected


def test_pentecost_title_uses_red(agent):
    assert agent.infer_liturgical_color("Easter", "Domenica di Pentecoste") == "Red"
    assert agent.infer_liturgical_color("Easter", "Pentecost Sunday") == "Red"


def test_ordinary_season_stays_green(agent):
    assert agent.infer_liturgical_color("Ordinary", "Mercoledì della VII settimana") == "Green"


def test_build_reading_applies_advent_cycle_and_pentecost_color(agent):
    scraped = {
        "date": "2026-11-29",
        "sources": {
            "evangelizo.ws": {
                "source": "evangelizo.ws",
                "liturgic_title": "I Domenica di Avvento",
                "first_reading": {"reference": "a", "text": "a"},
                "psalm": {"reference": "b", "text": "b"},
                "gospel": {"reference": "c", "text": "c"},
            }
        },
    }
    reading = agent._build_reading_from_scraped(scraped, datetime(2026, 11, 29))
    assert reading.metadata.year_cycle == "B"
    assert reading.metadata.season == "Advent"
    assert reading.metadata.color == "Purple"

    scraped["sources"]["evangelizo.ws"]["liturgic_title"] = "Domenica di Pentecoste"
    reading = agent._build_reading_from_scraped(scraped, datetime(2026, 5, 24))
    assert reading.metadata.color == "Red"
