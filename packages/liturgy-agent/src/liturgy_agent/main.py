"""
Main entry point for Liturgy Agent as an A2A (Agent-to-Agent) server.

Implements the A2A Protocol using JSON-RPC 2.0 for communication.
HTTP transport only (SSE streaming for real-time responses).

Usage:
    # Start HTTP server (default port 8001)
    python -m liturgy_agent.main
    
    # Custom port
    python -m liturgy_agent.main --port 9000
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .state import LiturgyAgentState
from .graph import create_liturgy_agent_graph

# Import A2A protocol
try:
    from a2a_protocol import create_server, AgentHandler, create_llm
    HAS_A2A = True
except ImportError:
    HAS_A2A = False
    logging.warning("A2A protocol not available")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Log to stderr to keep stdout clean
)
logger = logging.getLogger(__name__)


class LiturgyAgentHandler:
    """
    Handler for Liturgy Agent A2A requests.
    
    Implements AgentHandler interface for A2A protocol.
    """
    
    def __init__(self):
        """Initialize the handler with agent graph."""
        self.llm = create_llm(strict=False)
        self.graph = create_liturgy_agent_graph(self.llm)
    
    async def __call__(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle A2A method calls.
        
        Supported methods:
        - liturgy_agent.get_readings: Get liturgical readings
        - liturgy_agent.get_lectionary: Get lectionary options
        
        Args:
            method: Agent method name
            params: Method parameters
            
        Returns:
            Result dictionary
            
        Raises:
            ValueError: If method unknown or params invalid
        """
        logger.info(f"Handling method: {method}")
        
        if method == "liturgy_agent.get_readings":
            return await self._handle_get_readings(params)
        elif method == "liturgy_agent.get_lectionary":
            return await self._handle_get_lectionary(params)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    async def _handle_get_readings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_readings request.
        
        Params:
            date: Optional date string (YYYY-MM-DD)
            occasion: Occasion type (sunday, mass, marriage, baptism, funeral)
            
        Returns:
            Readings data
        """
        # Extract parameters
        date_str = params.get("date")
        occasion = params.get("occasion", "").lower()
        logger.info(f"Received get_readings request: occasion={occasion}, date={date_str}")

        if not occasion:
            logger.error("Missing required parameter: occasion")
            raise ValueError("Missing required parameter: occasion")

        # Validate date if provided
        if date_str:
            try:
                datetime.fromisoformat(date_str)
            except ValueError as e:
                logger.error(f"Invalid date format: {date_str}")
                raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD") from e

        # Create agent
        from .agent import LiturgyAgent
        from .cache import LiturgyCache
        from .scrapers import fetch_liturgical_data, ScraperError

        agent = LiturgyAgent(self.llm)
        cache = agent.cache

        # Handle daily Mass readings (sunday, mass, weekday)
        if occasion in ["sunday", "mass", "weekday", "daily"]:
            # Parse date
            if date_str is None:
                target_date = datetime.now()
            else:
                target_date = datetime.fromisoformat(date_str)

            logger.info(f"Looking for cached readings: date={target_date.strftime('%Y-%m-%d')}, occasion=mass")
            cached = cache.get(
                target_date.strftime("%Y-%m-%d"),
                "mass"
            )
            if cached:
                logger.info("Cache hit for readings: returning cached data.")
                return {
                    "status": "success",
                    "data": cached.model_dump(mode='json'),
                    "source": "cache"
                }

            logger.info("Cache miss: scraping external sources for readings.")
            # Fetch from web sources
            try:
                scraped_data = await fetch_liturgical_data(target_date)
                logger.info(f"Scraping complete. Building reading object. Date: {target_date.strftime('%Y-%m-%d')}. Scraped data keys: {list(scraped_data.keys())}. Values: {[type(v) for v in scraped_data.values()]}")
                # Create LiturgicalReading from scraped data
                reading = agent._build_reading_from_scraped(
                    scraped_data,
                    target_date
                )

                # Cache the result
                cache.set(reading)
                logger.info("Scraped readings cached successfully.")

                return {
                    "status": "success",
                    "data": reading.model_dump(mode='json'),
                    "source": "web"
                }

            except ScraperError as e:
                logger.error(f"Scraping error: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "message": "Could not fetch readings from web sources"
                }

        # Handle special occasions (marriage, baptism, funeral)
        elif occasion in ["marriage", "baptism", "funeral"]:
            logger.info(f"Loading lectionary for occasion: {occasion}")
            # Load from lectionary files
            lectionary_data = agent._load_lectionary(occasion)

            if not lectionary_data:
                logger.warning(f"No readings found for occasion: {occasion}")
                return {
                    "status": "error",
                    "error": f"No readings found for occasion: {occasion}"
                }

            logger.info(f"Returning lectionary readings for occasion: {occasion}")
            return {
                "status": "success",
                "data": lectionary_data,
                "source": "lectionary"
            }

        else:
            logger.error(f"Unknown occasion: {occasion}")
            raise ValueError(
                f"Unknown occasion: {occasion}. "
                f"Valid options: sunday, mass, weekday, marriage, baptism, funeral"
            )
    
    async def _handle_get_lectionary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_lectionary request.
        
        Params:
            occasion: Occasion type
            
        Returns:
            Lectionary options
        """
        occasion = params.get("occasion", "")
        
        if not occasion:
            raise ValueError("Missing required parameter: occasion")
        
        # Load lectionary data
        from .agent import LiturgyAgent
        agent = LiturgyAgent(self.llm)
        
        try:
            lectionary_data = agent._load_lectionary(occasion)
            if lectionary_data is None:
                raise ValueError(f"No lectionary data found for occasion: {occasion}")
            occasion_data = lectionary_data.get(occasion, {})
            readings = occasion_data.get("general_readings", [])
            
            return {
                "occasion": occasion,
                "lectionary": lectionary_data,
                "readings_count": len(readings)
            }
        except FileNotFoundError as e:
            raise ValueError(f"No lectionary found for occasion: {occasion}") from e
    
    async def _execute_graph(self, state: LiturgyAgentState) -> Dict[str, Any]:
        """
        Execute agent graph with given state.
        
        Args:
            state: Initial state
            
        Returns:
            Result dictionary
        """
        # Mock result for now
        # In production, this would invoke the graph:
        # result = await self.graph.ainvoke(state)
        
        return {
            "status": "success",
            "date": state.date or datetime.now().strftime("%Y-%m-%d"),
            "occasion": state.occasion,
            "readings": {
                "first_reading": {
                    "reference": "Genesis 1:26-28, 31a",
                    "type": "First",
                    "text": "Then God said: Let us make human beings...",
                    "source": "evangelizo.org"
                },
                "psalm": {
                    "reference": "Psalm 128:1-2, 3, 4-5",
                    "type": "Psalm",
                    "text": "Blessed are all who fear the Lord...",
                    "source": "evangelizo.org"
                },
                "second_reading": {
                    "reference": "1 John 4:7-12",
                    "type": "Second",
                    "text": "Beloved, let us love one another...",
                    "source": "evangelizo.org"
                },
                "gospel": {
                    "reference": "John 15:9-12",
                    "type": "Gospel",
                    "text": "Jesus said to his disciples: As the Father loves me...",
                    "source": "evangelizo.org"
                }
            },
            "from_cache": False,
            "cache_key": f"{state.occasion}_{state.date or 'today'}"
        }


def _get_contract_path() -> Optional[str]:
    """Resolve contract path from env var or default relative path."""
    env_path = os.getenv("AGENT_CONTRACT_PATH")
    if env_path:
        return env_path
    default = Path(__file__).parent.parent.parent.parent.parent / "contracts" / "liturgy-agent-contract.json"
    if default.exists():
        return str(default)
    logger.warning("Contract file not found via AGENT_CONTRACT_PATH or default path")
    return None


def _get_agent_url() -> Optional[str]:
    """Resolve agent public URL from env var."""
    return os.getenv("AGENT_URL")


def _get_basic_auth_config() -> dict:
    return {
        "basic_auth_username": os.getenv("A2A_BASIC_AUTH_USERNAME"),
        "basic_auth_password": os.getenv("A2A_BASIC_AUTH_PASSWORD"),
    }


async def serve_http(host: str = "0.0.0.0", port: int = 8001):
    """Serve agent via HTTP."""
    if not HAS_A2A:
        logger.error("A2A protocol not available. Cannot start server.")
        sys.exit(1)
    
    handler = LiturgyAgentHandler()
    server = create_server(
        handler=handler,
        name="liturgy_agent",
        contract_path=_get_contract_path(),
        agent_url=_get_agent_url(),
        **_get_basic_auth_config(),
    )
    
    await server.serve_http(host=host, port=port)


def main():
    """
    Main entry point.
    
    Parses arguments and starts HTTP server.
    """
    parser = argparse.ArgumentParser(
        description="Liturgy Agent A2A Server (HTTP)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to bind HTTP server (default: 8001)"
    )
    
    args = parser.parse_args()
    
    logger.info("Starting Liturgy Agent A2A Server (HTTP)")
    logger.info(f"Starting HTTP server on {args.host}:{args.port}")
    
    try:
        asyncio.run(serve_http(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
