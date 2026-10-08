"""Required vs optional availability and capability-error semantics."""

from __future__ import annotations

import pytest

import conftest as contracts_conftest
from test_homily_contract import require_homily_agent
from test_liturgy_contract import require_agent_available


def test_require_optional_live_skips_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRETE_RUN_OPTIONAL_LIVE", raising=False)
    with pytest.raises(pytest.skip.Exception, match="optional live"):
        contracts_conftest.require_optional_live()


def test_require_optional_live_allows_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRETE_RUN_OPTIONAL_LIVE", "1")
    contracts_conftest.require_optional_live()  # must not raise/skip


def test_require_liturgy_agent_fails_when_unavailable() -> None:
    with pytest.raises(pytest.fail.Exception, match="Liturgy agent not running"):
        require_agent_available(False)


def test_require_liturgy_agent_message_includes_url() -> None:
    with pytest.raises(pytest.fail.Exception, match="http"):
        require_agent_available(False)


def test_require_homily_agent_fails_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import test_homily_contract as homily_mod

    monkeypatch.setattr(homily_mod, "is_agent_available", lambda: False)
    with pytest.raises(pytest.fail.Exception, match="Homily agent not running"):
        require_homily_agent()
