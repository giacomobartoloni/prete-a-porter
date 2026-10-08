"""Mandatory daily Mass contract checks against fixture-backed upstream.

These tests require a running liturgy agent whose EVANGELIZO_BASE_URL points at
contracts/scripts/fixture_evangelizo_server.py. They are not optional_live.
"""

from __future__ import annotations

import pytest

from test_liturgy_contract import (
    AGENT_URL,
    ReadingsResult,
    extract_reply,
    make_message_send,
    require_agent_available,
)


@pytest.fixture
def agent_available():
    try:
        import httpx

        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{AGENT_URL.rstrip('/')}/health")
            return response.status_code == 200
    except Exception:
        return False


@pytest.mark.asyncio
async def test_fixture_backed_get_readings_happy(agent_available):
    """Daily Mass happy path must succeed against deterministic fixtures."""
    require_agent_available(agent_available)

    data = await make_message_send(
        "liturgy_agent.get_readings",
        {"occasion": "mass", "date": "2026-05-19"},
    )
    reply = extract_reply(data)
    result = ReadingsResult(**reply)
    assert result.status == "success"
    assert result.data is not None
    assert result.data.get("first_reading", {}).get("text")
    assert result.data.get("psalm", {}).get("text")
    assert result.data.get("gospel", {}).get("text")
    # Weekday fixture has no second reading — optional must stay absent/empty-ok.
    second = result.data.get("second_reading")
    assert second is None or not (second.get("text") or "").strip() or (
        second.get("reference") and second.get("text")
    )


@pytest.mark.asyncio
async def test_fixture_backed_sunday_requires_complete_second(agent_available):
    require_agent_available(agent_available)
    data = await make_message_send(
        "liturgy_agent.get_readings", {"occasion": "mass", "date": "2026-10-11"}
    )
    result = ReadingsResult(**extract_reply(data))
    assert result.status == "success"
    assert result.data["second_reading"]["reference"]
    assert result.data["second_reading"]["text"]


@pytest.mark.asyncio
async def test_fixture_backed_get_readings_upstream_error(agent_available):
    """Fixture date 2099-12-31 forces upstream failure → controlled error status."""
    require_agent_available(agent_available)

    data = await make_message_send(
        "liturgy_agent.get_readings",
        {"occasion": "mass", "date": "2099-12-31"},
    )
    reply = extract_reply(data)
    result = ReadingsResult(**reply)
    assert result.status == "error"
    assert result.error or result.message


@pytest.mark.asyncio
async def test_fixture_backed_current_date_readings(agent_available):
    """Omitting date must resolve to today against the fixture upstream."""
    require_agent_available(agent_available)

    data = await make_message_send(
        "liturgy_agent.get_readings",
        {"occasion": "mass"},
    )
    reply = extract_reply(data)
    result = ReadingsResult(**reply)
    assert result.status == "success"
    assert result.data is not None
    assert result.data.get("gospel", {}).get("text")


@pytest.mark.asyncio
async def test_fixture_backed_malformed_reference_displayed(agent_available):
    """Fixture date 2099-12-29 forces object reference_displayed → controlled error."""
    require_agent_available(agent_available)

    data = await make_message_send(
        "liturgy_agent.get_readings",
        {"occasion": "mass", "date": "2099-12-29"},
    )
    reply = extract_reply(data)
    result = ReadingsResult(**reply)
    assert result.status == "error"
    assert result.error or result.message
