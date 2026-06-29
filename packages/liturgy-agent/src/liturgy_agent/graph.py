"""
LangGraph state machine for Liturgy Agent.

This module defines the agent workflow using LangGraph, including:
- State graph definition
- Node transitions
- Tool execution and error handling
- Integration with LLM for reasoning
"""

from typing import Optional, Any
from langgraph.graph import StateGraph, END

from .state import LiturgyAgentState
from .agent import agent_node


def create_liturgy_agent_graph(
    llm: Any
) -> StateGraph:
    """
    Create and compile the Liturgy Agent state graph.
    
    Graph structure:
    ```
    input -> parse_request -> execute_tools -> format_response -> output
    ```
    
    Args:
        llm: Language model for agent reasoning
        
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the state graph
    graph = StateGraph(LiturgyAgentState)
    
    # Define nodes
    graph.add_node(
        "parse_request",
        lambda state: _parse_request_node(state, llm)
    )
    graph.add_node(
        "agent",
        lambda state: agent_node(state, llm)
    )
    graph.add_node(
        "format_response",
        _format_response_node
    )
    graph.add_node(
        "error_handler",
        _error_handler_node
    )
    
    # Define edges
    graph.set_entry_point("parse_request")
    
    graph.add_edge("parse_request", "agent")
    
    # Conditional edge based on agent result
    graph.add_conditional_edges(
        "agent",
        lambda state: "format_response" if state.error is None else "error_handler",
        {
            "format_response": "format_response",
            "error_handler": "error_handler"
        }
    )
    
    graph.add_edge("format_response", END)
    graph.add_edge("error_handler", END)
    
    # Compile the graph
    return graph.compile()


def _parse_request_node(
    state: LiturgyAgentState,
    llm: Any
) -> LiturgyAgentState:
    """
    Parse incoming request and validate input.
    
    Args:
        state: Current agent state
        llm: Language model for parsing
        
    Returns:
        Updated state with parsed data
    """
    # Simple validation - could be enhanced with LLM
    if not state.occasion:
        state.error = "No occasion or query provided"
        return state
    
    # Date validation
    if state.date:
        try:
            from datetime import datetime
            datetime.fromisoformat(state.date)
        except (ValueError, AttributeError):
            state.error = f"Invalid date format: {state.date}. Use YYYY-MM-DD"
            return state
    
    return state


def _format_response_node(state: LiturgyAgentState) -> dict:
    """
    Format the response for return to caller.
    
    Args:
        state: Current agent state with results
        
    Returns:
        Dictionary with formatted response
    """
    if state.readings:
        return {
            "status": "success",
            "data": {
                "date": state.readings.date,
                "occasion": state.readings.occasion,
                "readings": {
                    "first_reading": state.readings.first_reading.model_dump(),
                    "psalm": state.readings.psalm.model_dump(),
                    "second_reading": state.readings.second_reading.model_dump(),
                    "gospel": state.readings.gospel.model_dump(),
                    "alleluia_verse": state.readings.alleluia_verse.model_dump(),
                },
                "metadata": state.readings.metadata.model_dump(),
                "from_cache": state.from_cache
            }
        }
    
    return {
        "status": "error",
        "error": state.error or "No readings found"
    }


def _error_handler_node(state: LiturgyAgentState) -> dict:
    """
    Handle errors with appropriate user messaging.
    
    Args:
        state: Current agent state with error
        
    Returns:
        Dictionary with error response
    """
    error_msg = state.error or "An unknown error occurred"
    
    # Map internal errors to user-friendly messages
    error_messages = {
        "Invalid date format": "Please provide a valid date in YYYY-MM-DD format",
        "No occasion provided": "Please specify what liturgical readings you need",
        "Could not fetch readings": "Unable to fetch readings. Please try again later.",
    }
    
    user_msg = error_messages.get(error_msg, error_msg)
    
    return {
        "status": "error",
        "error": user_msg,
        "details": error_msg
    }


def create_minimal_graph() -> StateGraph:
    """
    Create a minimal testing graph without LLM dependency.
    
    Useful for testing and environments without LLM setup.
    
    Returns:
        Compiled StateGraph in minimal configuration
    """
    from unittest.mock import MagicMock
    
    mock_llm = MagicMock()
    return create_liturgy_agent_graph(mock_llm)
