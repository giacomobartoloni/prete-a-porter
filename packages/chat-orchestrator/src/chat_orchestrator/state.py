"""
State models for Chat Orchestrator.

Defines the ChatState class, which extends MessagesState and adds session and control fields.
"""

from typing import Any, Literal

from langgraph.graph import MessagesState


class ChatState(MessagesState):
    """
    State for the chat orchestrator, including session ID and next action.
    Inherits from MessagesState (which provides a 'messages' field).
    """

    session_id: str
    next_action: Literal["continue", "end"]

    liturgical_context: dict[str, Any] | None
    preference_overrides: dict[str, str]
