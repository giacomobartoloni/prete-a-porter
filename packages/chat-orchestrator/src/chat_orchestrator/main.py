"""
Chat Orchestrator — WebSocket server for agent coordination.

Coordinates liturgy-agent and homily-agent via A2A protocol.
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .cleanup import cleanup_old_checkpoints
from .error_handlers import register_exception_handlers
from .graph import get_graph
from .routes import chat_websocket, correlation_id_middleware, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start cleanup task on startup, cancel on shutdown."""
    graph = await get_graph()
    cleanup_task = asyncio.create_task(_periodic_cleanup(graph))
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


async def _periodic_cleanup(graph):
    """Run cleanup every 24 hours."""
    interval = int(os.getenv("CHECKPOINT_CLEANUP_INTERVAL", "86400"))
    while True:
        await asyncio.sleep(interval)
        try:
            await cleanup_old_checkpoints(graph)
        except Exception as e:
            logger.error("Periodic cleanup failed", error=str(e))


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


@app.delete("/checkpoints/{session_id}")
async def delete_checkpoint(session_id: str):
    """Delete a checkpoint by session ID (fire-and-forget from frontend)."""
    try:
        graph = await get_graph()
        await graph.checkpointer.adelete_thread(session_id)
    except Exception:
        pass
    return Response(status_code=204)


def start() -> None:
    """Start the application using Uvicorn."""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start()
