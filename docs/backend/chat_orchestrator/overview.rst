=====================
Chat Orchestrator
=====================

Overview
========

The Chat Orchestrator is the main entry point for user interactions. It handles WebSocket connections, message processing, tool invocation, and session management.

**Location**: ``packages/chat-orchestrator/src/chat_orchestrator/``

**Modules**:

- ``state.py`` - ChatState and MessagesState models
- ``agent.py`` - Agent node for LLM invocation
- ``graph.py`` - LangGraph StateGraph construction
- ``tools.py`` - Tool definitions and registry

Architecture
============

The orchestrator uses a ReAct (Reasoning + Acting) pattern:

.. code-block:: text

    Entry Point: agent_node
           |
           v
    Should continue to tools?
           |
      +----+----+
      |         |
     No       Yes
      |         |
      v         v
     END   tools_node
             |
             v
         agent_node (loop)

State Flow
==========

1. **agent_node**: LLM processes messages and decides whether to use tools
2. **Conditional Edge**: Check ``next_action`` field
3. **tools_node**: Execute any tool calls from LLM
4. **Loop**: Return to agent_node if tools were called

Tool Binding
============

The orchestrator binds tools to the LLM using LangChain's ``bind_tools()`` method:

.. code-block:: python

    tools = [get_current_date, calculate_date]
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(messages)

Available tools are registered in the TOOLS_REGISTRY dictionary.

Session Persistence
====================

Each session is identified by a unique ``session_id`` and uses SQLite for state persistence:

- **Storage**: ``packages/chat-orchestrator/data/chat_orchestrator.db``
- **Checkpointer**: ``langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver``
- **Configuration**: ``DATABASE_PATH`` environment variable

Sessions survive reconnections and server restarts.

WebSocket Protocol
==================

**Endpoint**: ``/ws/chat/{session_id}``

**Message Format** (User → Server)::

    "Your message here"

**Response Format** (Server → User)::

    {
        "type": "message",
        "content": "Response text here",
        "session_id": "sess-abc123"
    }

**Error Format**::

    {
        "type": "error",
        "error": {
            "code": "ERROR_CODE",
            "message": "Error message in Italian",
            "correlation_id": "trace-xyz789"
        }
    }

Configuration
=============

Environment Variables::

    # Database
    DATABASE_PATH=data/chat_orchestrator.db
    
    # LLM API Keys (at least one required)
    ANTHROPIC_API_KEY=sk-...
    GOOGLE_API_KEY=...
    
    # Logging
    LOG_LEVEL=INFO
    LOG_JSON_FORMAT=false
    
    # Testing
    TEST_MODE=false

Logging
=======

The orchestrator logs all significant events:

- Connection/disconnection (INFO)
- Message processing (DEBUG)
- Tool execution (DEBUG)
- Errors (ERROR with correlation_id)

Example log entry::

    {
        "timestamp": "2026-02-20T10:30:45.123Z",
        "level": "DEBUG",
        "logger": "chat_orchestrator",
        "message": "Message received",
        "session_id": "sess-abc123",
        "correlation_id": "trace-xyz789",
        "message_number": 3
    }

Error Handling
==============

The orchestrator implements comprehensive error handling:

**LLM Errors**:
- ``LLMNotConfiguredException`` - No API key configured
- ``LLMRateLimitException`` - Rate limit exceeded
- ``LLMTimeoutException`` - Request timeout
- ``LLMContentException`` - Content safety violation

**Tool Errors**:
- ``ToolNotFoundException`` - Requested tool not found
- ``ToolExecutionException`` - Tool execution failed

**WebSocket Errors**:
- ``WebSocketConnectionException`` - Connection failed
- ``WebSocketMessageException`` - Message handling failed

All errors are logged with context (session_id, correlation_id) and sent to client with Italian messages.

Performance Considerations
===========================

**Response Time Targets**:

- Tool execution: < 1 second
- LLM invocation: < 10 seconds
- Total message round-trip: < 15 seconds (including LLM + tools)

**Optimization Strategies**:

1. **Caching**: Tool results cached in session state (Phase 2+)
2. **Streaming**: LLM responses streamed to client (Phase 5+)
3. **Connection Pooling**: Database connection pooling via SQLite
4. **Async I/O**: All operations async (FastAPI + asyncio)

Testing
=======

See :doc:`../testing` for comprehensive testing information.

**Key Test Scenarios**:

- WebSocket connection/disconnection
- Message sending and response receiving
- Session persistence across reconnections
- Tool execution and error handling
- Concurrent sessions with different state

API Reference
=============

See the module reference pages:

.. toctree::
   :maxdepth: 2

   state
   agent
   graph
   tools
