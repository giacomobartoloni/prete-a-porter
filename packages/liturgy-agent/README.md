# liturgy-agent

Liturgical data retrieval agent. Communicates via the standard **Google A2A protocol**.

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/` | Standard A2A JSON-RPC (`message/send`) |
| `GET` | `/.well-known/agent-card.json` | Agent Card |
| `GET` | `/tasks/{id}` | Get task status |
| `GET` | `/tasks` | List tasks |
| `GET` | `/health` | Health check |

## Skills

Callable via `message/send` with text `{"method":"...","params":{}}`:

| Method | Description |
|---|---|
| `agent.ping` | Health check, returns pong |
| `liturgy_agent.get_readings` | Get liturgical readings for date + occasion |
| `liturgy_agent.get_lectionary` | Get lectionary options (marriage, baptism, funeral) |

## Quick Start

```bash
# Start the agent
uv run python -m liturgy_agent.main --port 8001

# Request daily readings
curl -s -X POST http://localhost:8001/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"text": "{\"method\":\"liturgy_agent.get_readings\",\"params\":{\"occasion\":\"mass\"}}"}]
      }
    }
  }'

# Ping
curl -s http://localhost:8001/health
```

## Docker

```bash
docker compose up liturgy-agent
```

## Structure

- `src/liturgy_agent/main.py` — Entry point + A2A handler
- `src/liturgy_agent/agent.py` — LiturgyAgent class + LangGraph tools
- `src/liturgy_agent/scrapers.py` — Web scraping (evangelizo.org)
- `src/liturgy_agent/cache.py` — SQLite cache
- `src/liturgy_agent/lectionaries/` — JSON lectionary data
