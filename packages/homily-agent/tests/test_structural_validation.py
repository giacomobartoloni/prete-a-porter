"""Structural completeness checks for generated homilies (not theology)."""

from __future__ import annotations

import pytest

from homily_agent.agent import HomilyAgent
from homily_agent.graph import GraphState, _format_node, _validate_node
from homily_agent.state import GeneratedHomily, HomilyAgentState, HomilySection


def _section(content: str = "body") -> HomilySection:
    return HomilySection(title="t", content=content)


def _homily(**overrides: str) -> GeneratedHomily:
    sections = {
        "introduction": _section("intro"),
        "reading_reflection": _section("reflect"),
        "practical_application": _section("apply"),
        "conclusion": _section("end"),
    }
    for key, content in overrides.items():
        sections[key] = _section(content)
    return GeneratedHomily(
        occasion="mass",
        liturgical_date="2026-05-19",
        **sections,
    )


def test_validate_accepts_complete_sections():
    agent = HomilyAgent()
    state = HomilyAgentState(generated_homily=_homily())
    result = agent.validate_homily(state)
    assert result["validation"]["valid"] is True
    assert result["validation"].get("kind") == "structural"
    assert "error" not in result


def test_validate_rejects_whitespace_section():
    agent = HomilyAgent()
    state = HomilyAgentState(generated_homily=_homily(conclusion="   "))
    result = agent.validate_homily(state)
    assert result["validation"]["valid"] is False
    assert result.get("error")
    assert any("conclusion" in i for i in result["validation"]["issues"])


def test_validate_rejects_missing_homily_with_error():
    agent = HomilyAgent()
    result = agent.validate_homily(HomilyAgentState())
    assert result["validation"]["valid"] is False
    assert result.get("error")


def test_validate_node_propagates_error_onto_state():
    agent = HomilyAgent()
    state = HomilyAgentState(generated_homily=_homily(introduction=""))
    graph_state: GraphState = {"homily_state": state}
    out = _validate_node(graph_state, agent)
    assert out["homily_state"].validation["valid"] is False
    assert out["homily_state"].error


def test_format_node_keeps_validation_error_for_handler():
    agent = HomilyAgent()
    state = HomilyAgentState(error="structurally incomplete")
    graph_state: GraphState = {"homily_state": state}
    out = _format_node(graph_state, agent)
    assert out["homily_state"].error == "structurally incomplete"
