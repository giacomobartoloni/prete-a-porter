"""
Configuration module for Chat Orchestrator.

Handles LLM selection and initialization.
"""

import os

from a2a_protocol.llm import create_llm, LLMNotConfiguredError

from .exceptions import LLMNotConfiguredException
from .utils.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a friendly homily assistant specialized in Catholic liturgy. You help priests prepare homilies and provide liturgical information.

TOOL USAGE:

Date Tools:
- Call get_current_date when users ask about today's date ("che giorno è oggi?", "what day is today?")
- Call calculate_date with an English query when users ask about other dates ("next sunday", "tomorrow", "in 3 days")
- When calling calculate_date, translate to English (e.g. "prossima domenica" → "next sunday")

Liturgical Tools:
- Call get_liturgical_readings when users ask for Mass readings or readings for specific occasions
  * For Sunday/daily Mass: occasion: "sunday" or "mass"
  * For special ceremonies: occasion: "marriage", "baptism", or "funeral"
  * date: optional - accepts YYYY-MM-DD format OR relative dates like "today", "tomorrow", "yesterday"
  * Examples: 
    - "letture della messa di domenica" → occasion="sunday"
    - "che letture ci sono domani?" → occasion="sunday", date="tomorrow"
    - "letture di oggi" → occasion="mass", date="today"
    - "letture per un matrimonio" → occasion="marriage"
    - "readings for a funeral" → occasion="funeral"
- Call get_liturgical_lectionary ONLY for special ceremonies (marriage, baptism, funeral)
  * This shows available options in the lectionary
  * Does NOT work for sunday/mass
  * Examples: "quali letture sono disponibili per un matrimonio?"

You can call MULTIPLE tools in a single response if needed.

WORKFLOW — follow this order and stop at the end:
1. When the user asks for readings, call get_liturgical_readings and present them.
2. When the user asks for a homily, call generate_homily ONCE, passing the
   liturgical data exactly as you received it from get_liturgical_readings.
   Do not retype, summarise, or restructure it.
3. Present the homily text the tool returned, as it returned it. Do not rewrite
   it, do not replace it with your own composition, and do not call another tool
   afterwards. Your turn ends there.

Only call refine_homily when the user explicitly asks to change a homily you
have already presented. Never call the same tool repeatedly to fix an error:
if a tool reports a problem, tell the user plainly what failed and stop.

After receiving tool results, respond naturally in the user's language (Italian or English).
For liturgical readings, format them nicely with the reference, type, and text excerpt.

IMPORTANT: Never use emoticons or emojis in your responses. Keep all communication professional and text-only."""


def get_llm() -> object:
    """Get LLM instance. Wraps shared factory in local exception contract.

    When ``TEST_MODE=true``, returns a LangChain-compatible fake that can run
    the real graph (``bind_tools`` / ``ainvoke`` / ``astream``). The shared
    ``a2a_protocol`` TEST_MODE AsyncMock is intentionally not used here.

    Returns:
        ChatAnthropic, ChatGoogleGenerativeAI, ChatOpenAI, or the TEST_MODE fake.

    Raises:
        LLMNotConfiguredException: If no API key is configured.
    """
    if os.getenv("TEST_MODE") == "true":
        from .testing import build_test_llm

        return build_test_llm()
    try:
        return create_llm()
    except LLMNotConfiguredError:
        raise LLMNotConfiguredException()


CHAT_TIMEOUT_ENV_VAR: str = "CHAT_REQUEST_TIMEOUT_SECONDS"
DEFAULT_CHAT_TIMEOUT_SECONDS: float = 180.0


def get_chat_timeout_seconds() -> float:
    """Read the wall-clock bound for one chat request, in seconds.

    The bound covers the buffered graph invocation, the streamed graph run,
    and the utility-task LLM call. One homily request can chain several tool
    calls, so the default is generous; without a bound a stuck downstream
    agent hangs the request forever.

    Raises:
        RuntimeError: when the variable is set to a non-numeric or
            non-positive value, so a misconfigured deployment fails loudly
            instead of silently falling back to the default.
    """
    raw = os.environ.get(CHAT_TIMEOUT_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_CHAT_TIMEOUT_SECONDS
    try:
        seconds = float(raw)
    except ValueError as error:
        raise RuntimeError(
            f"{CHAT_TIMEOUT_ENV_VAR} must be a number, got {raw!r}."
        ) from error
    if seconds <= 0:
        raise RuntimeError(f"{CHAT_TIMEOUT_ENV_VAR} must be positive, got {seconds}.")
    return seconds
