"""Per-user identity and thread correlation from client headers.

Both supported clients authenticate as a service (``ORCHESTRATOR_API_KEY``) and
forward the end-user identity in headers:

- LibreChat sends ``X-User-ID``, ``X-Conversation-ID``, ``X-Message-ID`` and
  ``X-User-Email``, as configured in ``deploy/librechat/librechat.yaml``.
- OpenWebUI sends ``X-OpenWebUI-User-Id``, ``X-OpenWebUI-Chat-Id`` and
  ``X-OpenWebUI-User-Email``, but only when ``ENABLE_FORWARD_USER_INFO_HEADERS=True``
  is set on its container.

None of the headers are signed, so this module trusts them because the
orchestrator is reachable only on the internal Docker network behind the API
key (see ``auth.py``). The OpenWebUI-prefixed names win when both families are
present: they are namespaced, while ``X-User-ID`` is a generic name any client
could send.

Both fallbacks are deliberate and logged once per process, so a misconfigured
deployment degrades visibly rather than silently collapsing every user into one
rate-limit bucket.
"""

import uuid
from dataclasses import dataclass

from fastapi import Header

from ..utils.logging import get_logger

logger = get_logger(__name__)

ANONYMOUS_USER_ID: str = "anonymous"

_warned_missing_user_id: bool = False
_warned_missing_chat_id: bool = False


@dataclass(frozen=True)
class CallerIdentity:
    """Who is calling, and which conversation the call belongs to."""

    user_id: str
    thread_id: str
    user_email: str | None
    message_id: str | None = None


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


def _first_non_blank(*values: str | None) -> str:
    """Return the first value that survives stripping, or an empty string."""
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


async def get_caller_identity(
    x_openwebui_user_id: str | None = Header(default=None),
    x_openwebui_chat_id: str | None = Header(default=None),
    x_openwebui_user_email: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_conversation_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_message_id: str | None = Header(default=None),
) -> CallerIdentity:
    """Build the caller identity from the forwarded client headers.

    Missing or blank user id degrades to ``"anonymous"``, which means every
    such caller shares one rate-limit bucket. Missing or blank conversation id
    degrades to a fresh UUID per request, which means no cross-turn context.
    """
    user_id = _first_non_blank(x_openwebui_user_id, x_user_id)
    if not user_id:
        _warn_once(
            "user_id",
            f"No user id header (X-OpenWebUI-User-Id or X-User-ID); falling back to "
            f"'{ANONYMOUS_USER_ID}'. Every such caller shares one rate-limit bucket. Set "
            "ENABLE_FORWARD_USER_INFO_HEADERS=True on OpenWebUI, or the X-User-ID "
            "header in the LibreChat endpoint config.",
        )
        user_id = ANONYMOUS_USER_ID

    thread_id = _first_non_blank(x_openwebui_chat_id, x_conversation_id)
    if not thread_id:
        _warn_once(
            "chat_id",
            "No conversation id header (X-OpenWebUI-Chat-Id or X-Conversation-ID); "
            "generating a per-request thread id. Cross-turn context will be lost.",
        )
        thread_id = str(uuid.uuid4())

    email = _first_non_blank(x_openwebui_user_email, x_user_email) or None
    message_id = _first_non_blank(x_message_id) or None
    return CallerIdentity(
        user_id=user_id,
        thread_id=thread_id,
        user_email=email,
        message_id=message_id,
    )
