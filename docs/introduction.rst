===============
Introduction
===============

Welcome to Prete-a-porter! This document introduces the system and provides a roadmap for using the documentation.

What is Prete-a-porter?
=======================

**Prete-a-porter** (Italian for "ready-to-wear") is an AI-powered system for generating homilies and retrieving liturgical information. It combines modern AI technology with Catholic theological traditions to help priests craft meaningful sermons for any occasion.

Key Features
============

- **Multi-Occasion Support**: Generate homilies for Mass, marriages, baptisms, and funerals
- **Real-time Retrieval**: Fetch daily liturgical readings via web scraping
- **RAG-Powered**: Retrieval-Augmented Generation for contextual, theologically accurate content
- **WebSocket Chat**: Real-time conversation interface
- **Distributed Architecture**: Multi-agent system that scales independently
- **Structured Logging**: Full observability with correlation IDs

Who Should Read This?
=====================

- **Developers**: Implementing features and maintaining the codebase
- **DevOps Engineers**: Deploying and operating the system
- **System Administrators**: Managing infrastructure and backups
- **Theologians**: Reviewing theological accuracy and refining prompts
- **Users**: Operating the chat interface

Documentation Structure
=======================

- **:doc:`introduction`** (this document) - Overview and orientation
- **:doc:`architecture`** - System design and component overview
- **:doc:`backend/index`** - Backend API and module documentation (see also `AGENTS.md <../AGENTS.md>`_ for agent architecture)
- **:doc:`frontend/index`** - Frontend components and usage
- **:doc:`deployment`** - Deployment guides for all environments
- **:doc:`testing`** - Testing philosophy and strategies
- **:doc:`troubleshooting`** - Common issues and solutions

Quick Start
===========

For the impatient, here's the quickest path to a working system:

**Development Setup** (10 minutes):

1. Clone repository
2. Create `packages/chat-orchestrator/.env` with API keys
3. Start backend: `cd packages/chat-orchestrator && uv run uvicorn src.chat_orchestrator.main:app --reload`
4. Start frontend: `cd frontend && npm install && npm run dev`
5. Open http://localhost:3000

**Production Deployment** (See :doc:`deployment`):

Deploy with Docker Compose for multi-container setup:

.. code-block:: bash

    docker-compose up -d

Key Concepts
============

Chat Orchestrator
-----------------

The main entry point for user conversations. It:

- Handles WebSocket connections
- Invokes tools (date calculations, liturgical data, homily generation)
- Manages session state with SQLite
- Routes to specialized agents (Phase 2+)

Agents (Future)
---------------

Specialized AI agents for specific tasks:

- **Liturgy Agent** (Phase 2): Retrieves liturgical readings
- **Homily Agent** (Phase 4): Generates homilies with RAG

A2A Protocol
------------

Agent-to-Agent communication protocol allowing:

- Chat Orchestrator to request data from specialized agents
- Stdio transport for development (Phase 1-4)
- HTTP/SSE transport for production (Phase 7)

Technology Stack
================

**Backend**:

- Python 3.12, FastAPI, LangGraph, LangChain
- SQLite (development), PostgreSQL (production)
- structlog (structured logging)

**Frontend**:

- Next.js 14, React 18, TypeScript
- Tailwind CSS
- WebSocket

**Infrastructure**:

- Docker & Docker Compose
- Kubernetes (Phase 7)

Development Phases
==================

The project is organized into phases:

- **Phase 1**: Foundation (SQLite, logging, modularization) ✅ **IN PROGRESS**
- **Phase 2**: Liturgy Agent (web scraping, caching)
- **Phase 3**: A2A Protocol (agent communication)
- **Phase 4**: Homily Agent (RAG, generation)
- **Phase 5**: Frontend Enhancement (rich components)
- **Phase 6**: Testing & QA
- **Phase 7**: Production (microservices, deployment)

Current Status: Phase 1 (Sub-phase 1.5 - Documentation)

Getting Setup
=============

See :doc:`deployment` for detailed setup instructions:

- **Local Development** (monolithic, fastest iteration)
- **Docker Compose** (multi-container, closer to production)
- **Kubernetes** (production, fully distributed)

Philosophy
==========

Prete-a-porter follows these core principles:

**Always Develop Tests**
  No feature is complete without tests. Minimum 70% coverage for all new code.

**Structured Logging**
  All operations are logged with correlation IDs for end-to-end tracing.

**Error Handling**
  Comprehensive error handling with user-friendly Italian messages.

**Modular Design**
  Clean separation of concerns, independent scaling of components.

**Type Safety**
  Full type hints and docstrings throughout codebase.

Finding Information
==================

**I want to:**

- **Deploy the system** → See :doc:`deployment`
- **Write or understand code** → See :doc:`backend/index` and `AGENTS.md <../AGENTS.md>`_ for agent architecture
- **Work on frontend** → See :doc:`frontend/index`
- **Set up tests** → See :doc:`testing`
- **Fix a problem** → See :doc:`troubleshooting`
- **Understand architecture** → See :doc:`architecture`

Contributing
============

All contributions should follow the project's philosophy:

1. Write tests first or concurrently
2. Add type hints and docstrings
3. Update documentation
4. Maintain or improve test coverage
5. Follow existing code style

Next Steps
==========

1. **Read** :doc:`architecture` for system overview
2. **Set up** development environment (:doc:`deployment`)
3. **Explore** code in appropriate module docs
4. **Write** tests as you develop features

Questions?
==========

- **Code questions** → See relevant module documentation
- **Deployment questions** → See :doc:`deployment`
- **Issues** → See :doc:`troubleshooting`
- **Architecture questions** → See :doc:`architecture`

Current Phase Status
====================

✅ Phase 1.1 - SQLite Integration
  - Completed with AsyncSqliteSaver
  - 100% working

✅ Phase 1.2 - Structured Logging
  - Completed with structlog
  - JSON and human-readable formats
  - Sensitive data filtering

✅ Phase 1.3 - Error Handling
  - 19 custom exception types
  - Italian error messages
  - Global exception handlers

✅ Phase 1.4 - Modularization
  - Chat orchestrator modularized
  - Type hints everywhere
  - Comprehensive docstrings

🔄 Phase 1.5 - Documentation (THIS PHASE)
  - Sphinx documentation system
  - Module documentation
  - Deployment guides
  - Testing strategies

📅 Phase 2 onwards
  - Coming in future iterations

See Also
========

- :doc:`architecture` - Deep dive into system design
- :doc:`troubleshooting` - Common issues and solutions
- `GitHub Repository <https://github.com/...>`_
