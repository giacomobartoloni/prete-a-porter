"""
Shared LLM factory for all agents.

Provides a unified way to create LLM instances based on environment
configuration. Each agent can specialize the factory for its needs.
"""

import os
import logging

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(Exception):
    """Raised when no LLM API key is configured."""
    pass


def create_llm(strict: bool = True) -> object:
    """Create an LLM instance based on available API keys.

    Checks ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY
    in priority order. Each provider reads its model name from a
    provider-specific env var (ANTHROPIC_MODEL_NAME, GOOGLE_MODEL_NAME,
    OPENAI_MODEL_NAME) or falls back to its default.

    Args:
        strict: If True, raise LLMNotConfiguredError when no key is found.

    Returns:
        Configured LLM instance (ChatAnthropic, ChatGoogleGenerativeAI,
        or ChatOpenAI).

    Raises:
        LLMNotConfiguredError: If no API key is available and strict=True.
    """
    if os.getenv("TEST_MODE") == "true":
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = AsyncMock()
        mock_response.content = "Test response from mock LLM"
        mock_response.tool_calls = []
        mock_llm.invoke.return_value = mock_response
        mock_llm.ainvoke.return_value = mock_response
        logger.debug("Using mock LLM for testing")
        return mock_llm

    providers = [
        ("ANTHROPIC_API_KEY", _create_anthropic, "langchain_anthropic"),
        ("GOOGLE_API_KEY", _create_google, "langchain_google_genai"),
        ("OPENAI_API_KEY", _create_openai, "langchain_openai"),
    ]

    provider_errors = []

    for env_var, factory, package_name in providers:
        api_key = os.getenv(env_var)
        if api_key:
            llm = factory(api_key)
            if llm:
                return llm
            provider_errors.append(f"{env_var} is set but {package_name} is not installed")

    if strict:
        if provider_errors:
            raise LLMNotConfiguredError("; ".join(provider_errors))
        raise LLMNotConfiguredError("No LLM API key configured")

    from unittest.mock import MagicMock
    logger.warning("No LLM API key configured, using mock LLM")
    return MagicMock()


def _create_anthropic(api_key: str) -> object | None:
    model = os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-5-sonnet-20241022")
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model_name=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_anthropic not available")
        return None


def _create_google(api_key: str) -> object | None:
    model = os.getenv("GOOGLE_MODEL_NAME", "gemini-flash-lite-latest")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, api_key=api_key)
    except ImportError:
        logger.warning("langchain_google_genai not available")
        return None


def _create_openai(api_key: str) -> object | None:
    model = os.getenv("OPENAI_MODEL_NAME", "gpt-4-turbo-preview")
    base_url = os.getenv("OPENAI_BASE_URL")
    try:
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    except ImportError:
        logger.warning("langchain_openai not available")
        return None
