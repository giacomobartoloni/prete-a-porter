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
  public/                   logo, favicon, trimmed brand mark, custom CSS
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

The command runs inside the service container (the database publishes no port);
the operator procedure — interactive and non-interactive forms, semantics and
verification query — lives in `deploy/chainlit/README.md` → Users.

## Branding and language

| Item | Where |
|---|---|
| Name, description, `cot = "tool_call"`, logo, custom CSS | `.chainlit/config.toml` |
| Logo / favicon | `public/logo_light.png`, `public/logo_dark.png` (500×500; byte-identical today), `public/favicon.png` (64×64, area-averaged with premultiplied alpha from the same asset) and `public/logo_mark.png` (96×96, trimmed to the artwork's alpha box) — the legacy frontend ships only `frontend/public/logo.png`, no favicon of its own |
| Mark URL | `[UI] logo_file_url` / `default_avatar_file_url` point at `public/logo_light.png?v=1`, not at Chainlit's `GET /logo`. That route answers with plain `last-modified`/`etag`, and browsers kept serving a superseded artwork from their own cache after a deploy (seen on 2026-09-22: the mark reported as missing was a stale response). The static path is versioned by URL, like `custom.css`; bump `v=` when the artwork changes. Only the login screen still asks `/logo`, because no config reaches the page before authentication |
| Sidebar header | `public/custom.css`: the mark plus the wordmark on the header's first line, the collapse trigger on that line's right edge (`#sidebar-trigger-button`, lifted out of Chainlit's control row with `position: absolute`), then search and new chat as full-width rows with their label beside the icon — the arrangement the owner asked for on 2026-09-22 (Gemini's sidebar) and the shape the legacy sidebar gave its "new conversation" button (`frontend/src/components/Sidebar.tsx`, "Top section: logo + toggle" plus `flex items-center gap-2 w-full px-3 py-2 rounded-lg`). The wordmark is a pseudo-element and the row labels (`Nuova Chat`, `Cerca`) are `::after` literals, because `content` reads neither the config nor the catalogue: the wordmark must move with `[UI] name`, the labels with a Chainlit rename, and the bundled `it` tooltips still fire on hover. No DOM patching |
| Collapsed sidebar | Chainlit collapses off-canvas (`data-collapsible="offcanvas"`) and puts an open-sidebar trigger in the main header (`#header`), beside the new-chat button. `public/custom.css` gives that trigger the brand mark at rest (`logo_mark.png` at 24px, with the same dark-theme rim light as the other marks) and swaps it for the stock glyph on hover — Gemini's trade, requested by the owner the same day, tooltip included ("Apri barra laterale", already in the `it` catalogue). The header's left group stacks (mark, then new chat below it, the rail order of the reference), which grows `#header` from its stock 60px to ~91px; both rules are scoped with `:has(#sidebar-trigger-button)`, i.e. only while the panel is closed, so the open layout is untouched. Only `background-image` is overridden, never the `background` shorthand, so the stock hover pill survives |
| Brand colours | `public/custom.css` (Chainlit's shadcn CSS variables only; no frontend patching) |
| Typography and chat bubbles | `public/custom.css`, ported from the legacy frontend: Inter (UI/body), Playfair Display (headings), JetBrains Mono (code), the user bubble gradient `#c06e22 → #7c1dff` and the card-style assistant bubble, both with the 16px/6px radii and 12px padding from `frontend/src/components/Chat.tsx` |
| Welcome readme ("Leggimi") | `chainlit.md` at the package root — Chainlit's app root, not `public/` |
| Empty-state suggestions | `@cl.set_starters` in `app.py` |
| Italian strings | Chainlit's bundled `it` catalogue (`[UI] language = "it"`) |

`custom_css` carries a `?v=` cache-buster (`/public/custom.css?v=N`): Chainlit serves `public/` with a long-lived cache entry, so a browser would otherwise keep the old stylesheet after a deploy. Bump `N` whenever `custom.css` changes. The mark URLs carry the same buster for the same reason (see the Mark URL row above) — bump theirs whenever the artwork changes.

**Dark-theme mark decision (2026-09-22).** The mark is a near-black 3D glyph; on Chainlit's stock dark surfaces its lower faces vanish, so `custom.css` lifts the dark palette into graphite (`--background` 13 % → 22 %, cards 18 % → 26 %, sidebar 9 % → 18 %). Four alternatives were prototyped and reviewed with the owner — a light plate behind the mark, and three reversed artworks (luminance inversion; flat light monochrome; light faces with preserved shading) — and **the owner chose to keep the original artwork on the graphite surfaces**. Graphite alone did not hold on the live surfaces: seeing the app in the dark theme the owner reported the centred mark as absent at 200 px, and chose the legacy frontend's own remedy — `html.dark img.logo` and the sidebar brand row's mark now carry `frontend/src/app/globals.css`'s `.dark .logo-glow` (a 2 px white-10 % drop shadow that separates the silhouette from the ground). The artwork is unchanged; reversed variants stay rejected. Consequence, recorded as required when relying on the logo exemption of WCAG 2.2 SC 1.4.11: the mark's faces stay at roughly 1.4–1.7:1 against the dark surface, below the 3:1 non-text threshold — the rim light is the separation cue, and the product name is available as text everywhere the mark appears (page title, sidebar wordmark, readme); the brand row's 28 px mark is decorative next to that wordmark. Revisit only if a designer supplies an approved reversed asset — the previous prototyping script is gone, but the transformation is one luminance remap of the PNG.

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
