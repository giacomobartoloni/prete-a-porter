"""Regression: contract fixtures must not manage the shared Docker stack."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Any

import pytest

_CONFTEST_PATH = Path(__file__).resolve().parent / "conftest.py"
_SPEC = importlib.util.spec_from_file_location(
    "_contracts_lifecycle_conftest", _CONFTEST_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
contracts_conftest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(contracts_conftest)


class _Config:
    def __init__(self, no_docker: bool) -> None:
        self._no_docker = no_docker

    def getoption(self, name: str) -> bool:
        if name == "--no-docker":
            return self._no_docker
        raise AssertionError(f"unexpected option: {name}")


class _Request:
    def __init__(self, no_docker: bool = False) -> None:
        self.config = _Config(no_docker)


def _collect_lifecycle_calls(calls: list[list[str]]) -> list[list[str]]:
    lifecycle: list[list[str]] = []
    for cmd in calls:
        if "compose" not in cmd:
            continue
        if "up" in cmd or "down" in cmd:
            lifecycle.append(cmd)
    return lifecycle


def _run_fixture(request: _Request, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd_list = [str(part) for part in cmd]
        calls.append(cmd_list)
        stdout = ""
        if "ps" in cmd_list:
            # Satisfy any health poll without waiting on real Docker.
            stdout = (
                '{"Service":"liturgy-agent","Health":"healthy"}\n'
                '{"Service":"homily-agent","Health":"healthy"}\n'
                '{"Service":"chat-orchestrator","Health":"healthy"}\n'
            )
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    fixture_fn = contracts_conftest.docker_compose._get_wrapped_function()
    gen = fixture_fn(request)
    next(gen)
    with pytest.raises(StopIteration):
        next(gen)
    return calls


def test_docker_compose_fixture_does_not_start_or_stop_shared_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _run_fixture(_Request(no_docker=False), monkeypatch)
    assert _collect_lifecycle_calls(calls) == []


def test_docker_compose_fixture_no_docker_flag_also_skips_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _run_fixture(_Request(no_docker=True), monkeypatch)
    assert _collect_lifecycle_calls(calls) == []


def test_docker_compose_fixture_never_deletes_volumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _run_fixture(_Request(no_docker=False), monkeypatch)
    volume_deletes = [cmd for cmd in calls if "down" in cmd and "-v" in cmd]
    assert volume_deletes == []
