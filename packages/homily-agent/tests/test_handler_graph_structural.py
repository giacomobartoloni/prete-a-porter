"""Compact compiled-graph + handler regressions for structural completeness."""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

import pytest

from homily_agent.generator import HomilyGenerator
from homily_agent.graph import create_homily_graph
from homily_agent.main import HomilyAgentHandler
from homily_agent.rag.retrieval import RetrievalService
from homily_agent.state import (
    GeneratedHomily,
    HomilySection,
    LiturgicalMetadata,
    LiturgicalReading,
    Reading,
)


def _section(content: str) -> HomilySection:
    return HomilySection(title="t", content=content)


def _complete_homily() -> GeneratedHomily:
    return GeneratedHomily(
        introduction=_section("intro"),
        reading_reflection=_section("reflect"),
        practical_application=_section("apply"),
        conclusion=_section("end"),
        occasion="mass",
        liturgical_date="2026-05-19",
    )


def _liturgical_data() -> dict:
    return LiturgicalReading(
        date="2026-05-19",
        occasion="mass",
        metadata=LiturgicalMetadata(
            date="2026-05-19",
            occasion="mass",
            season="Ordinary",
            color="Green",
            year_cycle="A",
            sunday_or_weekday="Weekday",
        ),
        first_reading=Reading(reference="Gc 4,13-17", text="primo", type="First"),
        psalm=Reading(reference="Sal 48", text="salmo", type="Psalm"),
        gospel=Reading(reference="Mc 9,38-40", text="vangelo", type="Gospel"),
    ).model_dump()


class _StubGenerator(HomilyGenerator):
    def __init__(self, homily: Optional[GeneratedHomily]):
        super().__init__(retrieval_service=MagicMock(spec=RetrievalService))
        self._homily = homily

    def generate(self, *args, **kwargs):
        if self._homily is None:
            return None, []  # type: ignore[return-value]
        return self._homily, ["stub-source"]


def _handler_with(homily: Optional[GeneratedHomily]) -> HomilyAgentHandler:
    handler = HomilyAgentHandler.__new__(HomilyAgentHandler)
    handler.retrieval_service = MagicMock(spec=RetrievalService)
    handler.graph = create_homily_graph(
        retrieval_service=handler.retrieval_service,
        generator=_StubGenerator(homily),
    )
    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["generate", "refine", "adjust"])
async def test_handler_rejects_missing_homily(intent):
    handler = _handler_with(None)
    params = {
        "liturgical_data": _liturgical_data(),
        "occasion": "mass",
        "existing_draft": "draft" if intent != "generate" else None,
    }
    with pytest.raises(RuntimeError):
        await handler._invoke_graph(params, intent)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["generate", "refine", "adjust"])
async def test_handler_rejects_blank_section(intent):
    blank = _complete_homily()
    blank.conclusion = _section("   ")
    handler = _handler_with(blank)
    params = {
        "liturgical_data": _liturgical_data(),
        "occasion": "mass",
        "existing_draft": "draft" if intent != "generate" else None,
    }
    with pytest.raises(RuntimeError, match="conclusion|structur|incomplete|Empty"):
        await handler._invoke_graph(params, intent)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["generate", "refine", "adjust"])
async def test_handler_accepts_complete_homily_envelope(intent):
    handler = _handler_with(_complete_homily())
    params = {
        "liturgical_data": _liturgical_data(),
        "occasion": "mass",
        "existing_draft": "draft" if intent != "generate" else None,
    }
    result = await handler._invoke_graph(params, intent)  # type: ignore[arg-type]
    assert "homily" in result
    assert result["homily"]["introduction"]["content"] == "intro"
    assert result["sources"] == ["stub-source"]
