"""Chainlit entry point: lifecycle hooks and wiring.

Only this module is referenced by ``chainlit run``. Everything it calls lives in
importable, unit-tested modules: ``runner`` (core bridge), ``history``
(conversation context), ``errors`` (user-facing text), ``labels`` (step titles).
"""

import asyncio
import time
import uuid

import chainlit as cl
from chat_orchestrator.application import is_visible_token
from chat_orchestrator.context import effective_preferences
from chat_orchestrator.utils.logging import configure_logging, get_logger, set_correlation_id

from prete_chat import actions, auth, config, data_layer, errors, history, labels, preferences, presentation, runner

configure_logging()
logger = get_logger(__name__)

config.validate()

# Persistence and authentication are opt-in: a postgresql+asyncpg DATABASE_URL
# turns both on; anything else (including the legacy frontend's `file:` URL)
# keeps the service in POC mode — no data layer, no login.
if config.persistence_enabled():
    cl.data_layer(data_layer.build)
    cl.password_auth_callback(auth.password_auth)
    if config.google_oauth_enabled():
        cl.oauth_callback(auth.google_oauth)
else:
    logger.warning("persistence disabled: no conversation history and no authentication")


@cl.set_starters
async def set_starters(user: cl.User | None, language: str | None) -> list[cl.Starter]:
    """Empty-state suggestions, mirroring the legacy UI's suggestion buttons."""
    return [
        cl.Starter(
            label="Letture di domenica prossima",
            message="Quali sono le letture di domenica prossima?",
        ),
        cl.Starter(
            label="Letture per un matrimonio",
            message="Che letture ci sono per un matrimonio?",
        ),
        cl.Starter(
            label="Prepara un'omelia",
            message="Prepara un'omelia di dieci minuti per adulti.",
        ),
    ]


def _user_id() -> str:
    """Quota key for this shell; anonymous until authentication exists."""
    user = cl.context.session.user
    identifier = getattr(user, "identifier", None)
    return identifier or "anonymous"


def _log_turn(
    *,
    user_id: str,
    thread_id: str,
    request_id: str,
    started: float,
    outcome: str,
    streamed_chars: int,
) -> None:
    """One boundary line per turn; message content is never logged."""
    logger.info(
        "chat turn finished",
        user_id=user_id,
        thread_id=thread_id,
        request_id=request_id,
        duration_ms=round((time.monotonic() - started) * 1000),
        outcome=outcome,
        streamed_chars=streamed_chars,
    )


def _record_turns(turns: list[dict[str, str]], user_text: str, assistant_parts: list[str]) -> None:
    """Persist the model-visible turns in the session history (plan §15).

    Status notices and tool steps never enter the history: only what the model
    actually said becomes context for the next invocation.
    """
    history.append(turns, "user", user_text)
    history.append(turns, "assistant", "".join(assistant_parts))
    cl.user_session.set("history", turns)


async def _show_settings() -> None:
    """Show the effective profile without turning defaults into user choices."""
    context = cl.user_session.get("liturgical_context") or {}
    displayed = {
        **preferences.INITIAL_VALUES,
        **context.get("preferences", {}),
        **preferences.selected_values(cl.user_session.get("homily_preferences")),
    }
    cl.user_session.set("displayed_settings", displayed)
    await cl.ChatSettings(preferences.settings_widgets(displayed)).send()


@cl.on_chat_start
async def on_chat_start() -> None:
    """Start a fresh conversation: empty model-visible history, no core call.

    No programmatic welcome message: a message would end the empty state that
    the starters (the replacement for the legacy suggestion buttons) live in,
    and the welcome text is already the readme panel (``chainlit.md``).
    """
    cl.user_session.set("history", [])
    cl.user_session.set("liturgical_context", None)
    cl.user_session.set("homily_preferences", {})
    await _show_settings()
    logger.info("chat started", user_id=_user_id(), thread_id=cl.context.session.thread_id)


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Keep the conversation preferences for the next invocations.

    Chosen fields enter the invocation as typed overrides and a system block;
    the core retains no preference state between requests (plan §18).
    """
    selected = preferences.updated_overrides(
        cl.user_session.get("homily_preferences"), cl.user_session.get("displayed_settings"), settings
    )
    cl.user_session.set("homily_preferences", selected)
    displayed = {**(cl.user_session.get("displayed_settings") or {}), **preferences.selected_values(settings)}
    cl.user_session.set("displayed_settings", displayed)
    logger.info("chat settings updated", user_id=_user_id(), fields=sorted(settings))


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    """Continue an existing thread: rebuild the model-visible history.

    Chainlit replays the persisted messages and elements by itself; only the
    context for the next model invocation is rebuilt here.
    """
    turns = history.from_thread(thread)
    cl.user_session.set("liturgical_context", history.context_from_thread(thread))
    cl.user_session.set("history", turns)
    stored = (thread.get("metadata") or {}).get("homily_preferences") or {}
    cl.user_session.set("homily_preferences", preferences.selected_values(stored))
    await _show_settings()
    logger.info(
        "chat resumed",
        user_id=_user_id(),
        thread_id=cl.context.session.thread_id,
        turns=len(turns),
    )


async def _answer_turn(user_text: str, user_message: cl.Message | None = None) -> None:
    """Answer one user turn: quota, streamed answer, steps, history, boundary log.

    Shared by typed messages and by the refinement action callback, which sends
    its composed user message before calling this.
    """
    user_id = _user_id()
    thread_id = cl.context.session.thread_id
    request_id = uuid.uuid4().hex[:12]
    set_correlation_id(request_id)
    started = time.monotonic()

    quota = await runner.check_quota(user_id)
    refusal = errors.refusal_for(quota)
    if refusal is not None:
        if user_message is not None:
            user_message.metadata[history.MODEL_CONTENT_METADATA_KEY] = ""
            await user_message.update()
        await cl.Message(content=refusal, metadata={history.MODEL_CONTENT_METADATA_KEY: ""}).send()
        _log_turn(
            user_id=user_id,
            thread_id=thread_id,
            request_id=request_id,
            started=started,
            outcome="rate_limited",
            streamed_chars=0,
        )
        return

    turns: list[dict[str, str]] = cl.user_session.get("history") or []
    context = cl.user_session.get("liturgical_context")
    messages = history.build_messages(turns, user_text, context=context)
    view = presentation.TurnPresentation()
    await view.start()

    overrides_at_start = preferences.selected_values(cl.user_session.get("homily_preferences"))

    async def remember_result(name: str, result: object, inputs: object) -> None:
        if name not in {"generate_homily", "refine_homily"}:
            return
        candidate = history.context_from_result(result, preferences=effective_preferences(inputs))
        if candidate is not None:
            cl.user_session.set("liturgical_context", candidate)
            # A newer explicit textual change supersedes an older UI override.
            overrides = preferences.selected_values(cl.user_session.get("homily_preferences"))
            profile = candidate.get("preferences", {})
            overrides = {
                key: value
                for key, value in overrides.items()
                if key not in profile or profile[key] == value or overrides_at_start.get(key) != value
            }
            cl.user_session.set("homily_preferences", overrides)
            await _show_settings()

    handler = labels.ItalianLabelsHandler(
        on_tool_start=view.tool_started, on_tool_end=view.tool_finished, on_tool_result=remember_result
    )
    conversation_preferences = preferences.from_settings(cl.user_session.get("homily_preferences"))
    text_parts: list[str] = []

    notice = None
    try:
        async for chunk, metadata in runner.stream_chat(
            messages,
            session_id=thread_id,
            config={"callbacks": [handler]},
            liturgical_context=context,
            preferences=conversation_preferences,
        ):
            if is_visible_token(chunk, metadata):
                await view.stream_token(chunk.content)
                text_parts.append(chunk.content)
        outcome = "completed"
    except asyncio.CancelledError:
        # The user pressed Stop: keep what was streamed, mark it, re-raise so
        # Chainlit's own task handling sees the cancellation (socket.py).
        outcome = "cancelled"
        await view.finish(notice=errors.CANCELLED_MESSAGE_IT)
        _record_turns(turns, user_text, text_parts)
        _log_turn(
            user_id=user_id,
            thread_id=thread_id,
            request_id=request_id,
            started=started,
            outcome=outcome,
            streamed_chars=len("".join(text_parts)),
        )
        raise
    except Exception as error:
        outcome = errors.outcome_for(error)
        if outcome == "timeout":
            logger.error("chat turn timed out", request_id=request_id)
        else:
            logger.error("chat turn failed", request_id=request_id, exc_info=True)
        notice = errors.user_message_for(error)

    await view.finish(notice=notice, actions=actions.refinement_actions() if outcome == "completed" else None)
    if view.answer is not None:
        current_context = cl.user_session.get("liturgical_context")
        if history.valid_context(current_context):
            view.answer.metadata["liturgical_context"] = current_context
            await view.answer.update()
    _record_turns(turns, user_text, text_parts)
    _log_turn(
        user_id=user_id,
        thread_id=thread_id,
        request_id=request_id,
        started=started,
        outcome=outcome,
        streamed_chars=len("".join(text_parts)),
    )


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Answer a typed user message."""
    await _answer_turn(message.content, user_message=message)


@cl.action_callback("refine_homily")
async def on_refine_homily(action: cl.Action) -> None:
    """Re-enter the normal run path with a composed Italian message.

    The payload carries a typed operation and the visible user turn is composed
    here, so the model sees plain prose and the history stays coherent. The
    callback runs inside Chainlit's action request rather than the message task,
    so the Stop button does not cancel it.
    """
    message_text = actions.message_for((action.payload or {}).get("operation"))
    if message_text is None:
        logger.warning("unknown refinement action", payload=action.payload)
        return
    await action.remove()
    message = cl.Message(content=message_text, type="user_message", author=_user_id())
    await message.send()
    await _answer_turn(message_text, user_message=message)


@cl.on_stop
async def on_stop() -> None:
    """The user pressed Stop while a turn was running."""
    logger.info("generation stopped", user_id=_user_id(), thread_id=cl.context.session.thread_id)


@cl.on_chat_end
async def on_chat_end() -> None:
    """The session disconnected; nothing durable is held by this service yet."""
    logger.info("chat closed", user_id=_user_id(), thread_id=cl.context.session.thread_id)


@cl.on_logout
async def on_logout(request: object, response: object) -> bool:
    """Chainlit clears the session cookie; there is no server-side session."""
    logger.info("user logged out")
    return True
