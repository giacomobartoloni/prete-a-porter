"""Generate or revise homilies from scripture and bounded theological context."""

import json
import logging
import os
from typing import Any

from a2a_protocol.llm import create_llm

from homily_agent.composition import DEFAULT_WORD_COUNTS, compose
from homily_agent.rag import RetrievalService
from homily_agent.state import GeneratedHomily, LiturgicalReading, UserPreferences

logger = logging.getLogger(__name__)


class HomilyGenerator:
    """One content owner for generation and full-draft revision.

    The synchronous model call runs in LangGraph's worker for synchronous nodes,
    not directly on the HTTP event loop. Provider requests have a 45-second
    timeout and no SDK retries. Two composition attempts bound residual work
    after cancellation; no automatic A2A retry should duplicate a generation.
    """

    def __init__(self, retrieval_service: RetrievalService | None = None, llm: Any = None):
        self.retrieval_service = retrieval_service
        self.llm = llm

    def _model(self) -> Any:
        if self.llm is None:
            if os.getenv("TEST_MODE") == "true":
                from homily_agent.testing import FixtureHomilyModel

                self.llm = FixtureHomilyModel()
            else:
                timeout = float(os.getenv("HOMILY_MODEL_TIMEOUT_SECONDS", "45"))
                max_tokens = int(os.getenv("HOMILY_MAX_OUTPUT_TOKENS", "4096"))
                if not 0 < timeout <= 300 or not 512 <= max_tokens <= 32768:
                    raise ValueError("Invalid homily model timeout or output token budget")
                model = create_llm(timeout=timeout, max_retries=0, max_tokens=max_tokens)
                effort = os.getenv("HOMILY_OPENAI_REASONING_EFFORT", "").strip()
                json_mode = os.getenv("HOMILY_OPENAI_JSON_MODE", "false").strip().lower()
                if json_mode not in {"true", "false"}:
                    raise ValueError("HOMILY_OPENAI_JSON_MODE must be true or false")
                options = {}
                if (effort or json_mode == "true") and not type(model).__module__.startswith("langchain_openai"):
                    raise ValueError("Homily JSON/reasoning options require an OpenAI-compatible model")
                if effort:
                    if effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
                        raise ValueError("Invalid homily reasoning effort")
                    options["reasoning_effort"] = effort
                if json_mode == "true":
                    options["response_format"] = {"type": "json_object"}
                if options:
                    model = model.bind(**options)
                self.llm = model
        return self.llm

    def _sources(self, query: str) -> list[dict[str, str]]:
        if self.retrieval_service is None:
            return []
        try:
            documents = self.retrieval_service.retrieve(query)
        except Exception:
            logger.warning("Theological retrieval unavailable; composing from scripture only")
            return []
        sources = []
        remaining = 11998
        for document in documents:
            label = document.source[:512]
            if (document.metadata or {}).get("paragraph_num") is not None:
                label += f" §{document.metadata['paragraph_num']}"
            source = {"id": f"S{len(sources) + 1}", "source": label, "content": ""}
            overhead = len(json.dumps(source, ensure_ascii=False)) + 2
            available = min(2500, remaining - overhead)
            if available <= 0:
                break
            source["content"] = document.content.strip()[:available]
            # Escaped quotes/newlines count toward the serialized context too.
            while source["content"]:
                cost = len(json.dumps(source, ensure_ascii=False)) + 2
                if cost <= remaining:
                    break
                source["content"] = source["content"][: max(0, len(source["content"]) - (cost - remaining))]
            if not source["content"]:
                continue
            sources.append(source)
            remaining -= cost
        return sources

    def generate(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        existing_draft: str | None = None,
    ) -> tuple[GeneratedHomily, list[str]]:
        """Compose complete sections; a supplied draft requests a real rewrite."""
        if existing_draft is not None and not existing_draft.strip():
            raise ValueError("The existing draft must not be blank")
        query = " ".join(
            [occasion, liturgical_data.gospel.text[:1200], *(preferences.themes or []), *(preferences.parables or [])]
        )
        request = {
            "operation": "refine" if existing_draft is not None else "generate",
            "readings": liturgical_data.model_dump(),
            "occasion": occasion,
            "preferences": preferences.model_dump(),
            "target_word_count": preferences.target_word_count or DEFAULT_WORD_COUNTS[preferences.length],
            "existing_draft": existing_draft,
            "sources": self._sources(query),
        }
        return compose(self._model(), request)
