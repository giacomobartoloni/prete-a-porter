"""
Custom exception classes for Prete-a-porter backend.

Provides a hierarchy of exceptions for different error scenarios
with support for user-friendly messages in Italian.
"""

from typing import Any, Dict, Optional


class PreteAPorterException(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.user_message_it = user_message_it or "Si è verificato un errore imprevisto. Riprova più tardi."
        self.error_code = error_code or "GENERIC_ERROR"
        self.details = details or {}


# LLM / AI Exceptions
class LLMException(PreteAPorterException):
    """Base exception for LLM-related errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Il servizio di intelligenza artificiale non è disponibile al momento.",
            error_code=error_code or "LLM_ERROR",
            details=details
        )


class LLMNotConfiguredException(LLMException):
    """Raised when no LLM API key is configured."""
    
    def __init__(self, message: str = "No LLM API key configured"):
        super().__init__(
            message=message,
            user_message_it="Il servizio non è configurato correttamente. Contatta l'amministratore.",
            error_code="LLM_NOT_CONFIGURED"
        )


class LLMRateLimitException(LLMException):
    """Raised when LLM API rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "LLM rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            user_message_it="Troppe richieste. Attendi qualche istante e riprova.",
            error_code="LLM_RATE_LIMIT",
            details={"retry_after": retry_after}
        )


class LLMTimeoutException(LLMException):
    """Raised when LLM request times out."""
    
    def __init__(self, message: str = "LLM request timed out"):
        super().__init__(
            message=message,
            user_message_it="La risposta sta prendendo più tempo del previsto. Riprova.",
            error_code="LLM_TIMEOUT"
        )


class LLMContentException(LLMException):
    """Raised when LLM generates inappropriate content."""
    
    def __init__(self, message: str = "LLM generated inappropriate content"):
        super().__init__(
            message=message,
            user_message_it="Non sono riuscito a generare una risposta appropriata. Riprova con una domanda diversa.",
            error_code="LLM_CONTENT_ERROR"
        )


# Database Exceptions
class DatabaseException(PreteAPorterException):
    """Base exception for database-related errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Errore nel salvataggio dei dati. Riprova più tardi.",
            error_code=error_code or "DB_ERROR",
            details=details
        )


class DatabaseConnectionException(DatabaseException):
    """Raised when database connection fails."""
    
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(
            message=message,
            user_message_it="Impossibile connettersi al database. Riprova più tardi.",
            error_code="DB_CONNECTION_ERROR"
        )


class DatabaseQueryException(DatabaseException):
    """Raised when database query fails."""
    
    def __init__(self, message: str, query: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Errore nel recupero dei dati. Riprova più tardi.",
            error_code="DB_QUERY_ERROR",
            details={"query": query} if query else {}
        )


# WebSocket Exceptions
class WebSocketException(PreteAPorterException):
    """Base exception for WebSocket-related errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Errore di connessione. Riprova più tardi.",
            error_code=error_code or "WS_ERROR",
            details=details
        )


class WebSocketConnectionException(WebSocketException):
    """Raised when WebSocket connection fails."""
    
    def __init__(self, message: str = "WebSocket connection failed", session_id: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Connessione interrotta. Riconnettiti e riprova.",
            error_code="WS_CONNECTION_ERROR",
            details={"session_id": session_id} if session_id else {}
        )


class WebSocketMessageException(WebSocketException):
    """Raised when WebSocket message handling fails."""
    
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        message_type: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message_it="Errore nella comunicazione. Riprova.",
            error_code="WS_MESSAGE_ERROR",
            details={
                "session_id": session_id,
                "message_type": message_type
            }
        )


# Validation Exceptions
class ValidationException(PreteAPorterException):
    """Base exception for validation errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        field: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "I dati inseriti non sono validi.",
            error_code=error_code or "VALIDATION_ERROR",
            details={"field": field} if field else {}
        )


class DateValidationException(ValidationException):
    """Raised when date validation fails."""
    
    def __init__(self, message: str, date_value: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it=f"La data '{date_value}' non è valida." if date_value else "La data inserita non è valida.",
            error_code="INVALID_DATE",
            field="date"
        )


class SessionValidationException(ValidationException):
    """Raised when session validation fails."""
    
    def __init__(self, message: str, session_id: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Sessione non valida o scaduta. Ricarica la pagina.",
            error_code="INVALID_SESSION",
            field="session_id"
        )


# Tool Exceptions
class ToolException(PreteAPorterException):
    """Base exception for tool execution errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        tool_name: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Errore nell'esecuzione dell'operazione richiesta.",
            error_code=error_code or "TOOL_ERROR",
            details={"tool_name": tool_name} if tool_name else {}
        )


class ToolNotFoundException(ToolException):
    """Raised when requested tool is not found."""
    
    def __init__(self, tool_name: str):
        super().__init__(
            message=f"Tool '{tool_name}' not found",
            user_message_it="L'operazione richiesta non è disponibile.",
            error_code="TOOL_NOT_FOUND",
            tool_name=tool_name
        )


class ToolExecutionException(ToolException):
    """Raised when tool execution fails."""
    
    def __init__(self, message: str, tool_name: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Errore nell'esecuzione dell'operazione. Riprova.",
            error_code="TOOL_EXECUTION_ERROR",
            tool_name=tool_name
        )


# Agent Exceptions
class AgentException(PreteAPorterException):
    """Base exception for agent-related errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        agent_name: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Errore nel processamento della richiesta.",
            error_code=error_code or "AGENT_ERROR",
            details={"agent_name": agent_name} if agent_name else {}
        )


class AgentGraphException(AgentException):
    """Raised when agent graph execution fails."""
    
    def __init__(self, message: str, agent_name: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Errore nel processamento della richiesta. Riprova.",
            error_code="AGENT_GRAPH_ERROR",
            agent_name=agent_name
        )


class AgentTimeoutException(AgentException):
    """Raised when agent execution times out."""
    
    def __init__(self, message: str = "Agent execution timed out"):
        super().__init__(
            message=message,
            user_message_it="La richiesta sta prendendo troppo tempo. Riprova con una domanda più semplice.",
            error_code="AGENT_TIMEOUT"
        )


# A2A Protocol Exceptions
class A2AException(PreteAPorterException):
    """Base exception for A2A protocol errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        agent_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Errore nella comunicazione tra servizi.",
            error_code=error_code or "A2A_ERROR",
            details={"agent_id": agent_id} if agent_id else {}
        )


class A2ACommunicationException(A2AException):
    """Raised when A2A communication fails."""
    
    def __init__(self, message: str, from_agent: Optional[str] = None, to_agent: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Errore nella comunicazione con altri servizi. Riprova più tardi.",
            error_code="A2A_COMMUNICATION_ERROR",
            agent_id=to_agent
        )
        self.from_agent = from_agent
        self.to_agent = to_agent


class A2ATimeoutException(A2AException):
    """Raised when A2A request times out."""
    
    def __init__(self, message: str, agent_id: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Timeout nella comunicazione con altri servizi. Riprova più tardi.",
            error_code="A2A_TIMEOUT",
            agent_id=agent_id
        )


# External Service Exceptions
class ExternalServiceException(PreteAPorterException):
    """Base exception for external service errors."""
    
    def __init__(
        self,
        message: str,
        user_message_it: Optional[str] = None,
        error_code: Optional[str] = None,
        service_name: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message_it=user_message_it or "Errore nel collegamento con servizi esterni.",
            error_code=error_code or "EXTERNAL_SERVICE_ERROR",
            details={"service_name": service_name} if service_name else {}
        )


class ScrapingException(ExternalServiceException):
    """Raised when web scraping fails."""
    
    def __init__(self, message: str, url: Optional[str] = None):
        super().__init__(
            message=message,
            user_message_it="Errore nel recupero dei dati liturgici. Riprova più tardi.",
            error_code="SCRAPING_ERROR",
            service_name="liturgical_data_source"
        )
        self.url = url