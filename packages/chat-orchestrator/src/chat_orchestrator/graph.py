"""
Graph construction and node logic for Chat Orchestrator.

Builds the LangGraph state graph that manages conversation flow
and coordinates tool execution.
"""

import json
import re
from typing import Literal

from langchain_core.messages import (
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph

from .config import SYSTEM_PROMPT, get_llm
from .exceptions import (
    AgentGraphException,
    LLMNotConfiguredException,
    ToolExecutionException,
    ToolNotFoundException,
)
from .state import ChatState
from .news import search_news
from .tools import (
    calculate_date,
    generate_homily,
    get_current_date,
    get_liturgical_lectionary,
    get_liturgical_readings,
    refine_homily,
)
from .utils.logging import get_logger

logger = get_logger(__name__)

TOOLS_REGISTRY = {
    "get_current_date": get_current_date,
    "calculate_date": calculate_date,
    "get_liturgical_readings": get_liturgical_readings,
    "get_liturgical_lectionary": get_liturgical_lectionary,
    "generate_homily": generate_homily,
    "refine_homily": refine_homily,
    "search_news": search_news,
}

_graph = None


async def agent_node(state: ChatState) -> dict:
    """
    Agent node: calls LLM with tools bound. LLM decides whether to use tools.
    """
    try:
        llm = get_llm()
    except LLMNotConfiguredException:
        raise
    except Exception as e:
        logger.error(
            "Failed to initialize LLM",
            session_id=state.get("session_id"),
            error=str(e),
            exc_info=True,
        )
        raise AgentGraphException(message=f"Failed to initialize LLM: {str(e)}", agent_name="chat_orchestrator") from e

    llm_with_tools = llm.bind_tools(list(TOOLS_REGISTRY.values()))
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    try:
        response = await llm_with_tools.ainvoke(messages)
        has_tool_calls = hasattr(response, "tool_calls") and response.tool_calls
        next_action = "continue" if has_tool_calls else "end"
        logger.debug(
            "Agent node completed",
            session_id=state.get("session_id"),
            has_tool_calls=has_tool_calls,
        )
        return {"messages": [response], "next_action": next_action}
    except Exception as e:
        logger.error(
            "Agent node failed",
            session_id=state.get("session_id"),
            error=str(e),
            exc_info=True,
        )
        raise AgentGraphException(message=f"Agent execution failed: {str(e)}", agent_name="chat_orchestrator") from e


def _news_search_confirmed(state: ChatState) -> bool:
    """Require approval of an actual search invitation in the last assistant question.

    Matching a substring anywhere in the turn can authorize unrelated or
    negated questions. This deterministic check runs at the execution boundary.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    messages = state.get("messages", [])
    last_user_index = next(
        (i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)),
        -1,
    )
    if last_user_index < 1:
        return False
    previous = messages[last_user_index - 1]
    current = messages[last_user_index]
    if not isinstance(previous, AIMessage):
        return False
    if not isinstance(previous.content, str) or not isinstance(current.content, str):
        return False

    # Short affirmations approve only the immediately preceding question.
    questions = re.findall(r"[^.!?]*\?", previous.content)
    if not questions:
        return False
    question = questions[-1].strip().casefold()
    if re.search(r"\b(?:non|senza|evita|evitare|no)\b", question):
        return False
    if not re.fullmatch(
        r"(?:vuoi che (?:io )?cerchi online|posso cercare online)(?:\s+[^?]*)?\?",
        question,
    ):
        return False

    reply = re.sub(r"\s+", " ", current.content.casefold()).strip().rstrip(".!?").strip()
    # Reject search cancellations without treating ordinary query constraints
    # (for example, "senza dettagli cruenti") as a refusal.
    explicitly_declines_search = re.search(
        r"\b(?:non cercare online|non fare la ricerca|procedi senza notizie)\b",
        reply,
    ) or reply.endswith("senza notizie")
    if explicitly_declines_search:
        return False
    if re.fullmatch(
        r"(?:sì|si|yes|ok|certo|va bene|confermo|procedi|autorizzo la ricerca)"
        r"(?:\s*,\s*(?:grazie(?: mille)?|per favore|pure))?",
        reply,
    ):
        return True
    # Permit an explicit search command with an affirmative or polite prefix.
    return re.fullmatch(
        r"(?:(?:sì|si|yes|ok|certo|va bene)\s*[,! ]+"
        r"(?:(?:grazie|per favore)\s*,?\s*)?)?"
        r"(?:cerca(?: pure)?|procedi(?: pure)?|puoi cercare|fai(?: pure)? la ricerca)"
        r"(?:\s+.+)?",
        reply,
    ) is not None

async def tools_node(state: ChatState) -> dict:
    """
    Execute tool calls from the last AI message and return ToolMessages.
    """
    last_message = state["messages"][-1]
    tool_messages = []

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    context = state.get("liturgical_context")
    overrides = dict(state.get("preference_overrides") or {})
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = dict(tool_call.get("args", {}))
        if tool_name == "refine_homily" and context:
            # Refinement edits the existing homily. A different date/occasion is
            # a new generation, never an implicit mutation of the old context.
            from .tools import _map_liturgical_data, _parse_llm_json

            try:
                raw_data = tool_args.get("liturgical_data", "{}")
                supplied = _parse_llm_json(raw_data) if isinstance(raw_data, str) else {}
                mapped = _map_liturgical_data(supplied) if isinstance(supplied, dict) else {}
            except (ValueError, TypeError, AttributeError):
                mapped = {}
            if mapped.get("date") != context["date"] or tool_args.get("occasion") != context["occasion"]:
                # Discard mismatched readings so the specialist fetches the
                # pinned date rather than relabelling another day's passages.
                tool_args["liturgical_data"] = json.dumps(context)
                tool_args["occasion"] = context["occasion"]

        if tool_name == "refine_homily":
            from .context import json_object, stable_preferences

            supplied_preferences = json_object(tool_args.get("preferences") or {}) or {}
            pinned = stable_preferences((context or {}).get("preferences"))
            # Always pin, including malformed/defaultable model snapshots.
            # Current textual changes are applied last by the tool wrapper.
            supplied_preferences = {**supplied_preferences, **pinned, **overrides}
            if supplied_preferences:
                tool_args["preferences"] = json.dumps(supplied_preferences)

        logger.debug("Executing tool", tool_name=tool_name, tool_args=tool_args)

        func = TOOLS_REGISTRY.get(tool_name)
        if tool_name == "search_news" and not _news_search_confirmed(state):
            tool_messages.append(ToolMessage(
                content="Ricerca non eseguita: chiedi prima conferma esplicita all'utente.",
                tool_call_id=tool_call["id"], name=tool_name,
            ))
            continue
        if func:
            try:
                result = await func.ainvoke(tool_args)
            except Exception as e:
                logger.error(
                    "Tool execution failed",
                    tool_name=tool_name,
                    error=str(e),
                    exc_info=True,
                )
                raise ToolExecutionException(
                    message=f"Failed to execute {tool_name}: {str(e)}",
                    tool_name=tool_name,
                ) from e
        else:
            logger.error("Unknown tool requested", tool_name=tool_name)
            raise ToolNotFoundException(tool_name=tool_name)

        if (
            tool_name in {"generate_homily", "refine_homily"}
            and isinstance(result, dict)
            and result.get("status") == "success"
            and not result.get("error")
        ):
            data = result.get("data")
            homily = data.get("homily") if isinstance(data, dict) else None
            if isinstance(homily, dict):
                from .context import effective_preferences, parse_liturgical_context

                updated = parse_liturgical_context(
                    {
                        "date": homily.get("liturgical_date"),
                        "occasion": homily.get("occasion"),
                        "preferences": effective_preferences(tool_args),
                    }
                )
                if updated:
                    context = updated
                    profile = context.get("preferences", {})
                    overrides = {
                        key: value for key, value in overrides.items() if key not in profile or profile[key] == value
                    }

        tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_name))

    return {"messages": tool_messages, "liturgical_context": context, "preference_overrides": overrides}


def should_continue(state: ChatState) -> Literal["tools", "end"]:
    """Check next_action to decide whether to continue to tools or end."""
    return "tools" if state["next_action"] == "continue" else "end"


async def create_graph() -> object:
    """Build and compile the chat orchestrator graph without a checkpointer.

    The graph carries no server-side conversation state: every invocation
    receives its full message history from the caller.
    """
    workflow = StateGraph(ChatState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")

    return workflow.compile()


async def get_graph() -> object:
    """Get or create the compiled graph instance."""
    global _graph
    if _graph is None:
        _graph = await create_graph()
    return _graph


def reset_graph() -> None:
    """Reset the graph instance (useful for testing)."""
    global _graph
    _graph = None
    logger.debug("Graph instance reset")
