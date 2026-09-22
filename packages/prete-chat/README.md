# prete-chat

Chainlit native conversational UI for Prête-à-Porter. The service **imports the
`chat-orchestrator` application seam in-process**, so chat execution has one
implementation shared with the OpenAI-compatible `/v1` surface, and the core
never depends on Chainlit.

## Layout

```text
packages/prete-chat/
  .chainlit/config.toml     Chainlit configuration (name, language, cot, starters)
  chainlit.md               readme shown in the UI ("Leggimi")
  public/                   logo, favicon, custom CSS
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
| `DATABASE_URL` | `postgresql+asyncpg://…` enables persistence **and** login; anything else keeps POC mode (no history, no auth) |
| `CHAINLIT_AUTH_SECRET` | signs the session cookie; required with persistence (`openssl rand -hex 32`) |
| `CHAINLIT_URL` | public URL of the native UI (cookies, redirects) |
| `LOG_LEVEL` / `LOG_JSON_FORMAT` | honoured here (`configure_logging()` is called at startup) |

## Persistence and users

Conversation history for the native UI is stored by Chainlit's SQLAlchemy data
layer in the service's own PostgreSQL database (schema:
`deploy/chainlit/init.sql`, operations: `deploy/chainlit/README.md`). The
orchestrator core stays stateless: only user/assistant text is reconstructed as
model context on resume; tool steps, notices and the welcome message never are.

Accounts are operator-provisioned (Chainlit has no stock signup), with bcrypt
hashes (cost 10) in the Chainlit user metadata:

```bash
uv run python scripts/create_user.py --email don@example.com --name "Don Mario"
```

## Branding and language

| Item | Where |
|---|---|
| Name, description, `cot = "tool_call"`, logo, custom CSS | `.chainlit/config.toml` |
| Logo / favicon | `public/logo_light.png`, `public/logo_dark.png` (theme-aware `GET /logo`, 500×500) and `public/favicon.png` (64×64, area-averaged with premultiplied alpha from the same asset) — the legacy frontend ships only `frontend/public/logo.png`, no favicon of its own |
| Brand colours | `public/custom.css` (Chainlit's shadcn CSS variables only; no frontend patching) |
| Typography and chat bubbles | `public/custom.css`, ported from the legacy frontend: Inter (UI/body), Playfair Display (headings), JetBrains Mono (code), the user bubble gradient `#c06e22 → #7c1dff` and the card-style assistant bubble, both with the 16px/6px radii and 12px padding from `frontend/src/components/Chat.tsx` |
| Welcome readme ("Leggimi") | `chainlit.md` at the package root — Chainlit's app root, not `public/` |
| Empty-state suggestions | `@cl.set_starters` in `app.py` |
| Italian strings | Chainlit's bundled `it` catalogue (`[UI] language = "it"`) |

`custom_css` carries a `?v=` cache-buster (`/public/custom.css?v=N`): Chainlit serves `public/` with a long-lived cache entry, so a browser would otherwise keep the old stylesheet after a deploy. Bump `N` whenever `custom.css` changes.

Per-key translation overrides are deferred on purpose: `load_translation()`
returns the file found in `.chainlit/translations/` **instead of** the bundled
catalogue, and that directory is generated at startup (ignored in git), so an
override means committing a full catalogue copy and re-checking it on every
Chainlit bump. Revisit only if a string actually needs changing.

## Preferences and refinement actions

The composer's settings panel pins three conversation preferences (Destinatari,
Tono, Lunghezza): Italian labels in `preferences.py`, core values submitted to
`chat_orchestrator.application.ChatPreferences`. The selection becomes one
deterministic line in the invocation's system prompt; nothing is persisted by
the core and an untouched panel pins nothing. Changed settings persist with the
thread (Chainlit session metadata) and are restored on resume.

Each answer carries four refinement actions (`actions.py`): the payload holds a
typed operation, the adapter composes the Italian user turn — "Accorcia l'ultima
omelia, ..." — and re-enters the normal run path, so the model sees plain prose
and the history stays coherent. Actions run inside Chainlit's action request,
not the message task, so the Stop button does not cancel them.
