"""Black-box user journeys through the real /v1 OpenAI-compatible chat API.

Testcontainers starts the production Dockerfile and a separate scripted HTTP
provider. The real FastAPI + LangGraph + search_news tool run in the app container.
No live LLM, Tavily API calls, Chainlit browser, or database are involved.
"""
import time
from pathlib import Path

import httpx
import pytest
from testcontainers.compose import DockerCompose

E2E_DIR = Path(__file__).resolve().parent
TOKEN = "e2e-shell-token"
MODEL = "prete-a-porter"


@pytest.fixture(scope="session")
def running_stack():
    with DockerCompose(context=str(E2E_DIR), compose_file_name="compose.yml", build=True) as compose:
        def url(service, port):
            host = compose.get_service_host(service, port)
            if host in ("0.0.0.0", "::", None):
                host = "127.0.0.1"
            return f"http://{host}:{compose.get_service_port(service, port)}"

        app = url("orchestrator", 8000)
        provider = url("fake-provider", 8080)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if (
                    httpx.get(app + "/health", timeout=2).status_code == 200
                    and httpx.get(provider + "/health", timeout=2).status_code == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            logs = compose.get_logs()
            pytest.fail(f"E2E services did not become healthy: {str(logs)[-4000:]}")

        yield {"app": app, "provider": provider}


@pytest.fixture
def journey(running_stack):
    reset = httpx.post(running_stack["provider"] + "/reset", timeout=10)
    reset.raise_for_status()
    return running_stack


def audit(journey):
    response = httpx.get(journey["provider"] + "/audit", timeout=10)
    response.raise_for_status()
    return response.json()


def send(journey, messages, *, headers=None):
    response = httpx.post(
        journey["app"] + "/v1/chat/completions",
        json={"model": MODEL, "messages": messages, "stream": False},
        headers=headers or {
            "Authorization": f"Bearer {TOKEN}",
            "X-OpenWebUI-User-Id": "e2e-user",
            "X-OpenWebUI-Chat-Id": "e2e-conversation",
        },
        timeout=65,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["object"] == "chat.completion"
    assert result["model"] == MODEL
    return result["choices"][0]["message"]["content"]


def test_user_is_asked_before_searching_and_natural_yes_fetches_recent_news(journey):
    history = [{"role": "user", "content": "Vorrei preparare un'omelia sulla pace."}]
    proposed = send(journey, history)
    assert "Vuoi che cerchi online?" in proposed
    assert audit(journey)["tavily_calls"] == [], "The proposal alone cannot search"

    history.extend([
        {"role": "assistant", "content": proposed},
        {"role": "user", "content": "Sì, grazie"},
    ])
    response = send(journey, history)
    assert "https://example.org/news/pace" in response
    assert "https://example.org/news/broken" not in response
    assert "https://example.org/news/old" not in response

    evidence = audit(journey)
    assert len(evidence["tavily_calls"]) == 1
    assert evidence["tavily_calls"][0]["topic"] == "news"
    assert evidence["tavily_calls"][0]["query"].startswith("pace")


def test_user_can_approve_with_a_natural_search_request(journey):
    history = [
        {"role": "user", "content": "Vorrei preparare un'omelia sulla pace."},
        {"role": "assistant", "content": "Posso cercare online notizie recenti sulla pace. Vuoi che cerchi online?"},
        {"role": "user", "content": "Sì, cerca notizie sulla pace"},
    ]
    response = send(journey, history)
    assert "https://example.org/news/pace" in response
    assert len(audit(journey)["tavily_calls"]) == 1


@pytest.mark.parametrize("history", [
    [{"role": "user", "content": "Cerca subito notizie recenti sulla pace"}],
    [
        {"role": "assistant", "content": "Non posso cercare online. Vuoi procedere senza notizie?"},
        {"role": "user", "content": "Sì"},
    ],
    [
        {"role": "assistant", "content": "Vuoi che cerchi online? Vuoi procedere senza notizie?"},
        {"role": "user", "content": "Sì"},
    ],
    [
        {"role": "assistant", "content": "Posso cercare online. Vuoi che cerchi online?"},
        {"role": "user", "content": "No, grazie"},
    ],
    [
        {"role": "assistant", "content": "Vuoi preparare un'omelia?"},
        {"role": "user", "content": "Sì"},
    ],
])
def test_adversarial_model_cannot_search_without_consent(journey, history):
    # The scripted LLM intentionally requests a search even for "No" or when
    # no real search proposal occurred. The production tool gate must stop it.
    answer = send(journey, history)
    assert "Non ho cercato online" in answer
    assert audit(journey)["tavily_calls"] == []
    assert len(audit(journey)["llm_calls"]) >= 2, "Exercise the real tool execution path"


def test_chat_endpoint_requires_client_authentication(journey):
    response = httpx.post(
        journey["app"] + "/v1/chat/completions",
        json={"model": MODEL, "messages": [{"role": "user", "content": "Ciao"}]},
        timeout=10,
    )
    assert response.status_code == 401
    assert audit(journey)["tavily_calls"] == []
    assert audit(journey)["llm_calls"] == []
