"""Conversation preferences: Italian controls mapped to core values.

``Select.items`` maps **label → value** (Chainlit renders the key and submits the
value), so the Italian labels live here and the core only ever sees its own
literals (plan §18). Nothing is pinned until the user changes a control: the
panel shows the homily agent's defaults and an untouched conversation behaves
exactly as before.
"""

from collections.abc import Mapping
from typing import Any

from chainlit.input_widget import Select

from chat_orchestrator.application import ChatPreferences

AUDIENCE_ITEMS: dict[str, str] = {
    "Adulti": "adults",
    "Giovani": "youth",
    "Bambini": "children",
    "Pubblico misto": "mixed",
}

TONE_ITEMS: dict[str, str] = {
    "Formale": "formal",
    "Conversazionale": "conversational",
    "Poetico": "poetic",
    "Consolatorio": "consolatory",
    "Festoso": "celebratory",
}

LENGTH_ITEMS: dict[str, str] = {
    "Breve (5-7 minuti)": "short",
    "Media (10-12 minuti)": "medium",
    "Lunga (oltre 15 minuti)": "long",
}

ITEM_SETS: dict[str, dict[str, str]] = {
    "target_audience": AUDIENCE_ITEMS,
    "tone": TONE_ITEMS,
    "length": LENGTH_ITEMS,
}

INITIAL_VALUES: dict[str, str] = {
    "target_audience": "adults",
    "tone": "formal",
    "length": "medium",
}


def settings_widgets() -> list[Select]:
    """The three selects shown in the composer's settings panel."""
    return [
        Select(id=field, label=label, items=items, initial_value=INITIAL_VALUES[field])
        for field, label, items in (
            ("target_audience", "Destinatari", AUDIENCE_ITEMS),
            ("tone", "Tono", TONE_ITEMS),
            ("length", "Lunghezza", LENGTH_ITEMS),
        )
    ]


def from_settings(settings: Mapping[str, Any] | None) -> ChatPreferences | None:
    """Map a settings mapping onto the core model, dropping unknown values.

    Returns ``None`` when nothing usable was selected, so an untouched
    conversation sends no preference block to the model. Values come from the
    browser: unknown ids and values the core does not accept are ignored
    instead of raising, so a stale stored session cannot break a turn.
    """
    selected: dict[str, str] = {}
    for field, items in ITEM_SETS.items():
        value = (settings or {}).get(field)
        if isinstance(value, str) and value in items.values():
            selected[field] = value
    if not selected:
        return None
    return ChatPreferences(**selected)
