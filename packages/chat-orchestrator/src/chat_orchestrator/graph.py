"""
Graph construction and node logic for Chat Orchestrator.

Builds the LangGraph state graph that manages conversation flow
and coordinates tool execution.
"""

import os
from pathlib import Path
from typing import Literal

from langchain_core.messages import (
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .config import SYSTEM_PROMPT, get_llm
from .exceptions import (
    AgentGraphException,
    LLMNotConfiguredException,
    ToolExecutionException,
    ToolNotFoundException,
)
from .state import ChatState
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
}

_graph = None
_checkpointer_context = None


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
        raise AgentGraphException(
            message=f"Failed to initialize LLM: {str(e)}",
            agent_name="chat_orchestrator"
        ) from e

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
        raise AgentGraphException(
            message=f"Agent execution failed: {str(e)}",
            agent_name="chat_orchestrator"
        ) from e


async def tools_node(state: ChatState) -> dict:
    """
    Execute tool calls from the last AI message and return ToolMessages.
    """
    last_message = state["messages"][-1]
    tool_messages = []

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})

        logger.debug("Executing tool", tool_name=tool_name, tool_args=tool_args)

        func = TOOLS_REGISTRY.get(tool_name)
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

        tool_messages.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_name)
        )

    return {"messages": tool_messages}


def should_continue(state: ChatState) -> Literal["tools", "end"]:
    """Check next_action to decide whether to continue to tools or end."""
    return "tools" if state["next_action"] == "continue" else "end"


async def create_graph() -> tuple:
    """Build and compile the chat orchestrator graph with SQLite checkpointer."""
    workflow = StateGraph(ChatState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")

    db_path = os.getenv("DATABASE_PATH", "/app/data/chat_orchestrator.db")

    if not Path(db_path).is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        full_db_path = str(project_root / db_path)
    else:
        full_db_path = db_path

    Path(full_db_path).parent.mkdir(parents=True, exist_ok=True)

    checkpointer_context = AsyncSqliteSaver.from_conn_string(full_db_path)
    checkpointer = await checkpointer_context.__aenter__()

    return workflow.compile(checkpointer=checkpointer), checkpointer_context


async def get_graph() -> object:
    """Get or create the compiled graph instance."""
    global _graph, _checkpointer_context
    if _graph is None:
        _graph, _checkpointer_context = await create_graph()
    return _graph


def reset_graph() -> None:
    """Reset the graph instance (useful for testing)."""
    global _graph, _checkpointer_context
    _graph = None
    _checkpointer_context = None
    logger.debug("Graph instance reset")
