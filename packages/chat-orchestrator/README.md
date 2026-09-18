# chat-orchestrator

Chat orchestration service managing conversation flow and agent coordination.

## Structure

- `src/` - Source code
- `tests/` - Test suite

## Application seam

`chat_orchestrator.application` is the transport-independent chat execution shared by
every adapter. It owns message conversion (`to_langchain_messages`, `flatten_content`),
reply extraction (`extract_reply_text`), the visible-token filter (`is_visible_token`),
the recursion limit and the per-request timeout.

| Adapter | Entry point |
|---|---|
| `api/v1.py` (OpenAI-compatible HTTP) | `run_chat` (buffered), `stream_chat` (SSE) |
| `packages/prete-chat` (Chainlit native UI) | `stream_chat` with a Chainlit callback handler passed in `config` |

`stream_chat` yields LangGraph's native `(chunk, metadata)` tuples; each adapter filters
them itself. Nothing in the core imports Chainlit, and the module imports no web
framework.

## OpenAI-compatible API

LibreChat, OpenWebUI, and any OpenAI-compatible SDK connect to this service as a
model provider. Every `/v1/*` route requires a bearer key.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/v1/models` | Bearer | Advertises the single model `prete-a-porter` |
| `POST` | `/v1/chat/completions` | Bearer | Chat completion, buffered (`stream=false`) or SSE (`stream=true`) |

### Required environment

| Variable | Purpose |
|---|---|
| `ORCHESTRATOR_API_KEY` | Bearer key for `/v1/*`. Must not be named `OPENAI_API_KEY`. |
| `CHAT_REQUEST_TIMEOUT_SECONDS` | Wall-clock bound for one request (default 180). Buffered requests return `504` on expiry; streams emit an in-band `timeout` error before `[DONE]`. |

### Identity headers

Per-user quota and thread correlation come from headers the client shell forwards.
Both header families are accepted:

| Header | Client | Used for | Fallback when absent |
|---|---|---|---|
| `X-OpenWebUI-User-Id` | OpenWebUI | Rate-limit key | |
| `X-User-ID` | LibreChat | Rate-limit key | `anonymous` — all such callers share one bucket |
| `X-OpenWebUI-Chat-Id` | OpenWebUI | Thread correlation | |
| `X-Conversation-ID` | LibreChat | Thread correlation | A fresh UUID per request — no cross-turn context |
| `X-OpenWebUI-User-Email` / `X-User-Email` | either | Logging only | `None` |
| `X-Message-ID` | LibreChat | Log correlation | `None` |

The namespaced OpenWebUI names win when both families are present: they are
unambiguous, while `X-User-ID` is a generic name. OpenWebUI sends its headers only
with `ENABLE_FORWARD_USER_INFO_HEADERS=True`; LibreChat sends them because
`deploy/librechat/librechat.yaml` configures them. Both fallbacks log a warning
once per process.

### Utility-task bypass (OpenWebUI)

OpenWebUI issues **eight** auxiliary model requests, all to the same
`/v1/chat/completions` endpoint as real chat. These are classified and answered
with a bare LLM call — no homily system prompt, no tools — so they never run the
ReAct loop.

LibreChat issues no auxiliary requests in this deployment: `titleConvo: false` and
`TITLE_CONVO=false` disable title generation, and no other LibreChat task calls the
model. If a title model is enabled later, point it at a provider, not at
`prete-a-porter`.

| Task | Env var | Default | Detected as |
|---|---|---|---|
| Chat title | `ENABLE_TITLE_GENERATION` | `True` | `title_generation` |
| Tags | `ENABLE_TAGS_GENERATION` | `True` | `tags_generation` |
| Follow-up suggestions | `ENABLE_FOLLOW_UP_GENERATION` | `True` | `follow_up_generation` |
| Autocomplete | `ENABLE_AUTOCOMPLETE_GENERATION` | `True` | `autocomplete_generation` |
| Retrieval query rewriting | `ENABLE_RETRIEVAL_QUERY_GENERATION` | `True` | `query_generation` |
| Web search query rewriting | `ENABLE_SEARCH_QUERY_GENERATION` | `True` | `query_generation` |
| Image prompt generation | `ENABLE_IMAGE_PROMPT_GENERATION` | — | not detected (no images) |
| Context compaction summary | `ENABLE_CONTEXT_COMPACTION` | `False` | `context_compaction` |

Detection signals, in order:

1. `metadata.task` present and non-blank → that name, whatever it is.
2. Prompt starts with `### Task:` and matches a marker pair → the task name.

Markers are anchored on each template's `### Output:` line and its JSON key, not
on the prose in `### Guidelines:`. Administrators can reword the guidelines; the
JSON key is what OpenWebUI's own parser requires, so it is the stable anchor.

Two omissions from the reference implementation are fixed here:

- **Autocomplete** fires as the user types and is the highest-frequency task. It
  is detected by `autocompletion system` + `"text"`.
- **Context compaction** sends the entire older conversation for summarisation.
  It is detected by its `{{COMPACTED_MESSAGES}}` / `{{RECENT_MESSAGES}}`
  placeholders.

### No follow-up heuristic

Unlike the reference implementation, a short third-turn message is **not**
treated as a conversational follow-up. In a pure RAG backend, skipping retrieval
on "tell me more" is correct. This agent is tool-driven, and a short message here
is an *action authorisation*: after the assistant offers to generate a homily,
`sì`, `ok` or `vai` mean "generate it now", which requires the graph and the
liturgical tools. Bypassing the graph on those turns silently breaks the primary
flow. The cost is one extra LLM call on a genuinely conversational turn.

### Task models — the cheaper alternative

`TASK_MODEL` (local connections) and `TASK_MODEL_EXTERNAL` (OpenAI-compatible
connections) route all auxiliary work to a different model. Both default to
**Current Model**, which is why this backend receives those requests at all.

Prefer a dedicated task model over disabling the features when a second model is
available: titles and tags keep working at negligible cost. If the named model is
unavailable, OpenWebUI **falls back to the chat's model** rather than failing, so
a misconfigured value silently restores the expensive path.

This deployment disables the tasks because only one model is connected. The
backend bypass exists regardless, because it must not depend on an
administrator's UI settings. The task model removes the *cost*; the bypass
removes the *wrongness*.

Compose sets every `ENABLE_*_GENERATION=False`. Persisted OpenWebUI settings
override environment defaults, so for an existing install also disable them in
**Admin Panel > Settings > Interface > Tasks**. Do not use
`RESET_CONFIG_ON_START` — it clears all persisted OpenWebUI configuration.
