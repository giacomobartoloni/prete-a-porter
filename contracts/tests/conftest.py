"""
Shared fixtures for end-to-end tests.

Handles Docker Compose lifecycle and provides URL fixtures
for all agent services.
"""

import json
import os
import subprocess
import time

import pytest

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))


def pytest_addoption(parser):
    parser.addoption(
        "--no-docker",
        action="store_true",
        default=False,
        help="Skip Docker Compose lifecycle (assume services are already running)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")


def _wait_for_healthy(timeout: int = 120):
    """Poll docker compose ps until all agent services are healthy."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        lines = [l for l in result.stdout.strip().split("\n") if l]
        if not lines:
            time.sleep(3)
            continue
        try:
            services = [json.loads(line) for line in lines]
        except json.JSONDecodeError:
            time.sleep(3)
            continue

        agent_services = [s for s in services if s.get("Service") not in ("a2a-inspector",)]
        all_healthy = all(s.get("Health") == "healthy" for s in agent_services if "Health" in s)
        if all_healthy:
            return
        time.sleep(3)

    pytest.fail("Services did not become healthy within {timeout}s")


@pytest.fixture(scope="session")
def docker_compose(request):
    """Start all services before test session, stop after."""
    if request.config.getoption("--no-docker"):
        yield
        return

    subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        check=True, cwd=PROJECT_ROOT,
    )
    _wait_for_healthy()
    yield
    subprocess.run(
        ["docker", "compose", "down", "-v"],
        check=True, cwd=PROJECT_ROOT,
    )


@pytest.fixture(scope="module")
def _ensure_docker(docker_compose):
    """Ensure Docker services are running (depends on session-scoped docker_compose)."""
    pass


@pytest.fixture
def liturgy_url(_ensure_docker):
    return "http://localhost:8001"


@pytest.fixture
def homily_url(_ensure_docker):
    return "http://localhost:8002"


@pytest.fixture
def chat_url(_ensure_docker):
    return "http://localhost:8000"


MOCK_LITURGICAL_DATA = {
    "date": "2026-05-15",
    "occasion": "mass",
    "metadata": {
        "date": "2026-05-15",
        "occasion": "mass",
        "season": "Easter",
        "color": "White",
        "year_cycle": "A",
        "sunday_or_weekday": "Weekday",
    },
    "first_reading": {"reference": "Acts 18:9-18", "text": "Paul remained in Corinth...", "type": "First"},
    "psalm": {"reference": "Ps 47:2-7", "text": "God mounts his throne...", "type": "Psalm"},
    "gospel": {"reference": "Jn 16:20-23a", "text": "Jesus said to his disciples...", "type": "Gospel"},
    "cached_at": "2026-05-15T10:00:00",
    "source": "web",
}
