================
Backend Modules
================

Chat Orchestrator
=================

Core orchestrator handling WebSocket communication and message processing.

.. toctree::
   :maxdepth: 2

   chat_orchestrator/overview
   chat_orchestrator/state
   chat_orchestrator/agent
   chat_orchestrator/graph
   chat_orchestrator/tools

Main Application
================

FastAPI application setup and endpoints.

.. automodule:: main
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
=========

Logging configuration and helper utilities.

.. toctree::
   :maxdepth: 2

   utils/logging

Error Handling
==============

Custom exception classes and global error handlers.

.. automodule:: exceptions
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: error_handlers
   :members:
   :undoc-members:
   :show-inheritance:

Liturgy Agent
=============

See ``packages/liturgy-agent/src/liturgy_agent/``. Full details in `AGENTS.md <../../AGENTS.md>`_.

.. code-block:: text

    packages/liturgy-agent/src/liturgy_agent/
    ├── __init__.py
    ├── agent.py          # Agent nodes
    ├── graph.py          # StateGraph setup
    ├── state.py          # LiturgyAgentState
    ├── scrapers.py       # Web scraping
    ├── cache.py          # SQLite caching
    └── main.py           # Entry point

Homily Generation Agent
=======================

See ``packages/homily-agent/src/homily_agent/``. Full details in `AGENTS.md <../../AGENTS.md>`_.

.. code-block:: text

    packages/homily-agent/src/homily_agent/
    ├── __init__.py
    ├── agent.py
    ├── graph.py
    ├── state.py
    ├── generator.py      # Generation logic
    ├── rag/
    │   ├── embeddings.py
    │   └── retrieval.py
    └── main.py
