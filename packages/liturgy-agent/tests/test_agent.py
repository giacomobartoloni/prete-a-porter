"""Tests for liturgy_agent.agent module."""

from unittest.mock import AsyncMock, patch

import pytest

from liturgy_agent.state import LiturgyAgentState
from liturgy_agent.agent import agent_node


def _make_valid_data(**overrides) -> dict:
    """Build a dict parseable as LiturgicalReading."""
    data = {
        "date": "2026-05-19",
        "occasion": "mass",
        "metadata": {
            "date": "2026-05-19",
            "occasion": "mass",
            "season": "Ordinary",
            "color": "Green",
            "year_cycle": "A",
            "sunday_or_weekday": "Weekday",
        },
        "first_reading": {"reference": "Gn 1:1", "text": "In the beginning...", "type": "First"},
        "psalm": {"reference": "Ps 1:1", "text": "Blessed is the man...", "type": "Psalm"},
        "second_reading": {"reference": "1 Cor 1:1", "text": "Paul called...", "type": "Second"},
        "gospel": {"reference": "Jn 1:1", "text": "In the beginning was...", "type": "Gospel"},
        "alleluia_verse": {"reference": "Jn 1:14", "text": "And the Word became...", "type": "Alleluia"},
        "cached_at": "2026-05-19T10:00:00",
        "source": "test",
    }
    data.update(overrides)
    return data


@pytest.fixture
def mock_agent():
    with patch("liturgy_agent.agent.LiturgyAgent") as m:
        instance = m.return_value
        instance.get_daily_readings = AsyncMock(return_value={
            "status": "success",
            "data": _make_valid_data(),
        })
        instance.get_occasion_readings = AsyncMock(return_value={
            "status": "success",
            "data": _make_valid_data(occasion="marriage"),
        })
        instance.search_readings = AsyncMock(return_value={
            "status": "success",
            "data": [],
        })
        yield instance


class TestAgentNodeDispatch:
    """Verify agent_node dispatches to the correct tool."""

    @pytest.mark.asyncio
    async def test_daily_mass_calls_get_daily_readings_with_date(self, mock_agent):
        state = LiturgyAgentState(date="2026-05-19", occasion="mass")
        await agent_node(state, object())
        mock_agent.get_daily_readings.assert_awaited_once_with("2026-05-19")
        mock_agent.get_occasion_readings.assert_not_awaited()
        mock_agent.search_readings.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_marriage_calls_get_occasion_readings(self, mock_agent):
        state = LiturgyAgentState(date="2026-03-15", occasion="marriage")
        await agent_node(state, object())
        mock_agent.get_occasion_readings.assert_awaited_once_with("marriage")
        mock_agent.get_daily_readings.assert_not_awaited()
        mock_agent.search_readings.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_baptism_calls_get_occasion_readings(self, mock_agent):
        state = LiturgyAgentState(date="2026-06-01", occasion="baptism")
        await agent_node(state, object())
        mock_agent.get_occasion_readings.assert_awaited_once_with("baptism")
        mock_agent.get_daily_readings.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_funeral_calls_get_occasion_readings(self, mock_agent):
        state = LiturgyAgentState(date="2026-07-10", occasion="funeral")
        await agent_node(state, object())
        mock_agent.get_occasion_readings.assert_awaited_once_with("funeral")
        mock_agent.get_daily_readings.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_daily_mass_without_date_defaults_to_empty(self, mock_agent):
        state = LiturgyAgentState(date="", occasion="mass")
        await agent_node(state, object())
        mock_agent.get_daily_readings.assert_awaited_once_with("")


class TestAgentNodeErrorHandling:
    """Verify agent_node propagates errors correctly."""

    @pytest.mark.asyncio
    async def test_propagates_error_from_tool(self, mock_agent):
        mock_agent.get_daily_readings.return_value = {
            "status": "error",
            "error": "Could not fetch readings",
        }
        state = LiturgyAgentState(date="2026-05-19", occasion="mass")
        result = await agent_node(state, object())
        assert result.error == "Could not fetch readings"
