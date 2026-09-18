# prete-chat

Chainlit native conversational UI for Prête-à-Porter. The service **imports the
`chat-orchestrator` application seam in-process**, so chat execution has one
implementation shared with the OpenAI-compatible `/v1` surface, and the core
never depends on Chainlit.

## Layout

```text
packages/prete-chat/
  .chainlit/config.toml     Chainlit configuration (name, language, cot, starters)
  public/                   branding, welcome text, custom CSS
  src/prete_chat/
    app.py                  Chainlit entry point: lifecycle hooks and wiring
    history.py              conversation history accumulation/reconstruction
    runner.py               core bridge (quota, streaming)
    errors.py               exception -> Italian user-facing text
    labels.py               tool name -> Italian step label
  scripts/create_user.py    operator provisioning (P3)
  tests/                    adapter unit tests (core stubbed at the runner seam)
```

## Running

```bash
# Whole stack including agents (from the repository root)
docker compose -f docker-compose.yml -f deploy/chainlit/docker-compose.chainlit.yml up -d --build

# Native UI
open http://localhost:3003
```

## Environment

| Variable | Purpose |
|---|---|
| LLM provider keys + `*_MODEL_NAME` / `OPENAI_BASE_URL` | same provider selection as the core (`a2a_protocol.llm.create_llm`) |
| `A2A_LITURGY_URL` / `A2A_HOMILY_URL` / `A2A_BASIC_AUTH_*` | the in-process core calls the agents directly |
| `CHAT_REQUEST_TIMEOUT_SECONDS` | same wall-clock bound as `/v1` (default 180) |
| `RATE_LIMIT_MESSAGES_PER_HOUR` / `_PER_DAY` | per-user quota, same defaults as `/v1` (5 / 20) |
| `RATE_LIMIT_DB_PATH` | this container's own SQLite file; never shared with the orchestrator |
| `LOG_LEVEL` / `LOG_JSON_FORMAT` | honoured here (`configure_logging()` is called at startup) |

Status: the POC has no persistence and no authentication; both arrive with the
Postgres data layer in the next phase.
