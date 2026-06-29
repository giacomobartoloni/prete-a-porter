# A2A Contract Tests

Consumer-driven contract tests for the A2A (Agent-to-Agent) JSON-RPC 2.0 API.
Verifies that all agents comply with the protocol specification and produce
responses that consumers expect.

## Test Layers

The suite has four layers, each with different infrastructure requirements:

| Layer | Files | Needs agents? | Needs Docker? | Tests run |
|-------|-------|:---:|:---:|-----------|
| **A. Contract definition** | `test_liturgy_contract.py::TestContractCompliance`, `test_homily_contract.py::TestHomilyContractDefinition` | No | No | Validates contract JSON files: required fields, method names, error codes, enum values |
| **B. Live agent** | `test_liturgy_contract.py::TestLiturgyAgentContract`, `test_homily_contract.py::TestHomilyAgentContract` | Yes (ports 8001/8002) | No | Sends `message/send` requests, validates reply against Pydantic models. Skips if agent unreachable |
| **C. E2E** | `test_liturgy_agent_e2e.py`, `test_homily_agent_e2e.py`, `test_chat_orchestrator_e2e.py`, `test_scenarios_e2e.py` | Yes (ports 8000-8002) | Optional | Raw JSON-RPC POSTs + WebSocket flows. `conftest.py` can start Docker Compose automatically |
| **D. Protocol unit** | `packages/a2a-protocol/tests/` | No | No | Mock-handler unit tests of the A2A server, transport, and LLM factory |

## Test File Structure

```
contracts/
├── liturgy-agent-contract.json      # Liturgy agent API spec (3 methods)
├── homily-agent-contract.json       # Homily agent API spec (4 methods)
├── pyproject.toml                   # pytest config, dependencies
└── tests/
    ├── conftest.py                        # Fixtures: .env loader, Docker lifecycle, URL fixtures, MOCK_LITURGICAL_DATA
    ├── test_liturgy_contract.py           # Layer A+B: contract definition + live agent
    ├── test_homily_contract.py            # Layer A+B: contract definition + live agent
    ├── test_liturgy_agent_e2e.py          # Layer C: liturgy agent A2A methods
    ├── test_homily_agent_e2e.py           # Layer C: homily agent A2A methods
    ├── test_chat_orchestrator_e2e.py      # Layer C: WebSocket + chat orchestration
    └── test_scenarios_e2e.py              # Layer C: multi-step user scenarios
```

## Agents Under Test

### Liturgy Agent (port 8001)
- `agent.ping` — Health check
- `liturgy_agent.get_readings` — Fetch liturgical readings for a date
- `liturgy_agent.get_lectionary` — Get ritual lectionary for sacraments

### Homily Agent (port 8002)
- `agent.ping` — Health check
- `homily.generate` — Generate homily from liturgical data
- `homily.refine` — Refine existing homily with new preferences
- `homily.adjust_tone` — Adjust tone of an existing homily

### Chat Orchestrator (port 8000)
- `GET /health` — Health check
- `WS /ws/chat/{session_id}` — WebSocket chat with JWT auth

## Running Tests

```bash
# --- Layer A: Static contract definition tests (no agents needed) ---
cd contracts
uv run pytest tests/test_liturgy_contract.py::TestContractCompliance \
               tests/test_homily_contract.py::TestHomilyContractDefinition -v

# --- Layer A+D: All static + protocol unit tests (no agents needed) ---
cd contracts && uv run pytest tests/test_liturgy_contract.py tests/test_homily_contract.py -v
cd packages/a2a-protocol && uv run pytest -v

# --- Layer A+B+C: Full suite via Docker Compose (auto starts/stops services) ---
cd contracts && uv run pytest tests/ -v

# --- Full suite, services already running ---
cd contracts && uv run pytest tests/ -v --no-docker

# --- Specific agent ---
cd contracts && uv run pytest tests/test_liturgy_agent_e2e.py -v
cd contracts && uv run pytest tests/test_homily_contract.py -v

# --- Skip slow tests ---
cd contracts && uv run pytest tests/ -v -m "not slow"
```

## Environment Requirements

The test suite loads `.env` automatically via `conftest.py:_load_env()`.
The following variables must be set for live/E2E tests:

| Variable | Required for | Source |
|----------|-------------|--------|
| `WS_JWT_SECRET` | WebSocket tests (chat orchestrator) | `.env` (auto-loaded by conftest) |
| `A2A_BASIC_AUTH_USERNAME` | A2A HTTP requests | `.env` — **must be empty to run tests** (test helpers don't send auth headers) |
| `A2A_BASIC_AUTH_PASSWORD` | A2A HTTP requests | `.env` — **must be empty to run tests** |
| `OPENAI_API_KEY` | Homily generation (LLM) | `.env` — needed for `homily.generate`/`refine`/`adjust_tone` |
| `A2A_LITURGY_URL` | Liturgy agent URL | Defaults to `http://localhost:8001` |
| `A2A_HOMILY_URL` | Homily agent URL | Defaults to `http://localhost:8002` |

> **Note on Basic Auth:** The test helpers (`make_message_send`, `httpx.post`) do not
> send `Authorization` headers. If `A2A_BASIC_AUTH_*` are set, all live/E2E tests will
> 401. To run the full suite, start Docker with auth disabled:
> ```bash
> A2A_BASIC_AUTH_USERNAME= A2A_BASIC_AUTH_PASSWORD= docker compose up -d --build liturgy-agent homily-agent chat-orchestrator
> ```

## Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `docker_compose` | session | Starts/stops Docker Compose (skipped with `--no-docker`) |
| `_ensure_docker` | module | Depends on `docker_compose` |
| `liturgy_url` | function | Returns `http://localhost:8001` |
| `homily_url` | function | Returns `http://localhost:8002` |
| `chat_url` | function | Returns `http://localhost:8000` |
| `MOCK_LITURGICAL_DATA` | — | Module-level dict with sample readings for homily tests |

## CI

Contract tests run on push/PR to `main` via `.github/workflows/contract-tests.yml`.
The workflow installs all packages, starts liturgy + homily agents with mock LLM,
waits for health, then runs `uv run pytest tests/ -v --junit-xml=test-results.xml`.

## Test Count Summary

| File | Tests | Layer | What it covers |
|------|-------|-------|----------------|
| `test_liturgy_contract.py` | 9 | A+B | Contract definition (5) + live agent ping/readings/lectionary (4) |
| `test_homily_contract.py` | 9 | A+B | Contract definition (2) + live agent ping/generate/refine/tone (5) + error handling (2) |
| `test_liturgy_agent_e2e.py` | 10 | C | Ping, readings (happy + errors), lectionary, cache hit |
| `test_homily_agent_e2e.py` | 10 | C | Ping, generate (all occasions), refine, adjust tone, errors |
| `test_chat_orchestrator_e2e.py` | 4 | C | Health, WebSocket chat, multi-message, homily flow |
| `test_scenarios_e2e.py` | 3 | C | Liturgy→homily full flow, wedding flow, error recovery |
| **Total** | **45** | | |

## Related

- Protocol definition: `packages/a2a-protocol/`
- Agent implementations: `packages/liturgy-agent/`, `packages/homily-agent/`
- Consumer: `packages/chat-orchestrator/`
- Architecture guide: `AGENTS.md` §10 (Testing)
