# Refactoring Plan — Prete-a-porter

## Phase 1: Structural (massima priorità)
## Phase 2: Error Handling & Packaging (media priorità)
## Phase 3: Code Style & Consistency (bassa priorità)

---

# Phase 1 — Structural

---

## 1.0 Fix Pre-Existing Tool Registry Bug

**Prima di tutto**, un bug attuale: `TOOLS_REGISTRY` in `main.py` mappa solo **4** dei **6** tools che l'LLM può chiamare.

```python
# main.py:113-118 — stato attuale
TOOLS_REGISTRY = {
    "get_current_date": get_current_date,
    "calculate_date": calculate_date,
    "get_liturgical_readings": get_liturgical_readings,
    "get_liturgical_lectionary": get_liturgical_lectionary,
    # generate_homily e refine_homily MANCANTI ← BUG
}
```

ma `agent_node` line 305-312 ne bind 6:
```python
tools = [get_current_date, calculate_date, get_liturgical_readings,
         get_liturgical_lectionary, generate_homily, refine_homily]
```

**Conseguenza**: se l'LLM chiama `generate_homily`, `tools_node` lancia `ToolNotFoundException`.

### Fix

```python
TOOLS_REGISTRY = {
    "get_current_date": get_current_date,
    "calculate_date": calculate_date,
    "get_liturgical_readings": get_liturgical_readings,
    "get_liturgical_lectionary": get_liturgical_lectionary,
    "generate_homily": generate_homily,
    "refine_homily": refine_homily,
}
```

---

## 1.1 Split `chat-orchestrator/main.py` into Modules

**File attuale**: 696 linee, 7 responsabilità, 11 funzioni/endpoint.

### Target structure

```
packages/chat-orchestrator/src/chat_orchestrator/
├── __init__.py
├── main.py              ← solo entry point e app FastAPI
├── config.py            ← LLM selection, system prompt
├── graph.py             ← graph construction, nodes, edges
├── tools.py             ← tool definitions (già esiste)
├── routes.py            ← HTTP + WebSocket endpoints
├── exceptions.py        ← exception hierarchy
├── error_handlers.py    ← error handlers
└── utils/
    └── logging.py
```

### Task 1.1a: Extract `config.py`

**Move from `main.py`:**
- `_get_llm()` — LLM selection logic (lines 212–263)
- `SYSTEM_PROMPT` — system prompt constant (lines 120–148)

**New file: `config.py`**

```python
"""
Configuration module for Chat Orchestrator.

Handles LLM selection and initialization.
"""

import os
from .utils.logging import get_logger
from .exceptions import LLMNotConfiguredException

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a friendly homily assistant specialized in Catholic liturgy..."""
# (same content, moved verbatim)


def get_llm() -> object:
    """Select and initialize LLM based on available API keys.
    
    Checks ANTHROPIC_API_KEY, GOOGLE_API_KEY, FIREWORKS_API_KEY
    in priority order. Falls back to mock in test mode.
    
    Returns:
        ChatAnthropic, ChatGoogleGenerativeAI, ChatFireworks, or mock.
    
    Raises:
        LLMNotConfiguredException: If no API key is configured.
    """
    if os.getenv("TEST_MODE") == "true":
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = AsyncMock()
        mock_response.content = "Test response from mock LLM"
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response
        logger.debug("Using mock LLM for testing")
        return mock_llm

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    fireworks_key = os.getenv("FIREWORKS_API_KEY")

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            logger.debug("Using Anthropic Claude")
            return ChatAnthropic(model_name="claude-3-5-sonnet-20241022", api_key=anthropic_key)
        except ImportError:
            logger.warning("langchain_anthropic not available, skipping Anthropic LLM.")

    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.debug("Using Google Gemini")
            return ChatGoogleGenerativeAI(model="gemini-flash-lite-latest", api_key=google_key)
        except ImportError:
            logger.warning("langchain_google_genai not available, skipping Gemini LLM.")

    if fireworks_key:
        try:
            from langchain_fireworks import ChatFireworks
            logger.debug("Using Fireworks.ai")
            return ChatFireworks(model="accounts/fireworks/models/llama-v3p1-70b-instruct", api_key=fireworks_key)
        except ImportError:
            logger.warning("langchain_fireworks not available, skipping Fireworks.ai LLM.")

    logger.error("No LLM API key configured")
    raise LLMNotConfiguredException()
```

> **Nota**: il logging usa `get_logger(__name__)` (pattern del progetto), non `logging.getLogger()`.

### Task 1.1b: Extract `graph.py`

**Move from `main.py`:**
- `agent_node()` (lines 266–343)
- `tools_node()` (lines 346–419)
- `should_continue()` (lines 422–432)
- `create_graph()` (lines 437–485)
- `get_graph()` (lines 492–503)
- `reset_graph()` (lines 506–513)
- `TOOLS_REGISTRY` (lines 112–118) — già fixato in 1.0
- Global state `_graph`, `_checkpointer_context`

**New file: `graph.py`**

```python
"""
Graph construction and node logic for Chat Orchestrator.

Builds the LangGraph state graph that manages conversation flow
and coordinates tool execution.
"""

from pathlib import Path
from typing import Literal

from langchain_core.messages import (
    AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.tools import tool

from .config import SYSTEM_PROMPT, get_llm
from .exceptions import (
    AgentGraphException, LLMNotConfiguredException,
    ToolExecutionException, ToolNotFoundException,
)
from .state import ChatState
from .tools import (
    calculate_date, generate_homily, get_current_date,
    get_liturgical_lectionary, get_liturgical_readings, refine_homily,
)
from .utils.logging import get_logger

logger = get_logger(__name__)

# Tool registry: maps tool names (as the LLM knows them) to their functions.
TOOLS_REGISTRY = {
    "get_current_date": get_current_date,
    "calculate_date": calculate_date,
    "get_liturgical_readings": get_liturgical_readings,
    "get_liturgical_lectionary": get_liturgical_lectionary,
    "generate_homily": generate_homily,
    "refine_homily": refine_homily,
}

_TOOLS = list(TOOLS_REGISTRY.values())

_graph = None
_checkpointer_context = None


def agent_node(state: ChatState) -> dict:
    """
    Agent node: calls LLM with tools bound. LLM decides whether to use tools.
    """
    try:
        llm = get_llm()
    except LLMNotConfiguredException:
        raise
    except Exception as e:
        logger.error("Failed to initialize LLM", session_id=state.get("session_id"), error=str(e), exc_info=True)
        raise AgentGraphException(
            message=f"Failed to initialize LLM: {str(e)}",
            agent_name="chat_orchestrator"
        ) from e

    llm_with_tools = llm.bind_tools(_TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    try:
        response = llm_with_tools.invoke(messages)
        has_tool_calls = hasattr(response, 'tool_calls') and response.tool_calls
        next_action = "continue" if has_tool_calls else "end"

        logger.debug("Agent node completed", session_id=state.get("session_id"), has_tool_calls=has_tool_calls)
        return {"messages": [response], "next_action": next_action}
    except Exception as e:
        logger.error("Agent node failed", session_id=state.get("session_id"), error=str(e), exc_info=True)
        raise AgentGraphException(
            message=f"Agent execution failed: {str(e)}",
            agent_name="chat_orchestrator"
        ) from e


def tools_node(state: ChatState) -> dict:
    """
    Execute tool calls from the last AI message and return ToolMessages.
    """
    last_message = state["messages"][-1]
    tool_messages = []

    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return {"messages": []}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})

        logger.debug("Executing tool", tool_name=tool_name, tool_args=tool_args)

        func = TOOLS_REGISTRY.get(tool_name)
        if func:
            try:
                result = func.invoke(tool_args)
            except Exception as e:
                logger.error("Tool execution failed", tool_name=tool_name, error=str(e), exc_info=True)
                raise ToolExecutionException(
                    message=f"Failed to execute {tool_name}: {str(e)}",
                    tool_name=tool_name
                ) from e
        else:
            logger.error("Unknown tool requested", tool_name=tool_name)
            raise ToolNotFoundException(tool_name=tool_name)

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_name)
        )

    return {"messages": tool_messages}


def should_continue(state: ChatState) -> Literal["tools", "end"]:
    """Check the next_action to decide whether to continue to tools or end."""
    return "tools" if state["next_action"] == "continue" else "end"


async def create_graph() -> tuple:
    """Build and compile the chat orchestrator graph with SQLite checkpointer."""
    workflow = StateGraph(ChatState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")

    backend_dir = Path(__file__).parent.parent
    db_path = os.getenv("DATABASE_PATH", "data/chat_orchestrator.db")

    if not Path(db_path).is_absolute():
        full_db_path = str(backend_dir / db_path)
    else:
        full_db_path = db_path

    Path(full_db_path).parent.mkdir(parents=True, exist_ok=True)

    checkpointer_context = AsyncSqliteSaver.from_conn_string(full_db_path)
    checkpointer = await checkpointer_context.__aenter__()

    return workflow.compile(checkpointer=checkpointer), checkpointer_context


async def get_graph() -> object:
    """Get or create the compiled chat orchestrator graph instance."""
    global _graph, _checkpointer_context
    if _graph is None:
        _graph, _checkpointer_context = await create_graph()
    return _graph


def reset_graph() -> None:
    """Reset the graph instance (useful for testing)."""
    global _graph, _checkpointer_context
    _graph = None
    _checkpointer_context = None
    logger.debug("Graph instance reset")
```

> **Nota**: `TOOLS_REGISTRY` unifica tool names + tool functions. Il vecchio codice di `main.py` aveva un array separato `tools = [...]` per il binding LLM. Qui usiamo `list(TOOLS_REGISTRY.values())` per evitare duplicazione.

### Task 1.1c: Extract `routes.py`

**Move from `main.py`:**
- `health()` (lines 518–527)
- `chat_websocket()` (lines 529–696)
- `correlation_id_middleware()` (lines 168–207)

**Le route non hanno più `@app` decorators** — vengono registrate in `main.py`.

**chat_websocket** viene anche suddivisa internamente (da 149→~40 linee):

```python
"""
HTTP and WebSocket route handlers for Chat Orchestrator.
"""

from fastapi import Request, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from .exceptions import WebSocketConnectionException, WebSocketMessageException
from .graph import get_graph
from .utils.logging import get_logger, set_correlation_id, clear_correlation_id

logger = get_logger(__name__)


async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to each request for tracing."""
    import uuid
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)

    logger.debug("Request started", method=request.method, url=str(request.url))

    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.debug("Request completed", status_code=response.status_code)
        return response
    except Exception as e:
        logger.error("Request failed", error=str(e), exc_info=True)
        raise
    finally:
        clear_correlation_id()


async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "chat-orchestrator"}


async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for chat."""
    correlation_id = set_correlation_id()

    try:
        await _accept_and_init(websocket, session_id)
        graph = await get_graph()
        await _message_loop(websocket, graph, session_id, correlation_id)
    except WebSocketDisconnect:
        logger.info("Client disconnected", session_id=session_id, correlation_id=correlation_id)
    except Exception as e:
        logger.error("WebSocket error", session_id=session_id, error=str(e), exc_info=True)
        await _send_error_and_close(websocket, e)
    finally:
        clear_correlation_id()


async def _accept_and_init(websocket: WebSocket, session_id: str) -> None:
    """Accept WebSocket connection and set up state."""
    try:
        await websocket.accept()
    except Exception as e:
        raise WebSocketConnectionException(
            message=f"Failed to accept connection: {str(e)}",
            session_id=session_id
        ) from e


async def _message_loop(websocket: WebSocket, graph, session_id: str, correlation_id: str) -> None:
    """Main message receive/respond loop."""
    message_count = 0

    while True:
        try:
            data = await websocket.receive_text()
        except WebSocketDisconnect:
            raise

        message_count += 1

        try:
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=data)], "session_id": session_id},
                config={"configurable": {"thread_id": session_id}, "recursion_limit": 15},
            )

            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            ai_message = ai_messages[-1].content if ai_messages else "No response"

            await websocket.send_json({
                "type": "message", "content": ai_message, "session_id": session_id,
            })
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error("Error processing message", session_id=session_id, error=str(e), exc_info=True)
            await websocket.send_json({
                "type": "error",
                "error": {
                    "code": "MESSAGE_PROCESSING_ERROR",
                    "message": "Si è verificato un errore nel processare il messaggio. Riprova.",
                    "correlation_id": correlation_id,
                }
            })


async def _send_error_and_close(websocket: WebSocket, error: Exception) -> None:
    """Send error response and close WebSocket connection."""
    from .error_handlers import websocket_exception_handler
    try:
        await websocket_exception_handler(websocket, error)
    except Exception:
        pass
    try:
        await websocket.close()
    except Exception:
        pass
```

> **Nota**: `_accept_and_init` non include più l'autenticazione WebSocket. La versione di `packages/chat-orchestrator` non ha il modulo `auth.py` (era solo in `backend/src/`, rimosso). Se serve auth in futuro va reimplementato.

### Task 1.1d: Rewrite `main.py` — entry point only

Dopo l'estrazione, `main.py` scende da 696 a ~40 linee:

```python
"""
Chat Orchestrator — WebSocket server for agent coordination.

Coordinates liturgy-agent and homily-agent via A2A protocol.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .error_handlers import register_exception_handlers
from .routes import chat_websocket, correlation_id_middleware, health

app = FastAPI()
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(correlation_id_middleware)
app.get("/health")(health)
app.websocket("/ws/chat/{session_id}")(chat_websocket)


def start() -> None:
    """Start the application using Uvicorn."""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start()
```

> **Nota**: si usa `app.websocket("/path")(func)`, NON `app.add_websocket_route()` che non esiste in FastAPI.

### Riepilogo dipendenze tra moduli

```
main.py → routes.py → graph.py → config.py → exceptions.py
         → error_handlers.py         → tools.py
         → CORS middleware
```

Nessuna dipendenza circolare.

---

## 1.2 Fix `asyncio.run()` — Convert 4 tools to async

**Problema**: 4 funzioni sync `@tool` usano `asyncio.run()` per chiamare funzioni async.

```
graph.ainvoke() [event loop running]
  → tools_node (sync)
    → get_liturgical_readings() [sync @tool]
      → asyncio.run(request_liturgical_data())  ← CRASH!
```

**Soluzione**: rendere i tool async, `agent_node` e `tools_node` async. `should_continue` resta sync.

### Task 1.2a: Convert 4 tool functions to `async def`

In `packages/chat-orchestrator/src/chat_orchestrator/tools.py`:

```python
@tool
async def get_liturgical_readings(occasion: str, date: Optional[str] = None) -> Dict[str, Any]:
    """Request liturgical readings for Sunday Mass or special occasions."""
    try:
        result = await request_liturgical_data(occasion, date)
        return result
    except Exception as e:
        logger.error(f"Error getting liturgical readings: {e}")
        return {"error": str(e), "occasion": occasion, "date": date or get_current_date()}
```

Stessa modifica per:
- `get_liturgical_lectionary`
- `generate_homily`
- `refine_homily`

**Attenzione**: `generate_homily` e `refine_homily` hanno parametri `str` (JSON). Le funzioni async interne `request_homily_generation()` e `request_homily_refinement()` sono già async. Le conversioni:

```python
# generate_homily: liturgical_data e preferences sono stringhe JSON
@tool
async def generate_homily(liturgical_data: str, occasion: str, preferences: Optional[str] = None) -> Dict[str, Any]:
    try:
        import json
        lit_data = json.loads(liturgical_data)  
        prefs = json.loads(preferences) if preferences else {}
        result = await request_homily_generation(lit_data, occasion, prefs)
        return result
    except Exception as e:
        logger.error(f"Error generating homily: {e}")
        return {"error": str(e), "occasion": occasion}


@tool
async def refine_homily(
    liturgical_data: str, occasion: str, preferences: Optional[str] = None,
    existing_draft: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        import json
        lit_data = json.loads(liturgical_data) if liturgical_data else {}
        prefs = json.loads(preferences) if preferences else {}
        result = await request_homily_refinement(lit_data, occasion, prefs, existing_draft)
        return result
    except Exception as e:
        logger.error(f"Error refining homily: {e}")
        return {"error": str(e), "occasion": occasion}
```

### Task 1.2b: Convert `agent_node` and `tools_node` to async

In `graph.py` (dopo l'estrazione di 1.1b):

```python
# agent_node diventa async e usa ainvoke
async def agent_node(state: ChatState) -> dict:
    # ... (same except/wrapping code)
    response = await llm_with_tools.ainvoke(messages)
    # ...


# tools_node diventa async e usa func.ainvoke() per tool async
async def tools_node(state: ChatState) -> dict:
    # ...
    for tool_call in last_message.tool_calls:
        func = TOOLS_REGISTRY.get(tool_name)
        if func:
            result = await func.ainvoke(tool_args)  # ← .ainvoke() non .invoke()
        # ...


# should_continue resta sync — LangGraph gestisce i conditional edge sync
def should_continue(state: ChatState) -> Literal["tools", "end"]:
    return "tools" if state["next_action"] == "continue" else "end"
```

> **Nota cruciale**: per tool async, LangChain usa `.ainvoke()`, non `.invoke()`. Usare `await func.invoke()` su un tool async equivale a chiamare `asyncio.run()` su un sync — crea un nuovo event loop e fallisce.

### Task 1.2c: Aggiornare il mock LLM in test mode

Il mock in `config.py` deve supportare anche `.ainvoke()`:

```python
if os.getenv("TEST_MODE") == "true":
    from unittest.mock import AsyncMock
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_response = AsyncMock()
    mock_response.content = "Test response from mock LLM"
    mock_response.tool_calls = []
    mock_llm.ainvoke.return_value = mock_response  # ← aggiunto per async
    mock_llm.invoke.return_value = mock_response
    return mock_llm
```

---

## 1.3 Split `A2AServer.create_fastapi_app()` (187 lines)

**Problema**: `A2AServer` (466 lines) god class. `create_fastapi_app` ha 5 route closures inline.

### Task 1.3a: Extract route handlers to methods

Invece di closures dentro `create_fastapi_app`, diventano metodi di `A2AServer`:

```python
class A2AServer:
    def create_fastapi_app(self) -> FastAPI:
        app = FastAPI(title=self.name, version="1.0.0")
        app.post("/")(self._handle_root_post)
        app.post("/message:send")(self._handle_send_message_route)
        app.get("/tasks/{task_id}")(self._handle_get_task_route)
        app.get("/tasks")(self._handle_list_tasks_route)
        app.get("/.well-known/agent-card.json")(self._handle_agent_card)
        app.get("/health")(self._handle_health)
        logger.info(f"Created FastAPI app for {self.name}")
        return app

    async def _handle_root_post(self, request: Request) -> Response:
        """Handle POST / — custom A2A method routing."""
        body = await request.json()
        req_id = body.get("id", str(uuid.uuid4())[:8])
        jsonrpc = body.get("jsonrpc")
        method = body.get("method", "")

        if jsonrpc != "2.0" or not method:
            return Response(json.dumps({"error": "Unsupported request format"}), status_code=400)

        # Standard A2A methods
        if method == "message/send":
            return await self._handle_message_send(request)
        if method == "tasks/get":
            return await self._handle_get_task(request)
        if method == "tasks/list":
            return await self._handle_list_tasks(request)
        if method == "agent.ping":
            return _jsonrpc_ok(req_id, self._handle_ping())
        if method == "agent.describe":
            return _jsonrpc_ok(req_id, self._get_contract_methods())

        # Custom agent methods
        try:
            params = body.get("params", {})
            result = await self.handler(method, params)
            return _jsonrpc_ok(req_id, result)
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            logger.error(f"Internal error {error_id}: {e}", exc_info=True)
            return _jsonrpc_error(req_id, -32603, "Internal error", error_id)

    async def _handle_agent_card(self) -> dict:
        """GET /.well-known/agent-card.json"""
        return self._generate_agent_card()

    async def _handle_health(self) -> dict:
        """GET /health"""
        return {"status": "healthy", "agent": self.name}
```

### Task 1.3b: Extract JSON-RPC helpers to module-level functions

```python
def _jsonrpc_ok(request_id: str, result: dict) -> Response:
    return Response(
        content=json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}),
        media_type="application/json",
        status_code=200,
    )

def _jsonrpc_error(request_id: str, code: int, message: str, error_id: str = "") -> Response:
    data = {"error_id": error_id} if error_id else None
    return Response(
        content=json.dumps({
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message, "data": data},
        }),
        media_type="application/json",
        status_code=200,
    )
```

### Task 1.3c: Sanitize error responses everywhere

Tutti i `return Response(content=json.dumps({"error": str(e)}), ...)` diventano:

```python
# PRIMA — leak di dettagli interni
except Exception as e:
    return Response(content=json.dumps({"error": str(e)}), status_code=500)

# DOPO — error id sicuro, logga il dettaglio
except Exception as e:
    error_id = str(uuid.uuid4())[:8]
    logger.error(f"Internal error {error_id}: {e}", exc_info=True)
    return _jsonrpc_error(req_id, -32603, "Internal error", error_id)
```

### Dopo: `create_fastapi_app` da 187 → ~15 lines

```python
def create_fastapi_app(self) -> FastAPI:
    """Create FastAPI application with all routes registered."""
    app = FastAPI(title=self.name, version="1.0.0")
    app.post("/")(self._handle_root_post)
    app.post("/message:send")(self._handle_send_message_route)
    app.get("/tasks/{task_id}")(self._handle_get_task_route)
    app.get("/tasks")(self._handle_list_tasks_route)
    app.get("/.well-known/agent-card.json")(self._handle_agent_card)
    app.get("/health")(self._handle_health)
    return app
```

---

## 1.4 Extract Duplicated `_get_llm()` into Shared Factory

**Problema**: `_get_llm()` è duplicato in 2 file (52 + 59 linee) con logica quasi identica.

### Task 1.4a: Create `packages/a2a-protocol/src/a2a_protocol/llm.py`

```python
"""
Shared LLM factory for all agents.

Provides a unified way to create LLM instances based on environment
configuration. Each agent can specialize the factory for its needs.
"""

import os
import logging

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(Exception):
    """Raised when no LLM API key is configured."""
    pass


def create_llm(
    preferred_model: str | None = None,
    prefer_google: bool = False,
) -> object:
    """Create an LLM instance based on available API keys.

    Checks ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY,
    FIREWORKS_API_KEY in priority order.

    Args:
        preferred_model: Optional specific model identifier.
        prefer_google: If True, try Google before Anthropic.

    Returns:
        Configured LLM instance (ChatAnthropic, ChatGoogleGenerativeAI,
        ChatOpenAI, or ChatFireworks).

    Raises:
        LLMNotConfiguredError: If no API key is available.
    """
    if os.getenv("TEST_MODE") == "true":
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = AsyncMock()
        mock_response.content = "Test response from mock LLM"
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response
        mock_llm.ainvoke.return_value = mock_response
        logger.debug("Using mock LLM for testing")
        return mock_llm

    providers = [
        ("ANTHROPIC_API_KEY", _create_anthropic, "claude-3-5-sonnet-20241022"),
        ("GOOGLE_API_KEY", _create_google, "gemini-flash-lite-latest"),
        ("OPENAI_API_KEY", _create_openai, "gpt-4-turbo-preview"),
        ("FIREWORKS_API_KEY", _create_fireworks, "accounts/fireworks/models/llama-v3p1-70b-instruct"),
    ]

    if prefer_google:
        providers[0], providers[1] = providers[1], providers[0]

    for env_var, factory, default_model in providers:
        api_key = os.getenv(env_var)
        if api_key:
            model = preferred_model or default_model
            llm = factory(api_key, model)
            if llm:
                return llm

    raise LLMNotConfiguredError()


def _create_anthropic(api_key: str, model: str) -> object | None:
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model_name=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_anthropic not available")
        return None


def _create_google(api_key: str, model: str) -> object | None:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_google_genai not available")
        return None


def _create_openai(api_key: str, model: str) -> object | None:
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_openai not available")
        return None


def _create_fireworks(api_key: str, model: str) -> object | None:
    try:
        from langchain_fireworks import ChatFireworks
        return ChatFireworks(model=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_fireworks not available")
        return None
```

> **Nota**: `_create_mock_llm()` non esiste come funzione separata — il mock è inline in `create_llm()` per semplicità.

### Task 1.4b: Update `chat-orchestrator/config.py` to use factory

```python
from a2a_protocol.llm import create_llm, LLMNotConfiguredError
from .exceptions import LLMNotConfiguredException
from .utils.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """..."""


def get_llm() -> object:
    """Get LLM instance. Wraps shared factory in local exception contract."""
    try:
        return create_llm()
    except LLMNotConfiguredError:
        raise LLMNotConfiguredException()
```

### Task 1.4c: Update `liturgy-agent/main.py` to use factory

```python
# PRIMA: 59 linee di _get_llm() con logica duplicata

class LiturgyAgentHandler:
    def __init__(self):
        self.llm = self._get_llm()   # ← 59 linee
        self.graph = create_liturgy_agent_graph(self.llm)

    def _get_llm(self): ...          # ← 59 linee duplicate


# DOPO: 1 linea

from a2a_protocol.llm import create_llm

class LiturgyAgentHandler:
    def __init__(self):
        self.llm = create_llm()
        self.graph = create_liturgy_agent_graph(self.llm)
    # _get_llm() rimosso
```

### Task 1.4d: Add `langchain-*` as optional deps in a2a-protocol

```toml
# packages/a2a-protocol/pyproject.toml
[project.optional-dependencies]
anthropic = ["langchain-anthropic"]
google = ["langchain-google-genai"]
openai = ["langchain-openai"]
fireworks = ["langchain-fireworks"]
```

I singoli agent continuano a dichiarare le proprie dipendenze dirette nei loro `pyproject.toml` perché il Dockerfile installa solo il package specifico.

---

## 1.5 Fix Liturgy Agent Cache

**File**: `packages/liturgy-agent/src/liturgy_agent/main.py:193`

```python
# PRIMA (cache permanentemente bypassata):
if False and cached:
    logger.info("Cache hit for readings: returning cached data.")
    ...

# DOPO:
if cached:
    logger.info("Cache hit for readings: returning cached data.")
    ...
```

---

# Phase 2 — Error Handling & Packaging

---

## 2.1 Usa eccezioni custom in tools.py

`RuntimeError` diventa `A2ACommunicationException`:

```python
# PRIMA:
raise RuntimeError(f"Failed to get liturgical data: {e}") from e

# DOPO:
from .exceptions import A2ACommunicationException
raise A2ACommunicationException(
    message=f"Failed to get liturgical data: {e}",
    from_agent="chat_orchestrator",
    to_agent="liturgy_agent"
) from e
```

Stessa modifica per tutte le 4 async functions in `tools.py`.

---

## 2.2 Fix a2a-protocol version mismatch

```toml
# pyproject.toml
version = "0.1.0"  # ← resta 0.1.0
```

```python
# __init__.py
__version__ = "0.1.0"  # ← passa da 1.0.0 a 0.1.0
```

---

## 2.3 Remove duplicate dev dep groups in a2a-protocol

Rimuovere `[dependency-groups] dev` (linee 59-64), tenere solo `[project.optional-dependencies] dev`.

---

## 2.4 Add authors/license to all 4 pyproject.toml

```toml
authors = [{name = "Prete-a-porter Contributors", email = "contributors@preteaporter.local"}]
license = {text = "MIT"}
```

Aggiungere a: a2a-protocol, chat-orchestrator, liturgy-agent, homily-agent.

---

## 2.5 Add `__version__` to missing init files

```python
# packages/chat-orchestrator/src/chat_orchestrator/__init__.py
__version__ = "0.1.0"

# packages/homily-agent/src/homily_agent/__init__.py
__version__ = "0.1.0"
```

---

## 2.6 Fix `numpy<2` — add lower bound

```toml
# packages/homily-agent/pyproject.toml
# PRIMA:
"numpy<2",

# DOPO:
"numpy>=1.24.0,<2",
```

---

# Phase 3 — Code Style & Consistency

---

## 3.1 Add ruff/mypy config to all 4 pyproject.toml

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true
```

---

## 3.2 Fix `Evangelize_Scraper` → `EvangelizeScraper`

```python
# packages/liturgy-agent/src/liturgy_agent/scrapers.py
class EvangelizeScraper:  # ← era Evangelize_Scraper
    ...
```

Aggiornare anche tutti i riferimenti (classi che lo estendono o istanziano).

---

## 3.3 Add exception chaining in liturgy agent

```python
# packages/liturgy-agent/src/liturgy_agent/main.py:167
# PRIMA:
raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
# DOPO:
raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD") from e
```

```python
# packages/liturgy-agent/src/liturgy_agent/scrapers.py
# Aggiungere `from e` a tutti i `raise ScraperError(...)` dentro blocchi `except`
```

---

## 3.4 Standardize homily-agent methods

Estrarre la logica condivisa di `_generate_homily`, `_refine_homily`, `_adjust_tone`:

```python
def _invoke_graph(
    self,
    params: Dict[str, Any],
    intent: Literal["generate", "refine", "adjust"],
) -> Dict[str, Any]:
    """Execute graph with given parameters and intent."""
    from .state import HomilyAgentState, LiturgicalReading, UserPreferences
    from .graph import GraphState

    liturgical_data = params.get("liturgical_data")
    occasion = params.get("occasion", "mass")
    preferences = params.get("preferences", {})
    existing_draft = params.get("existing_draft")

    lit_reading = LiturgicalReading(**liturgical_data) if liturgical_data else None
    user_prefs = UserPreferences(**preferences) if preferences else UserPreferences()

    initial_state = HomilyAgentState(
        intent=intent,
        liturgical_data=lit_reading,
        occasion=occasion,
        user_preferences=user_prefs,
        existing_draft=existing_draft,
    )

    graph_state: GraphState = {"homily_state": initial_state}
    final_state = self.graph.invoke(graph_state)
    homily_state = final_state["homily_state"]

    return {
        "homily": homily_state.generated_homily.model_dump() if homily_state.generated_homily else None,
        "sources": homily_state.theological_sources or [],
    }


async def _generate_homily(self, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = self._invoke_graph(params, intent="generate")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error generating homily: {e}")
        raise


async def _refine_homily(self, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = self._invoke_graph(params, intent="refine")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error refining homily: {e}")
        raise


async def _adjust_tone(self, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = self._invoke_graph(params, intent="adjust")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error adjusting tone: {e}")
        raise
```

---

# Execution Order (Dependency Graph)

```
Phase 1 (strutturale):

  ┌─ 1.0 Fix TOOLS_REGISTRY bug (1 file, 2 righe)
  │
  ├─ 1.5 Fix cache (1 file, 1 right)
  │
  ├─ 1.4 LLM factory (a2a-protocol/llm.py + 2 agent updates)
  │     └── 1.4a Create llm.py
  │     ├── 1.4b Update chat-orchestrator/config.py  
  │     └── 1.4c Update liturgy-agent/main.py
  │
  ├─ 1.1 Split main.py (4 nuovi file, 1 ridotto)
  │     └── Dopo 1.0 (registry già fixato)
  │     └── Dopo 1.4 (config.py usa LLM factory)
  │     ├── Crea graph.py (da tools.py importa tool sync)
  │     └── Crea routes.py, aggiorna main.py
  │
  ├─ 1.2 Convert sync→async (tools.py + graph.py)
  │     └── Dopo 1.1 (graph.py già estratto)
  │     ├── Modifica 4 @tool → async
  │     ├── Modifica agent_node → async (ainvoke)
  │     └── Modifica tools_node → async (ainvoke)
  │
  └─ 1.3 Split server.py (indipendente da 1.1-1.2)
        └── Estrae route handlers + helper JSON-RPC
        └── Sanitizza errori

Phase 2 (errori + packaging) — indipendente da Phase 1
  ├── 2.1 Custom exceptions in tools.py
  ├── 2.2 Fix version mismatch
  ├── 2.3 Remove duplicate dep groups
  ├── 2.4 Add authors/license (4 pyproject.toml)
  ├── 2.5 Add __version__
  └── 2.6 Fix numpy lower bound

Phase 3 (stile) — dopo tutto
  ├── 3.1 Add ruff/mypy config
  ├── 3.2 Fix EvangelizeScraper naming
  ├── 3.3 Add exception chaining
  └── 3.4 Standardize homily methods
```
