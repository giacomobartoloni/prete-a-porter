# SPECIFICATION.md

## Project Overview

**Project Name**: Prete-a-porter  
**Version**: 1.0.0  
**Architecture**: Multi-Agent System with Agent-to-Agent (A2A) Communication  
**Primary Language**: English (code, comments, documentation)  
**User Interface Language**: Italian (primary), multi-language support planned

---

## System Purpose

An AI-powered system to assist Catholic priests and deacons in preparing liturgically accurate and pastorally effective homilies. The system leverages autonomous agents communicating via standardized A2A protocols to provide liturgical data retrieval, homily generation guidance, and iterative refinement.

---

## High-Level Architecture

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                          │
│                    (Web Chat Interface)                      │
└────────────────────────────┬────────────────────────────────┘
                             │ WebSocket
                             ↓
┌─────────────────────────────────────────────────────────────┐
│              CHAT ORCHESTRATOR AGENT                         │
│              (Homily Assistant Agent)                        │
│                                                              │
│  Role: Conversation management, workflow coordination        │
│  Capabilities:                                               │
│  - Natural language conversation with users                  │
│  - Extract user preferences and requirements                 │
│  - Coordinate with specialized agents                        │
│  - Guide homily preparation workflow                         │
│  - Iterative refinement based on feedback                    │
│                                                              │
│  Technology: LangGraph + Claude/Gemini                       │
└─────────────┬──────────────────────────────┬────────────────┘
              │ A2A Protocol                 │ A2A Protocol
              │ (a2a-protocol.org)           │ (a2a-protocol.org)
              ↓                              ↓
┌─────────────────────────────┐  ┌─────────────────────────────┐
│       LITURGY AGENT         │  │   HOMILY GENERATION AGENT   │
│  (Liturgical Data Spec.)    │  │   (Content Generator)       │
│                             │  │                             │
│  Role: Liturgical data      │  │  Role: Homily content       │
│  retrieval and validation   │  │  generation and refinement  │
│                             │  │                             │
│  Capabilities:              │  │  Capabilities:              │
│  - Parse liturgical reqs    │  │  - Generate homily drafts   │
│  - Resolve date expressions │  │  - RAG with theological KB  │
│  - Intelligent caching      │  │  - Style adaptation         │
│  - Web scraping fallbacks   │  │  - Multi-section structure  │
│  - Calendar calculations    │  │  - Iterative refinement     │
│  - Context-aware responses  │  │  - Pastoral contextualize   │
│                             │  │                             │
│  Tech: LangGraph + LLM      │  │  Tech: LangGraph + LLM      │
│  + Web Scrapers             │  │  + RAG + Vector Store       │
└─────────────────────────────┘  └─────────────────────────────┘
```

---

## Core Components

The system consists of three specialized agents and a frontend. See [`AGENTS.md`](./AGENTS.md) for complete details.

| Component | Location | Role |
|-----------|----------|------|
| **Chat Orchestrator** | `packages/chat-orchestrator/` | Conversation management, agent coordination, WebSocket gateway |
| **Liturgy Agent** | `packages/liturgy-agent/` | Liturgical data retrieval, web scraping, caching |
| **Homily Agent** | `packages/homily-agent/` | RAG-powered homily generation, refinement, validation |
| **Frontend** | `frontend/` | Next.js 14 chat interface |

---

## Agent-to-Agent (A2A) Protocol

The system uses JSON-RPC 2.0 for inter-agent communication via stdio (development) or HTTP/SSE (production) transports. See [`AGENTS.md`](./AGENTS.md#2-agent-to-agent-a2a-protocol) for the complete protocol specification including message format, error codes, and capability matrix.

---

## Data Models

All data models are defined in each agent's `state.py` file. See [`AGENTS.md`](./AGENTS.md#6-data-models) for the canonical definitions of `LiturgicalDay`, `Reading`, and agent state types. The key structures are implemented as Pydantic models in:

- `packages/liturgy-agent/src/liturgy_agent/state.py`
- `packages/homily-agent/src/homily_agent/state.py`
- `packages/chat-orchestrator/src/chat_orchestrator/state.py`

---

## Technical Specifications

### Backend

#### Language & Runtime
- Python 3.11+
- Async/await throughout
- Type hints required (mypy compliance)

#### Core Dependencies
```
# Shared dependencies
fastapi==0.109.0
uvicorn[standard]==0.27.0
websockets==12.0
langgraph==0.2.28
langchain-core==0.1.23
langchain-anthropic==0.1.4
langchain-google-genai==2.0.0
pydantic==2.6.0
python-dotenv==1.0.0
aiosqlite==0.19.0  # Async SQLite

# A2A Protocol (a2a-protocol.org compliant)
a2a-protocol==0.1.0  # A2A protocol implementation

# Liturgy Agent specific
httpx==0.26.0
beautifulsoup4==4.12.0
lxml==5.1.0

# Homily Generation Agent specific
langchain-openai==0.0.5  # For GPT-4 and embeddings
pinecone-client==3.0.0  # Vector database
chromadb==0.4.22  # Alternative vector database
sentence-transformers==2.3.1  # For embeddings
```

#### LangGraph Pattern
- **StateGraph**: All agents use LangGraph's StateGraph
- **ReAct Loop**: Reasoning + Acting pattern
- **Tool Calling**: Native LLM tool binding via `bind_tools()`
- **Checkpointer**: MemorySaver for state persistence
- **Recursion Limit**: 15 iterations max per request

#### API Endpoints

**Chat Orchestrator**:
- `GET /health` - Health check
- `WS /ws/chat/{session_id}` - WebSocket chat endpoint

**Liturgy Agent**:
- A2A Server (stdio or HTTP/SSE)
- No REST API endpoints (agent-only interface)

**Homily Generation Agent**:
- A2A Server (stdio or HTTP/SSE)
- No REST API endpoints (agent-only interface)

---

### Frontend

#### Language & Framework
- TypeScript (strict mode)
- Next.js 14 (App Router)
- React 18

#### Core Dependencies
```json
{
  "next": "14.1.0",
  "react": "^18",
  "react-dom": "^18",
  "lucide-react": "^0.323.0",
  "tailwindcss": "^3.4.0"
}
```

#### WebSocket Communication
- Native WebSocket API
- Auto-reconnection on disconnect
- Connection status indicators
- Message queuing during reconnection

---

### Infrastructure

#### Development
```yaml
# docker-compose.yml
services:
  # SQLite databases are file-based, no service needed
  # Database files stored in packages/*/data/
```

#### Production (Future)
- Kubernetes deployment
- SQLite with persistent volumes (or PostgreSQL for high-scale)
- Vector database (Pinecone/Chroma) managed service
- Load balancing
- Horizontal scaling of agents
- CDN for static assets

---

## Workflow Specifications

See [`AGENTS.md`](./AGENTS.md#7-workflows) for the canonical workflow documentation. The system supports four primary flows:

| Flow | Description |
|------|-------------|
| **Homily Preparation** | User requests Sunday homily → date resolution → liturgy agent → readings display → homily generation → refinement |
| **Occasion-Specific** | Marriage/baptism/funeral → ritual lectionary → occasion-adapted homily |
| **Date Validation** | Local tool check for invalid dates (no A2A needed) |
| **Liturgical Search** | Search readings by theme via liturgy agent |

---

## Configuration

All agents are configured via environment variables. See `.env.example` files in each package and [`AGENTS.md`](./AGENTS.md#8-configuration) for the complete configuration reference. Key variables:

| Component | Config file |
|-----------|-------------|
| Chat Orchestrator | `packages/chat-orchestrator/.env.example` |
| Liturgy Agent | `packages/liturgy-agent/.env.example` |
| Homily Agent | `packages/homily-agent/.env.example` |
| Frontend | `frontend/.env.local` (not committed) |

---

## Security & Privacy

### Data Handling
- **No PII Storage**: User conversations not persisted beyond session
- **Session Isolation**: Each WebSocket session isolated via unique ID
- **Secure Connections**: WSS (WebSocket Secure) in production
- **API Key Security**: Environment variables only, never committed

### Rate Limiting
- WebSocket: Max 100 messages/minute per session
- LLM Calls: Governed by provider limits
- Scraping: Respectful delays between requests

### Error Handling
- Sensitive errors sanitized before user display
- Full error traces logged server-side only
- Graceful degradation on service failures

---

## Testing Strategy

See [`AGENTS.md`](./AGENTS.md#9-testing) for per-agent test locations and commands. The project follows the testing pyramid:

- **Unit tests** — Individual modules (tools, graph nodes, scrapers, A2A messages)
- **Integration tests** — Agent boundaries, A2A communication, WebSocket flows
- **E2E tests** — Complete user conversation flows across all agents

---

## Performance Requirements

### Response Times (P95)
- Simple queries (date calculation): < 500ms
- Liturgical data (cache hit): < 800ms
- Liturgical data (cache miss): < 5s
- Multi-turn conversations: < 1s per turn

### Scalability
- Concurrent users: 100+ (single instance)
- Messages/second: 50+ per instance
- Horizontal scaling: Stateless design allows multiple instances

### Resource Usage
- Memory: < 512MB per agent instance
- CPU: < 1 core per agent instance (idle)
- SQLite: < 50MB for typical cache and session data

---

## Observability

### Logging
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Correlation IDs across agent calls
- Sensitive data filtering

### Metrics (Future)
- Request latency (per endpoint, per agent)
- Tool usage frequency
- Cache hit rate
- Agent reasoning steps count
- Error rates

### Tracing (Future)
- LangSmith integration for agent traces
- Full conversation replay capability
- Tool call visualization

---

## Future Enhancements

### Phase 2: Enhanced Homily Agent Features
- Advanced theological knowledge base expansion
- Occasion-specific theological corpus (marriage theology, baptismal theology, funeral rites)
- Multi-language homily generation
- Voice narration and audio export
- Homily analytics and effectiveness tracking
- Collaborative editing with other priests

### Phase 3: Multi-Language Support
- UI language switching
- Liturgical data in multiple languages
- LLM responses in user's language

### Phase 4: Advanced Features
- Voice input/output
- Mobile app (React Native)
- Offline mode with local LLM
- Homily library and version control
- Collaboration features (multiple priests)

### Phase 5: Extended Agent Network
- Prayer Agent (daily prayer suggestions)
- Scripture Study Agent (biblical commentary)
- Music Agent (liturgical music recommendations)
- Art Agent (liturgical art and imagery)

---

## Constraints & Limitations

### Current Limitations
- Italian language only (user interface)
- Catholic liturgy only (Roman Rite)
- Supported occasions: Sunday/weekday Mass, marriage, baptism, funeral
- Dependent on external scraping (evangelizo.org availability)
- No offline mode
- Single-user sessions (no collaboration)

### Technical Debt
- Print statements instead of structured logging
- Basic error handling (no circuit breakers)
- No retry logic for scraping failures
- No performance monitoring
- Limited test coverage

### Known Issues
- Gemini tool calling less reliable than Claude
- System prompt may duplicate in conversation history
- No tool execution timeout handling
- WebSocket reconnection not implemented

---

## Success Criteria

### MVP Success Metrics
- [ ] User can request readings for any date and occasion type
- [ ] Readings retrieved within 5 seconds
- [ ] Cache hit rate > 70% after warm-up
- [ ] Agent-to-agent communication works reliably (Liturgy + Homily)
- [ ] Homily generation completes within 30 seconds
- [ ] Generated homilies are theologically sound and liturgically appropriate
- [ ] Occasion-specific content generation (Mass, marriage, baptism, funeral) works correctly
- [ ] No crashes during normal operation
- [ ] Conversation context maintained across turns

### Quality Metrics
- [ ] Liturgical data accuracy: 99%+
- [ ] Date calculation accuracy: 100%
- [ ] Homily generation quality: Native Italian speaker + theological review
- [ ] RAG relevance score: > 0.7 average
- [ ] User satisfaction: Qualitative feedback
- [ ] Response clarity: Native Italian speaker validation

---

## Glossary

**A2A (Agent-to-Agent)**: Communication protocol between autonomous AI agents

**LangGraph**: Framework for building stateful, multi-actor applications with LLMs

**ReAct Pattern**: Reasoning + Acting loop where agent reasons about next action, executes tools, observes results, and repeats

**A2A Protocol**: Agent-to-Agent Protocol - standard protocol for inter-agent communication (https://a2a-protocol.org/)

**RAG (Retrieval-Augmented Generation)**: Technique combining information retrieval with text generation, allowing LLMs to access external knowledge

**Tool Calling**: LLM capability to decide when and how to invoke external functions

**Liturgical Year**: A, B, or C cycle determining which Gospel readings are used

**Ordinary Time**: Liturgical season outside major feast cycles (Advent, Christmas, Lent, Easter)

**Responsorial Psalm**: Psalm sung/recited between first and second readings

**Ritual Lectionary**: Collection of approved Scripture readings for sacramental celebrations (marriages, baptisms, funerals)

**Solemnity**: Highest-ranking liturgical celebration (e.g., Easter, Christmas)

---

## Document Control

**Version**: 1.0.0  
**Last Updated**: 2026-02-19  
**Status**: Draft  
**Next Review**: Upon Phase 1 completion

---

**END OF SPECIFICATIONS**
