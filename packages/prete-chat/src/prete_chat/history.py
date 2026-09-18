"""Conversation history for the native UI.

Only user and assistant text is model-visible context (plan §15): tool steps,
status notices, the welcome message and system prompts never become messages.
In-session accumulation lives here; resume reconstruction (from Chainlit's
``ThreadDict``) joins it in the persistence phase and shares these helpers.
"""

from chat_orchestrator.application import ChatMessage


def append(turns: list[dict[str, str]], role: str, content: str) -> None:
    """Append one model-visible turn, ignoring content that is only whitespace."""
    text = content.strip()
    if text:
        turns.append({"role": role, "content": text})


def build_messages(turns: list[dict[str, str]], user_text: str) -> list[ChatMessage]:
    """Build the message list for the next invocation: history + the new turn."""
    messages = [ChatMessage(role=turn["role"], content=turn["content"]) for turn in turns]
    messages.append(ChatMessage(role="user", content=user_text))
    return messages
