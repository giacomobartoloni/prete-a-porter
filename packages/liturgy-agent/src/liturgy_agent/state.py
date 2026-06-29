"""
State models for Liturgy Agent.

Defines the LiturgyAgentState for managing liturgical data requests and responses.
"""

from typing import Literal, Optional
from datetime import datetime
from pydantic import BaseModel


class Reading(BaseModel):
    """
    A single liturgical reading.
    
    Attributes:
        reference: Biblical reference (e.g., "Gn 1:1-5")
        text: Full text of the reading
        type: Type of reading (First, Second, Gospel, Psalm, Alleluia)
    """
    reference: str
    text: str
    type: Literal["First", "Second", "Gospel", "Psalm", "Alleluia"]


class LiturgicalMetadata(BaseModel):
    """
    Metadata about a liturgical date.
    
    Attributes:
        date: The liturgical date (ISO format)
        occasion: Type of occasion (mass, marriage, baptism, funeral)
        season: Liturgical season (Advent, Christmas, Epiphany, Lent, Easter, Ordinary)
        color: Liturgical color (White, Red, Green, Purple, Violet, etc.)
        year_cycle: Liturgical year (A, B, or C)
        Sunday_or_weekday: Whether it's a Sunday or weekday
    """
    date: str
    occasion: Literal["mass", "marriage", "baptism", "funeral"]
    season: Literal["Advent", "Christmas", "Epiphany", "Lent", "Easter", "Ordinary"]
    color: str
    year_cycle: Literal["A", "B", "C"]
    sunday_or_weekday: Literal["Sunday", "Weekday"]


class LiturgicalReading(BaseModel):
    """
    Complete liturgical readings for a specific date and occasion.
    
    Attributes:
        date: The date (ISO format)
        occasion: Type of occasion
        metadata: Liturgical metadata
        first_reading: First reading from Old Testament or epistles
        psalm: Responsorial psalm
        second_reading: Second reading (if present)
        gospel: Gospel reading
        alleluia_verse: Alleluia verse (if before Gospel)
        cached_at: Timestamp when this was retrieved/cached
        source: Source of the data (evangelizo.org, lectionary, etc.)
    """
    date: str
    occasion: Literal["mass", "marriage", "baptism", "funeral"]
    metadata: LiturgicalMetadata
    first_reading: Reading
    psalm: Reading
    second_reading: Optional[Reading] = None
    gospel: Reading
    alleluia_verse: Optional[Reading] = None
    cached_at: datetime
    source: str


class LiturgyAgentState(BaseModel):
    """
    State for the Liturgy Agent.
    
    Manages the request and response for liturgical data retrieval.
    
    Attributes:
        date: Target date for readings (ISO format YYYY-MM-DD)
        occasion: Type of occasion (mass, marriage, baptism, funeral)
        readings: Retrieved readings (if successful)
        error: Error message (if request failed)
        from_cache: Whether the reading came from cache
    """
    date: str
    occasion: Literal["mass", "marriage", "baptism", "funeral"]
    readings: Optional[LiturgicalReading] = None
    error: Optional[str] = None
    from_cache: bool = False
