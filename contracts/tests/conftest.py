"""
Shared fixtures for end-to-end tests.

Provides URL fixtures for agent services. Contract tests never start, stop,
or delete the shared Docker Compose stack; start the test services explicitly
before running live/E2E layers.
"""

import os

import pytest

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))


def _load_env():
    """Load .env file so test helpers use the same secrets as Docker containers."""
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env()


def pytest_addoption(parser):
    parser.addoption(
        "--no-docker",
        action="store_true",
        default=False,
        help=(
            "Compatibility flag: contract fixtures never manage Docker Compose. "
            "Start the test stack explicitly before live/E2E runs."
        ),
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")


@pytest.fixture(scope="session")
def docker_compose(request):
    """Require an explicitly started test stack; never manage Compose lifecycle.

    `--no-docker` remains accepted for compatibility and has the same behaviour.
    """
    _ = request.config.getoption("--no-docker")
    yield


@pytest.fixture(scope="module")
def _ensure_docker(docker_compose):
    """Mark live/E2E modules as depending on an explicitly started stack."""
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
