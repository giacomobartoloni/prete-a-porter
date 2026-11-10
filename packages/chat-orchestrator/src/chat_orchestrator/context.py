"""Validated per-invocation liturgical identity, owned by the calling adapter."""

import ast
import json
from datetime import date
from typing import Any


def parse_liturgical_context(value: object) -> dict[str, Any] | None:
    """Return only an ISO date and supported occasion, ignoring malformed data."""
    if not isinstance(value, dict):
        return None
    occasion = value.get("occasion")
    if not isinstance(occasion, str) or occasion not in {"mass", "marriage", "baptism", "funeral"}:
        return None
    day = value.get("date")
    if not isinstance(day, str):
        return None
    try:
        if date.fromisoformat(day).isoformat() == day:
            context: dict[str, Any] = {"date": day, "occasion": occasion}
            preferences = stable_preferences(value.get("preferences"))
            if preferences:
                context["preferences"] = preferences
            return context
    except ValueError:
        pass
    return None


STABLE_OPTIONS = {
    "target_audience": {"adults", "youth", "children", "mixed"},
    "tone": {"formal", "conversational", "poetic", "consolatory", "celebratory"},
}


def json_object(value: object) -> dict | None:
    """Decode bounded tool strings; malformed/non-object values stay invalid."""
    if isinstance(value, str) and len(value) <= 50000:
        try:
            value = json.loads(value)
        except ValueError:
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError, RecursionError, MemoryError):
                return None
    return value if isinstance(value, dict) else None


def stable_preferences(value: object) -> dict[str, str]:
    value = json_object(value) or {}
    return {
        key: item
        for key, options in STABLE_OPTIONS.items()
        if isinstance(item := value.get(key), str) and item in options
    }


def effective_preferences(inputs: object) -> dict[str, str]:
    """Stable profile actually requested, including explicit per-turn changes."""
    inputs = json_object(inputs) or {}
    return {**stable_preferences(inputs.get("preferences")), **stable_preferences(inputs.get("preference_changes"))}
