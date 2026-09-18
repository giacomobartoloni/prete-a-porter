"""User-facing Italian text and the exception -> outcome mapping.

The wording mirrors ``chat_orchestrator.api.v1``; that module is HTTP-specific
and importing it would pull FastAPI into this service, so the strings live here
too. Never render internal details: no stack traces, URLs, credentials or raw
tool JSON reaches the user.
"""

import asyncio

from chat_orchestrator.rate_limiter import RateLimitResult

RATE_LIMIT_MESSAGE_IT = "Hai raggiunto il limite di messaggi. Riprova più tardi."
TIMEOUT_MESSAGE_IT = "La richiesta ha superato il tempo massimo di elaborazione. Riprova tra qualche istante."
INTERNAL_ERROR_MESSAGE_IT = "Si è verificato un errore nel generare la risposta. Riprova tra qualche istante."
CANCELLED_MESSAGE_IT = "Generazione interrotta."


def _message_count(limit: int) -> str:
    """Italian agreement for the quota windows."""
    return f"{limit} messaggio" if limit == 1 else f"{limit} messaggi"


def refusal_for(result: RateLimitResult) -> str | None:
    """Refusal text when the per-user quota is exhausted, else ``None``."""
    if result.ok:
        return None
    hour = result.limits["hour"]
    day = result.limits["day"]
    return f"{RATE_LIMIT_MESSAGE_IT} Limite: {_message_count(hour.limit)}/ora, {_message_count(day.limit)} al giorno."


def user_message_for(error: BaseException) -> str:
    """Map a failed turn to the text the user sees."""
    if isinstance(error, TimeoutError):
        return TIMEOUT_MESSAGE_IT
    return INTERNAL_ERROR_MESSAGE_IT


def outcome_for(error: BaseException) -> str:
    """Boundary-log outcome for a failed turn."""
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, asyncio.CancelledError):
        return "cancelled"
    return "error"
