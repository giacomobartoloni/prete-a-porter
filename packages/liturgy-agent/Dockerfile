# Liturgy Agent Dockerfile
# HTTP-only A2A server on port 8001

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
# Copy a2a-protocol fully (local dependency needs source)
COPY packages/a2a-protocol /app/packages/a2a-protocol
COPY packages/liturgy-agent/pyproject.toml /app/packages/liturgy-agent/
COPY packages/liturgy-agent/uv.lock /app/packages/liturgy-agent/

# Copy contract file for runtime agent metadata
COPY contracts/liturgy-agent-contract.json /app/contracts/liturgy-agent-contract.json

# Stage 2: Set working directory to liturgy-agent
WORKDIR /app/packages/liturgy-agent

# Stage 3: Install dependencies (cached if pyproject.toml/uv.lock unchanged)
RUN uv sync --frozen --no-install-project

# Stage 4: Copy source code (invalidates only this layer when code changes)
COPY packages/liturgy-agent /app/packages/liturgy-agent

# Stage 5: Install project
RUN uv sync --frozen

# Expose HTTP port
EXPOSE 8001

# Health check for HTTP endpoint
# Uses JSON-RPC 2.0 ping method with uv run to access venv
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD uv run python -c "import httpx; r = httpx.post('http://localhost:8001/a2a', json={'jsonrpc': '2.0', 'id': 'health', 'method': 'agent.ping', 'params': {}}, timeout=5.0); exit(0 if r.status_code == 200 and r.json().get('result', {}).get('status') == 'pong' else 1)"

# Set entry point for HTTP server
ENTRYPOINT ["uv", "run", "python", "-m", "liturgy_agent.main", "--port", "8001"]