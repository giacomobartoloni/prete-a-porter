# Liturgy Agent

An autonomous liturgical data retrieval agent for the Prete-a-porter system. See [`AGENTS.md`](../../../AGENTS.md#4-liturgy-agent) for the full architecture documentation.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest packages/liturgy-agent/tests/ -v

# Start A2A server (stdio mode, default)
python -m liturgy_agent.main

# Start A2A server (HTTP mode)
python -m liturgy_agent.main --http --port 8001
```

## A2A Protocol

```bash
# Ping the agent
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"agent.ping","params":{}}'

# Get readings for a date
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"2","method":"liturgy_agent.get_readings","params":{"date":"2026-03-15","occasion":"mass"}}'
```

## Testing

```bash
# All tests
pytest packages/liturgy-agent/tests/

# Specific module
pytest packages/liturgy-agent/tests/test_cache.py

# With coverage
pytest --cov=packages.liturgy-agent.src.liturgy_agent packages/liturgy-agent/tests/
```

## Dependencies

- `pydantic>=2.5` — Data validation
- `langgraph>=0.2.28` — Agent orchestration
- `httpx>=0.25.2` — Async HTTP client
- `beautifulsoup4>=4.12.2` — HTML parsing
- `lxml` — HTML/XML parsing
