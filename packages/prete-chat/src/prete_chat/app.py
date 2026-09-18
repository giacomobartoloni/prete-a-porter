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
from chat_orchestrator.utils.logging import configure_logging, get_logger, set_correlation_id

from prete_chat import actions, auth, config, data_layer, errors, history, labels, preferences, runner

configure_logging()
logger = get_logger(__name__)

config.validate()

# Persistence and authentication are opt-in: a postgresql+asyncpg DATABASE_URL
# turns both on; anything else (including the legacy frontend's `file:` URL)
# keeps the service in POC mode — no data layer, no login.
if config.persistence_enabled():
    cl.data_layer(data_layer.build)
    cl.password_auth_callback(auth.password_auth)
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


def _append_notice(answer: cl.Message, notice: str) -> None:
    """Append a status notice to the answer the user is looking at."""
    answer.content = f"{answer.content}\n\n{notice}" if answer.content else notice


def _record_turns(turns: list[dict[str, str]], user_text: str, assistant_parts: list[str]) -> None:
    """Persist the model-visible turns in the session history (plan §15).

    Status notices and tool steps never enter the history: only what the model
    actually said becomes context for the next invocation.
    """
    history.append(turns, "user", user_text)
    history.append(turns, "assistant", "".join(assistant_parts))
    cl.user_session.set("history", turns)


@cl.on_chat_start
async def on_chat_start() -> None:
    """Start a fresh conversation: empty model-visible history, no core call.

    No programmatic welcome message: a message would end the empty state that
    the starters (the replacement for the legacy suggestion buttons) live in,
    and the welcome text is already the readme panel (``chainlit.md``).
    """
    cl.user_session.set("history", [])
    cl.user_session.set("chat_settings", {})
    await cl.ChatSettings(preferences.settings_widgets()).send()
    logger.info("chat started", user_id=_user_id(), thread_id=cl.context.session.thread_id)


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Keep the conversation preferences for the next invocations.

    Only the chosen fields reach the model, and only as part of the invocation's
    system prompt — nothing is persisted by the core (plan §18).
    """
    cl.user_session.set("chat_settings", dict(settings))
    logger.info("chat settings updated", user_id=_user_id(), fields=sorted(settings))


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    """Continue an existing thread: rebuild the model-visible history.

    Chainlit replays the persisted messages and elements by itself; only the
    context for the next model invocation is rebuilt here.
    """
    turns = history.from_thread(thread)
    cl.user_session.set("history", turns)
    cl.user_session.set("chat_settings", dict(cl.context.session.chat_settings or {}))
    logger.info(
        "chat resumed",
        user_id=_user_id(),
        thread_id=cl.context.session.thread_id,
        turns=len(turns),
    )


async def _answer_turn(user_text: str) -> None:
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
        await cl.Message(content=refusal).send()
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
    messages = history.build_messages(turns, user_text)
    answer = cl.Message(content="", actions=actions.refinement_actions())
    await answer.send()
    handler = labels.ItalianLabelsHandler()
    conversation_preferences = preferences.from_settings(cl.user_session.get("chat_settings"))
    text_parts: list[str] = []

    try:
        async for chunk, metadata in runner.stream_chat(
            messages,
            session_id=thread_id,
            config={"callbacks": [handler]},
            preferences=conversation_preferences,
        ):
            if is_visible_token(chunk, metadata):
                await answer.stream_token(chunk.content)
                text_parts.append(chunk.content)
        outcome = "completed"
    except asyncio.CancelledError:
        # The user pressed Stop: keep what was streamed, mark it, re-raise so
        # Chainlit's own task handling sees the cancellation (socket.py).
        _append_notice(answer, errors.CANCELLED_MESSAGE_IT)
        outcome = "cancelled"
        await answer.update()
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
        _append_notice(answer, errors.user_message_for(error))

    await answer.update()
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
    await _answer_turn(message.content)


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
    await cl.Message(content=message_text, type="user_message", author=_user_id()).send()
    await _answer_turn(message_text)


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
