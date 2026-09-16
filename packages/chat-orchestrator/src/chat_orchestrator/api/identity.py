"""Per-user identity and thread correlation from OpenWebUI headers.

OpenWebUI forwards ``X-OpenWebUI-User-Id`` and ``X-OpenWebUI-Chat-Id`` only
when ``ENABLE_FORWARD_USER_INFO_HEADERS=True`` is set on its container. The
headers are not signed, so this module trusts them because the orchestrator is
reachable only on the internal Docker network behind the API key.

Both fallbacks are deliberate and logged once per process, so a misconfigured
deployment degrades visibly rather than silently collapsing every user into one
rate-limit bucket.
"""

import logging
import uuid
from dataclasses import dataclass

from fastapi import Header

logger = logging.getLogger(__name__)

ANONYMOUS_USER_ID: str = "anonymous"

_warned_missing_user_id: bool = False
_warned_missing_chat_id: bool = False


@dataclass(frozen=True)
class CallerIdentity:
    """Who is calling, and which conversation the call belongs to."""

    user_id: str
    thread_id: str
    user_email: str | None


def _warn_once(flag_name: str, message: str) -> None:
    """Emit a warning the first time only, to avoid per-request log flooding."""
    global _warned_missing_user_id, _warned_missing_chat_id
    if flag_name == "user_id":
        if _warned_missing_user_id:
            return
        _warned_missing_user_id = True
    else:
        if _warned_missing_chat_id:
            return
        _warned_missing_chat_id = True
    logger.warning(message)


async def get_caller_identity(
    x_openwebui_user_id: str | None = Header(default=None),
    x_openwebui_chat_id: str | None = Header(default=None),
    x_openwebui_user_email: str | None = Header(default=None),
) -> CallerIdentity:
    """Build the caller identity from OpenWebUI's forwarded headers.

    Missing or blank ``X-OpenWebUI-User-Id`` degrades to ``"anonymous"``,
    which means every such caller shares one rate-limit bucket. Missing or
    blank ``X-OpenWebUI-Chat-Id`` degrades to a fresh UUID per request, which
    means no cross-turn context.
    """
    user_id = (x_openwebui_user_id or "").strip()
    if not user_id:
        _warn_once(
            "user_id",
            "X-OpenWebUI-User-Id missing or blank; falling back to '{anon}'. Every such "
            "caller shares one rate-limit bucket. Set ENABLE_FORWARD_USER_INFO_HEADERS=True "
            "on the OpenWebUI container.".format(anon=ANONYMOUS_USER_ID),
        )
        user_id = ANONYMOUS_USER_ID

    thread_id = (x_openwebui_chat_id or "").strip()
    if not thread_id:
        _warn_once(
            "chat_id",
            "X-OpenWebUI-Chat-Id missing or blank; generating a per-request thread id. "
            "Cross-turn context will be lost.",
        )
        thread_id = str(uuid.uuid4())

    email = (x_openwebui_user_email or "").strip() or None
    return CallerIdentity(user_id=user_id, thread_id=thread_id, user_email=email)
