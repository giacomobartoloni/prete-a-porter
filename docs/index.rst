==================
Prete-a-porter
==================

Welcome to Prete-a-porter documentation! This is a multi-agent AI system for generating homilies and retrieving liturgical information.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   introduction
   architecture
   backend/index
   frontend/index
   deployment
   testing
   troubleshooting

Introduction
============

Prete-a-porter is a comprehensive homily generation and liturgical information retrieval system built with modern AI technologies. It supports multiple liturgical occasions (masses, marriages, baptisms, funerals) and provides multi-agent architecture for scalability.

See `AGENTS.md <../AGENTS.md>`_ for the full agent architecture documentation.

Key Features
-----------

- **Multi-Agent Architecture**: Modular agents for chat orchestration, liturgical data retrieval, and homily generation
- **LLM Integration**: Support for Claude 3.5 Sonnet and Google Gemini
- **WebSocket Communication**: Real-time chat interface over WebSocket
- **Session Persistence**: SQLite-based session management
- **Structured Logging**: JSON logging with correlation IDs and sensitive data filtering
- **Error Handling**: Comprehensive error handling with Italian user messages
- **RAG-Powered**: Retrieval-Augmented Generation for context-aware responses
- **Liturgical Data**: Web scraping for daily Mass readings and ritual-specific lectionaries

Tech Stack
----------

**Backend**:

- FastAPI (web framework)
- LangGraph (agent orchestration)
- LangChain (LLM integration)
- SQLite (session persistence)
- structlog (structured logging)

**Frontend**:

- Next.js 14 (React framework)
- TypeScript (type safety)
- Tailwind CSS (styling)
- WebSocket (real-time communication)

**Infrastructure**:

- Docker & Docker Compose
- Kubernetes-ready (Phase 7)

Quick Start
-----------

See the :doc:`deployment` guide for setup instructions.

Contributing
-----------

This project follows the "Always Develop Tests" philosophy. Every feature must include:

- Type hints for all functions
- Comprehensive docstrings
- Unit tests (70% minimum coverage)
- Integration tests for complex flows

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
