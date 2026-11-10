"""Conversation history for the native UI.

Only user and assistant text is model-visible context (plan §15): tool steps,
status notices, the welcome message and system prompts never become messages.
In-session accumulation and resume reconstruction share these helpers.
"""

import ast
import json

from chat_orchestrator.application import ChatMessage
from chat_orchestrator.context import effective_preferences, json_object, parse_liturgical_context, stable_preferences

MODEL_VISIBLE_STEP_TYPES = ("user_message", "assistant_message")
WELCOME_METADATA_KEY = "welcome"
MODEL_CONTENT_METADATA_KEY = "model_content"


def append(turns: list[dict[str, str]], role: str, content: str) -> None:
    """Append one model-visible turn, ignoring content that is only whitespace."""
    text = content.strip()
    if text:
        turns.append({"role": role, "content": text})


def build_messages(turns: list[dict[str, str]], user_text: str, *, context: dict | None = None) -> list[ChatMessage]:
    """Build the message list for the next invocation: history + the new turn."""
    messages = [ChatMessage(role=turn["role"], content=turn["content"]) for turn in turns]
    if valid_context(context):
        messages.insert(
            0,
            ChatMessage(
                role="system",
                content=(
                    f"Contesto verificato dell'omelia precedente: date={context['date']}, occasion={context['occasion']}. "
                    f"Profilo precedente: {json.dumps(context.get('preferences', {}), ensure_ascii=False)}. "
                    "Una riscrittura con refine_homily conserva data, occasione, destinatari e tono. "
                    "Solo una modifica esplicita nel messaggio corrente di destinatari o tono va in preference_changes. "
                    "Se l'utente richiede una diversa celebrazione o data, usa generate_homily per la nuova omelia."
                ),
            ),
        )
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
        output = metadata.get(MODEL_CONTENT_METADATA_KEY, step.get("output"))
        if isinstance(output, str):
            append(turns, "user" if step_type == "user_message" else "assistant", output)
    return turns


def valid_context(value: object) -> bool:
    return parse_liturgical_context(value) is not None


def context_from_result(result: object, *, preferences: object = None) -> dict | None:
    """Accept only a successful authored homily, never model tool arguments."""
    if isinstance(result, str) and len(result) <= 100000:
        try:
            result = json.loads(result)
        except ValueError:
            try:
                result = ast.literal_eval(result)
            except (ValueError, SyntaxError, RecursionError):
                return None
    if not isinstance(result, dict) or result.get("error"):
        return None
    if "output" in result:
        return context_from_result(result["output"], preferences=preferences)
    if result.get("status") != "success":
        return None
    data = result.get("data")
    homily = data.get("homily") if isinstance(data, dict) else None
    if not isinstance(homily, dict):
        return None
    context = {"date": homily.get("liturgical_date"), "occasion": homily.get("occasion")}
    profile = stable_preferences(preferences)
    if profile:
        context["preferences"] = profile
    return parse_liturgical_context(context)


def context_from_thread(thread: dict) -> dict | None:
    """Recover the latest successful profile; old refine defaults cannot reset it."""
    context = None
    for step in sorted(thread.get("steps") or [], key=lambda step: step.get("createdAt") or ""):
        candidate = (step.get("metadata") or {}).get("liturgical_context")
        if step.get("type") == "assistant_message" and valid_context(candidate):
            candidate = parse_liturgical_context(candidate)
            if (
                context
                and context["date"] == candidate["date"]
                and context["occasion"] == candidate["occasion"]
                and context.get("preferences")
            ):
                candidate.setdefault("preferences", context["preferences"])
            context = candidate
        elif step.get("type") == "tool" and not step.get("isError"):
            inputs = json_object(step.get("input")) or {}
            candidate = context_from_result(step.get("output"), preferences=effective_preferences(inputs))
            if candidate:
                is_refinement = step.get("name") in {"refine_homily", "Rivedo l'omelia"}
                if (
                    is_refinement
                    and context
                    and context["date"] == candidate["date"]
                    and context["occasion"] == candidate["occasion"]
                ):
                    candidate["preferences"] = {
                        **candidate.get("preferences", {}),
                        **context.get("preferences", {}),
                        **stable_preferences(inputs.get("preference_changes")),
                    }
                context = candidate
    return parse_liturgical_context(context)
