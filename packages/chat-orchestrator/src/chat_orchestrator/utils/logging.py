"""
Logging configuration for Prete-a-porter backend.

Provides structured logging with JSON output, correlation IDs,
and sensitive data filtering.
"""

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Optional

import structlog
from pythonjsonlogger import jsonlogger

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


class SensitiveDataFilter(logging.Filter):
    """Filter sensitive data from log records."""
    
    SENSITIVE_KEYS = {
        "api_key", "apikey", "api-key",
        "password", "passwd", "pwd",
        "secret", "token", "auth",
        "authorization", "session_id",
        "cookie", "private_key", "private-key",
    }
    
    MASKED_VALUE = "***REDACTED***"
    
    def _mask_sensitive_data(self, data: Any) -> Any:
        """Recursively mask sensitive data."""
        if isinstance(data, dict):
            return {
                key: self.MASKED_VALUE if key.lower() in self.SENSITIVE_KEYS else self._mask_sensitive_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            # Check if the string itself is a sensitive key
            if data.lower() in self.SENSITIVE_KEYS:
                return self.MASKED_VALUE
            # Mask patterns like "Authorization: Bearer xxx"
            for key in self.SENSITIVE_KEYS:
                if key.lower() in data.lower():
                    return self.MASKED_VALUE
        return data
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Mask sensitive fields in log record attributes
        if hasattr(record, "msg"):
            record.msg = self._mask_sensitive_data(record.msg)
        if hasattr(record, "args"):
            record.args = self._mask_sensitive_data(record.args)
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["timestamp"] = self.formatTime(record)
        log_record["source"] = f"{record.filename}:{record.lineno}"
        log_record["function"] = record.funcName
        
        # Add correlation ID
        log_record["correlation_id"] = getattr(record, "correlation_id", "")
        
        # Remove redundant fields
        if "levelname" in log_record:
            del log_record["levelname"]
        if "name" in log_record:
            del log_record["name"]


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set a correlation ID. If not provided, generates a new UUID."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """Clear the correlation ID."""
    correlation_id_var.set("")


def configure_logging(log_level: Optional[str] = None, json_format: Optional[bool] = None) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to env var LOG_LEVEL or INFO.
        json_format: Whether to output JSON format. Defaults to env var LOG_JSON_FORMAT or False for dev.
    """
    # Determine log level
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Determine format
    if json_format is None:
        json_format = os.getenv("LOG_JSON_FORMAT", "false").lower() == "true"
    
    # Create formatter
    if json_format:
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s %(correlation_id)s"
        )
    else:
        log_format = "%(asctime)s [%(correlation_id)s] %(levelname)s - %(name)s - %(message)s"
        formatter = logging.Formatter(log_format)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationIdFilter())
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)