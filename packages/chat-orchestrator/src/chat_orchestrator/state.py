
"""
State models for Chat Orchestrator.

Defines the ChatState class, which extends MessagesState and adds session and control fields.
"""

from langgraph.graph import MessagesState
from typing import Literal

class ChatState(MessagesState):
	"""
	State for the chat orchestrator, including session ID and next action.
	Inherits from MessagesState (which provides a 'messages' field).
	"""
	session_id: str
	user_id: str
	next_action: Literal["continue", "end"]
