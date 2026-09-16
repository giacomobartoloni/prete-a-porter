# chat-orchestrator

Chat orchestration service managing conversation flow and agent coordination.

## Structure

- `src/` - Source code
- `tests/` - Test suite
## OpenAI-compatible API

OpenWebUI connects to this service as a model provider. Every `/v1/*` route
requires a bearer key.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/v1/models` | Bearer | Advertises the single model `prete-a-porter` |
| `POST` | `/v1/chat/completions` | Bearer | Chat completion (buffered) |

### Required environment

| Variable | Purpose |
|---|---|
| `ORCHESTRATOR_API_KEY` | Bearer key for `/v1/*`. Must not be named `OPENAI_API_KEY`. |

### Identity headers

Per-user quota and thread correlation come from headers OpenWebUI forwards when
`ENABLE_FORWARD_USER_INFO_HEADERS=True` is set on its container:

| Header | Used for | Fallback when absent |
|---|---|---|
| `X-OpenWebUI-User-Id` | Rate-limit key | `anonymous` — all such callers share one bucket |
| `X-OpenWebUI-Chat-Id` | Thread correlation | A fresh UUID per request — no cross-turn context |
| `X-OpenWebUI-User-Email` | Logging only | `None` |

Both fallbacks log a warning once per process.
