# a2a-protocol

Agent-to-Agent protocol implementation for inter-agent communication.
Implements the **Google A2A standard** protocol with JSON-RPC 2.0 transport.

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/` | Standard A2A JSON-RPC: `message/send`, `tasks/get`, `tasks/list` |
| `POST` | `/message:send` | REST alternative for SendMessage |
| `GET` | `/tasks/{id}` | Get task status |
| `GET` | `/tasks` | List all tasks |
| `GET` | `/.well-known/agent-card.json` | Agent Card (discovery) |
| `GET` | `/health` | Health check |

## Usage — Server

```python
from a2a_protocol import create_server

async def handler(method: str, params: dict) -> dict:
    if method == "my.skill":
        return {"status": "success"}
    raise ValueError(f"Unknown: {method}")

server = create_server(
    handler=handler,
    name="my_agent",
    contract_path="contract.json",
    agent_url="http://my-agent:8001"
)
await server.serve_http(port=8001)
```

## Usage — Client

```python
import asyncio
from a2a_protocol import create_client

async def main():
    client = create_client(agent_url="http://liturgy-agent:8001")
    
    # Check connectivity
    await client.ping()  # GET /health
    
    # Call an agent skill via standard message/send
    result = await client.call_agent_method(
        "liturgy_agent.get_readings",
        {"occasion": "mass"}
    )
    print(result)

asyncio.run(main())
```

## API

### `create_server(handler, name, contract_path, agent_url)`

Creates an A2A server with standard endpoints.

- `handler` — async `(method, params) -> dict`
- `contract_path` — path to JSON contract (enables Agent Card)
- `agent_url` — public URL for Agent Card

### `create_client(agent_url, timeout, retries)`

Creates an A2A client.

- `agent_url` — base URL of the agent (e.g. `http://liturgy-agent:8001`)
- `call_agent_method(method, params)` — calls agent skill via `message/send`
- `ping()` — checks `GET /health`

### Agent Card format (`/.well-known/agent-card.json`)

```json
{
  "name": "my-agent",
  "description": "...",
  "url": "http://my-agent:8001",
  "version": "0.1.0",
  "capabilities": {"streaming": false, "pushNotifications": false},
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [...],
  "supportedInterfaces": [{"url": "...", "protocolBinding": "HTTP+JSON", "protocolVersion": "1.0"}]
}
```

## Structure

- `src/a2a_protocol/server.py` — A2AServer + FastAPI routes
- `src/a2a_protocol/client.py` — A2AClient
- `src/a2a_protocol/transport.py` — HTTP transport
- `src/a2a_protocol/protocol.py` — Message models (legacy)
- `tests/` — Test suite
