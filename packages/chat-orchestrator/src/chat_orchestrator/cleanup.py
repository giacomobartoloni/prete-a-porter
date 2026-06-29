"""Background task for cleaning up old checkpoints."""

import os
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def cleanup_old_checkpoints(graph) -> int:
    """Delete checkpoints older than CHECKPOINT_TTL_DAYS (default 90)."""
    ttl_days = int(os.getenv("CHECKPOINT_TTL_DAYS", "90"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    deleted = 0

    try:
        async for checkpoint in graph.checkpointer.alist():
            ts_str = checkpoint.checkpoint.get("ts")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    thread_id = checkpoint.config["configurable"]["thread_id"]
                    await graph.checkpointer.adelete_thread(thread_id)
                    deleted += 1
            except (ValueError, TypeError):
                continue
    except Exception as e:
        logger.error("Cleanup iteration failed", error=str(e))

    logger.info("Cleanup complete: deleted %d old checkpoints", deleted)
    return deleted
