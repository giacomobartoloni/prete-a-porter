# Prete-à-porter

**Prete-à-porter** is an AI-powered Catholic homily generator — born as a joke, looking for a provocative use case for AI, and turned into an excuse to learn agentic engineering, LLM interaction, agents, and RAG technologies. Drop in the Sunday Gospel, pick a tone, and get a pulpit-ready text in seconds. It is not a serious tool — it is a serious question dressed as provocation. What happens when we delegate to AI what by definition requires a human being? The homily theme is deliberately uncomfortable: a testbed to probe the limits of language models on the most human form of expression that exists: the homily.

It is also a multi-agent A2A (Agent-to-Agent) system with WebSocket orchestration, coordinating specialized agents for liturgical data retrieval and homily generation through a Next.js chat interface.

## What you'll learn

This project started as a way to force a conversation about architecture instead of just wiring up APIs. If you go through the code, here is what you will run into:

**How to design an inter-agent protocol from scratch.** The A2A layer implements JSON-RPC 2.0 over HTTP. Client, server, transport — a few hundred lines, no framework abstraction hiding the details. Request IDs, error codes, retry logic, what happens when one service is down but the others are not.

**Three LangGraph patterns in one repo.** The chat orchestrator runs a ReAct loop — call the LLM, pick a tool, execute, repeat. The liturgy agent is a linear pipeline — parse, fetch, format, done. The homily agent uses intent routing — same entry point dispatches to generate, refine, or adjust-tone depending on what the request says. Same library, three different state machine shapes, comparable side by side.

**RAG without cloud dependencies.** ChromaDB and sentence-transformers locally. No Pinecone, no OpenAI embeddings. The pipeline is straightforward — parse documents, chunk them, embed them, store them, retrieve them — but it is all self-contained. If you have only used managed vector stores, this shows you what happens underneath.

**An LLM abstraction that actually switches providers.** The factory picks the first available API key — Anthropic, Google, or OpenAI — and supports OpenAI-compatible endpoints (Fireworks, Groq, Ollama) without code changes. Swap providers by changing one environment variable.

**Testing strategies for agentic systems.** Mock LLMs via `TEST_MODE`, checkpointer test doubles, Playwright browser tests for WebSocket auth, contract tests that start real agent servers and verify the protocol end to end.

**Honest documentation.** Alongside the code, AGENTS.md does not just describe the system — it documents active bugs, trade-offs for every design decision (seven ADRs with rationale and cost), and links to a full code review report with 39 findings. The contract JSON files even document known unimplemented methods inline. If you are used to polished demo projects, this one leaves the scaffolding visible.

## Architecture

```
User ←→ Frontend (Next.js, port 3000)
            │ WebSocket (JWT)
            ↓
         Chat Orchestrator (FastAPI, port 8000)
            │ A2A JSON-RPC 2.0 over HTTP (Basic Auth)
           ╱                      ╲
          ↓                        ↓
   Liturgy Agent (8001)    Homily Agent (8002)
   SQLite cache, scrapers   ChromaDB + sentence-transformers
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (version 20.10 or later)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0 or later)

## Quick Start

```bash
# 1. Clone and enter the project
cd preteaporter

# 2. Copy environment template and configure
cp .env.example .env
# Edit .env: set at least one LLM API key and WS_JWT_SECRET

# 3. Create persistent data directory
mkdir -p data

# 4. Start all services
docker compose up --build

# Or run in background
docker compose up --build -d
```

Wait ~30s for all services to become healthy.

## Usage

1. Open **http://localhost:3000** in your browser
2. Register a new account (email + password)
3. Log in to access the chat interface
4. Type a message like *"I need a homily for next Sunday"*
   — the system fetches the readings and offers to generate a homily
5. Ask *"Generate a homily"* to produce a full 4-section homily

## Services

| Service | Port | Description | Dockerfile |
|---------|------|-------------|------------|
| frontend | 3000 | Next.js 14 chat UI | `frontend/Dockerfile` |
| chat-orchestrator | 8000 | WebSocket server, A2A coordinator | `packages/chat-orchestrator/Dockerfile` |
| liturgy-agent | 8001 | Liturgical data retrieval | `packages/liturgy-agent/Dockerfile` |
| homily-agent | 8002 | Homily generation (RAG) | `packages/homily-agent/Dockerfile` |
| a2a-inspector | 8080 | A2A debug tool (requires separate image build) | External |

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Note 1 | Claude provider |
| `GOOGLE_API_KEY` | Note 1 | Gemini provider |
| `OPENAI_API_KEY` | Note 1 | OpenAI / compatible (Fireworks, Groq, Ollama) |
| `WS_JWT_SECRET` | **Yes** | WebSocket JWT signing (frontend + orchestrator) |
| `AUTH_SECRET` | **Yes** | NextAuth session signing |
| `A2A_BASIC_AUTH_USERNAME` | **Yes** | Inter-agent HTTP Basic Auth |
| `A2A_BASIC_AUTH_PASSWORD` | **Yes** | Inter-agent HTTP Basic Auth |

> **Note 1**: Set exactly **one** LLM API key. Provider is selected by priority:
> `ANTHROPIC_API_KEY` → `GOOGLE_API_KEY` → `OPENAI_API_KEY`.
> See `.env.example` for compatible providers and model names.

## Health Checks

All services expose `GET /health`:

```bash
curl http://localhost:3000/api/health   # frontend
curl http://localhost:8000/health       # chat-orchestrator
curl http://localhost:8001/health       # liturgy-agent
curl http://localhost:8002/health       # homily-agent
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

Run this **once** before first use (local development) or ensure the files are mounted into the homily-agent container (Docker — see `docker-compose.yml`).

## Testing A2A Protocol

```bash
# Ping liturgy agent
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {}}'

# Ping homily agent
curl -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {}}'

# Get liturgical readings
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_readings", "params": {"occasion": "mass"}}'
```

## A2A Inspector

A web-based debug tool for A2A agents. Build and run from the [upstream repo](https://github.com/a2aproject/a2a-inspector):

```bash
git clone https://github.com/a2aproject/a2a-inspector.git
cd a2a-inspector
docker build -t a2a-inspector .
cd ../preteaporter
docker compose up -d a2a-inspector
```

Access at **http://localhost:8080**, then enter an agent URL
(e.g., `http://liturgy-agent:8001`).

## Local Development (without Docker)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/):

```bash
# Install dependencies for a package
cd packages/chat-orchestrator
uv sync

# Run tests
cd packages/liturgy-agent
uv run pytest

# Run an agent directly
cd packages/homily-agent
uv run python -m homily_agent.main --port 8002
```

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
