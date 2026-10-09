"""Preserve selected readings and canonicalize liturgical occasions."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from copy import deepcopy

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
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
@pytest.mark.parametrize("recovery", ["complete", "matching", "absent", "mismatch"])
async def test_sunday_second_recovery_before_homily(monkeypatch, tool_name, recovery):
    payload = deepcopy(_weekday_complete())
    payload["date"] = payload["metadata"]["date"] = "2026-10-11"
    payload["metadata"]["sunday_or_weekday"] = "Sunday"
    if recovery in ("matching", "mismatch"):
        reference = "selected" if recovery == "mismatch" else "2 Tm 2,8-13"
        payload["second_reading"] = {"reference": reference, "text": "", "type": "Second"}
    fetched = deepcopy(payload)
    if recovery != "absent":
        fetched["second_reading"] = {"reference": "2 Tm 2,8-13", "text": "second", "type": "Second"}
    recovered = []
    dispatched = []

    async def fetch(occasion, date):
        recovered.append((occasion, date))
        return {"data": fetched}

    class Client:
        async def call_agent_method(self, **kwargs):
            dispatched.append(kwargs["params"]["liturgical_data"])
            return {"status": "success"}

    @asynccontextmanager
    async def client(**kwargs):
        yield Client()

    monkeypatch.setattr(tools, "request_liturgical_data", fetch)
    monkeypatch.setattr("a2a_protocol.a2a_client", client)
    if tool_name == "generation":
        result = await tools.request_homily_generation({"data": payload}, "mass")
    else:
        result = await tools.request_homily_refinement({"data": payload}, "mass", existing_draft="draft")
    assert recovered == [("mass", "2026-10-11")]
    if recovery in ("complete", "matching"):
        assert result["status"] == "success"
        assert dispatched[0]["second_reading"]["text"] == "second"
        assert dispatched[0]["gospel"] == payload["gospel"]
    else:
        assert "error" in result
        assert dispatched == []


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
@pytest.mark.parametrize("kind,date,recover", [
    ("Sunday", "2026-10-10", True),
    ("Sunday", "2026-10-10", False),
    ("Weekday", "2026-10-11", False),
])
async def test_partial_metadata_preserves_day_kind(monkeypatch, tool_name, kind, date, recover):
    payload = deepcopy(_weekday_complete())
    payload["date"] = date
    payload["metadata"] = {"sunday_or_weekday": kind}
    fetched = deepcopy(_weekday_complete())
    if recover:
        fetched["second_reading"] = {"reference": "2 Tm 2,8-13", "text": "second", "type": "Second"}
    recovered, dispatched = [], []

    async def fetch(*args):
        recovered.append(args)
        return {"data": fetched}

    class Client:
        async def call_agent_method(self, **kwargs):
            dispatched.append(kwargs["params"]["liturgical_data"])
            return {"status": "success"}

    @asynccontextmanager
    async def client(**kwargs):
        yield Client()

    monkeypatch.setattr(tools, "request_liturgical_data", fetch)
    monkeypatch.setattr("a2a_protocol.a2a_client", client)
    wrapper = getattr(tools, f"request_homily_{tool_name}")
    result = await wrapper({"data": payload}, "mass")
    assert bool(recovered) == (kind == "Sunday")
    if kind == "Sunday" and not recover:
        assert "error" in result
        assert dispatched == []
    else:
        assert result["status"] == "success"
        assert bool(dispatched[0].get("second_reading")) == recover
        assert "_sunday_or_weekday" not in dispatched[0]
    assert payload["metadata"] == {"sunday_or_weekday": kind}


@pytest.mark.asyncio
@pytest.mark.parametrize("occasion", ["mass", "marriage", "baptism", "funeral"])
async def test_sunday_date_fallback_only_requires_second_for_mass(monkeypatch, occasion):
    payload = _weekday_complete()
    payload["date"] = "2026-10-11"
    payload["occasion"] = occasion
    payload.pop("metadata")
    calls = []

    async def fetch(*args):
        calls.append(args)
        return {"data": payload}

    monkeypatch.setattr(tools, "request_liturgical_data", fetch)
    mapped = await tools._with_full_reading_texts(tools._map_liturgical_data(payload), occasion)
    assert bool(calls) == (occasion == "mass")
    assert tools._required_readings_complete(mapped, occasion) == (occasion != "mass")


@pytest.mark.parametrize("kind", [[], {}])
def test_invalid_partial_day_kind_falls_back_to_date(kind):
    payload = deepcopy(_weekday_complete())
    payload["date"] = "2026-10-11"
    payload["metadata"] = {"sunday_or_weekday": kind}
    mapped = tools._map_liturgical_data(payload)
    assert "metadata" not in mapped
    assert not tools._required_readings_complete(mapped, "mass")


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


def _incomplete_meta_marriage() -> dict:
    """Incomplete metadata that _normalize_metadata would drop, with conflicting occasion."""
    return {"occasion": "marriage"}


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
async def test_incomplete_metadata_occasion_conflict_rejects_before_homily(
    monkeypatch, wrapper, tool_name
):
    base = _weekday_complete()
    base["metadata"] = _incomplete_meta_marriage()
    payload = {"data": base} if wrapper == "wrapped" else base

    async def no_recovery(*args, **kwargs):
        raise AssertionError("must not recover before occasion rejection")

    monkeypatch.setattr(tools, "request_liturgical_data", no_recovery)

    def boom_client(**kwargs):
        raise AssertionError("homily agent must not be called")

    monkeypatch.setattr("a2a_protocol.a2a_client", boom_client)

    if tool_name == "generation":
        result = await tools.request_homily_generation(payload, "mass")
    else:
        result = await tools.request_homily_refinement(
            payload, "mass", existing_draft="draft"
        )
    assert "error" in result
    assert "conflict" in result["error"].lower() or "marriage" in result["error"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
async def test_unknown_nested_occasion_rejects_both_wrappers(monkeypatch, wrapper, tool_name):
    base = _weekday_complete()
    base["metadata"] = {"occasion": "vespers"}
    payload = {"data": base} if wrapper == "wrapped" else base
    monkeypatch.setattr("a2a_protocol.a2a_client", lambda **kwargs: (_ for _ in ()).throw(AssertionError()))

    if tool_name == "generation":
        result = await tools.request_homily_generation(payload, "mass")
    else:
        result = await tools.request_homily_refinement(
            payload, "mass", existing_draft="draft"
        )
    assert "error" in result
    assert "occasion" in result["error"].lower() or "unknown" in result["error"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
async def test_recovers_absent_required_first_reading(monkeypatch, wrapper):
    calls = []

    async def fake_request(occasion, date):
        calls.append((occasion, date))
        return {"data": _weekday_complete()}

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request)
    base = _weekday_complete()
    del base["first_reading"]
    payload = tools._map_liturgical_data({"data": base} if wrapper == "wrapped" else base)
    assert "first_reading" not in payload
    mapped = await tools._with_full_reading_texts(payload, "mass")
    assert calls, "expected a recovery refetch for absent required reading"
    assert mapped["first_reading"]["reference"] == "Gc 4,13-17"
    assert mapped["first_reading"]["text"] == "primo"
    assert mapped["gospel"]["text"] == "vangelo"
    assert "second_reading" not in mapped


@pytest.mark.asyncio
async def test_absent_optional_second_is_not_invented(monkeypatch):
    async def fake_request(occasion, date):
        complete = _weekday_complete()
        complete["second_reading"] = {
            "reference": "1 Cor 1,1",
            "text": "optional second",
            "type": "Second",
        }
        return {"data": complete}

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request)
    # Required texts already complete; optional second absent → no fetch, no invent.
    mapped = await tools._with_full_reading_texts(
        tools._map_liturgical_data(_weekday_complete()), "mass"
    )
    assert "second_reading" not in mapped


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
async def test_whitespace_reference_rejects_without_homily_call(
    monkeypatch, wrapper, tool_name
):
    base = _weekday_complete()
    base["gospel"] = {"reference": "   ", "text": "nonempty gospel text", "type": "Gospel"}
    payload = {"data": base} if wrapper == "wrapped" else base

    async def no_useful_recovery(occasion, date):
        return {"data": base}

    monkeypatch.setattr(tools, "request_liturgical_data", no_useful_recovery)

    def boom_client(**kwargs):
        raise AssertionError("homily agent must not be called on blank reference")

    monkeypatch.setattr("a2a_protocol.a2a_client", boom_client)

    if tool_name == "generation":
        result = await tools.request_homily_generation(payload, "mass")
    else:
        result = await tools.request_homily_refinement(
            payload, "mass", existing_draft="draft"
        )
    assert "error" in result


def test_required_readings_complete_requires_nonblank_string_refs():
    mapped = tools._map_liturgical_data(_weekday_complete())
    mapped["gospel"]["reference"] = "  "
    assert tools._required_readings_complete(mapped) is False
    mapped["gospel"]["reference"] = "Mc 9,38-40"
    mapped["gospel"]["text"] = "  "
    assert tools._required_readings_complete(mapped) is False
    mapped["gospel"]["text"] = "vangelo"
    assert tools._required_readings_complete(mapped) is True


def _payload_with_nested_marriage(wrapper: str, conflict_shape: str) -> dict:
    """Outer/method mass with an explicit nested marriage in the named shape."""
    base = _weekday_complete()
    if conflict_shape == "data_occasion":
        base["occasion"] = "marriage"
    elif conflict_shape == "readings_occasion":
        base = {
            "date": base["date"],
            "occasion": "mass",
            "metadata": base["metadata"],
            "readings": {
                "occasion": "marriage",
                "first_reading": base["first_reading"],
                "psalm": base["psalm"],
                "gospel": base["gospel"],
            },
        }
    else:
        base["metadata"] = {**VALID_METADATA, "occasion": "marriage"}

    if wrapper == "wrapped":
        # Outer occasion=mass must not first-wins-mask data.occasion=marriage.
        return {"occasion": "mass", "data": base}
    # Direct: method=mass; nested marriage lives on body/readings/metadata.
    if conflict_shape == "data_occasion":
        return base  # body occasion=marriage conflicts with method mass
    return base


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
@pytest.mark.parametrize(
    "conflict_shape",
    ["data_occasion", "readings_occasion", "metadata_occasion"],
)
async def test_all_explicit_occasions_validated_not_first_wins(
    monkeypatch, wrapper, tool_name, conflict_shape
):
    """Every explicit occasion across outer/data/readings/metadata must be checked."""
    payload = _payload_with_nested_marriage(wrapper, conflict_shape)

    async def no_recovery(*args, **kwargs):
        raise AssertionError("must not recover before occasion rejection")

    monkeypatch.setattr(tools, "request_liturgical_data", no_recovery)

    class _Boom:
        async def __aenter__(self):
            raise AssertionError("homily agent must not be called on occasion conflict")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("a2a_protocol.a2a_client", lambda **kwargs: _Boom())

    if tool_name == "generation":
        result = await tools.request_homily_generation(payload, "mass")
    else:
        result = await tools.request_homily_refinement(
            payload, "mass", existing_draft="draft"
        )
    assert "error" in result
    err = result["error"].lower()
    assert "conflict" in err or "marriage" in err or "occasion" in err


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
@pytest.mark.parametrize("tool_name", ["generation", "refinement"])
@pytest.mark.parametrize(
    "bad_gospel",
    [
        {"reference": "", "text": "nonempty", "type": "Gospel"},
        {"reference": {"bad": "shape"}, "text": "nonempty", "type": "Gospel"},
    ],
)
async def test_invalid_present_reading_ref_rejects_without_substitution(
    monkeypatch, wrapper, tool_name, bad_gospel
):
    """Present invalid refs must error — not drop-then-recover as absent."""
    fresh = _weekday_complete()
    recovery_calls = []

    async def fake_request(occasion, date):
        recovery_calls.append((occasion, date))
        return {"data": fresh}

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request)

    class _Boom:
        async def __aenter__(self):
            raise AssertionError("homily must not run on invalid-present reading")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("a2a_protocol.a2a_client", lambda **kwargs: _Boom())

    base = _weekday_complete()
    base["gospel"] = bad_gospel
    payload = {"data": base} if wrapper == "wrapped" else base

    if tool_name == "generation":
        result = await tools.request_homily_generation(payload, "mass")
    else:
        result = await tools.request_homily_refinement(
            payload, "mass", existing_draft="draft"
        )
    assert "error" in result
    # Must not silently adopt the fresh gospel via absent-key recovery.
    assert "Mc 9,38-40" not in str(result.get("data", ""))


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", ["direct", "wrapped"])
async def test_valid_bare_string_reference_recovers_text(monkeypatch, wrapper):
    async def fake_request(occasion, date):
        return {"data": _weekday_complete()}

    monkeypatch.setattr(tools, "request_liturgical_data", fake_request)
    base = _weekday_complete()
    base["gospel"] = "Mc 9,38-40"
    payload = tools._map_liturgical_data({"data": base} if wrapper == "wrapped" else base)
    assert payload["gospel"]["reference"] == "Mc 9,38-40"
    assert payload["gospel"]["text"] == ""
    mapped = await tools._with_full_reading_texts(payload, "mass")
    assert mapped["gospel"]["text"] == "vangelo"
    assert mapped["gospel"]["reference"] == "Mc 9,38-40"
