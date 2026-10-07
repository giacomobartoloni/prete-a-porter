"""Classify OpenWebUI utility requests so they bypass the homily ReAct loop.

OpenWebUI issues eight auxiliary model requests (title, tags, follow-up,
autocomplete, retrieval-query, search-query, image-prompt, context compaction).
They arrive at the same ``/v1/chat/completions`` endpoint as real chat, so
without classification the LLM would run the homily tools to generate a chat
title.

Marker design: every marker pair is anchored on the ``### Output:`` line and
its JSON key, taken from OpenWebUI's documented default templates. Anchoring on
the prose in ``### Guidelines:`` would break whenever an administrator rewords a
template, and the JSON key is what OpenWebUI's own parser requires anyway.

One deliberate deparature from the reference implementation:

**There is no follow-up heuristic.** The reference implementation treats a short
third-turn message as a conversational follow-up that needs no fresh work, which
is correct for a pure RAG backend where skipping retrieval on "tell me more" is
the desired behaviour. It is wrong here. This agent is tool-driven, and in this
domain a short message is an *action authorisation*: after the assistant offers
to generate a homily, "si", "ok" or "vai" mean "generate it now", which requires
the graph and the liturgical tools. Bypassing the graph on those turns silently
breaks the primary flow.

The cost of not having the heuristic is one extra LLM call on a genuinely
conversational turn, which decides not to use any tool. That is cheap; a broken
homily flow is not.
"""

from .schemas import ChatCompletionRequest

TITLE_GENERATION: str = "title_generation"
TAGS_GENERATION: str = "tags_generation"
FOLLOW_UP_GENERATION: str = "follow_up_generation"
AUTOCOMPLETE_GENERATION: str = "autocomplete_generation"
QUERY_GENERATION: str = "query_generation"
CONTEXT_COMPACTION: str = "context_compaction"

UTILITY_TASKS: frozenset[str] = frozenset({
    TITLE_GENERATION,
    TAGS_GENERATION,
    FOLLOW_UP_GENERATION,
    AUTOCOMPLETE_GENERATION,
    QUERY_GENERATION,
    CONTEXT_COMPACTION,
})

TASK_PREFIX: str = "### task:"

# Each entry maps a task name to the markers that must ALL appear in the prompt.
# Markers are lowercase; the prompt is lowercased before matching.
PROMPT_MARKERS: dict[str, tuple[str, ...]] = {
    TITLE_GENERATION: ("### output:", '"title"'),
    TAGS_GENERATION: ("### output:", '"tags"'),
    FOLLOW_UP_GENERATION: ("### output:", '"follow_ups"'),
    QUERY_GENERATION: ("### output:", '"queries"'),
    # Autocomplete has no "### Output:" heading; it uses "#### Output:" and its
    # distinctive opening line. It is the highest-frequency task (fires as the
    # user types), so it must be caught by its own markers.
    AUTOCOMPLETE_GENERATION: ("autocompletion system", '"text"'),
    # Context compaction substitutes these two placeholders into its template.
    CONTEXT_COMPACTION: ("compacted_messages", "recent_messages"),
}

def _last_message_text(request: ChatCompletionRequest) -> str:
    """Return the last message's text, flattened to a string."""
    content = request.messages[-1].content
    if isinstance(content, str):
        return content
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _task_from_metadata(request: ChatCompletionRequest) -> str | None:
    """Read an explicit task name from the request metadata."""
    metadata = request.metadata or {}
    task = metadata.get("task")
    if isinstance(task, str) and task.strip():
        return task.strip()
    return None


def _task_from_prompt_shape(request: ChatCompletionRequest) -> str | None:
    """Detect a utility task from the ``### Task:`` prompt prefix."""
    prompt = _last_message_text(request).lstrip().lower()
    if not prompt.startswith(TASK_PREFIX):
        return None
    for name, markers in PROMPT_MARKERS.items():
        if all(marker in prompt for marker in markers):
            return name
    return None


def classify_task(request: ChatCompletionRequest) -> str | None:
    """Return the utility task name, or ``None`` for a real chat.

    An unrecognised ``metadata.task`` value is still returned: it signals a
    utility request even when the name is unknown.
    """
    explicit = _task_from_metadata(request)
    if explicit is not None:
        return explicit

    return _task_from_prompt_shape(request)
