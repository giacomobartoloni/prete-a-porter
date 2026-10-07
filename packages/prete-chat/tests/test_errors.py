"""Error and quota mapping: every row of the taxonomy (plan §20.1)."""

import asyncio

from chat_orchestrator.rate_limiter import RateLimitInfo, RateLimitResult

from prete_chat import errors


def _result(*, ok: bool) -> RateLimitResult:
    return RateLimitResult(
        ok=ok,
        limits={
            "hour": RateLimitInfo(limit=5, remaining=1 if ok else 0, reset_at="2026-09-18T18:00:00Z"),
            "day": RateLimitInfo(limit=20, remaining=3 if ok else 0, reset_at="2026-09-19T00:00:00Z"),
        },
    )


class TestRefusalFor:
    def test_under_the_limit_lets_the_turn_through(self):
        assert errors.refusal_for(_result(ok=True)) is None

    def test_over_the_limit_refuses_with_both_windows(self):
        message = errors.refusal_for(_result(ok=False))
        assert message is not None
        assert "5" in message and "20" in message
        assert errors.RATE_LIMIT_MESSAGE_IT in message


class TestOutcomeFor:
    def test_timeout(self):
        assert errors.outcome_for(TimeoutError()) == "timeout"

    def test_cancellation(self):
        assert errors.outcome_for(asyncio.CancelledError()) == "cancelled"

    def test_any_other_failure(self):
        assert errors.outcome_for(RuntimeError("boom")) == "error"


class TestUserMessageFor:
    def test_timeout_gets_its_own_message(self):
        assert errors.user_message_for(TimeoutError()) == errors.TIMEOUT_MESSAGE_IT

    def test_internal_errors_get_the_generic_message_without_details(self):
        message = errors.user_message_for(RuntimeError("/srv/secret/path is unreadable"))
        assert message == errors.INTERNAL_ERROR_MESSAGE_IT
        assert "secret" not in message
