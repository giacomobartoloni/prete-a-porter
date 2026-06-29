# E2E Test Plan — Prete-a-porter

## pytest + Docker Compose

---

## Architecture under test

```
pytest (host)
  │
  ├── http://localhost:8001/  →  liturgy-agent container
  ├── http://localhost:8002/  →  homily-agent  container
  ├── ws://localhost:8000/    →  chat-orchestrator container
  └── (via chat-orch) ──A2A──→  liturgy-agent + homily-agent
```

---

## Test File Structure

```
contracts/tests/
├── conftest.py                    # Shared fixtures (docker compose lifecycle)
├── test_liturgy_agent_e2e.py      # Liturgy agent A2A methods
├── test_homily_agent_e2e.py       # Homily agent A2A methods  
├── test_chat_orchestrator_e2e.py  # WebSocket + A2A orchestration flow
└── test_scenarios_e2e.py          # Multi-step user scenarios
```

---

## Fixtures (conftest.py)

### docker_compose — session scope

```python
@pytest.fixture(scope="session")
def docker_compose():
    """Start all services before test session, stop after."""
    subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True, cwd=PROJECT_ROOT)
    _wait_for_healthy(timeout=120)
    yield
    subprocess.run(["docker", "compose", "down", "-v"], check=True, cwd=PROJECT_ROOT)
```

### wait_for_healthy helper

```python
def _wait_for_healthy(timeout: int = 120):
    """Poll docker compose ps until all services are healthy."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        services = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
        if all(s.get("Health") == "healthy" for s in services if s.get("Service") not in ("a2a-inspector",)):
            return
        time.sleep(3)
    pytest.fail("Services did not become healthy in time")
```

### a2a_client fixture

```python
@pytest.fixture
def liturgy_url():
    return "http://localhost:8001"

@pytest.fixture
def homily_url():
    return "http://localhost:8002"

@pytest.fixture
def chat_url():
    return "http://localhost:8000"
```

---

## Test: Liturgy Agent (test_liturgy_agent_e2e.py)

### Ping
```python
def test_ping(liturgy_url):
    """agent.ping returns pong with version."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {}
    })
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["status"] == "pong"
    assert result["agent"] == "liturgy_agent"
    assert result["version"] is not None
```

### Get daily readings (cache miss → web scrape)
```python
def test_get_readings_mass(liturgy_url):
    """get_readings with occasion=mass returns structured readings."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "2", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass"}
    })
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["status"] == "success"
    data = result["data"]
    assert "date" in data
    assert "season" in data["metadata"]
    assert "color" in data["metadata"]
    assert all(k in data for k in ("first_reading", "psalm", "gospel"))
```

### Get daily readings with specific date
```python
def test_get_readings_specific_date(liturgy_url):
    """get_readings with YYYY-MM-DD date returns readings for that date."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "3", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass", "date": "2026-04-05"}
    })
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["status"] == "success"
    assert result["data"]["date"] == "2026-04-05"
```

### Unknown occasion raises error
```python
def test_get_readings_unknown_occasion(liturgy_url):
    """get_readings with invalid occasion returns error."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "4", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "invalid_occasion"}
    })
    assert resp.status_code == 200
    error = resp.json()["error"]
    assert error["code"] == -32601
```

### Missing occasion raises error
```python
def test_get_readings_missing_occasion(liturgy_url):
    """get_readings without required occasion returns error."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "5", "method": "liturgy_agent.get_readings",
        "params": {}
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
```

### Invalid date format raises error
```python
def test_get_readings_invalid_date(liturgy_url):
    """get_readings with non-ISO date returns error."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "6", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass", "date": "not-a-date"}
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
```

### Get lectionary for wedding
```python
@pytest.mark.parametrize("occasion", ["marriage", "baptism", "funeral"])
def test_get_lectionary(liturgy_url, occasion):
    """get_lectionary returns readings for each special occasion."""
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "7", "method": "liturgy_agent.get_lectionary",
        "params": {"occasion": occasion}
    })
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["occasion"] == occasion
    assert result["readings_count"] > 0
```

### Cache hit (requires two calls)
```python
def test_cache_hit(liturgy_url):
    """Second call for same date returns cached data."""
    date = "2026-06-01"
    # First call: cache miss → scrape
    resp1 = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "8", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass", "date": date}
    })
    assert resp1.json()["result"]["status"] == "success"
    source1 = resp1.json()["result"].get("source")
    # Second call: should be cache hit
    resp2 = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "9", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass", "date": date}
    })
    assert resp2.json()["result"]["status"] == "success"
    source2 = resp2.json()["result"].get("source")
    assert source2 == "cache"  # or allow "web" if cache disabled
```

---

## Test: Homily Agent (test_homily_agent_e2e.py)

### Ping
```python
def test_ping(homily_url):
    """agent.ping returns pong."""
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "1", "method": "agent.ping", "params": {}
    })
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "pong"
```

### Generate homily (happy path)
```python
MOCK_LITURGICAL_DATA = {
    "date": "2026-05-15", "occasion": "mass",
    "metadata": {
        "date": "2026-05-15", "occasion": "mass",
        "season": "Easter", "color": "White",
        "year_cycle": "A", "sunday_or_weekday": "Weekday",
    },
    "first_reading": {"reference": "Acts 18:9-18", "text": "Paul remained in Corinth...", "type": "First"},
    "psalm": {"reference": "Ps 47:2-7", "text": "God mounts his throne...", "type": "Psalm"},
    "gospel": {"reference": "Jn 16:20-23a", "text": "Jesus said to his disciples...", "type": "Gospel"},
    "cached_at": "2026-05-15T10:00:00", "source": "web",
}


def test_generate_homily(homily_url):
    """homily.generate returns structured homily with 4 sections."""
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "2", "method": "homily.generate",
        "params": {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "preferences": {"tone": "conversational", "length": "medium"},
        }
    })
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["status"] == "success"
    homily = result["data"]["homily"]
    assert all(s in homily for s in ("introduction", "reading_reflection", "practical_application", "conclusion"))
    for section in ("introduction", "reading_reflection", "practical_application", "conclusion"):
        assert len(homily[section]["content"]) > 20
```

### Generate homily without data raises error
```python
def test_generate_homily_missing_data(homily_url):
    """homily.generate without liturgical_data returns error."""
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "3", "method": "homily.generate",
        "params": {"occasion": "mass"}
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
```

### Generate homily for wedding
```python
@pytest.mark.parametrize("occasion", ["mass", "marriage", "baptism", "funeral"])
def test_generate_homily_occasions(homily_url, occasion):
    """homily.generate works for all occasion types."""
    data = dict(MOCK_LITURGICAL_DATA, occasion=occasion)
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "4", "method": "homily.generate",
        "params": {"liturgical_data": data, "occasion": occasion}
    })
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "success"
```

### Refine homily
```python
def test_refine_homily(homily_url):
    """homily.refine accepts existing draft and returns refined version."""
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "5", "method": "homily.refine",
        "params": {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "existing_draft": "Brothers and sisters, today we reflect on the Gospel...",
        }
    })
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "success"
```

### Adjust tone
```python
def test_adjust_tone(homily_url):
    """homily.adjust_tone returns homily with adjusted tone."""
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "6", "method": "homily.adjust_tone",
        "params": {
            "liturgical_data": MOCK_LITURGICAL_DATA,
            "occasion": "mass",
            "preferences": {"tone": "celebratory"},
        }
    })
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "success"
```

### Unknown method
```python
def test_unknown_method(homily_url):
    """Unknown method returns error."""
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "7", "method": "nonexistent.method", "params": {}
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
```

---

## Test: Chat Orchestrator (test_chat_orchestrator_e2e.py)

### Health
```python
def test_health(chat_url):
    """GET /health returns ok."""
    resp = requests.get(chat_url + "/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

### WebSocket chat — send message, receive response
```python
def test_websocket_chat(chat_url):
    """
    Establish WebSocket connection, send a message,
    receive a response from the chat orchestrator.
    """
    import websockets
    ws_url = chat_url.replace("http://", "ws://") + "/ws/chat/test_session_123"
    
    async def run():
        async with websockets.connect(ws_url) as ws:
            await ws.send("Che letture ci sono oggi?")
            response = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data = json.loads(response)
            assert data["type"] == "message"
            assert len(data["content"]) > 0
            assert "letture" in data["content"].lower() or "Parola" in data["content"]
    
    asyncio.run(run())
```

### WebSocket with A2A agent coordination
```python
def test_websocket_homily_flow(chat_url):
    """
    Full flow: request readings → receive response → readings formatted.
    """
    import websockets
    ws_url = chat_url.replace("http://", "ws://") + "/ws/chat/test_homily_flow"

    async def run():
        async with websockets.connect(ws_url) as ws:
            await ws.send("Vorrei un'omelia per la prossima domenica")
            response = await asyncio.wait_for(ws.recv(), timeout=60.0)
            data = json.loads(response)
            assert data["type"] == "message"
            # Might ask for clarification or start generating
            assert len(data["content"]) > 0

    asyncio.run(run())
```

### Invalid session ID
```python
def test_websocket_invalid_session(chat_url):
    """WebSocket connection with invalid session still connects (accepts any)."""
    import websockets
    ws_url = chat_url.replace("http://", "ws://") + "/ws/chat/" + "a" * 100

    async def run():
        async with websockets.connect(ws_url) as ws:
            await ws.send("test")
            response = await asyncio.wait_for(ws.recv(), timeout=30.0)
            assert response is not None

    asyncio.run(run())
```

---

## Test: Scenarios (test_scenarios_e2e.py)

### Full flow: liturgy → homily
```python
def test_readings_then_homily(liturgy_url, homily_url):
    """Full flow: get readings from liturgy agent, then generate homily."""
    # Step 1: Get readings
    resp = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass"}
    })
    assert resp.status_code == 200
    readings = resp.json()["result"]["data"]

    # Step 2: Generate homily from readings
    resp = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "2", "method": "homily.generate",
        "params": {
            "liturgical_data": readings,
            "occasion": "mass",
            "preferences": {"tone": "conversational", "length": "medium"},
        }
    })
    assert resp.status_code == 200
    homily = resp.json()["result"]["data"]["homily"]
    assert homily["introduction"]["content"] is not None
```

### Wedding full flow
```python
def test_wedding_flow(liturgy_url, homily_url):
    """Full wedding flow: lectionary selection → homily generation."""
    resp_lectionary = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_lectionary",
        "params": {"occasion": "marriage"}
    })
    assert resp_lectionary.status_code == 200
    readings = resp_lectionary.json()["result"]["lectionary"]

    resp_homily = requests.post(homily_url + "/", json={
        "jsonrpc": "2.0", "id": "2", "method": "homily.generate",
        "params": {
            "liturgical_data": readings.get("marriage", {}),
            "occasion": "marriage",
            "preferences": {"tone": "celebratory"},
        }
    })
    assert resp_homily.status_code == 200
    assert resp_homily.json()["result"]["status"] == "success"
```

### Error recovery: bad request → good request
```python
def test_error_recovery(liturgy_url):
    """Error on bad request, then success on corrected request."""
    # Bad request
    resp1 = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "1", "method": "liturgy_agent.get_readings",
        "params": {}
    })
    assert "error" in resp1.json()

    # Corrected request — same session, should work
    resp2 = requests.post(liturgy_url + "/", json={
        "jsonrpc": "2.0", "id": "2", "method": "liturgy_agent.get_readings",
        "params": {"occasion": "mass"}
    })
    assert resp2.json()["result"]["status"] == "success"
```

---

## Run Commands

```bash
# Run all e2e tests (starts docker services automatically)
cd contracts && pytest tests/ -v --timeout=180

# Run by category
pytest tests/test_liturgy_agent_e2e.py -v
pytest tests/test_homily_agent_e2e.py -v
pytest tests/test_chat_orchestrator_e2e.py -v
pytest tests/test_scenarios_e2e.py -v

# Skip Docker lifecycle (assumes services are already up)
pytest tests/ -v --no-docker
```

### pyproject.toml additions

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "docker: marks tests that start docker compose",
]
asyncio_mode = "auto"
timeout = 180
```

### Dependencies

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-timeout>=2.0.0",
    "requests>=2.28.0",
    "websockets>=12.0",
]
```

---

## Test Count Summary

| File | Tests | Coverage |
|---|---|---|
| `test_liturgy_agent_e2e.py` | 8 | Ping, readings (happy + error), lectionary, cache |
| `test_homily_agent_e2e.py` | 8 | Ping, generate (happy + error), refine, tone, unknown method |
| `test_chat_orchestrator_e2e.py` | 3 | Health, WebSocket chat, WebSocket homily flow |
| `test_scenarios_e2e.py` | 3 | Liturgy→homily full flow, wedding flow, error recovery |
| **Total** | **22** | |

---

## CI Integration

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: { python-version: "3.12" }
      - run: pip install pytest requests websockets
      - run: docker compose up -d --build
      - run: pytest contracts/tests/ -v --timeout=180
      - run: docker compose down -v
```
