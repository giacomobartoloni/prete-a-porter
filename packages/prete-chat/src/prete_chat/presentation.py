"""Transient progress and lazy answer rendering for a native chat turn."""

import chainlit as cl
from chainlit.utils import utc_now

from prete_chat import history

TRANSIENT_PROGRESS_KEY = "transient_progress"
EMPTY_RESPONSE_NOTICE = "Non ho ricevuto una risposta. Riprova tra poco."


class TurnPresentation:
    """Keep tool progress separate from generated, persisted assistant text."""

    def __init__(self) -> None:
        self.status: cl.Message | None = None
        self.answer: cl.Message | None = None
        self.model_text = ""

    async def start(self) -> None:
        self.status = cl.Message(
            content="Sto elaborando la richiesta…",
            metadata={
                history.MODEL_CONTENT_METADATA_KEY: "",
                TRANSIENT_PROGRESS_KEY: True,
            },
        )
        await self.status.send()

    async def tool_started(self, label: str) -> None:
        if self.status is not None:
            self.status.content = label + "…"
            await self.status.update()

    async def tool_finished(self) -> None:
        if self.status is not None:
            self.status.content = "Preparo la risposta…"
            await self.status.update()

    async def _clear_status(self) -> None:
        if self.status is not None:
            status, self.status = self.status, None
            await status.remove()

    async def stream_token(self, text: str) -> None:
        if not text:
            return
        self.model_text += text
        if self.answer is None:
            if not self.model_text.strip():
                return
            await self._clear_status()
            # Construct at first visible token so its timestamp follows tools.
            self.answer = cl.Message(content="", metadata={history.MODEL_CONTENT_METADATA_KEY: ""})
            self.answer.created_at = utc_now()
            await self.answer.stream_token(self.model_text)
        else:
            await self.answer.stream_token(text)

    async def finish(self, notice: str | None = None, actions: list | None = None) -> None:
        """Finalize success or interruption, excluding notices from model history."""
        await self._clear_status()
        if self.answer is None:
            self.answer = cl.Message(
                content=notice or EMPTY_RESPONSE_NOTICE, metadata={history.MODEL_CONTENT_METADATA_KEY: ""}
            )
            await self.answer.send()
            return
        if notice:
            self.answer.content += "\n\n" + notice
        elif self.model_text.strip():
            self.answer.actions = actions or []
        self.answer.metadata[history.MODEL_CONTENT_METADATA_KEY] = self.model_text
        await self.answer.update()
