"""
Liturgy Agent - AI agent for retrieving and processing liturgical data.

This module implements the core agent logic that:
1. Parses user requests for liturgical information
2. Fetches data from web sources or cache
3. Formats responses in structured format
4. Handles errors with graceful fallbacks

The agent integrates with:
- State models for type-safe data structures
- Cache for efficient data retrieval
- Web scrapers for current liturgical information
- LangGraph for agent state management
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Literal, Any
import logging

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from .state import (
    LiturgyAgentState,
    LiturgicalReading,
    LiturgicalMetadata,
    Reading
)
from .cache import LiturgyCache
from .scrapers import (
    fetch_liturgical_data,
    EvangelizeScraper,
    ScraperError
)

logger = logging.getLogger(__name__)


class LiturgyAgent:
    """
    AI agent for retrieving liturgical information.
    
    Provides tools and reasoning for understanding liturgical requests
    and returning appropriate Mass readings and information.
    """
    
    def __init__(self, llm: Any):
        """
        Initialize the Liturgy Agent.
        
        Args:
            llm: Language model for reasoning and parsing
        """
        self.llm = llm
        self.cache = LiturgyCache()
        self.tools = self._setup_tools()
    
    def _setup_tools(self):
        """
        Set up tools available to the agent.
        
        Returns:
            List of tool definitions
        """
        return [
            self.get_daily_readings,
            self.get_occasion_readings,
            self.search_readings,
        ]
    
    @tool
    async def get_daily_readings(
        self,
        date: Optional[str] = None
    ) -> dict:
        """
        Get Mass readings for a specific date.
        
        Args:
            date: ISO format date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Dictionary with readings and metadata
        """
        if date is None:
            target_date = datetime.now()
        else:
            target_date = datetime.fromisoformat(date)
        
        # Try cache first
        cached = self.cache.get(
            target_date.strftime("%Y-%m-%d"),
            "Mass of the Day"
        )
        if cached:
            return {
                "status": "success",
                "data": cached.model_dump(),
                "source": "cache"
            }
        
        # Fetch from web sources
        try:
            scraped_data = await fetch_liturgical_data(target_date)
            
            # Create LiturgicalReading from scraped data
            reading = self._build_reading_from_scraped(
                scraped_data,
                target_date
            )
            
            # Cache the result
            self.cache.set(reading)
            
            return {
                "status": "success",
                "data": reading.model_dump(),
                "source": "web"
            }
        
        except ScraperError as e:
            logger.error(f"Scraping error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Could not fetch readings from web sources"
            }
    
    @tool
    async def get_occasion_readings(
        self,
        occasion: Literal["marriage", "baptism", "funeral"]
    ) -> dict:
        """
        Get readings for special occasions.
        
        Args:
            occasion: Type of occasion (marriage, baptism, funeral)
            
        Returns:
            Dictionary with occasion-specific readings
        """
        # Load from lectionary files
        lectionary_data = self._load_lectionary(occasion)
        
        if not lectionary_data:
            return {
                "status": "error",
                "error": f"No readings found for occasion: {occasion}"
            }
        
        return {
            "status": "success",
            "data": lectionary_data,
            "source": "lectionary"
        }
    
    @tool
    async def search_readings(
        self,
        query: str,
        limit: int = 5
    ) -> dict:
        """
        Search for readings by text or reference.
        
        Args:
            query: Search query (book, chapter, or keyword)
            limit: Maximum results to return
            
        Returns:
            List of matching readings
        """
        # Convert query to standard Bible reference format
        # e.g., "John 3:16" -> "Jn 3:16"
        normalized_query = self._normalize_bible_reference(query)
        
        results = []
        
        # Search all loaded lectionaries
        for occasion in ["marriage", "baptism", "funeral"]:
            lectionary = self._load_lectionary(occasion)
            if not lectionary:
                continue
            
            readings = lectionary.get(occasion, {}).get("general_readings", [])
            for reading in readings:
                if self._matches_query(reading, normalized_query):
                    results.append(reading)
                    if len(results) >= limit:
                        return {
                            "status": "success",
                            "data": results,
                            "query": normalized_query
                        }
        
        return {
            "status": "success",
            "data": results,
            "query": normalized_query
        }
    
    def _load_lectionary(self, occasion: str) -> Optional[dict]:
        """
        Load lectionary data from JSON file.
        
        Args:
            occasion: Occasion type (marriage, baptism, funeral)
            
        Returns:
            Dictionary with lectionary data or None
        """
        try:
            import importlib.resources as resources
            
            # Try Python 3.9+ syntax
            try:
                files = resources.files("liturgy_agent").joinpath(
                    f"lectionaries/{occasion}_readings.json"
                )
                data = json.loads(files.read_text())
            except (AttributeError, TypeError):
                # Fallback for Python 3.7-3.8
                import importlib
                module = importlib.import_module("liturgy_agent")
                file_path = (
                    module.__path__[0] +
                    f"/lectionaries/{occasion}_readings.json"
                )
                with open(file_path, 'r') as f:
                    data = json.load(f)
            
            return data
        
        except Exception as e:
            logger.error(f"Error loading lectionary {occasion}: {e}")
            return None
    
    def _normalize_bible_reference(self, query: str) -> str:
        """
        Normalize Bible references to standard form.
        
        Examples:
            "John 3:16" -> "Jn 3:16"
            "Matthew 5:1-12" -> "Mt 5:1-12"
        
        Args:
            query: Raw query string
            
        Returns:
            Normalized reference
        """
        # Common abbreviations
        book_map = {
            "genesis": "Gn",
            "exodus": "Ex",
            "leviticus": "Lv",
            "numbers": "Nm",
            "deuteronomy": "Dt",
            "joshua": "Jos",
            "judges": "Jdg",
            "ruth": "Ru",
            "samuel": "Sm",
            "kings": "Kgs",
            "chronicles": "Chr",
            "ezra": "Ezr",
            "nehemiah": "Neh",
            "esther": "Est",
            "job": "Jb",
            "psalms": "Ps",
            "proverbs": "Prv",
            "ecclesiastes": "Eccl",
            "isaiah": "Is",
            "jeremiah": "Jer",
            "lamentations": "Lam",
            "ezekiel": "Ez",
            "daniel": "Dn",
            "hosea": "Hos",
            "joel": "Jl",
            "amos": "Am",
            "obadiah": "Ob",
            "jonah": "Jon",
            "micah": "Mi",
            "nahum": "Na",
            "habakkuk": "Hab",
            "zephaniah": "Zep",
            "haggai": "Hg",
            "zechariah": "Zec",
            "malachi": "Mal",
            "matthew": "Mt",
            "mark": "Mk",
            "luke": "Lk",
            "john": "Jn",
            "acts": "Acts",
            "romans": "Rm",
            "corinthians": "Cor",
            "galatians": "Gal",
            "ephesians": "Eph",
            "philippians": "Phil",
            "colossians": "Col",
            "thessalonians": "Thess",
            "timothy": "Tm",
            "titus": "Ti",
            "philemon": "Phlm",
            "hebrews": "Heb",
            "james": "Jas",
            "peter": "Pt",
            "john": "Jn",
            "revelation": "Rv",
        }
        
        normalized = query.lower().strip()
        for full_name, abbrev in book_map.items():
            normalized = normalized.replace(full_name, abbrev)
        
        return normalized
    
    def _matches_query(self, reading: dict, query: str) -> bool:
        """
        Check if reading matches query.
        
        Args:
            reading: Reading dictionary with reference and text
            query: Normalized query string
            
        Returns:
            True if reading matches query
        """
        reference = reading.get("reference", "").lower()
        text = reading.get("text", "").lower()
        
        return query in reference or query in text
    
    # -----------------------------------------------------------------
    # Season / colour inference helpers
    # -----------------------------------------------------------------

    _SEASON_KEYWORDS: dict = {
        "Advent":    ["avvento", "advent"],
        "Christmas": ["natale", "christmas", "epifania", "epiphany"],
        "Lent":      ["quaresima", "lent", "ceneri", "ash"],
        "Easter":    ["pasqua", "easter", "pentecoste", "pentecost"],
    }

    _SEASON_COLORS: dict = {
        "Advent":    "Purple",
        "Christmas": "White",
        "Lent":      "Purple",
        "Easter":    "White",
        "Ordinary":  "Green",
    }

    def _infer_season(self, liturgic_title: str) -> str:
        """Infer liturgical season from the Italian/English liturgic title."""
        lower = liturgic_title.lower()
        for season, keywords in self._SEASON_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return season
        return "Ordinary"

    def _build_reading_from_scraped(
        self,
        scraped: dict,
        date: datetime
    ) -> LiturgicalReading:
        """
        Build LiturgicalReading from scraped data.

        Expects the structure produced by fetch_liturgical_data():
            {
                "date": "YYYY-MM-DD",
                "sources": {
                    "evangelizo.ws": {
                        "liturgic_title": str,
                        "first_reading":  {"reference": str, "text": str, ...},
                        "psalm":          {"reference": str, "text": str, "chorus": str, ...},
                        "second_reading": {"reference": str, "text": str, ...},  # optional
                        "gospel":         {"reference": str, "text": str, ...},
                        ...
                    }
                }
            }

        Args:
            scraped: Dictionary with scraped data from multiple sources
            date: Target date

        Returns:
            LiturgicalReading object ready for caching
        """
        sources = scraped.get("sources", {})
        ev = sources.get("evangelizo.ws", {})

        def _reading(entry: dict, reading_type: str) -> Reading:
            return Reading(
                reference=entry.get("reference", ""),
                text=entry.get("text", ""),
                type=reading_type,
            )

        # Required readings
        first_reading = _reading(ev.get("first_reading", {}), "First")
        psalm         = _reading(ev.get("psalm", {}),         "Psalm")
        gospel        = _reading(ev.get("gospel", {}),        "Gospel")

        # Optional second reading
        second_reading: Optional[Reading] = None
        if ev.get("second_reading"):
            second_reading = _reading(ev["second_reading"], "Second")

        # Infer season and colour from liturgical title
        liturgic_title = ev.get("liturgic_title", "")
        season = self._infer_season(liturgic_title)
        color  = self._SEASON_COLORS.get(season, "Green")

        # Liturgical year cycle (A/B/C) based on the Gregorian year.
        # Year C: divisible by 3 (e.g. 2025), B: remainder 1, A: remainder 2.
        # Cycle switches at the start of Advent (late Nov/early Dec).
        year = date.year
        cycle_index = year % 3          # 0→C, 1→A, 2→B  (approx.)
        year_cycle  = ["C", "A", "B"][cycle_index]

        # Build metadata
        metadata = LiturgicalMetadata(
            date=date.strftime("%Y-%m-%d"),
            occasion="mass",
            season=season,
            color=color,
            year_cycle=year_cycle,
            sunday_or_weekday="Sunday" if date.weekday() == 6 else "Weekday",
        )

        return LiturgicalReading(
            date=date.strftime("%Y-%m-%d"),
            occasion="mass",
            metadata=metadata,
            first_reading=first_reading,
            psalm=psalm,
            second_reading=second_reading,
            gospel=gospel,
            alleluia_verse=None,
            cached_at=datetime.now(),
            source=ev.get("source", "evangelizo.ws"),
        )


async def agent_node(
    state: LiturgyAgentState,
    llm: Any
) -> LiturgyAgentState:
    """
    Agent processing node for LangGraph integration.
    
    This node processes a request through the Liturgy Agent and returns
    updated state with readings and metadata.
    
    Args:
        state: Current agent state
        llm: Language model to use
        
    Returns:
        Updated state with results
    """
    agent = LiturgyAgent(llm)
    
    # Execute the appropriate tool based on occasion type
    if state.occasion == "mass":
        result = await agent.get_daily_readings(state.date)
    elif state.occasion in ("marriage", "baptism", "funeral"):
        result = await agent.get_occasion_readings(state.occasion)
    else:
        result = await agent.search_readings(state.date or "")
    
    # Process result and update state
    if result.get("status") == "success":
        # Parse the result data
        data = result.get("data", {})
        
        if isinstance(data, dict):
            reading = LiturgicalReading(**data)
            state.readings = reading
            state.error = None
        else:
            state.error = "Invalid data format"
    else:
        state.error = result.get("error", "Unknown error")
    
    return state

