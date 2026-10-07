"""Bearer API-key validation for the OpenAI-compatible surface.

The key authenticates the *caller* (OpenWebUI), not the end user. Per-user
identity comes from the forwarded headers handled in ``identity.py``.

``ORCHESTRATOR_API_KEY`` must not be named ``OPENAI_API_KEY``: that name is
already the upstream LLM provider key and reusing it would silently break
provider selection in ``a2a_protocol.llm``.
"""

import logging
import os
import secrets

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

ENV_VAR: str = "ORCHESTRATOR_API_KEY"
BEARER_PREFIX: str = "Bearer "
UNAUTHORIZED_DETAIL_IT: str = "Credenziali non valide o mancanti."


def get_api_key() -> str:
    """Read the configured API key.

    Raises:
        RuntimeError: when the variable is unset, so a misconfigured
            deployment fails loudly instead of serving requests openly.
    """
    key = os.environ.get(ENV_VAR)
    if not key:
        raise RuntimeError(
            f"{ENV_VAR} environment variable is required. "
            "Set it in .env or docker-compose environment."
        )
    return key


async def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency validating the ``Authorization: Bearer`` header.

    Raises:
        HTTPException: 401 when the header is missing, malformed, or wrong.
    """
    if not authorization or not authorization.startswith(BEARER_PREFIX):
        raise HTTPException(status_code=401, detail=UNAUTHORIZED_DETAIL_IT)

    presented = authorization[len(BEARER_PREFIX):]
    if not presented or not secrets.compare_digest(presented, get_api_key()):
        logger.warning("Rejected request with invalid API key")
        raise HTTPException(status_code=401, detail=UNAUTHORIZED_DETAIL_IT)
