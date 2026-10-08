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
_REQUIRED_READING_KEYS = ("first_reading", "psalm", "gospel")
_METADATA_KEYS = ("date", "occasion", "season", "color", "year_cycle", "sunday_or_weekday")
_YEAR_CYCLES = {"A", "B", "C"}
_WEEKDAY_KINDS = {"Sunday", "Weekday"}
_OCCASION_ALIASES = {
    "sunday": "mass",
    "weekday": "mass",
    "daily": "mass",
}
_CANONICAL_OCCASIONS = frozenset({"mass", "marriage", "baptism", "funeral"})


def canonicalize_occasion(value: Any) -> str:
    """Normalize sunday/weekday/daily to mass; reject unknown occasions."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("liturgical occasion is required")
    if not isinstance(value, str):
        raise ValueError(f"invalid liturgical occasion type: {type(value).__name__}")
    normalized = value.strip().lower()
    normalized = _OCCASION_ALIASES.get(normalized, normalized)
    if normalized not in _CANONICAL_OCCASIONS:
        raise ValueError(f"unknown liturgical occasion: {value}")
    return normalized


def resolve_request_occasion(
    method_occasion: Any,
    *nested_occasions: Any,
    payload_occasion: Any = None,
    metadata_occasion: Any = None,
) -> str:
    """Resolve method and every explicit nested occasion to one canonical value.

    Absent nested values inherit the canonical method occasion. Every explicit
    value across outer/data/readings/metadata must agree after alias normalization.
    """
    canonical = canonicalize_occasion(method_occasion)
    values = list(nested_occasions)
    if payload_occasion is not None:
        values.append(payload_occasion)
    if metadata_occasion is not None:
        values.append(metadata_occasion)
    for raw in values:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        nested = canonicalize_occasion(raw)
        if nested != canonical:
            raise ValueError(
                f"liturgical occasion conflict: method={canonical} nested={nested}"
            )
    return canonical


def _nonblank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _reading_fields_complete(reading: Optional[dict]) -> bool:
    """Require nonblank string reference and text."""
    if not isinstance(reading, dict):
        return False
    return _nonblank_string(reading.get("reference")) and _nonblank_string(
        reading.get("text")
    )


def _reading_text_missing(reading: Optional[dict]) -> bool:
    return reading is not None and not _reading_fields_complete(reading)


def _references_match(selected: Optional[str], fetched: Optional[str]) -> bool:
    if not selected or not fetched:
        return False
    return selected.strip() == fetched.strip()


def _required_reading_keys(mapped: dict, occasion: str) -> tuple[str, ...]:
    if occasion != "mass":
        return _REQUIRED_READING_KEYS
    metadata = mapped.get("metadata")
    kind = mapped.get("_sunday_or_weekday")
    if kind not in _WEEKDAY_KINDS:
        kind = metadata.get("sunday_or_weekday") if isinstance(metadata, dict) else None
    if kind in _WEEKDAY_KINDS:
        sunday = kind == "Sunday"
    else:
        try:
            sunday = datetime.fromisoformat(mapped.get("date", "")).weekday() == 6
        except (TypeError, ValueError):
            sunday = False
    return _REQUIRED_READING_KEYS + (("second_reading",) if sunday else ())


def _required_readings_complete(mapped: dict, occasion: str = "mass") -> bool:
    for key in _required_reading_keys(mapped, occasion):
        if not _reading_fields_complete(mapped.get(key)):
            return False
    return True


def _explicit_occasions_from_payload(liturgical_data: Any) -> list[Any]:
    """Collect every explicit occasion across outer/data/readings/metadata.

    Incomplete metadata may later be dropped; occasions must still be validated
    against the method. No first-wins masking of nested conflicts.
    """
    found: list[Any] = []
    if not isinstance(liturgical_data, dict):
        return found

    stack: list[Any] = [liturgical_data]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        node_id = id(node)
        if node_id in seen:
            continue
        seen.add(node_id)
        raw = node.get("occasion")
        if raw is not None and (not isinstance(raw, str) or raw.strip()):
            found.append(raw)
        meta = node.get("metadata")
        if isinstance(meta, dict):
            meta_occ = meta.get("occasion")
            if meta_occ is not None and (
                not isinstance(meta_occ, str) or meta_occ.strip()
            ):
                found.append(meta_occ)
        for child_key in ("data", "readings"):
            child = node.get(child_key)
            if isinstance(child, dict):
                stack.append(child)
    return found


def _normalize_reading(reading: Any, reading_type: str) -> Optional[dict]:
    """Coerce a reading into the {reference, text, type} shape the homily agent validates.

    ``None`` means genuinely absent (eligible for recovery). Present-but-invalid
    shapes (blank/non-string reference, non-object non-string values) raise
    ``ValueError`` so callers reject instead of silently dropping the key.
    Bare nonblank strings remain valid reference-only input for text recovery.
    """
    if reading is None:
        return None

    if isinstance(reading, str):
        if not reading.strip():
            raise ValueError(f"invalid {reading_type}: blank reference")
        return {"reference": reading, "text": "", "type": reading_type}

    if not isinstance(reading, dict):
        raise ValueError(
            f"invalid {reading_type}: unsupported type {type(reading).__name__}"
        )

    normalized = dict(reading)
    normalized.setdefault("type", reading_type)
    normalized.setdefault("text", "")
    if "reference" in normalized:
        reference = normalized["reference"]
    elif "ref" in normalized:
        reference = normalized["ref"]
    else:
        raise ValueError(f"invalid {reading_type}: missing reference")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError(f"invalid {reading_type}: bad reference")
    normalized["reference"] = reference
    return normalized


def _normalize_metadata(metadata: Any, date: Any, occasion: Any) -> Optional[dict]:
    """Return a LiturgicalMetadata-shaped dict, or None so the homily agent applies its default."""
    if not isinstance(metadata, dict):
        return None

    normalized = dict(metadata)
    normalized.setdefault("date", date)
    normalized.setdefault("occasion", occasion)
    if not all(normalized.get(key) for key in _METADATA_KEYS):
        logger.warning(f"Dropping incomplete liturgical metadata: {metadata}")
        return None
    if normalized["year_cycle"] not in _YEAR_CYCLES or normalized["sunday_or_weekday"] not in _WEEKDAY_KINDS:
        logger.warning(f"Dropping non-conforming liturgical metadata: {metadata}")
        return None
    return normalized


def _has_top_level_readings(data: dict) -> bool:
    """True when any reading sits directly on the object.

    Checking only ``first_reading`` mis-classified partial payloads — the LLM
    may omit a reading it has no content for, which sent the whole object down
    the nested-readings branch and silently dropped everything.
    """
    return any(key in data for key, _ in _READING_KEYS)


def _map_liturgical_data(liturgical_data: dict) -> dict:
    """Map liturgy agent response to LiturgicalReading format expected by homily agent.
    
    Handles three formats:
    - Already in LiturgicalReading format (readings at top level)
    - Nested under "data" key (from A2A response wrapper)
    - Nested under "readings" key (from liturgy agent contract)

    In every case each reading is normalized into the {reference, text, type} object the
    homily agent validates.
    """
    inner = liturgical_data if _has_top_level_readings(liturgical_data) else liturgical_data.get("data", liturgical_data)
    if not isinstance(inner, dict):
        inner = liturgical_data
    nested = inner.get("readings")
    readings = nested if isinstance(nested, dict) else inner

    mapped = {
        "date": inner.get("date") or readings.get("date"),
        "occasion": inner.get("occasion") or readings.get("occasion"),
        "metadata": inner.get("metadata") or readings.get("metadata"),
    }
    for key, reading_type in _READING_KEYS:
        reading = _normalize_reading(readings.get(key), reading_type)
        if reading:
            mapped[key] = reading

    metadata = _normalize_metadata(mapped.get("metadata"), mapped.get("date"), mapped.get("occasion"))
    if metadata:
        mapped["metadata"] = metadata
    else:
        raw_metadata = mapped.get("metadata")
        raw_kind = raw_metadata.get("sunday_or_weekday") if isinstance(raw_metadata, dict) else None
        if isinstance(raw_kind, str) and raw_kind in _WEEKDAY_KINDS:
            # Retain valid day context even when other metadata fields are unusable.
            mapped["_sunday_or_weekday"] = raw_kind
        mapped.pop("metadata", None)

    return mapped


async def _with_full_reading_texts(mapped: dict, occasion: str) -> dict:
    """Recover missing/absent required readings without substituting selections.

    Absent required keys are filled from fresh data. Present incomplete readings
    are filled only when the fetched reference matches. Absent optional readings
    (e.g. weekday second reading) stay absent and are never invented. Complete
    selections are preserved.
    """
    incomplete_keys: list[str] = []
    required_keys = _required_reading_keys(mapped, occasion)
    for key, _ in _READING_KEYS:
        reading = mapped.get(key)
        if key in required_keys:
            if reading is None or not _reading_fields_complete(reading):
                incomplete_keys.append(key)
        elif _reading_text_missing(reading):
            incomplete_keys.append(key)
    if not incomplete_keys or not mapped.get("date"):
        return mapped

    try:
        fresh = _map_liturgical_data(
            await request_liturgical_data(occasion, mapped["date"])
        )
    except Exception as e:
        logger.warning(f"Could not re-fetch readings to fill missing texts: {e}")
        return mapped

    recovered: list[str] = []
    for key in incomplete_keys:
        selected = mapped.get(key)
        fetched = fresh.get(key)
        if not _reading_fields_complete(fetched):
            continue
        if selected is None:
            # Absent required key: adopt the complete fetched reading.
            mapped[key] = dict(fetched)
            recovered.append(key)
            continue
        if not _references_match(selected.get("reference"), fetched.get("reference")):
            logger.warning(
                "Refusing liturgical recovery for %s: selected=%r fetched=%r",
                key,
                selected.get("reference"),
                fetched.get("reference"),
            )
            continue
        filled = dict(selected)
        filled["text"] = fetched["text"]
        filled["reference"] = fetched["reference"]
        filled.setdefault("type", fetched.get("type"))
        mapped[key] = filled
        recovered.append(key)

    if not mapped.get("metadata") and fresh.get("metadata"):
        mapped["metadata"] = fresh["metadata"]
    if recovered:
        logger.info(
            "Recovered reading texts from the liturgy agent for: %s",
            ", ".join(recovered),
        )
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
    - Weekday names, English and Italian: "next sunday", "domenica"
    - Human-readable dates, as produced by calculate_date
    - None (returns None)

    The weekday and readable-format branches exist because this function is the
    last boundary before the liturgy agent, which accepts only ISO dates. The
    model is asked to resolve relative dates with calculate_date first, but it
    often passes the phrase straight through — and calculate_date itself returns
    "Sunday, September 20, 2026", which is not ISO either. Normalising here is
    the only point that covers both mistakes.

    Args:
        date_str: Date string to normalize

    Returns:
        Date in YYYY-MM-DD format, or None if input is None
    """
    if date_str is None:
        return None

    raw = date_str.strip()
    normalized = raw.lower()

    # Check if already YYYY-MM-DD format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', normalized):
        return normalized

    # Handle relative dates
    now = datetime.now()

    if normalized in ["today", "oggi"]:
        return now.strftime("%Y-%m-%d")

    if normalized in ["tomorrow", "domani"]:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    if normalized in ["yesterday", "ieri"]:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # Weekday names resolve to the next occurrence of that weekday.
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
        if day_name in normalized:
            days_ahead = (day_num - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Human-readable dates, including the format calculate_date returns.
    for fmt in ("%A, %B %d, %Y", "%A %B %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

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
    raw_occasions = _explicit_occasions_from_payload(liturgical_data or {})
    try:
        occasion = resolve_request_occasion(occasion, *raw_occasions)
    except ValueError as e:
        logger.error("Invalid liturgical occasion for homily generation: %s", e)
        return {"error": str(e), "occasion": occasion}

    try:
        mapped = _map_liturgical_data(liturgical_data or {})
    except ValueError as e:
        logger.error("Invalid liturgical reading for homily generation: %s", e)
        return {"error": str(e), "occasion": occasion}
    logger.info(f"Requesting homily generation: occasion={occasion}")

    mapped["occasion"] = occasion
    if isinstance(mapped.get("metadata"), dict):
        mapped["metadata"] = dict(mapped["metadata"])
        mapped["metadata"]["occasion"] = occasion
    mapped = await _with_full_reading_texts(mapped, occasion)
    if not _required_readings_complete(mapped, occasion):
        logger.error(
            "Incomplete liturgical data for homily generation: keys=%s",
            sorted(mapped.keys()),
        )
        return {"error": "Dati liturgici incompleti. Richiedi prima le letture del giorno.", "occasion": occasion}

    mapped.pop("_sunday_or_weekday", None)
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
    if not liturgical_data:
        logger.error("Missing liturgical data for homily refinement")
        return {"error": "Dati liturgici incompleti. Richiedi prima le letture del giorno.", "occasion": occasion}

    raw_occasions = _explicit_occasions_from_payload(liturgical_data)
    try:
        occasion = resolve_request_occasion(occasion, *raw_occasions)
    except ValueError as e:
        logger.error("Invalid liturgical occasion for homily refinement: %s", e)
        return {"error": str(e), "occasion": occasion}

    try:
        mapped = _map_liturgical_data(liturgical_data)
    except ValueError as e:
        logger.error("Invalid liturgical reading for homily refinement: %s", e)
        return {"error": str(e), "occasion": occasion}
    logger.info(f"Requesting homily refinement: occasion={occasion}")

    mapped["occasion"] = occasion
    if isinstance(mapped.get("metadata"), dict):
        mapped["metadata"] = dict(mapped["metadata"])
        mapped["metadata"]["occasion"] = occasion
    mapped = await _with_full_reading_texts(mapped, occasion)
    if not _required_readings_complete(mapped, occasion):
        logger.error("Incomplete liturgical data for homily refinement")
        return {"error": "Dati liturgici incompleti. Richiedi prima le letture del giorno.", "occasion": occasion}

    mapped.pop("_sunday_or_weekday", None)
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
