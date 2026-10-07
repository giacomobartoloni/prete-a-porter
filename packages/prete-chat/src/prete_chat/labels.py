"""Presentation-only mapping from core tool names to Italian step labels.

The core never knows about labels: it exposes tools with their own names, and
the adapter renames the Chainlit step while it is being created.
"""

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

    async def _start_trace(self, run: "Run") -> None:
        if run.run_type != "tool":
            await super()._start_trace(run)
            return
        original = run.name
        run.name = tool_step_label(original)
        try:
            await super()._start_trace(run)
        finally:
            run.name = original
