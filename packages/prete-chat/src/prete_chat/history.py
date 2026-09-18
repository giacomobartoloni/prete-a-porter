"""Conversation history for the native UI.

Only user and assistant text is model-visible context (plan §15): tool steps,
status notices, the welcome message and system prompts never become messages.
In-session accumulation and resume reconstruction share these helpers.
"""

from chat_orchestrator.application import ChatMessage

MODEL_VISIBLE_STEP_TYPES = ("user_message", "assistant_message")
WELCOME_METADATA_KEY = "welcome"


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


def from_thread(thread: dict) -> list[dict[str, str]]:
    """Rebuild the model-visible history from a Chainlit ``ThreadDict``.

    Chainlit replays the thread in the UI by itself; this function only
    reconstructs what the model may see again on the next turn. Steps are
    ordered by ``createdAt`` (the data layer stores ISO strings), and only
    ``user_message``/``assistant_message`` steps qualify — tool/run/llm steps
    are execution detail that can be re-derived, never assistant turns.
    """
    steps = thread.get("steps") or []
    ordered = sorted(steps, key=lambda step: step.get("createdAt") or "")
    turns: list[dict[str, str]] = []
    for step in ordered:
        step_type = step.get("type")
        if step_type not in MODEL_VISIBLE_STEP_TYPES:
            continue
        metadata = step.get("metadata") or {}
        if metadata.get(WELCOME_METADATA_KEY):
            # Threads created while the app still sent a programmatic welcome
            # keep it as an assistant step; it is not a model turn (plan §15).
            continue
        output = step.get("output")
        if isinstance(output, str):
            append(turns, "user" if step_type == "user_message" else "assistant", output)
    return turns
