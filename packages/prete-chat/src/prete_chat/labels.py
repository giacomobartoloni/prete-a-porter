"""Presentation-only mapping from core tool names to Italian step labels.

The core never knows about labels: it exposes tools with their own names, and
the adapter renames the Chainlit step while it is being created.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from chainlit.langchain.callbacks import LangchainCallbackHandler

if TYPE_CHECKING:
    from langchain_core.tracers.schemas import Run

TOOL_STEP_LABELS: dict[str, str] = {
    "get_current_date": "Controllo la data di oggi",
    "calculate_date": "Calcolo la data richiesta",
    "get_liturgical_readings": "Recupero le letture liturgiche",
    "get_liturgical_lectionary": "Cerco le opzioni del lezionario",
    "generate_homily": "Preparo l'omelia",
    "refine_homily": "Rivedo l'omelia",
}


def tool_step_label(name: str) -> str:
    """Italian label for a tool run; tools without a mapping keep their name."""
    return TOOL_STEP_LABELS.get(name, name)


class ItalianLabelsHandler(LangchainCallbackHandler):
    """Stock Chainlit handler that titles tool steps in Italian.

    Chainlit builds the step from ``run.name`` inside ``_start_trace``, before
    the step is sent, so the rename happens there and the UI never shows the
    English tool name. Only tool runs are touched: LLM and chain steps keep the
    stock names, which ``cot = "tool_call"`` hides anyway. The name is restored
    afterwards so the tracer's own bookkeeping sees the original run.
    """

    def __init__(
        self,
        *,
        on_tool_start: Callable[[str], Awaitable[None]] | None = None,
        on_tool_end: Callable[[], Awaitable[None]] | None = None,
        on_tool_result: Callable[[str, object, object], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__()
        self._owner_loop = asyncio.get_running_loop()
        self._progress_start = on_tool_start
        self._progress_end = on_tool_end
        self._tool_result = on_tool_result

    async def _start_trace(self, run: "Run") -> None:
        if asyncio.get_running_loop() is not self._owner_loop:
            future = asyncio.run_coroutine_threadsafe(self._start_trace(run), self._owner_loop)
            await asyncio.wrap_future(future)
            return
        if run.run_type != "tool":
            await super()._start_trace(run)
            return
        if self._progress_start is not None:
            await self._progress_start(tool_step_label(run.name))
        original = run.name
        run.name = tool_step_label(original)
        try:
            await super()._start_trace(run)
        finally:
            run.name = original

    async def _end_trace(self, run: "Run") -> None:
        if asyncio.get_running_loop() is not self._owner_loop:
            future = asyncio.run_coroutine_threadsafe(self._end_trace(run), self._owner_loop)
            await asyncio.wrap_future(future)
            return
        await super()._end_trace(run)
        if run.run_type == "tool" and not getattr(run, "error", None) and self._tool_result is not None:
            await self._tool_result(run.name, run.outputs, run.inputs)
        if run.run_type == "tool" and self._progress_end is not None:
            await self._progress_end()
