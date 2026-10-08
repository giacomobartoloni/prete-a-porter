"""
Shared fixtures for end-to-end tests.

Provides URL fixtures for agent services. Contract tests never start, stop,
or delete the shared Docker Compose stack; start the test services explicitly
before running live/E2E layers.
"""

import base64
import os

import pytest

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))

# Disposable credentials for required A2A HTTP auth in tests/CI.
# Never overwrite operator-provided values from the environment or .env.
DISPOSABLE_A2A_USERNAME = "a2a-test"
DISPOSABLE_A2A_PASSWORD = "a2a-test-secret"


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


def _nonblank_credential(value: str | None) -> str | None:
    """Return exact credential bytes, or None when absent/whitespace-only."""
    if value is None or not value.strip():
        return None
    return value


def _ensure_complete_a2a_test_credentials() -> None:
    user = _nonblank_credential(os.environ.get("A2A_BASIC_AUTH_USERNAME"))
    password = _nonblank_credential(os.environ.get("A2A_BASIC_AUTH_PASSWORD"))
    if user and password:
        return
    if user or password:
        # Leave partial pairs alone so fail-closed server/client behaviour surfaces.
        return
    os.environ["A2A_BASIC_AUTH_USERNAME"] = DISPOSABLE_A2A_USERNAME
    os.environ["A2A_BASIC_AUTH_PASSWORD"] = DISPOSABLE_A2A_PASSWORD


_load_env()
_ensure_complete_a2a_test_credentials()


def a2a_auth_headers() -> dict[str, str]:
    """HTTP Basic Auth headers matching the required A2A credential pair."""
    user = _nonblank_credential(os.environ.get("A2A_BASIC_AUTH_USERNAME"))
    password = _nonblank_credential(os.environ.get("A2A_BASIC_AUTH_PASSWORD"))
    if not user or not password:
        return {}
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def a2a_post(url: str, **kwargs):
    """POST with required A2A Basic Auth headers."""
    import httpx

    headers = {**a2a_auth_headers(), **kwargs.pop("headers", {})}
    return httpx.post(url, headers=headers, **kwargs)


async def a2a_apost(url: str, **kwargs):
    """Async POST with required A2A Basic Auth headers."""
    import httpx

    headers = {**a2a_auth_headers(), **kwargs.pop("headers", {})}
    async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 15.0)) as client:
        return await client.post(url, headers=headers, **kwargs)


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
    config.addinivalue_line(
        "markers",
        "optional_live: live upstream/LLM checks; require PRETE_RUN_OPTIONAL_LIVE=1",
    )


def require_optional_live() -> None:
    """Skip unless the operator explicitly opted into live upstream/LLM checks."""
    if os.environ.get("PRETE_RUN_OPTIONAL_LIVE", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("optional live check; set PRETE_RUN_OPTIONAL_LIVE=1 to run")


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
