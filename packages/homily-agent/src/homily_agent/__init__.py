"""
Homily Agent package.

Provides homily generation capabilities using RAG and LLM.
"""

__version__ = "0.1.0"

from .state import (
    HomilyAgentState,
    UserPreferences,
    GeneratedHomily,
    HomilySection,
    LiturgicalReading,
    LiturgicalMetadata,
    Reading,
)
from .generator import HomilyGenerator
from .agent import HomilyAgent
from .graph import create_homily_graph, run_homily_generation

__all__ = [
    "HomilyAgentState",
    "UserPreferences",
    "GeneratedHomily",
    "HomilySection",
    "LiturgicalReading",
    "LiturgicalMetadata",
    "Reading",
    "HomilyGenerator",
    "HomilyAgent",
    "create_homily_graph",
    "run_homily_generation",
]