"""
Tool definitions for Chat Orchestrator.

Defines tool functions for the chat orchestrator including:
- Date/calendar tools
- Liturgical data retrieval via A2A protocol
- Homily generation via A2A protocol
"""

import json
import os
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _parse_llm_json(text: str) -> dict:
    """Parse JSON string from LLM, handling single quotes via ast.literal_eval."""
    if not text or not text.strip():
        return {}
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    import ast
    try:
        result = ast.literal_eval(text)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError, MemoryError):
        pass
    logger.warning("Failed to parse LLM JSON, returning empty dict")
    return {}


_READING_KEYS = [("first_reading", "First"), ("psalm", "Psalm"), ("second_reading", "Second"), ("gospel", "Gospel")]


def _map_liturgical_data(liturgical_data: dict) -> dict:
    """Map liturgy agent response to LiturgicalReading format expected by homily agent.
    
    Handles three formats:
    - Already in LiturgicalReading format (first_reading at top level)
    - Nested under "data" key (from A2A response wrapper)
    - Nested under "readings" key (from liturgy agent contract)
    Also ensures each reading object has required "type" and "text" fields.
    """
    inner = liturgical_data if "first_reading" in liturgical_data else liturgical_data.get("data", liturgical_data)
    if "first_reading" in inner:
        mapped = dict(inner)
    else:
        readings = inner.get("readings", {})
        mapped = {
            "date": inner.get("date"),
            "occasion": inner.get("occasion"),
            "metadata": inner.get("metadata"),
        }
        for key, rtype in _READING_KEYS:
            r = readings.get(key)
            if r:
                r = dict(r)
                r.setdefault("type", rtype)
                r.setdefault("text", "")
                mapped[key] = r
    return mapped


# ── Date tools ──────────────────────────────────────────


@tool
def get_current_date(**kwargs: object) -> str:
    """Get the current date and time in a human-readable format.

    Args:
        **kwargs: Arbitrary keyword arguments (ignored).

    Returns:
        str: The current date and time as a formatted string.
    """
    now = datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M %p")


@tool
def calculate_date(query: str) -> str:
    """Calculate dates based on natural language queries.

    Handles 'next Sunday', 'tomorrow', 'in 3 days', etc. (English or Italian).

    Args:
        query: Natural language date query.

    Returns:
        Formatted date string or error message.
    """
    now = datetime.now()
    query_lower = query.lower().strip()

    day_map = {
        "sunday": 6, "domenica": 6,
        "monday": 0, "lunedì": 0, "lunedi": 0,
        "tuesday": 1, "martedì": 1, "martedi": 1,
        "wednesday": 2, "mercoledì": 2, "mercoledi": 2,
        "thursday": 3, "giovedì": 3, "giovedi": 3,
        "friday": 4, "venerdì": 4, "venerdi": 4,
        "saturday": 5, "sabato": 5,
    }

    for day_name, day_num in day_map.items():
        if day_name in query_lower:
            days_ahead = (day_num - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target_date = now + timedelta(days=days_ahead)
            return target_date.strftime("%A, %B %d, %Y")

    if "tomorrow" in query_lower or "domani" in query_lower:
        return (now + timedelta(days=1)).strftime("%A, %B %d, %Y")

    if "yesterday" in query_lower or "ieri" in query_lower:
        return (now - timedelta(days=1)).strftime("%A, %B %d, %Y")

    match = re.search(r'(?:in|tra)\s+(\d+)\s+(?:days|giorni)', query_lower)
    if match:
        return (now + timedelta(days=int(match.group(1)))).strftime("%A, %B %d, %Y")

    if "next week" in query_lower or "prossima settimana" in query_lower:
        return (now + timedelta(weeks=1)).strftime("%A, %B %d, %Y")

    return f"Could not parse date query: '{query}'. Today is {now.strftime('%A, %B %d, %Y')}."


def _get_auth_config() -> Dict[str, Any]:
    return {
        "auth_username": os.environ.get("A2A_BASIC_AUTH_USERNAME"),
        "auth_password": os.environ.get("A2A_BASIC_AUTH_PASSWORD"),
    }


def _get_liturgy_transport_config() -> Dict[str, Any]:
    """
    Get A2A transport configuration for liturgy agent from environment.
    
    Returns:
        Dictionary with agent_url for HTTP transport
    """
    config = {
        "agent_url": os.environ.get("A2A_LITURGY_URL", "http://localhost:8001")
    }
    config.update(_get_auth_config())
    return config


def _get_homily_transport_config() -> Dict[str, Any]:
    """
    Get A2A transport configuration for homily agent from environment.
    
    Returns:
        Dictionary with agent_url for HTTP transport
    """
    config = {
        "agent_url": os.environ.get("A2A_HOMILY_URL", "http://localhost:8002")
    }
    config.update(_get_auth_config())
    return config


def _today_iso() -> str:
    """Get current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalize a date string to YYYY-MM-DD format.
    
    Handles:
    - Already formatted YYYY-MM-DD dates (returns as-is)
    - Relative dates: "today", "tomorrow", "yesterday"
    - Italian: "oggi", "domani", "ieri"
    - None (returns None)
    
    Args:
        date_str: Date string to normalize
        
    Returns:
        Date in YYYY-MM-DD format, or None if input is None
    """
    if date_str is None:
        return None
    
    date_str = date_str.strip().lower()
    
    # Check if already YYYY-MM-DD format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # Handle relative dates
    now = datetime.now()
    
    if date_str in ["today", "oggi"]:
        return now.strftime("%Y-%m-%d")
    
    if date_str in ["tomorrow", "domani"]:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    if date_str in ["yesterday", "ieri"]:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # If we can't parse it, log warning and return as-is
    # (will cause error in agent, which will be caught and reported)
    logger.warning(f"Could not normalize date string: {date_str}")
    return date_str


async def request_liturgical_data(
    occasion: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Request liturgical readings for a specific occasion.
    
    This tool communicates with the Liturgy Agent via A2A protocol
    to retrieve liturgical readings.
    
    Args:
        occasion: Type of liturgical occasion (marriage, baptism, funeral, etc.)
        date: Optional date in YYYY-MM-DD format. If not provided, uses current date.
        
    Returns:
        Dictionary with readings data including first_reading, psalm, 
        second_reading, gospel, and metadata.
        
    Raises:
        RuntimeError: If A2A communication fails
    
    Example:
        >>> data = await request_liturgical_data(
        ...     occasion="marriage",
        ...     date="2024-01-15"
        ... )
        >>> print(data["readings"]["gospel"]["reference"])
    """
    from a2a_protocol import a2a_client

    config = _get_liturgy_transport_config()
    normalized_date = _normalize_date(date)
    logger.info(f"Requesting liturgical data: occasion={occasion}, date={normalized_date}")

    async with a2a_client(**config) as client:
        result = await client.call_agent_method(
            method="liturgy_agent.get_readings",
            params={"occasion": occasion, "date": normalized_date or _today_iso()},
            timeout=60.0,
        )
        return result


async def get_lectionary_options(occasion: str) -> Dict[str, Any]:
    """
    Get lectionary options for a specific occasion.
    
    Args:
        occasion: Type of liturgical occasion
        
    Returns:
        Dictionary with lectionary data
        
    Raises:
        RuntimeError: If A2A communication fails
    """
    from a2a_protocol import a2a_client

    config = _get_liturgy_transport_config()
    logger.info(f"Requesting lectionary options: occasion={occasion}")

    async with a2a_client(**config) as client:
        result = await client.call_agent_method(
            method="liturgy_agent.get_lectionary",
            params={"occasion": occasion},
            timeout=60.0,
        )
        return result


# ========== SYNCHRONOUS WRAPPERS FOR LANGCHAIN TOOLS ==========

@tool
async def get_liturgical_readings(occasion: str, date: Optional[str] = None) -> Dict[str, Any]:
    """Request liturgical readings for Sunday Mass or special occasions.
    
    Args:
        occasion: Type of liturgical occasion:
            - "sunday" or "mass" for Sunday/daily Mass readings
            - "marriage" for wedding ceremony
            - "baptism" for baptism ceremony  
            - "funeral" for funeral service
        date: Optional date in YYYY-MM-DD format. If not provided, uses current date.
        
    Returns:
        Dictionary with readings data including first_reading, psalm, second_reading, gospel.
    """
    try:
        result = await request_liturgical_data(occasion, date)
        return result
    except Exception as e:
        logger.error(f"Error getting liturgical readings: {e}")
        return {
            "error": str(e),
            "occasion": occasion,
            "date": date or _today_iso()
        }


@tool
async def get_liturgical_lectionary(occasion: str) -> Dict[str, Any]:
    """Get available lectionary options for a specific liturgical occasion.
    
    Args:
        occasion: Type of liturgical occasion (marriage, baptism, funeral)
        Note: This does NOT work for sunday/mass - only for special ceremonies.
        
    Returns:
        Dictionary with lectionary data and available readings count.
    """
    try:
        result = await get_lectionary_options(occasion)
        return result
    except Exception as e:
        logger.error(f"Error getting lectionary: {e}")
        return {
            "error": str(e),
            "occasion": occasion
        }


# ========== HOMILY AGENT TOOLS ==========

async def request_homily_generation(
    liturgical_data: Dict[str, Any],
    occasion: str,
    preferences: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Request homily generation from the Homily Agent.
    
    This tool communicates with the Homily Generation Agent via A2A protocol
    to generate a homily based on liturgical readings.
    
    Args:
        liturgical_data: Dictionary with readings data (from liturgy agent)
        occasion: Type of liturgical occasion (mass, marriage, baptism, funeral)
        preferences: Optional user preferences for homily generation
        
    Returns:
        Dictionary with generated homily content
        
    Raises:
        RuntimeError: If A2A communication fails
    """
    from a2a_protocol import a2a_client

    config = _get_homily_transport_config()
    logger.info(f"Requesting homily generation: occasion={occasion}")

    mapped = _map_liturgical_data(liturgical_data)
    if not mapped.get("first_reading") or not mapped.get("gospel"):
        logger.error("Incomplete liturgical data for homily generation", mapped=mapped)
        return {"error": "Dati liturgici incompleti. Richiedi prima le letture del giorno.", "occasion": occasion}

    async with a2a_client(**config) as client:
        result = await client.call_agent_method(
            method="homily.generate",
            params={
                "liturgical_data": mapped,
                "occasion": occasion,
                "preferences": preferences or {},
            },
            timeout=60.0,
        )
        return result


async def request_homily_refinement(
    liturgical_data: Dict[str, Any],
    occasion: str,
    preferences: Optional[Dict[str, Any]] = None,
    existing_draft: Optional[str] = None
) -> Dict[str, Any]:
    """
    Request refinement of an existing homily.
    
    Args:
        liturgical_data: Dictionary with readings data
        occasion: Type of liturgical occasion
        preferences: User preferences for refinement
        existing_draft: The existing homily to refine
        
    Returns:
        Dictionary with refined homily
    """
    from a2a_protocol import a2a_client

    config = _get_homily_transport_config()
    logger.info(f"Requesting homily refinement: occasion={occasion}")

    if not liturgical_data:
        logger.error("Missing liturgical data for homily refinement")
        return {"error": "Dati liturgici incompleti. Richiedi prima le letture del giorno.", "occasion": occasion}

    mapped = _map_liturgical_data(liturgical_data)
    if not mapped.get("first_reading") or not mapped.get("gospel"):
        logger.error("Incomplete liturgical data for homily refinement")
        return {"error": "Dati liturgici incompleti. Richiedi prima le letture del giorno.", "occasion": occasion}

    async with a2a_client(**config) as client:
        result = await client.call_agent_method(
            method="homily.refine",
            params={
                "liturgical_data": mapped,
                "occasion": occasion,
                "preferences": preferences or {},
                "existing_draft": existing_draft,
            },
            timeout=60.0,
        )
        return result


@tool
async def generate_homily(
    liturgical_data: str,
    occasion: str,
    preferences: Optional[str] = None
) -> Dict[str, Any]:
    """Generate a homily based on liturgical readings.
    
    Args:
        liturgical_data: JSON string with liturgical readings data
        occasion: Type of liturgical occasion (mass, marriage, baptism, funeral)
        preferences: Optional JSON string with user preferences:
            - target_audience: "adults", "youth", "children", "mixed"
            - tone: "formal", "conversational", "poetic", "consolatory", "celebratory"
            - length: "short", "medium", "long"
            - themes: list of additional themes
            - metaphors: list of metaphors to use
            - analogies: list of analogies to use
            - parables: list of biblical parables to reference
            
    Returns:
        Dictionary with generated homily
    """
    try:
        lit_data = _parse_llm_json(liturgical_data)
        prefs = _parse_llm_json(preferences) if preferences else {}
        
        result = await request_homily_generation(lit_data, occasion, prefs)
        return result
    except Exception as e:
        logger.error(f"Error generating homily: {e}")
        return {
            "error": str(e),
            "occasion": occasion
        }


@tool
async def refine_homily(
    liturgical_data: str,
    occasion: str,
    preferences: Optional[str] = None,
    existing_draft: Optional[str] = None
) -> Dict[str, Any]:
    """Refine an existing homily.
    
    Args:
        liturgical_data: JSON string with liturgical readings data
        occasion: Type of liturgical occasion
        preferences: Optional JSON string with user preferences
        existing_draft: The existing homily text to refine
        
    Returns:
        Dictionary with refined homily
    """
    try:
        lit_data = _parse_llm_json(liturgical_data) if liturgical_data else {}
        prefs = _parse_llm_json(preferences) if preferences else {}
        
        result = await request_homily_refinement(lit_data, occasion, prefs, existing_draft)
        return result
    except Exception as e:
        logger.error(f"Error refining homily: {e}")
        return {
            "error": str(e),
            "occasion": occasion
        }
