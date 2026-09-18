"""Bridge to the chat core: the only module that imports ``chat-orchestrator``.

The adapter's entire core surface lives here — quota counting and the streaming
entry point — so the rest of the service is plain Python and tests stub the core
in one place. The core never imports anything from this package.
"""

from chat_orchestrator.application import ChatMessage, stream_chat
from chat_orchestrator.rate_limiter import RateLimitResult, get_rate_limiter

__all__ = ["ChatMessage", "RateLimitResult", "check_quota", "stream_chat"]


async def check_quota(user_id: str) -> RateLimitResult:
    """Count one message against this shell's per-user quota.

    The quota is per shell (its own SQLite file), matching the identity model
    OpenWebUI and LibreChat already have.
    """
    limiter = await get_rate_limiter()
    return await limiter.check_and_increment(user_id)
