"""
State models for Homily Agent.

Defines the HomilyAgentState for managing homily generation requests and responses.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


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
        sunday_or_weekday: Whether it's a Sunday or weekday
    """
    date: str
    occasion: Literal["mass", "marriage", "baptism", "funeral"]
    season: str
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
    """
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    occasion: Literal["mass", "marriage", "baptism", "funeral"] = "mass"
    metadata: LiturgicalMetadata = Field(default_factory=lambda: LiturgicalMetadata(date=datetime.now().strftime("%Y-%m-%d"), occasion="mass", season="Ordinary", color="Green", year_cycle="A", sunday_or_weekday="Weekday"))
    first_reading: Reading
    psalm: Optional[Reading] = None
    second_reading: Optional[Reading] = None
    gospel: Reading


class UserPreferences(BaseModel):
    """
    User preferences for homily generation.
    
    Attributes:
        target_audience: Intended audience (adults, youth, children, mixed)
        tone: Desired tone (formal, conversational, poetic, consolatory, celebratory)
        length: Desired length (short: 5-7min, medium: 10-12min, long: 15+min)
        themes: Additional pastoral themes to incorporate
        metaphors: Specific metaphors to incorporate
        analogies: Specific analogies to use
        parables: Biblical or custom parables to reference
    """
    target_audience: Literal["adults", "youth", "children", "mixed"] = "adults"
    tone: Literal["formal", "conversational", "poetic", "consolatory", "celebratory"] = "formal"
    length: Literal["short", "medium", "long"] = "medium"
    themes: Optional[list[str]] = None
    metaphors: Optional[list[str]] = None
    analogies: Optional[list[str]] = None
    parables: Optional[list[str]] = None


class HomilySection(BaseModel):
    """
    A single section of a homily.
    
    Attributes:
        title: Title of the section
        content: Content of the section
    """
    title: str
    content: str


class GeneratedHomily(BaseModel):
    """
    A complete generated homily.
    
    Attributes:
        introduction: Introduction section
        reading_reflection: Reflection on the readings
        practical_application: Practical application section
        conclusion: Conclusion section
        occasion: The occasion type
        liturgical_date: The date of the liturgy
    """
    introduction: HomilySection
    reading_reflection: HomilySection
    practical_application: HomilySection
    conclusion: HomilySection
    occasion: Literal["mass", "marriage", "baptism", "funeral"]
    liturgical_date: str


class HomilyAgentState(BaseModel):
    """
    State for the Homily Generation Agent.
    
    Manages the request and response for homily generation.
    
    Attributes:
        intent: The intent of the request (generate, refine, adjust)
        liturgical_data: The liturgical readings and metadata
        occasion: Type of occasion (mass, marriage, baptism, funeral)
        user_preferences: User preferences for the homily
        existing_draft: Existing draft to refine (if any)
        rag_results: Retrieved documents from RAG
        generated_homily: The generated homily (if successful)
        error: Error message (if request failed)
    """
    intent: Literal["generate", "refine", "adjust", "validate"] = "generate"
    liturgical_data: Optional[LiturgicalReading] = None
    occasion: Literal["mass", "marriage", "baptism", "funeral"] = "mass"
    user_preferences: Optional[UserPreferences] = None
    existing_draft: Optional[str] = None
    rag_results: Optional[list[str]] = None
    generated_homily: Optional[GeneratedHomily] = None
    error: Optional[str] = None
    theological_sources: Optional[list[str]] = None
    validation: Optional[dict] = None