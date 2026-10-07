# Prete-à-porter

**Prete-à-porter** is an AI-powered Catholic homily generator — born as a joke, looking for a provocative use case for AI, and turned into an excuse to learn agentic engineering, LLM interaction, agents, and RAG technologies. Drop in the Sunday Gospel, pick a tone, and get a pulpit-ready text in seconds. It is not a serious tool — it is a serious question dressed as provocation. What happens when we delegate to AI what by definition requires a human being? The homily theme is deliberately uncomfortable: a testbed to probe the limits of language models on the most human form of expression that exists: the homily.

It is also a multi-agent A2A system whose agent runtime can be consumed by replaceable chat shells: OpenWebUI and LibreChat through an OpenAI-compatible HTTP API, a native Chainlit UI through the shared application seam, and the legacy Next.js frontend through WebSocket.

## What you'll learn

This project started as a way to force a conversation about architecture instead of just wiring up APIs. If you go through the code, here is what you will run into:

**How to design an inter-agent protocol from scratch.** The A2A layer implements JSON-RPC 2.0 over HTTP. Client, server, transport — a few hundred lines, no framework abstraction hiding the details. Request IDs, error codes, retry logic, what happens when one service is down but the others are not.

**Three LangGraph patterns in one repo.** The chat orchestrator runs a ReAct loop — call the LLM, pick a tool, execute, repeat. The liturgy agent is a linear pipeline — parse, fetch, format, done. The homily agent uses intent routing — same entry point dispatches to generate, refine, or adjust-tone depending on what the request says. Same library, three different state machine shapes, comparable side by side.

**RAG without cloud dependencies.** ChromaDB and sentence-transformers locally. No Pinecone, no OpenAI embeddings. The pipeline is straightforward — parse documents, chunk them, embed them, store them, retrieve them — but it is all self-contained. If you have only used managed vector stores, this shows you what happens underneath.

**An LLM abstraction that actually switches providers.** The factory picks the first available API key — Anthropic, Google, or OpenAI — and supports OpenAI-compatible endpoints (Fireworks, Groq, Ollama) without code changes. Swap providers by changing one environment variable.

**Testing strategies for agentic systems.** LangChain-compatible fake models and full-graph `TEST_MODE`, Playwright browser tests for WebSocket auth, PostgreSQL-backed Chainlit authentication integration, and live HTTP contract tests against the real `/v1` boundary — not only mocked units. CI also covers package unit tests, OpenAI-compatible boundary contracts, and a Chainlit + PostgreSQL auth smoke path.

**Honest documentation.** Alongside the code, AGENTS.md does not just describe the system — it documents active bugs, trade-offs for every design decision (nine ADRs with rationale and cost), and links to a full code review report with 39 findings. The contract JSON files even document known unimplemented methods inline. If you are used to polished demo projects, this one leaves the scaffolding visible.

## Architecture

```
   OpenWebUI (3001)                  LibreChat (3002, optional)
        │                                   │
        └──────── OpenAI-compatible /v1 ────┘
                         │
                         ▼
              Chat Orchestrator (8000)
                         │
                         │ A2A JSON-RPC / HTTP Basic Auth
                    ┌────┴────┐
                    ▼         ▼
             Liturgy Agent  Homily Agent


   Next.js (3000, transitional)
             │
             │ WebSocket + JWT
             ▼
       Chat Orchestrator


   Chainlit / prete-chat (3003, optional)
             │
             │ in-process application seam
             ▼
   chat_orchestrator.application
```

The base stack runs OpenWebUI and the legacy Next.js frontend side by side.
LibreChat and the native Chainlit UI are available as optional Compose overlays.
The orchestrator is **stateless**: every request carries its own message history
and no checkpointer exists. Chainlit imports `chat_orchestrator.application`
in-process and does not call `/v1`.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (version 20.10 or later)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0 or later)

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/giacomobartoloni/prete-a-porter.git
cd prete-a-porter

# 2. Copy environment template and configure
cp .env.example .env

# 3. Create the persistent data directory
mkdir -p data

# 4. Start the base stack
docker compose up -d --build

# 5. Wait until the orchestrator reports healthy
until curl -sf localhost:8000/health > /dev/null; do sleep 2; done; echo ready
```

Then open **http://localhost:3001** (OpenWebUI) or **http://localhost:3000**
(the Next.js chat). See *Interfaces* below for the full shell map.

### Optional chat shells

Chainlit native UI ([deploy/chainlit/README.md](deploy/chainlit/README.md)):

```bash
docker compose \
  -f docker-compose.yml \
  -f deploy/chainlit/docker-compose.chainlit.yml \
  up -d --build
```

Then open **http://localhost:3003**.

LibreChat ([deploy/librechat/README.md](deploy/librechat/README.md)):

```bash
docker compose \
  -f docker-compose.yml \
  -f deploy/librechat/docker-compose.librechat.yml \
  up -d
```

Then open **http://localhost:3002**.

### Required in `.env`

| Variable | Why |
|---|---|
| one of `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY` | The agents cannot answer without a model. The factory picks the first one set, in that order. |
| `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME` | Only when using `OPENAI_API_KEY`, including OpenAI-compatible providers. The model name must exist in that provider's catalogue. |
| `WS_JWT_SECRET` | WebSocket ticket signing. The orchestrator refuses to start without it. |
| `AUTH_SECRET` | NextAuth session signing, for the Next.js frontend. |
| `ORCHESTRATOR_API_KEY` | Required for `/v1/*`; a deployment with it unset is misconfigured and fails loudly. |
| `WEBUI_SECRET_KEY` | OpenWebUI session signing. |
| `A2A_BASIC_AUTH_USERNAME` / `_PASSWORD` | Inter-agent HTTP Basic Auth. |

Generate the four base-stack secrets with:

```bash
openssl rand -hex 32   # WS_JWT_SECRET, ORCHESTRATOR_API_KEY, WEBUI_SECRET_KEY
openssl rand -hex 32   # AUTH_SECRET
```

`.env.example` carries safe placeholders for all of them. Note that
`ORCHESTRATOR_API_KEY` must **not** be named `OPENAI_API_KEY`: that name is the
upstream provider key, and reusing it breaks provider selection.

Chainlit and LibreChat require additional variables when their Compose overlays
are enabled; see [`.env.example`](.env.example),
[deploy/chainlit/README.md](deploy/chainlit/README.md), and
[deploy/librechat/README.md](deploy/librechat/README.md).

### Verify the stack

```bash
curl -s localhost:8000/health                                   # {"status":"ok",...}
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/v1/models   # 401, as expected
KEY=$(awk -F= '/^ORCHESTRATOR_API_KEY=/{print $2}' .env)
curl -s -H "Authorization: Bearer $KEY" localhost:8000/v1/models    # the model card
```

If a chat request returns `500`, the message is deliberate and Italian. The cause is
in the orchestrator's logs:

```bash
docker compose logs chat-orchestrator --tail=40 | grep -iE "error|exception"
```

The most common one is a provider-side failure — an expired key, a suspended billing
account, or a model name absent from the catalogue. `GET {OPENAI_BASE_URL}/models`
with the same key distinguishes them.

### Stopping

```bash
docker compose down          # keep volumes
docker compose down -v       # also drop OpenWebUI's data and the frontend DB
```

## Interfaces

Replaceable chat shells share one agent runtime. OpenWebUI and LibreChat speak the
OpenAI-compatible `/v1` boundary; Chainlit imports the application seam in-process;
the Next.js frontend still uses the transitional WebSocket path.

| Interface | Local URL | Runtime path | Persistence / Auth | Deployment |
|---|---|---|---|---|
| OpenWebUI | **http://localhost:3001** | `POST /v1/chat/completions` | OpenWebUI-owned | base stack |
| Next.js | **http://localhost:3000** | WebSocket + JWT | NextAuth + SQLite | base stack, transitional |
| LibreChat | **http://localhost:3002** | `POST /v1/chat/completions` | LibreChat + MongoDB | optional overlay |
| Chainlit | **http://localhost:3003** | in-process application seam | Chainlit + PostgreSQL | optional overlay |

OpenWebUI listens on **3001, not 3000**, because the Next.js frontend still owns 3000.
When the cutover removes that service, change the `openwebui` ports entry to
`"127.0.0.1:3000:8080"` in `docker-compose.yml` so public traffic still reaches
OpenWebUI only through Caddy, not via a directly published host port.

OpenWebUI needs one manual step on first run: create the admin account, then select the
`prete-a-porter` model. The connection itself is preconfigured. Chainlit does **not**
use `ORCHESTRATOR_API_KEY`; it never calls `/v1`.

## Services

| Service | Port | Description | Dockerfile |
|---|---|---|---|
| openwebui | 127.0.0.1:3001 → 8080 | OpenWebUI chat UI | `ghcr.io/open-webui/open-webui:v0.11.4` |
| frontend | 3000 | Next.js 14 chat UI (transitional) | `frontend/Dockerfile` |
| chat-orchestrator | 8000 | WebSocket + OpenAI-compatible API, A2A coordinator | `packages/chat-orchestrator/Dockerfile` |
| liturgy-agent | 8001 | Liturgical data retrieval | `packages/liturgy-agent/Dockerfile` |
| homily-agent | 8002 | Homily generation (RAG) | `packages/homily-agent/Dockerfile` |
| caddy | 80, 443 | TLS reverse proxy (production) | `caddy:2-alpine` |
| a2a-inspector | 8080 | A2A debug tool (requires a separate image build) | External |

### Optional overlay services

| Service | Port | Description |
|---|---|---|
| `librechat` | 127.0.0.1:3002 → 3080 | Optional OpenAI-compatible chat shell |
| `librechat-mongodb` | internal only | LibreChat persistence |
| `prete-chat` | 127.0.0.1:3003 → 8000 | Chainlit native UI; imports the application seam |
| `prete-chat-db` | internal only | PostgreSQL for Chainlit users/history |

## Environment Variables

See **Required in `.env`** above for the mandatory set, and [`.env.example`](.env.example)
for the complete template with provider examples.

The LLM provider is selected by the **first** key found, in this order:

```
ANTHROPIC_API_KEY -> GOOGLE_API_KEY -> OPENAI_API_KEY
```

Set exactly **one**. OpenAI-compatible providers (Fireworks, Groq, Together, Ollama,
vLLM) all use `OPENAI_API_KEY` plus `OPENAI_BASE_URL` and `OPENAI_MODEL_NAME`.

## Health Checks

All base-stack agent services expose `GET /health` (exempt from A2A Basic Auth).
The Next.js frontend has no such route. Overlay health endpoints exist only when
that overlay is running.

```bash
curl http://localhost:8000/health       # chat-orchestrator
curl http://localhost:8001/health       # liturgy-agent (exempt from Basic Auth)
curl http://localhost:8002/health       # homily-agent (exempt from Basic Auth)
curl http://localhost:3001/health       # openwebui
curl -o /dev/null -w '%{http_code}\n' http://localhost:3000/api/config   # frontend: 200
curl http://localhost:3003/health       # Chainlit, when the overlay is running
```

## RAG Knowledge Base

The homily agent uses Retrieval-Augmented Generation (RAG) with a ChromaDB vector store backed by sentence-transformers embeddings. Two sources feed the knowledge base:

| Source | Format | Download |
|--------|--------|----------|
| **Bibbia CEI 2008** (Italian Bible) | HTML (75 books) | `support/download.sh` |
| **Catechismo della Chiesa Cattolica** (Catechism) | PDF | `support/download.sh` |

```bash
./support/download.sh
```

Run this **once** before first use. Then build the corpus — either locally
(`cd packages/homily-agent && uv sync --extras ml && uv run python scripts/ingest_corpus.py`)
or, for Docker deployments, through the one-off `rag-ingest` service:

```bash
mkdir -p data/chroma_db data/chroma_cache
docker compose build homily-agent
docker compose run --rm rag-ingest --reset
```

The corpus is persisted in `data/chroma_db/` and mounted into `homily-agent`
(see `docker-compose.yml`); `data/chroma_cache/` holds the ONNX embedding model
so both ingestion and retrieval use the same embedding function.

## Testing A2A Protocol

Agent JSON-RPC methods require HTTP Basic Auth. `GET /health` does not.

```bash
set -a
source .env
set +a

# Ping liturgy agent
curl \
  -u "$A2A_BASIC_AUTH_USERNAME:$A2A_BASIC_AUTH_PASSWORD" \
  -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {}}'

# Ping homily agent
curl \
  -u "$A2A_BASIC_AUTH_USERNAME:$A2A_BASIC_AUTH_PASSWORD" \
  -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {}}'

# Get liturgical readings
curl \
  -u "$A2A_BASIC_AUTH_USERNAME:$A2A_BASIC_AUTH_PASSWORD" \
  -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_readings", "params": {"occasion": "mass"}}'
```

## A2A Inspector

A web-based debug tool for A2A agents. Build and run from the [upstream repo](https://github.com/a2aproject/a2a-inspector):

```bash
git clone https://github.com/a2aproject/a2a-inspector.git
cd a2a-inspector
docker build -t a2a-inspector .
cd ../prete-a-porter
docker compose up -d a2a-inspector
```

Access at **http://localhost:8080**, then enter an agent URL
(e.g., `http://liturgy-agent:8001`).

## Local Development (without Docker)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
# Install dependencies for a package (include test extras)
cd packages/chat-orchestrator
uv sync --extra dev

# Run tests
uv run pytest

# Run an agent directly
cd packages/homily-agent
uv run python -m homily_agent.main --port 8002
```

CI includes package unit tests (`.github/workflows/unit-tests.yml`), live HTTP
contract tests for the OpenAI-compatible boundary
(`.github/workflows/contract-tests.yml`), and a PostgreSQL-backed Chainlit
authentication smoke test (`.github/workflows/prete-chat-postgres.yml`).

## Troubleshooting

```bash
# View logs
docker compose logs -f

# Rebuild after code changes
docker compose up --build

# Stop (keep data)
docker compose down

# Full cleanup
docker compose down -v --rmi all
```

## Architecture Documentation

See [AGENTS.md](AGENTS.md) for the full architecture guide, data models, workflows, configuration reference, and known issues.

## License

GNU AGPLv3 — see [LICENSE](LICENSE) for details.
