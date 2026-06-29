# Chat Orchestrator Dockerfile
# WebSocket-enabled FastAPI server on port 8000

FROM python:3.12-slim AS base

# Install UV for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# Set working directory
WORKDIR /app

# Stage 1: Copy dependency files FIRST (for layer caching)
COPY packages/a2a-protocol/pyproject.toml /app/packages/a2a-protocol/
COPY packages/chat-orchestrator/pyproject.toml /app/packages/chat-orchestrator/
COPY packages/chat-orchestrator/uv.lock /app/packages/chat-orchestrator/

# Stage 2: Copy local dependency source (a2a-protocol needed for build)
COPY packages/a2a-protocol /app/packages/a2a-protocol

# Stage 3: Set working directory to chat-orchestrator
WORKDIR /app/packages/chat-orchestrator

# Stage 4: Install dependencies (cached if pyproject.toml/uv.lock unchanged)
RUN uv sync --frozen --no-install-project

# Stage 5: Copy source code (invalidates only this layer when code changes)
COPY packages/chat-orchestrator /app/packages/chat-orchestrator

# Stage 6: Install project
RUN uv sync --frozen

# Expose WebSocket port
EXPOSE 8000

# Health check for WebSocket endpoint
# Uses /health endpoint with uv run to access venv
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD uv run python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/health', timeout=5.0).status_code == 200 else 1)"

# Set entry point for WebSocket server
ENTRYPOINT ["uv", "run", "python", "-m", "uvicorn", "chat_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]