"""Preserve selected readings and canonicalize liturgical occasions."""

from __future__ import annotations

import logging

import pytest

from chat_orchestrator import tools


VALID_METADATA = {
    "date": "2026-05-19",
    "occasion": "mass",
    "season": "Ordinary",
    "color": "Green",
    "year_cycle": "A",
    "sunday_or_weekday": "Weekday",
}


def _weekday_complete() -> dict:
    return {
        "date": "2026-05-19",
        "occasion": "mass",
        "metadata": VALID_METADATA,
        "first_reading": {"reference": "Gc 4,13-17", "text": "primo", "type": "First"},
        "psalm": {"reference": "Sal 48", "text": "salmo", "type": "Psalm"},
        "gospel": {"reference": "Mc 9,38-40", "text": "vangelo", "type": "Gospel"},
    }


@pytest.mark.asyncio
async def test_weekday_without_second_reading_does_not_fetch_or_invent_one(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("must not re-fetch when required texts are complete")

    monkeypatch.setattr(tools, "request_liturgical_data", fail_if_called)
    mapped = await tools._with_full_reading_texts(
        tools._map_liturgical_data(_weekday_complete()), "mass"
    )
    assert "second_reading" not in mapped


@pytest.mark.asyncio
async def test_preserves_complete_first_and_gospel_when_psalm_text_missing(monkeypatch):
    async def fake_request(occasion, date):
        return {
            "data": {
                **_weekday_complete(),
                "first_reading": {
                    "reference": "DIFFERENT 1,1",
                    "text": "wrong first",
                    "type": "First",
                },
                "psalm": {"reference": "Sal 48", "text": "salmo recovered", "type": "Psalm"},
                "gospel": {
                    "reference": "OTHER 2,2",
                    "text": "wrong gospel",
                    "type": "Gospel",
                },
            }
        }

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request)
    payload = _weekday_complete()
    payload["psalm"] = {"reference": "Sal 48", "text": "", "type": "Psalm"}
    mapped = await tools._with_full_reading_texts(tools._map_liturgical_data(payload), "mass")
    assert mapped["first_reading"]["text"] == "primo"
    assert mapped["first_reading"]["reference"] == "Gc 4,13-17"
    assert mapped["gospel"]["text"] == "vangelo"
    assert mapped["psalm"]["text"] == "salmo recovered"


@pytest.mark.asyncio
async def test_refuses_to_substitute_different_fetched_reference(monkeypatch):
    async def fake_request(occasion, date):
        return {
            "data": {
                **_weekday_complete(),
                "gospel": {
                    "reference": "Lc 1,1",
                    "text": "different gospel text",
                    "type": "Gospel",
                },
            }
        }

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request)
    payload = _weekday_complete()
    payload["gospel"] = {"reference": "Mc 9,38-40", "text": "", "type": "Gospel"}
    mapped = await tools._with_full_reading_texts(tools._map_liturgical_data(payload), "mass")
    assert mapped["gospel"]["reference"] == "Mc 9,38-40"
    assert mapped["gospel"]["text"] == ""


@pytest.mark.asyncio
async def test_unavailable_recovery_leaves_incomplete_required_text(monkeypatch):
    async def boom(occasion, date):
        raise RuntimeError("liturgy down")

    monkeypatch.setattr(tools, "request_liturgical_data", boom)
    payload = _weekday_complete()
    payload["gospel"] = {"reference": "Mc 9,38-40", "text": "", "type": "Gospel"}
    mapped = await tools._with_full_reading_texts(tools._map_liturgical_data(payload), "mass")
    assert mapped["gospel"]["text"] == ""


@pytest.mark.parametrize(
    "alias",
    ["sunday", "weekday", "daily", "Sunday", "WEEKDAY"],
)
def test_occasion_aliases_normalize_to_mass(alias):
    assert tools.canonicalize_occasion(alias) == "mass"


def test_unknown_occasion_is_rejected():
    with pytest.raises(ValueError, match="unknown|occasion"):
        tools.canonicalize_occasion("vespers")


def test_mass_versus_marriage_conflict_is_rejected():
    with pytest.raises(ValueError, match="conflict"):
        tools.resolve_request_occasion(
            method_occasion="mass",
            payload_occasion="marriage",
            metadata_occasion=None,
        )


def test_missing_payload_occasion_inherits_request():
    assert (
        tools.resolve_request_occasion(
            method_occasion="sunday",
            payload_occasion=None,
            metadata_occasion=None,
        )
        == "mass"
    )


@pytest.mark.asyncio
async def test_generation_rejects_unresolved_required_text(monkeypatch):
    payload = _weekday_complete()
    payload["gospel"] = {"reference": "Mc 9,38-40", "text": "", "type": "Gospel"}

    async def no_recovery(occasion, date):
        return {"data": payload}

    monkeypatch.setattr(tools, "request_liturgical_data", no_recovery)

    def boom_client(**kwargs):
        raise AssertionError("homily agent must not be called")

    monkeypatch.setattr("a2a_protocol.a2a_client", boom_client)
    result = await tools.request_homily_generation(payload, "mass")
    assert "error" in result


@pytest.mark.asyncio
async def test_generation_logger_error_branch_does_not_typeerror(monkeypatch, caplog):
    """Ordinary logger.error must not receive unsupported mapped= kwargs."""

    async def no_recovery(occasion, date):
        return {"data": {"date": "2026-05-19", "occasion": "mass"}}

    monkeypatch.setattr(tools, "request_liturgical_data", no_recovery)

    payload = {
        "date": "2026-05-19",
        "occasion": "mass",
        "gospel": {"reference": "Mc 9,38-40", "text": "only gospel", "type": "Gospel"},
    }
    with caplog.at_level(logging.ERROR):
        result = await tools.request_homily_generation(payload, "mass")
    assert "error" in result
