======================================
Introduction & Architecture
======================================

System Overview
===============

Prete-a-porter is a distributed AI system for homily generation and liturgical information retrieval. It uses a multi-agent architecture where agents communicate via the A2A (Agent-to-Agent) protocol.

Core Components
===============

Chat Orchestrator
-----------------

The main entry point for user interactions. Handles:

- WebSocket connections from frontend
- User message processing
- Tool invocation (date calculation, liturgical data retrieval, homily generation)
- Session management with SQLite
- Real-time response streaming

Location: ``packages/chat-orchestrator/src/chat_orchestrator/``

Liturgy Agent
-------------

Autonomous agent for retrieving liturgical information. Handles:

- Daily Mass readings from evangelizo.org
- Ritual-specific lectionaries (marriages, baptisms, funerals, etc.)
- Liturgical metadata (season, liturgical color, year cycle)
- Response caching (24-hour TTL)

Location: ``packages/liturgy-agent/src/liturgy_agent/``

Homily Generation Agent
-----------------------

AI-powered agent for generating contextual homilies. Handles:

- RAG-powered content retrieval
- Occasion-specific generation (mass, marriage, baptism, funeral)
- Rhetorical device integration (metaphors, analogies, parables)
- Theological validation
- Iterative refinement

Location: ``packages/homily-agent/src/homily_agent/``

Deployment Models
=================

Development (Phase 1-4)
----------------------

**Monolithic Architecture**:

.. code-block:: text

    Frontend -> Chat Orchestrator -> (in-process agents via stdio)
                      |
                      +-> Liturgy Agent (stdio)
                      +-> Homily Agent (stdio)

- Single Python process
- A2A protocol uses stdio transport
- Simplified debugging and development
- Lower resource requirements

Production (Phase 7)
-------------------

**Microservices Architecture**:

.. code-block:: text

    Frontend -> Load Balancer -> Chat Orchestrator (container)
                                      |
                                      +-> Liturgy Agent (container) via HTTP/SSE
                                      +-> Homily Agent (container) via HTTP/SSE
                                      +-> Vector DB (Chroma/Pinecone)
                                      +-> PostgreSQL (if scaling)

- Each agent runs in separate container
- A2A protocol uses HTTP/SSE transport
- Independent scaling per service
- Kubernetes-ready deployments

Request Flow
============

1. **User Message**: Frontend sends message via WebSocket
2. **Chat Orchestrator**: Receives and processes message
3. **Tool Invocation**: May call date tools, liturgical data, or homily generation
4. **Agent Communication**: Uses A2A protocol to coordinate with other agents
5. **Response Generation**: Aggregates responses and sends back to frontend
6. **Session Persistence**: State saved to SQLite

Data Flow Example: Homily Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    User Input: "Generate homily for Mass next Sunday"
    
    Chat Orchestrator:
    1. Parse user intent (occasion: Mass, date: next Sunday)
    2. Call Liturgy Agent for Sunday readings
    3. Call Homily Agent with readings + Mass context
    4. Stream response to user

State Management
================

ChatState (Chat Orchestrator)
----------------------------------

- ``messages``: Conversation history (LangGraph MessagesState)
- ``session_id``: User session identifier
- ``next_action``: Control flow ("continue" for tools, "end" for response)

LiturgyAgentState (Liturgy Agent, Phase 2)
-------------------------------------------

- ``date``: Target date for readings
- ``occasion``: Type of liturgical event
- ``cached_data``: Retrieved readings (if cached)
- ``error``: Error information (if any)

HomilyAgentState (Homily Agent, Phase 4)
-----------------------------------------

- ``readings``: Liturgical readings from Liturgy Agent
- ``occasion``: Type of homily (mass, marriage, baptism, funeral)
- ``user_preferences``: Rhetorical preferences, tone, etc.
- ``outline``: Generated homily outline
- ``sections``: Generated homily sections
- ``full_homily``: Complete homily text

Logging & Tracing
=================

All requests are traced using correlation IDs:

1. Generated at request entry (or from X-Correlation-ID header)
2. Propagated through all logs
3. Returned in response headers
4. Used for end-to-end tracing

Example Log Entry::

    {
        "timestamp": "2026-02-20T10:30:45.123Z",
        "level": "INFO",
        "logger": "chat_orchestrator",
        "message": "Message received",
        "session_id": "sess-abc123",
        "correlation_id": "trace-xyz789",
        "message_count": 5
    }

Error Handling
==============

Layered error handling strategy:

**Global Level** (FastAPI middleware)
- Catches unhandled exceptions
- Returns 500 with error details
- Always includes correlation_id

**Service Level** (Agent nodes)
- Try-catch blocks in critical sections
- Custom exceptions with Italian messages
- Recoverable errors (retries, fallbacks)

**Protocol Level** (WebSocket)
- Errors sent as JSON messages before disconnect
- User-friendly Italian messages
- Server-side detailed logging

See :doc:`troubleshooting` for error codes and recovery procedures.
