"""Precise authoring constraints cross the existing A2A boundary unchanged."""

from contextlib import asynccontextmanager

import pytest

from chat_orchestrator import tools


@pytest.mark.asyncio
async def test_word_count_and_revision_constraints_reach_specialist_without_retries(monkeypatch):
    import a2a_protocol

    observed = {}

    class Client:
        async def call_agent_method(self, method, params, timeout):
            observed.update(method=method, params=params, timeout=timeout)
            return {"status": "success", "data": {"homily": "specialist output"}}

    @asynccontextmanager
    async def client(**config):
        observed["config"] = config
        yield Client()

    monkeypatch.setattr(a2a_protocol, "a2a_client", client)

    async def full(mapped, occasion):
        return mapped

    monkeypatch.setattr(tools, "_with_full_reading_texts", full)
    data = {
        "date": "2026-11-01",
        "occasion": "mass",
        "metadata": {"sunday_or_weekday": "Weekday"},
        "first_reading": {"reference": "Ap 7", "text": "prima"},
        "psalm": {"reference": "Sal 23", "text": "salmo"},
        "gospel": {"reference": "Mt 5", "text": "beati gli operatori di pace"},
    }
    prefs = {"target_word_count": 200, "instructions": "Riscrivi con una lite tra fratelli", "target_audience": "youth"}
    result = await tools.request_homily_refinement(data, "mass", prefs, "Bozza integrale")
    assert result["status"] == "success"
    assert observed["params"]["preferences"] == prefs
    assert observed["params"]["existing_draft"] == "Bozza integrale"
    assert observed["config"]["retries"] == 1
    assert observed["timeout"] == 110


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_data", [None, "[]", "null", "not-json", {"date": "2025-11-01"}])
async def test_refinement_keeps_authoritative_date_even_if_model_changes_year(monkeypatch, invalid_data):
    import json

    from langchain_core.messages import AIMessage

    from chat_orchestrator import graph

    observed = []

    class Tool:
        async def ainvoke(self, args):
            observed.append(args)
            return {"status": "success"}

    monkeypatch.setitem(graph.TOOLS_REGISTRY, "refine_homily", Tool())
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "refine",
                        "name": "refine_homily",
                        "args": {
                            "liturgical_data": json.dumps({"date": "2025-11-01", "gospel": {"text": "wrong year"}}),
                            "occasion": "mass",
                            "existing_draft": "original",
                        },
                    }
                ],
            )
        ],
        "liturgical_context": {"date": "2026-11-01", "occasion": "mass"},
    }
    if invalid_data is not None:
        state["messages"][0].tool_calls[0]["args"]["liturgical_data"] = invalid_data
    await graph.tools_node(state)
    data = json.loads(observed[0]["liturgical_data"])
    assert data == {"date": "2026-11-01", "occasion": "mass"}
    assert observed[0]["existing_draft"] == "original"


@pytest.mark.asyncio
async def test_new_generation_updates_context_before_refinement_in_same_turn(monkeypatch):
    import json

    from langchain_core.messages import AIMessage

    from chat_orchestrator import graph

    seen = []

    class Generation:
        async def ainvoke(self, args):
            return {"status": "success", "data": {"homily": {"liturgical_date": "2026-12-25", "occasion": "mass"}}}

    class Refinement:
        async def ainvoke(self, args):
            seen.append(args)
            return {"status": "success"}

    monkeypatch.setitem(graph.TOOLS_REGISTRY, "generate_homily", Generation())
    monkeypatch.setitem(graph.TOOLS_REGISTRY, "refine_homily", Refinement())
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "new", "name": "generate_homily", "args": {}},
                    {
                        "id": "edit",
                        "name": "refine_homily",
                        "args": {"liturgical_data": json.dumps({"date": "2026-11-01"}), "occasion": "mass"},
                    },
                ],
            )
        ],
        "liturgical_context": {"date": "2026-11-01", "occasion": "mass"},
    }
    result = await graph.tools_node(state)
    assert json.loads(seen[0]["liturgical_data"])["date"] == "2026-12-25"
    assert result["liturgical_context"]["date"] == "2026-12-25"


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"date": "bad", "occasion": "mass"},
        {"date": None, "occasion": "mass"},
        [],
        {"date": "2026-11-01", "occasion": "invalid"},
        {"date": "2026-11-01", "occasion": []},
        {"date": "2026-11-01", "occasion": {}},
    ],
)
def test_invalid_adapter_context_is_ignored(value):
    from chat_orchestrator.context import parse_liturgical_context

    assert parse_liturgical_context(value) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes,ui,expected",
    [
        (None, {}, "youth"),
        ('{"target_audience":"adults"}', {}, "adults"),
        (None, {"target_audience": "adults"}, "adults"),
    ],
)
async def test_refinement_inherits_audience_unless_explicitly_changed(monkeypatch, changes, ui, expected):
    from langchain_core.messages import AIMessage

    from chat_orchestrator import graph, tools

    observed = []

    async def refine(data, occasion, preferences, existing_draft):
        observed.append(preferences)
        return {"status": "success", "data": {"homily": {"liturgical_date": "2026-11-01", "occasion": "mass"}}}

    monkeypatch.setattr(tools, "request_homily_refinement", refine)
    args = {
        "liturgical_data": "{}",
        "occasion": "mass",
        "preferences": '{"target_audience":"adults","target_word_count":200}',
        "existing_draft": "draft",
    }
    if changes:
        args["preference_changes"] = changes
    state = {
        "messages": [AIMessage(content="", tool_calls=[{"id": "edit", "name": "refine_homily", "args": args}])],
        "liturgical_context": {
            "date": "2026-11-01",
            "occasion": "mass",
            "preferences": {"target_audience": "youth", "tone": "formal"},
        },
        "preference_overrides": ui,
    }
    result = await graph.tools_node(state)
    assert observed[0]["target_audience"] == expected
    assert observed[0]["target_word_count"] == 200
    assert observed[0]["tone"] == "formal"
    assert result["liturgical_context"]["preferences"]["target_audience"] == expected


def test_context_keeps_valid_stable_preferences_only():
    from chat_orchestrator.context import parse_liturgical_context

    context = parse_liturgical_context(
        {
            "date": "2026-11-01",
            "occasion": "mass",
            "preferences": {
                "target_audience": "youth",
                "tone": "formal",
                "instructions": "old school",
                "target_word_count": 500,
            },
        }
    )
    assert context["preferences"] == {"target_audience": "youth", "tone": "formal"}


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["not json", "{'target_word_count': 200}"])
async def test_recoverable_preference_strings_cannot_bypass_profile_pin(monkeypatch, raw):
    from langchain_core.messages import AIMessage

    from chat_orchestrator import graph, tools

    seen = []

    async def refine(data, occasion, preferences, existing_draft):
        seen.append(preferences)
        return {"status": "success"}

    monkeypatch.setattr(tools, "request_homily_refinement", refine)
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "edit",
                        "name": "refine_homily",
                        "args": {
                            "liturgical_data": "{}",
                            "occasion": "mass",
                            "existing_draft": "draft",
                            "preferences": raw,
                        },
                    }
                ],
            )
        ],
        "liturgical_context": {"date": "2026-11-01", "occasion": "mass", "preferences": {"target_audience": "youth"}},
    }
    await graph.tools_node(state)
    assert seen[0]["target_audience"] == "youth"
    if raw.startswith("{"):
        assert seen[0]["target_word_count"] == 200


@pytest.mark.asyncio
async def test_explicit_change_removes_obsolete_ui_override_in_same_turn(monkeypatch):
    import json

    from langchain_core.messages import AIMessage

    from chat_orchestrator import graph, tools

    seen = []

    async def refine(data, occasion, preferences, existing_draft):
        seen.append(preferences["target_audience"])
        return {"status": "success", "data": {"homily": {"liturgical_date": "2026-11-01", "occasion": "mass"}}}

    monkeypatch.setattr(tools, "request_homily_refinement", refine)
    calls = [
        {
            "id": str(i),
            "name": "refine_homily",
            "args": {
                "liturgical_data": "{}",
                "occasion": "mass",
                "existing_draft": "draft",
                "preferences": json.dumps({"target_audience": "youth", "target_word_count": 200}),
                **({"preference_changes": '{"target_audience":"adults"}'} if i == 0 else {}),
            },
        }
        for i in range(2)
    ]
    state = {
        "messages": [AIMessage(content="", tool_calls=calls)],
        "liturgical_context": {"date": "2026-11-01", "occasion": "mass", "preferences": {"target_audience": "youth"}},
        "preference_overrides": {"target_audience": "youth"},
    }
    result = await graph.tools_node(state)
    assert seen == ["adults", "adults"]
    assert result["preference_overrides"] == {}


@pytest.mark.asyncio
async def test_failed_refinement_never_changes_profile_or_ui_overrides(monkeypatch):
    from langchain_core.messages import AIMessage

    from chat_orchestrator import graph, tools

    async def fail(*args):
        return {"error": "Model unavailable"}

    monkeypatch.setattr(tools, "request_homily_refinement", fail)
    context = {"date": "2026-11-01", "occasion": "mass", "preferences": {"target_audience": "youth"}}
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "edit",
                        "name": "refine_homily",
                        "args": {
                            "liturgical_data": "{}",
                            "occasion": "mass",
                            "existing_draft": "draft",
                            "preference_changes": '{"target_audience":"adults"}',
                        },
                    }
                ],
            )
        ],
        "liturgical_context": context,
        "preference_overrides": {"target_audience": "youth"},
    }
    result = await graph.tools_node(state)
    assert result["liturgical_context"] == context
    assert result["preference_overrides"] == {"target_audience": "youth"}
