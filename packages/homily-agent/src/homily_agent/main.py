"""
Homily Agent main entry point.

Provides A2A protocol server for homily generation.
"""

import asyncio
import sys
import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

# Import A2A protocol
try:
    from a2a_protocol import create_server
    HAS_A2A = True
except ImportError:
    HAS_A2A = False

# Lazy imports to avoid heavy dependencies at startup
# from .state import HomilyAgentState, LiturgicalReading, UserPreferences
# from .graph import create_homily_graph, GraphState
# from .generator import HomilyGenerator
# from .rag import RetrievalService, load_theological_corpus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HomilyAgentHandler:
    """
    Handler for A2A protocol requests to the Homily Agent.

    Implements the AgentHandler interface for A2A server.
    """

    def __init__(self):
        """Initialize the handler."""
        self.retrieval_service: Optional["RetrievalService"] = None
        self.graph = None

    def _ensure_initialized(self) -> None:
        """Lazy initialization of services."""
        if self.graph is None:
            # Lazy imports to avoid heavy dependencies at startup
            from .state import HomilyAgentState, LiturgicalReading, UserPreferences
            from .graph import create_homily_graph, GraphState
            from .generator import HomilyGenerator
            from .rag import RetrievalService, load_theological_corpus

            try:
                self.retrieval_service = load_theological_corpus()
            except Exception as e:
                logger.warning(f"Could not load theological corpus: {e}")
                self.retrieval_service = RetrievalService()

            generator = HomilyGenerator(self.retrieval_service)
            self.graph = create_homily_graph(self.retrieval_service, generator)
            logger.info("Homily Agent initialized")

    async def __call__(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle A2A method calls.

        Supported methods:
        - homily.generate: Generate a new homily
        - homily.refine: Refine an existing homily
        - homily.adjust_tone: Adjust tone of a homily

        Note: agent.ping is handled by A2AServer as a built-in method.

        Args:
            method: Agent method name
            params: Method parameters

        Returns:
            Result dictionary

        Raises:
            ValueError: If method unknown or params invalid
        """
        self._ensure_initialized()

        if method == "homily.generate":
            return await self._generate_homily(params)
        elif method == "homily.refine":
            return await self._refine_homily(params)
        elif method == "homily.adjust_tone":
            return await self._adjust_tone(params)
        else:
            raise ValueError(f"Unknown method: {method}")

    async def _invoke_graph(
        self,
        params: Dict[str, Any],
        intent: Literal["generate", "refine", "adjust"],
    ) -> Dict[str, Any]:
        """Execute graph with given parameters and intent."""
        from .state import HomilyAgentState, LiturgicalReading, UserPreferences
        from .graph import GraphState

        liturgical_data = params.get("liturgical_data")
        occasion = params.get("occasion", "mass")
        preferences = params.get("preferences", {})
        existing_draft = params.get("existing_draft")

        lit_reading = LiturgicalReading(**liturgical_data) if liturgical_data else None
        user_prefs = UserPreferences(**preferences) if preferences else UserPreferences()

        initial_state = HomilyAgentState(
            intent=intent,
            liturgical_data=lit_reading,
            occasion=occasion,
            user_preferences=user_prefs,
            existing_draft=existing_draft,
        )

        graph_state: GraphState = {"homily_state": initial_state}
        final_state = await self.graph.ainvoke(graph_state)
        homily_state = final_state["homily_state"]

        if homily_state.error:
            raise RuntimeError(homily_state.error)

        return {
            "homily": homily_state.generated_homily.model_dump() if homily_state.generated_homily else None,
            "sources": homily_state.theological_sources or [],
        }

    async def _generate_homily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {"status": "success", "data": await self._invoke_graph(params, "generate")}
        except Exception as e:
            logger.error(f"Error generating homily: {e}")
            raise

    async def _refine_homily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {"status": "success", "data": await self._invoke_graph(params, "refine")}
        except Exception as e:
            logger.error(f"Error refining homily: {e}")
            raise

    async def _adjust_tone(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {"status": "success", "data": await self._invoke_graph(params, "adjust")}
        except Exception as e:
            logger.error(f"Error adjusting tone: {e}")
            raise


def _get_contract_path() -> Optional[str]:
    """Resolve contract path from env var or default relative path."""
    env_path = os.getenv("AGENT_CONTRACT_PATH")
    if env_path:
        return env_path
    default = Path(__file__).parent.parent.parent.parent / "contracts" / "homily-agent-contract.json"
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


async def serve_http(host: str = "0.0.0.0", port: int = 8002):
    """Serve A2A requests via HTTP."""
    if not HAS_A2A:
        logger.error("A2A protocol not available. Cannot start server.")
        return

    handler = HomilyAgentHandler()
    server = create_server(
        handler=handler,
        name="homily_agent",
        contract_path=_get_contract_path(),
        agent_url=_get_agent_url(),
        **_get_basic_auth_config(),
    )

    await server.serve_http(host=host, port=port)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Homily Generation Agent")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind HTTP server")
    parser.add_argument("--port", type=int, default=8002, help="HTTP port")

    args = parser.parse_args()

    logger.info(f"Starting Homily Agent HTTP server on {args.host}:{args.port}")

    try:
        asyncio.run(serve_http(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
