"""
LangGraph state machine for Homily Agent.

Defines the graph structure and nodes for homily generation workflow.
"""

import logging
from typing import TypedDict
from langgraph.graph import StateGraph, END
from .state import HomilyAgentState
from .agent import HomilyAgent
from .generator import HomilyGenerator
from .rag import RetrievalService

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """Graph state that wraps HomilyAgentState."""
    homily_state: HomilyAgentState


def create_homily_graph(
    retrieval_service: RetrievalService = None,
    generator: HomilyGenerator = None
) -> StateGraph:
    """
    Create the LangGraph state machine for homily generation.
    
    Args:
        retrieval_service: RAG retrieval service
        generator: Homily generator
        
    Returns:
        Compiled LangGraph state machine
    """
    if generator is None:
        generator = HomilyGenerator(retrieval_service)
        
    agent = HomilyAgent(generator)
    
    workflow = StateGraph(GraphState)
    
    workflow.add_node("parse", lambda state: _parse_node(state, agent))
    workflow.add_node("generate", lambda state: _generate_node(state, agent))
    workflow.add_node("refine", lambda state: _refine_node(state, agent))
    workflow.add_node("adjust", lambda state: _adjust_node(state, agent))
    workflow.add_node("validate", lambda state: _validate_node(state, agent))
    workflow.add_node("format", lambda state: _format_node(state, agent))
    
    workflow.set_entry_point("parse")
    
    workflow.add_conditional_edges(
        "parse",
        _route_by_intent,
        {
            "generate": "generate",
            "refine": "refine",
            "adjust": "adjust",
            "validate": "validate"
        }
    )
    
    workflow.add_edge("generate", "validate")
    workflow.add_edge("refine", "validate")
    workflow.add_edge("adjust", "validate")
    workflow.add_edge("validate", "format")
    workflow.add_edge("format", END)
    
    return workflow.compile()


def _parse_node(state: GraphState, agent: HomilyAgent) -> GraphState:
    """Parse request node."""
    homily_state = state["homily_state"]
    updates = agent.parse_request(homily_state)
    
    for key, value in updates.items():
        setattr(homily_state, key, value)
    
    return state


def _generate_node(state: GraphState, agent: HomilyAgent) -> GraphState:
    """Generate homily node."""
    homily_state = state["homily_state"]
    updates = agent.generate_homily(homily_state)
    
    for key, value in updates.items():
        setattr(homily_state, key, value)
    
    return state


def _refine_node(state: GraphState, agent: HomilyAgent) -> GraphState:
    """Refine homily node."""
    homily_state = state["homily_state"]
    updates = agent.refine_homily(homily_state)
    
    for key, value in updates.items():
        setattr(homily_state, key, value)
    
    return state


def _adjust_node(state: GraphState, agent: HomilyAgent) -> GraphState:
    """Adjust tone node."""
    homily_state = state["homily_state"]
    updates = agent.adjust_tone(homily_state)
    
    for key, value in updates.items():
        setattr(homily_state, key, value)
    
    return state


def _validate_node(state: GraphState, agent: HomilyAgent) -> GraphState:
    """Validate homily node."""
    homily_state = state["homily_state"]
    updates = agent.validate_homily(homily_state)
    
    for key, value in updates.items():
        setattr(homily_state, key, value)
    
    return state


def _format_node(state: GraphState, agent: HomilyAgent) -> GraphState:
    """Format response node."""
    homily_state = state["homily_state"]
    updates = agent.format_response(homily_state)
    
    return state


def _route_by_intent(state: GraphState) -> str:
    """Route to the appropriate node based on intent."""
    intent = state["homily_state"].intent
    
    route_map = {
        "generate": "generate",
        "refine": "refine",
        "adjust": "adjust",
        "validate": "validate"
    }
    
    return route_map.get(intent, "generate")


def run_homily_generation(
    liturgical_data: dict,
    occasion: str,
    preferences: dict = None,
    existing_draft: str = None,
    intent: str = "generate",
    retrieval_service: RetrievalService = None
) -> dict:
    """
    Run the homily generation workflow.
    
    Args:
        liturgical_data: Liturgical readings data
        occasion: Type of occasion
        preferences: User preferences
        existing_draft: Existing draft to refine
        intent: Request intent
        retrieval_service: RAG retrieval service
        
    Returns:
        Generated homily response
    """
    from .state import HomilyAgentState, LiturgicalReading, UserPreferences
    
    lit_reading = LiturgicalReading(**liturgical_data)
    user_prefs = UserPreferences(**preferences) if preferences else UserPreferences()
    
    initial_state = HomilyAgentState(
        intent=intent,
        liturgical_data=lit_reading,
        occasion=occasion,
        user_preferences=user_prefs,
        existing_draft=existing_draft
    )
    
    graph_state: GraphState = {"homily_state": initial_state}
    
    graph = create_homily_graph(retrieval_service)
    
    final_state = graph.invoke(graph_state)
    
    homily_state = final_state["homily_state"]
    
    return {
        "homily": homily_state.generated_homily.model_dump() if homily_state.generated_homily else None,
        "error": homily_state.error,
        "sources": homily_state.theological_sources
    }