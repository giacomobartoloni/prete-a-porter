"""Adapter-side refinement actions (plan §21).

An action payload carries a typed operation; the message the core receives is
Italian prose composed here, exactly as if the user had typed it. The core never
parses button labels. Actions are re-created per message because Chainlit sends
them with the message and sharing instances would reuse their ids.
"""

from typing import Any

import chainlit as cl

REFINEMENT_MESSAGES: dict[str, str] = {
    "shorter": "Accorcia l'ultima omelia, mantenendo i passaggi essenziali.",
    "conversational": "Riscrivi l'ultima omelia con un tono più conversazionale.",
    "regenerate": "Rigenera l'ultima omelia con una formulazione diversa.",
    "gospel_link": "Collega più esplicitamente l'ultima omelia al Vangelo.",
}

ACTION_LABELS: list[tuple[str, str]] = [
    ("shorter", "Rendi più breve"),
    ("conversational", "Più conversazionale"),
    ("regenerate", "Rigenera"),
    ("gospel_link", "Collega al Vangelo"),
]


def refinement_actions() -> list[cl.Action]:
    """Actions shown under an assistant answer."""
    return [
        cl.Action(name="refine_homily", payload={"operation": operation}, label=label)
        for operation, label in ACTION_LABELS
    ]


def message_for(operation: Any) -> str | None:
    """Italian user message for an action payload; ``None`` for an unknown one."""
    if isinstance(operation, str):
        return REFINEMENT_MESSAGES.get(operation)
    return None
