"""
A2A Server Implementation.

Wraps an agent to handle A2A protocol requests via HTTP.
Supports Google A2A standard endpoints (POST /message:send, GET /tasks/{id}, etc.).
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Optional, Callable, Dict, Any, Awaitable
from pathlib import Path

try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import StreamingResponse
    from sse_starlette.sse import EventSourceResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


logger = logging.getLogger(__name__)


# Type alias for agent handler
AgentHandler = Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]


def _jsonrpc_response(request_id: str, result: Dict[str, Any]) -> Response:
    return Response(
        content=json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}),
        media_type="application/json",
        status_code=200,
    )


def _jsonrpc_error(request_id: str, code: int, message: str, error_id: str = "") -> Response:
    data = {"error_id": error_id} if error_id else None
    return Response(
        content=json.dumps({
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message, "data": data},
        }),
        media_type="application/json",
        status_code=200,
    )


def _sanitize_error(error: Exception) -> tuple[str, int, str]:
    error_id = str(uuid.uuid4())[:8]
    logger.error(f"Internal error {error_id}: {error}", exc_info=True)
    return error_id, -32603, "Internal error"


class A2AServer:
    """
    A2A protocol server.

    Wraps an agent and handles incoming A2A requests via HTTP.
    Supports custom A2A (POST /a2a) and Google A2A standard endpoints.

    Example:
        >>> async def my_agent(method: str, params: dict) -> dict:
        ...     return {"result": "success"}
        ...
        >>> server = A2AServer(handler=my_agent)
        >>> await server.serve_http(port=8001)
    """

    def __init__(
        self,
        handler: AgentHandler,
        name: str = "a2a-agent",
        contract_path: Optional[str] = None,
        agent_url: Optional[str] = None,
        basic_auth_username: Optional[str] = None,
        basic_auth_password: Optional[str] = None,
    ):
        """
        Initialize A2A server.

        Args:
            handler: Async function that handles agent methods
                     Signature: async def handler(method: str, params: dict) -> dict
            name: Server name for logging
            contract_path: Optional path to agent contract JSON file.
                           Enables built-in agent.describe and agent.contract methods.
            agent_url: Optional public URL of this agent.
                       Used in the standard A2A Agent Card at /.well-known/agent-card.json.
            basic_auth_username: Optional Basic Auth username.
            basic_auth_password: Optional Basic Auth password.
        """
        self.handler = handler
        self.name = name
        self.contract_path = Path(contract_path) if contract_path else None
        self._contract_data: Optional[dict] = None
        self._agent_url: Optional[str] = agent_url
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._basic_auth_username = basic_auth_username or os.environ.get("A2A_BASIC_AUTH_USERNAME")
        self._basic_auth_password = basic_auth_password or os.environ.get("A2A_BASIC_AUTH_PASSWORD")
        self._load_contract()

    def _load_contract(self) -> None:
        """Load contract JSON from path if provided."""
        if not self.contract_path:
            return
        try:
            if self.contract_path.exists():
                with open(self.contract_path, "r") as f:
                    self._contract_data = json.load(f)
                logger.info(f"Loaded contract from {self.contract_path}")
            else:
                logger.warning(f"Contract file not found: {self.contract_path}")
        except Exception as e:
            logger.warning(f"Failed to load contract from {self.contract_path}: {e}")

    def _get_base_url(self) -> str:
        """Get the agent's base URL (without path)."""
        if self._agent_url:
            return self._agent_url.rstrip("/")
        return f"http://{self.name}:8001"

    def _get_contract_methods(self) -> list[Dict[str, str]]:
        """Return method descriptors from contract data."""
        if not self._contract_data:
            return []
        return [
            {"name": m["name"], "description": m.get("description", "")}
            for m in self._contract_data.get("methods", [])
        ]

    def _handle_ping(self) -> Dict[str, Any]:
        """Handle agent.ping: health check."""
        version = self._contract_data.get("version", "unknown") if self._contract_data else "unknown"
        return {"status": "pong", "agent": self.name, "version": version}

    def _generate_agent_card(self) -> Dict[str, Any]:
        """
        Generate standard Google A2A Agent Card.
        """
        base_url = self._get_base_url()
        capabilities = {"streaming": False, "pushNotifications": False}

        name = self._contract_data.get("name", self.name) if self._contract_data else self.name
        description = self._contract_data.get("description", "") if self._contract_data else ""
        version = self._contract_data.get("version", "unknown") if self._contract_data else "unknown"

        methods = self._contract_data.get("methods", []) if self._contract_data else []
        skills = []
        for m in methods:
            skill_id = m["name"].replace(".", "_")
            name_parts = m["name"].split(".")
            tags = name_parts[:-1] if len(name_parts) > 1 else ["a2a"]
            if m["name"] in ("agent.ping",):
                continue
            skills.append({
                "id": skill_id,
                "name": m.get("name", skill_id),
                "description": m.get("description", ""),
                "tags": tags,
                "examples": [],
            })

        return {
            "name": name,
            "description": description,
            "url": base_url,
            "version": version,
            "capabilities": capabilities,
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": skills,
            "supported_interfaces": [
                {
                    "url": base_url,
                    "protocol_binding": "HTTP+JSON",
                    "protocol_version": "1.0",
                }
            ],
            "supportedInterfaces": [
                {
                    "url": base_url,
                    "protocolBinding": "HTTP+JSON",
                    "protocolVersion": "1.0",
                }
            ],
        }

    # --- Standard Google A2A endpoint handlers ---

    def _extract_text_from_message(self, message: Dict[str, Any]) -> str:
        """Extract text content from a standard A2A message."""
        parts = message.get("parts", [])
        for part in parts:
            if "text" in part:
                return str(part["text"])
            if "data" in part:
                return str(part["data"])
        return ""

    def _dispatch_from_text(self, text: str) -> Dict[str, Any]:
        """
        Parse a text message and dispatch to the appropriate handler.
        Supports both JSON-RPC format and plain text.
        """
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                cmd = json.loads(stripped)
                method = cmd.get("method", "")
                params = cmd.get("params", {})
                return {"method": method, "params": params}
            except json.JSONDecodeError:
                pass

        method_parts = stripped.split(None, 1)
        if method_parts and "." in method_parts[0]:
            method = method_parts[0]
            rest = method_parts[1] if len(method_parts) > 1 else ""
            params = {}
            if rest:
                try:
                    params = json.loads(rest)
                except json.JSONDecodeError:
                    params = {"text": rest}
            return {"method": method, "params": params}

        return {"method": "", "params": {"text": stripped}}

    async def _handle_send_message(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle standard Google A2A SendMessage.

        Accepts a SendMessageRequest and returns a SendMessageResponse
        with task containing the agent's reply.
        """
        task_id = body.get("id") or str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        message = body.get("message", {})
        user_text = self._extract_text_from_message(message)
        user_msg_id = message.get("id") or str(uuid.uuid4())
        cmd = self._dispatch_from_text(user_text)

        task = {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "working"},
            "history": [
                {"messageId": user_msg_id, "role": "user", "parts": [{"text": user_text}]}
            ],
        }
        self._tasks[task_id] = task

        try:
            if cmd["method"]:
                if cmd["method"] == "agent.ping":
                    result = self._handle_ping()
                else:
                    result = await self.handler(cmd["method"], cmd["params"])
                reply_content = json.dumps(result, indent=2, default=str)
            else:
                reply_content = json.dumps({
                    "error": "Unsupported message format. Send JSON: {\"method\": \"agent.ping\", \"params\": {}}"
                })
        except Exception as e:
            error_id, _, _ = _sanitize_error(e)
            reply_content = json.dumps({"error": f"Internal error {error_id}"})

        agent_msg_id = str(uuid.uuid4())
        reply_message = {
            "messageId": agent_msg_id,
            "role": "agent",
            "parts": [{"text": reply_content}],
        }

        task["status"]["state"] = "completed"
        task["history"].append(reply_message)
        self._tasks[task_id] = task

        return {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "completed"},
            "history": task["history"],
        }

    def _handle_get_task(self, task_id: str) -> Dict[str, Any]:
        """Handle standard Google A2A GetTask."""
        task = self._tasks.get(task_id)
        if not task:
            return {"error": {"code": -32602, "message": f"Task not found: {task_id}"}}
        return {
            "id": task["id"],
            "contextId": task.get("contextId", ""),
            "status": task.get("status", {"state": "unknown"}),
            "history": task["history"],
        }

    def _handle_list_tasks(self) -> Dict[str, Any]:
        """Handle standard Google A2A ListTasks."""
        return {
            "tasks": [
                {"id": tid, "state": t.get("status", {}).get("state", "UNKNOWN")}
                for tid, t in self._tasks.items()
            ],
        }

    # --- Route handlers (extracted from create_fastapi_app closures) ---

    async def _route_message_send(self, request: Request) -> Response:
        """POST /message:send — Standard Google A2A SendMessage."""
        try:
            body = await request.json()
            result = await self._handle_send_message(body)
            return Response(content=json.dumps(result), media_type="application/json", status_code=200)
        except Exception as e:
            error_id, code, msg = _sanitize_error(e)
            return _jsonrpc_error(str(uuid.uuid4())[:8], code, msg, error_id)

    async def _route_get_task(self, task_id: str, request: Request) -> Response:
        """GET /tasks/{task_id} — Standard Google A2A GetTask."""
        try:
            result = self._handle_get_task(task_id)
            return Response(content=json.dumps(result), media_type="application/json", status_code=200)
        except Exception as e:
            error_id, code, msg = _sanitize_error(e)
            return _jsonrpc_error(str(uuid.uuid4())[:8], code, msg, error_id)

    async def _route_list_tasks(self) -> Response:
        """GET /tasks — Standard Google A2A ListTasks."""
        try:
            result = self._handle_list_tasks()
            return Response(content=json.dumps(result), media_type="application/json", status_code=200)
        except Exception as e:
            error_id, code, msg = _sanitize_error(e)
            return _jsonrpc_error(str(uuid.uuid4())[:8], code, msg, error_id)

    async def _route_root_post(self, request: Request) -> Response:
        """POST / — Custom A2A JSON-RPC method routing."""
        try:
            body = await request.json()
            req_id = body.get("id", str(uuid.uuid4())[:8])
            jsonrpc = body.get("jsonrpc")
            method = body.get("method", "")

            if jsonrpc != "2.0" or not method:
                return Response(content=json.dumps({"error": "Unsupported request format"}), media_type="application/json", status_code=400)

            if method == "message/send":
                params = body.get("params", {})
                result = await self._handle_send_message(params)
                return _jsonrpc_response(req_id, result)

            if method == "tasks/get":
                params = body.get("params", {})
                task_id = params.get("id", "")
                result = self._handle_get_task(task_id)
                if "error" in result:
                    return _jsonrpc_error(req_id, -32602, result["error"]["message"])
                return _jsonrpc_response(req_id, result)

            if method == "tasks/list":
                result = self._handle_list_tasks()
                return _jsonrpc_response(req_id, result)

            if method == "agent.ping":
                return _jsonrpc_response(req_id, self._handle_ping())

            if method == "agent.describe":
                return _jsonrpc_response(req_id, self._get_contract_methods())

            # Route to custom agent handler for non-standard methods
            params = body.get("params", {})
            try:
                result = await self.handler(method, params)
                return _jsonrpc_response(req_id, result)
            except Exception as e:
                error_id, code, msg = _sanitize_error(e)
                return _jsonrpc_error(req_id, code, msg, error_id)

        except Exception as e:
            error_id, code, msg = _sanitize_error(e)
            req_id = str(uuid.uuid4())[:8]
            return _jsonrpc_error(req_id, code, msg, error_id)

    async def _route_agent_card(self) -> Dict[str, Any]:
        """GET /.well-known/agent-card.json"""
        return self._generate_agent_card()

    async def _route_health(self) -> Dict[str, Any]:
        """GET /health"""
        return {"status": "healthy", "agent": self.name}

    # --- FastAPI app creation ---

    @staticmethod
    async def _basic_auth_middleware(
        username: Optional[str],
        password: Optional[str],
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Basic Auth middleware. Skips /health for docker healthcheck."""
        if username and password and request.url.path != "/health":
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Basic "):
                return Response(
                    status_code=401,
                    content=json.dumps({"error": "Unauthorized"}),
                    headers={"WWW-Authenticate": "Basic"},
                )
            try:
                decoded = base64.b64decode(auth_header[6:]).decode()
                user, pwd = decoded.split(":", 1)
                if user != username or pwd != password:
                    return Response(
                        status_code=401,
                        content=json.dumps({"error": "Invalid credentials"}),
                        headers={"WWW-Authenticate": "Basic"},
                    )
            except Exception:
                return Response(
                    status_code=401,
                    content=json.dumps({"error": "Invalid auth header"}),
                    headers={"WWW-Authenticate": "Basic"},
                )
        return await call_next(request)

    def create_fastapi_app(self) -> "FastAPI":
        """
        Create FastAPI application for HTTP transport.

        Returns:
            Configured FastAPI app

        Raises:
            ImportError: If FastAPI not installed
        """
        if not HAS_FASTAPI:
            raise ImportError(
                "FastAPI required for HTTP transport. "
                "Install with: pip install fastapi sse-starlette uvicorn"
            )

        app = FastAPI(title=self.name, version="1.0.0")

        if self._basic_auth_username and self._basic_auth_password:
            username = self._basic_auth_username
            password = self._basic_auth_password

            @app.middleware("http")
            async def auth_middleware(request: Request, call_next):
                return await self._basic_auth_middleware(
                    username, password, request, call_next
                )

        app.post("/message:send")(self._route_message_send)
        app.get("/tasks/{task_id}")(self._route_get_task)
        app.get("/tasks")(self._route_list_tasks)
        app.post("/")(self._route_root_post)
        app.get("/.well-known/agent-card.json")(self._route_agent_card)
        app.get("/health")(self._route_health)
        logger.info(f"Created FastAPI app for {self.name}")
        return app

    async def serve_http(self, host: str = "0.0.0.0", port: int = 8001) -> None:
        """
        Serve via HTTP (requires uvicorn).

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "uvicorn required for HTTP server. "
                "Install with: pip install uvicorn"
            )

        app = self.create_fastapi_app()
        logger.info(f"Starting {self.name} HTTP server on {host}:{port}")

        config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


def create_server(
    handler: AgentHandler,
    name: str = "a2a-agent",
    contract_path: Optional[str] = None,
    agent_url: Optional[str] = None,
    basic_auth_username: Optional[str] = None,
    basic_auth_password: Optional[str] = None,
) -> A2AServer:
    """
    Factory function to create A2A server.

    Args:
        handler: Async function to handle agent methods
        name: Server name
        contract_path: Optional path to agent contract JSON file.
        agent_url: Optional public URL of this agent.
        basic_auth_username: Optional Basic Auth username.
        basic_auth_password: Optional Basic Auth password.

    Returns:
        Configured A2A server
    """
    return A2AServer(
        handler=handler,
        name=name,
        contract_path=contract_path,
        agent_url=agent_url,
        basic_auth_username=basic_auth_username,
        basic_auth_password=basic_auth_password,
    )
