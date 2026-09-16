"""Measure whether a utility request triggers liturgical tool calls.

Runs the SAME OpenWebUI default title prompt against the configured LLM twice:

  A. with the homily system prompt and the six liturgical tools bound
     (what happens without the bypass)
  B. with no system prompt and no tools
     (what the bypass does)

and reports the tool calls the model makes in each case.

Requires a configured provider API key. Run from packages/chat-orchestrator:

    uv run python scripts/measure_utility_cost.py

The prompt is OpenWebUI's documented default title template, verbatim.
"""

import asyncio
import os
import sys

from langchain_core.messages import HumanMessage, SystemMessage

from chat_orchestrator.config import SYSTEM_PROMPT, get_llm
from chat_orchestrator.graph import TOOLS_REGISTRY

# OpenWebUI's default TITLE_GENERATION_PROMPT_TEMPLATE, with the chat history
# placeholder filled with a realistic first user message from this app.
TITLE_PROMPT = """### Task:
Generate a concise title summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Keep it short: 2-4 words is best.
### Output:
JSON format: { "title": "your concise title here" }
### Chat History:
<chat_history>
user: letture di domenica prossima
</chat_history>"""

# A second sample, to distinguish "the model always calls tools" from
# "the model reacts to liturgical vocabulary".
NON_LITURGICAL_PROMPT = TITLE_PROMPT.replace(
    "user: letture di domenica prossima",
    "user: come si prepara una carbonara",
)


async def run_case(label: str, prompt: str, *, with_tools: bool) -> int:
    """Invoke the LLM once and report how many tools it called."""
    llm = get_llm()
    if with_tools:
        llm = llm.bind_tools(list(TOOLS_REGISTRY.values()))
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    else:
        messages = [HumanMessage(content=prompt)]

    response = await llm.ainvoke(messages)
    calls = getattr(response, "tool_calls", None) or []

    print(f"  {label}")
    print(f"    tool calls: {len(calls)}")
    for call in calls:
        print(f"      - {call.get('name')}({call.get('args')})")
    print(f"    content: {str(response.content)[:70]!r}")
    print()
    return len(calls)


async def main() -> None:
    print("=" * 70)
    print("Utility-request cost measurement")
    print("=" * 70)
    print()

    print("A. WITHOUT the bypass (homily prompt + 6 tools bound)")
    liturgical = await run_case("title prompt, liturgical vocabulary", TITLE_PROMPT, with_tools=True)
    neutral = await run_case("title prompt, neutral vocabulary", NON_LITURGICAL_PROMPT, with_tools=True)

    print("B. WITH the bypass (no system prompt, no tools)")
    bypassed = await run_case("title prompt, liturgical vocabulary", TITLE_PROMPT, with_tools=False)

    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"  Liturgical prompt, tools bound:  {liturgical} tool call(s)")
    print(f"  Neutral prompt, tools bound:     {neutral} tool call(s)")
    print(f"  Liturgical prompt, bypassed:     {bypassed} tool call(s)")
    print()
    if liturgical > 0:
        print("  The collision is REAL on this model: the homily system prompt")
        print("  overrides the title instruction and triggers liturgical tools.")
    elif neutral == 0:
        print("  No collision on this model: the title instruction dominates.")
        print("  The bypass still isolates the prompt, but the cost argument is")
        print("  weaker than assumed. Re-run on the smallest model you plan to")
        print("  support before deciding how much to invest here.")
    print()
    print("  Note: 1 tool call costs 2 LLM invocations + 1 A2A round trip.")


if __name__ == "__main__":
    if not any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")):
        print("No provider API key configured. Set one in .env and retry.", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(main())
