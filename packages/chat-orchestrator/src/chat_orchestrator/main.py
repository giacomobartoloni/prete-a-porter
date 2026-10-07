"""
Chat Orchestrator — WebSocket server for agent coordination.

Coordinates liturgy-agent and homily-agent via A2A protocol.
"""

import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .api.v1 import router as openai_router
from .error_handlers import register_exception_handlers
from .graph import get_graph
from .routes import chat_websocket, correlation_id_middleware, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: build the graph on startup."""
    await get_graph()
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(correlation_id_middleware)

app.include_router(openai_router)

# Rate limit health endpoint
@app.get("/health")
@limiter.limit("30/minute")
async def health_limited(request: Request):
    return await health()

# Rate limiter for WebSocket — simple per-IP connection tracker
_ws_connections: dict = defaultdict(list)
WS_MAX_CONNECTIONS_PER_IP = 10
WS_WINDOW_SECONDS = 60


def check_ws_rate_limit(websocket) -> bool:
    """Check if this IP has exceeded the WebSocket connection rate."""
    client_host = websocket.client.host if websocket.client else "unknown"
    now = time.time()
    window_start = now - WS_WINDOW_SECONDS

    conns = _ws_connections[client_host]
    conns[:] = [t for t in conns if t > window_start]

    if len(conns) >= WS_MAX_CONNECTIONS_PER_IP:
        return False

    conns.append(now)
    return True

app.websocket("/ws/chat/{session_id}")(chat_websocket)


def start() -> None:
    """Start the application using Uvicorn."""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start()
