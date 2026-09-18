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

from prete_chat import errors, history, labels, runner

configure_logging()
logger = get_logger(__name__)

WELCOME_MESSAGE = (
    "Benvenuto. Posso cercare le letture liturgiche e preparare un'omelia: "
    "prova con «Quali sono le letture di domenica prossima?»."
)


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
    """Start a fresh conversation: empty model-visible history, no core call."""
    cl.user_session.set("history", [])
    logger.info("chat started", user_id=_user_id(), thread_id=cl.context.session.thread_id)
    await cl.Message(content=WELCOME_MESSAGE).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Answer one user turn: quota, streamed answer, steps, history, boundary log."""
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
    messages = history.build_messages(turns, message.content)
    answer = cl.Message(content="")
    await answer.send()
    handler = labels.ItalianLabelsHandler()
    text_parts: list[str] = []

    try:
        async for chunk, metadata in runner.stream_chat(
            messages,
            session_id=thread_id,
            config={"callbacks": [handler]},
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
        _record_turns(turns, message.content, text_parts)
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
    _record_turns(turns, message.content, text_parts)
    _log_turn(
        user_id=user_id,
        thread_id=thread_id,
        request_id=request_id,
        started=started,
        outcome=outcome,
        streamed_chars=len("".join(text_parts)),
    )


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
