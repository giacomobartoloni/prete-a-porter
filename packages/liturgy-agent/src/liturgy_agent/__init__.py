"""
Liturgy Agent - Autonomous liturgical data retrieval agent.

This agent is responsible for retrieving liturgical information including:
- Daily Mass readings from evangelizo.org
- Ritual-specific lectionaries (marriages, baptisms, funerals)
- Liturgical metadata (season, liturgical color, year cycle)
- Caching with TTL-based expiration

The agent is designed to be called via A2A protocol from the Chat Orchestrator.
"""

__version__ = "0.1.0"
