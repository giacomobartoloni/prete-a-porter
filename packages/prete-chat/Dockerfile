# Prete-chat Dockerfile
# Chainlit native conversational UI on port 8000 (published as 127.0.0.1:3003)

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
COPY packages/prete-chat/pyproject.toml /app/packages/prete-chat/
COPY packages/prete-chat/uv.lock /app/packages/prete-chat/

# Stage 2: Copy local dependency sources (both are editable path deps)
COPY packages/a2a-protocol /app/packages/a2a-protocol
COPY packages/chat-orchestrator /app/packages/chat-orchestrator

# Stage 3: Set working directory to prete-chat
# Chainlit resolves .chainlit/config.toml and public/ from here.
WORKDIR /app/packages/prete-chat

# Stage 4: Install dependencies (cached if pyproject.toml/uv.lock unchanged)
RUN uv sync --frozen --no-install-project

# Stage 5: Copy source code (invalidates only this layer when code changes)
COPY packages/prete-chat /app/packages/prete-chat

# Stage 6: Install project
RUN uv sync --frozen

# Expose Chainlit port
EXPOSE 8000

# Chainlit serves GET /health (chainlit/server.py)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD uv run python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/health', timeout=5.0).status_code == 200 else 1)"

# -h runs headless: no attempt to open a browser inside the container
ENTRYPOINT ["uv", "run", "chainlit", "run", "src/prete_chat/app.py", "-h", "--host", "0.0.0.0", "--port", "8000"]
