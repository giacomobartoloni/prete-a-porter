# A2A Contract Tests

Consumer-driven contract tests for the A2A (Agent-to-Agent) JSON-RPC 2.0 API.
Verifies that all agents comply with the protocol specification and produce
responses that consumers expect.

`tests/models.py` defines independent consumer request/result expectations;
static tests compare declared schemas and validate examples, while required live
checks validate daily Mass, ritual lectionary and all three Homily capabilities.
The custom contract format remains in place; no producer state model is imported.

The JSON-RPC endpoint is `/`; `/message:send` is the standard message binding.
Custom handler exceptions currently return sanitized `-32603 Internal error`
with `data.error_id`. Inside `message/send`, failures appear as sanitized agent
reply text. Do not assume custom-handler `-32601/-32602` or domain-specific
codes; [typed error mapping is tracked separately](https://github.com/giacomobartoloni/prete-a-porter/issues/7). Upstream Liturgy failures
remain application replies with `status: error`.

## Test Layers

The suite has four layers, each with different infrastructure requirements:

| Layer | Files | Needs agents? | Needs Docker? | Tests run |
|-------|-------|:---:|:---:|-----------|
| **A. Contract definition** | `test_liturgy_contract.py::TestContractCompliance`, `test_homily_contract.py::TestHomilyContractDefinition` | No | No | Validates contract JSON files: required fields, method names, error codes, enum values |
| **B. Live agent** | `test_liturgy_contract.py::TestLiturgyAgentContract`, `test_homily_contract.py::TestHomilyAgentContract`, `test_liturgy_fixture_backed.py` | Yes (env URLs) | No | Sends `message/send` requests, validates reply against Pydantic models. Required daily Mass checks use a fixture Evangelizo upstream (`EVANGELIZO_BASE_URL`); homily generate/refine/adjust are mandatory with local fixture/`TEST_MODE` data. Live upstream/LLM checks need `PRETE_RUN_OPTIONAL_LIVE=1` |
| **C. E2E** | `test_liturgy_agent_e2e.py`, `test_homily_agent_e2e.py`, `test_chat_orchestrator_e2e.py`, `test_scenarios_e2e.py` | Yes (ports 8000-8002) | No (explicit start) | Raw JSON-RPC POSTs + WebSocket flows. Start the test stack yourself; fixtures never manage Compose |
| **D. Protocol unit** | `packages/a2a-protocol/tests/` | No | No | Mock-handler unit tests of the A2A server, transport, and LLM factory |

## Test File Structure

```
contracts/
├── liturgy-agent-contract.json      # Liturgy agent API spec (3 methods)
├── homily-agent-contract.json       # Homily agent API spec (4 methods)
├── pyproject.toml                   # pytest config, dependencies
└── tests/
    ├── conftest.py                        # Fixtures: .env loader, URL fixtures, MOCK_LITURGICAL_DATA (no Compose lifecycle)
    ├── test_docker_lifecycle_safety.py    # Regression: fixtures never start/stop/delete the shared stack
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

# --- Layer D: Protocol unit tests (no agents needed) ---
cd packages/a2a-protocol && uv run pytest -v

# --- Compatibility: --no-docker is accepted and is a no-op (same behaviour) ---
cd contracts && uv run pytest tests/ -v --no-docker

# --- Specific agent ---
cd contracts && uv run pytest tests/test_liturgy_agent_e2e.py -v
cd contracts && uv run pytest tests/test_homily_contract.py -v

# --- Skip slow tests ---
cd contracts && uv run pytest tests/ -v -m "not slow"
```

### Deterministic fixture-backed integration (all host processes)

Run from the repository root in Bash. Prepare the package environments first:

```bash
for package in a2a-protocol liturgy-agent homily-agent chat-orchestrator; do
  (cd "packages/$package" && uv sync --extra dev)
done
(cd contracts && uv sync)
```

The following block uses ports 18000–18002 and 18080; choose other free ports
and update the URLs if they are already occupied. Every service and pytest runs
on the host, so `127.0.0.1` refers to the same host. Use a fresh cache, matching
disposable credentials, and `TEST_MODE=true`; no external LLM or Evangelizo is
needed. The fixture supplies a second reading for Sundays.

```bash
export PYTHONDONTWRITEBYTECODE=1 TEST_MODE=true PRETE_RUN_OPTIONAL_LIVE=0
export ANTHROPIC_API_KEY= GOOGLE_API_KEY= OPENAI_API_KEY=
export A2A_BASIC_AUTH_USERNAME=a2a-test A2A_BASIC_AUTH_PASSWORD=a2a-test-secret
export WS_JWT_SECRET=test-jwt-secret-for-local-contracts-32-bytes
export ORCHESTRATOR_API_KEY=test-orchestrator-key
export RATE_LIMIT_MESSAGES_PER_HOUR=3 RATE_LIMIT_MESSAGES_PER_DAY=100
test_run_dir=$(mktemp -d)
export DATABASE_PATH="$test_run_dir/liturgy.db"
export RATE_LIMIT_DB_PATH="$test_run_dir/quota.db"
export EVANGELIZO_BASE_URL=http://127.0.0.1:18080
export A2A_LITURGY_URL=http://127.0.0.1:18001
export A2A_HOMILY_URL=http://127.0.0.1:18002
export CHAT_ORCHESTRATOR_URL=http://127.0.0.1:18000

packages/chat-orchestrator/.venv/bin/python contracts/scripts/fixture_evangelizo_server.py --port 18080 > "$test_run_dir/fixture.log" 2>&1 &
fixture_pid=$!
packages/liturgy-agent/.venv/bin/python -m liturgy_agent.main --host 127.0.0.1 --port 18001 > "$test_run_dir/liturgy.log" 2>&1 &
liturgy_pid=$!
packages/homily-agent/.venv/bin/python -m homily_agent.main --host 127.0.0.1 --port 18002 > "$test_run_dir/homily.log" 2>&1 &
homily_pid=$!
packages/chat-orchestrator/.venv/bin/python -m uvicorn chat_orchestrator.main:app --host 127.0.0.1 --port 18000 > "$test_run_dir/chat.log" 2>&1 &
chat_pid=$!
trap 'kill "$fixture_pid" "$liturgy_pid" "$homily_pid" "$chat_pid" 2>/dev/null || true; wait 2>/dev/null || true' EXIT

packages/chat-orchestrator/.venv/bin/python contracts/scripts/wait_for_health.py \
  "$EVANGELIZO_BASE_URL/health" "$A2A_LITURGY_URL/health" \
  "$A2A_HOMILY_URL/health" "$CHAT_ORCHESTRATOR_URL/health" --attempts 30 --sleep 1 &&
  contracts/.venv/bin/python -m pytest contracts/tests/ -v --no-docker
```

Run the block in its own shell/script so the EXIT trap cleans up only its owned
processes. Logs remain in `test_run_dir`. Pytest never starts or stops services;
`--no-docker` is a compatibility no-op. Do not combine this host-fixture URL
with containerized agents.

### Optional real upstream check

Start a separate agent using the normal publication API, then explicitly opt in:

```bash
cd contracts
PRETE_RUN_OPTIONAL_LIVE=1 uv run pytest \
  tests/test_liturgy_contract.py::TestLiturgyAgentContract::test_get_readings_format -v
```

Keep this external-source check separate from the deterministic fixture suite.

## Environment Requirements

The test suite loads `.env` automatically via `conftest.py:_load_env()`.
The following variables must be set for live/E2E tests:

| Variable | Required for | Source |
|----------|-------------|--------|
| `WS_JWT_SECRET` | WebSocket tests (chat orchestrator) | `.env` (auto-loaded by conftest) |
| `A2A_BASIC_AUTH_USERNAME` | A2A HTTP requests | Required complete pair (Compose rejects unset/empty) |
| `A2A_BASIC_AUTH_PASSWORD` | A2A HTTP requests | Required complete pair matching the agents under test |
| `A2A_LITURGY_URL` | Liturgy agent URL | Defaults to `http://localhost:8001` |
| `A2A_HOMILY_URL` | Homily agent URL | Defaults to `http://localhost:8002` |
| `CHAT_ORCHESTRATOR_URL` | Chat orchestrator URL | Defaults to `http://localhost:8000` (alias `A2A_CHAT_URL`) |
| `PRETE_RUN_OPTIONAL_LIVE` | Optional live Evangelizo/LLM checks | Unset by default; set `1` only for live upstream |
| `TEST_MODE` | Deterministic agent responses | CI/local fixture stack; required generate/refine/adjust use local data |

> **Note on Basic Auth:** Normal A2A HTTP execution requires a complete credential
> pair. Contract helpers send matching `Authorization: Basic` headers via
> `a2a_auth_headers()` / `a2a_post()`. When unset, conftest installs the disposable
> pair `a2a-test` / `a2a-test-secret` for the test process only — start agents with
> the same values, as in the all-host workflow above:
> ```bash
> export A2A_BASIC_AUTH_USERNAME=a2a-test A2A_BASIC_AUTH_PASSWORD=a2a-test-secret
> ```

## Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `docker_compose` | session | No-op availability marker; never starts/stops Compose (`--no-docker` kept for compatibility) |
| `_ensure_docker` | module | Depends on `docker_compose` |
| `liturgy_url` | function | `A2A_LITURGY_URL` or `http://localhost:8001` |
| `homily_url` | function | `A2A_HOMILY_URL` or `http://localhost:8002` |
| `chat_url` | function | `CHAT_ORCHESTRATOR_URL` / `A2A_CHAT_URL` or `http://localhost:8000` |
| `MOCK_LITURGICAL_DATA` | — | Module-level dict with sample readings for homily tests |

## CI

Contract tests run on push/PR to `main` via `.github/workflows/contract-tests.yml`.
The workflow installs all packages, starts the fixture upstream and all three
services with mock LLM, waits for health, then runs the complete contract suite.

Collect the current test inventory with `uv run pytest tests/ --collect-only -q`
from `contracts/`.

## Related

- Protocol definition: `packages/a2a-protocol/`
- Agent implementations: `packages/liturgy-agent/`, `packages/homily-agent/`
- Consumer: `packages/chat-orchestrator/`
- Architecture guide: `AGENTS.md` §10 (Testing)
