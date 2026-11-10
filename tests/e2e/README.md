# E2E journeys with Testcontainers

These tests run the **real, production Dockerfile** of the chat-orchestrator
(FastAPI + LangGraph + tool execution) and simulate a user through the
OpenAI-compatible HTTP endpoint used by the replaceable chat shells.

Testcontainers for Python controls a short-lived Docker Compose stack:

- `orchestrator`: actual application process, `/v1/chat/completions`.
- `fake-provider`: deterministic OpenAI Chat Completions and Tavily HTTP double.
  It deliberately attempts `search_news` even for refusals, so a passing test
  proves the application's consent gate blocks actual network calls.

The test makes **no real LLM or Tavily requests** and requires no credentials.
The orchestrator is stateless on this path: PostgreSQL belongs to the Chainlit
native UI, so spinning it up here would not improve coverage. This is an
**HTTP user journey E2E**, not a browser/Chainlit UI automation test.

## Run locally

Prerequisites: Docker Engine/Desktop running, `docker compose` v2, Python 3.12+.

From the repository root:

```bash
python -m pip install -r tests/e2e/requirements.txt
python -m pytest tests/e2e/test_chat_user_journeys.py -v
```

The first run builds the application image and can take longer than unit tests.
Testcontainers destroys the stack after the session. The separate GitHub
Actions workflow `.github/workflows/e2e-tests.yml` runs these tests
on pull requests to `main`. Normal package unit tests do not require Docker.

## Covered journeys

1. First request for a peace homily -> search proposal -> **zero** Tavily calls.
2. Explicit replies such as "Sì, grazie" or "Sì, cerca notizie sulla pace"
   -> one Tavily search -> only the valid, recent, RFC-2822-dated article survives.
3. Adversarial LLM asks to search on the first turn, for "No, grazie",
   after a "without news" question, or after an unrelated question -> zero calls.
4. API authentication rejects an unauthenticated user before model invocation.

The stub exposes `GET /audit` and `POST /reset` only inside
the ephemeral test stack. Its malformed record and old dated record protect the
provider-normalization boundary as well as the conversation.

## Limits / future coverage

This suite does not certify real-provider output quality, streamed browser
rendering, the Chainlit session and PostgreSQL persistence, or live A2A agent
coordination. Those should be additional, explicitly scoped E2E suites.

`TAVILY_API_URL` is set to the mock provider inside Compose; absent
that override, the production default stays `https://api.tavily.com/search`.
