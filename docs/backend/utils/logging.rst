===============
Logging System
===============

Structured logging configuration and utilities.

.. automodule:: utils.logging
   :members:
   :undoc-members:
   :show-inheritance:

Overview
========

The logging system provides:

- **Structured JSON logging** for production
- **Human-readable logging** for development
- **Correlation ID tracking** across requests
- **Sensitive data filtering** to prevent credential leaks
- **Configurable log levels** (DEBUG, INFO, WARNING, ERROR)

Configuration
=============

Environment Variables::

    # Log level (default: INFO)
    LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
    
    # Output format (default: false for human-readable)
    LOG_JSON_FORMAT=true|false

Example Configurations::

    # Development (human-readable, verbose)
    LOG_LEVEL=DEBUG
    LOG_JSON_FORMAT=false
    
    # Production (JSON, errors only)
    LOG_LEVEL=WARNING
    LOG_JSON_FORMAT=true

Logger Usage
============

Get a logger in any module:

.. code-block:: python

    from src.utils.logging import get_logger
    
    logger = get_logger(__name__)
    
    # Log events
    logger.info("User connected", user_id="user-123")
    logger.debug("Processing message", message_id="msg-456")
    logger.error("Connection failed", error="timeout")

Log Levels
==========

**DEBUG**
  Detailed diagnostic information.
  
  Use for:
  - Function entry/exit
  - State transitions
  - Detailed variable values
  
  Example::
  
      logger.debug("Agent node executing", session_id=session_id)

**INFO**
  Confirmation that things are working.
  
  Use for:
  - Major state changes
  - User actions
  - System events
  
  Example::
  
      logger.info("WebSocket connection established", session_id=session_id)

**WARNING**
  Something unexpected happened, but system continues.
  
  Use for:
  - Recoverable errors
  - Deprecated usage
  - Unusual conditions
  
  Example::
  
      logger.warning("Tool execution slow", tool_name="calculate_date", duration=5.2)

**ERROR**
  A serious problem, system may not function.
  
  Use for:
  - Unhandled exceptions
  - System failures
  - Invalid states
  
  Example::
  
      logger.error("Agent execution failed", error=str(e), exc_info=True)

Structured Fields
=================

Log entries include structured fields (key-value pairs):

.. code-block:: python

    logger.info(
        "Message processed",
        session_id="sess-abc123",
        message_count=5,
        response_time=2.3,
        status="success"
    )

Common Fields::

    - timestamp: ISO 8601 timestamp
    - level: Log level
    - logger: Logger name (module)
    - message: Main log message
    - correlation_id: Request tracing ID
    - session_id: Chat session ID
    - error: Error message (for ERROR logs)
    - exc_info: Stack trace (if exc_info=True)

Correlation IDs
===============

Correlation IDs enable end-to-end request tracing:

**Generation**:

.. code-block:: python

    from src.utils.logging import set_correlation_id
    
    # In middleware or entry point
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    set_correlation_id(correlation_id)

**Retrieval**:

.. code-block:: python

    from src.utils.logging import get_correlation_id
    
    current_id = get_correlation_id()

**Clearing**:

.. code-block:: python

    from src.utils.logging import clear_correlation_id
    
    # At end of request
    clear_correlation_id()

**In Responses**:

The correlation ID is included in:
- Response headers: ``X-Correlation-ID: {uuid}``
- Error JSON: ``error.correlation_id``
- All server logs

This allows:
- Client to reference errors in support requests
- Tracing complete request lifecycle
- Correlating related services (Phase 3+)

Sensitive Data Filtering
========================

Automatically masks sensitive keys:

**Protected Keys**:

- api_key, apikey, api-key
- password, passwd, pwd
- secret, token, auth, authorization
- session_id, cookie, private_key

**Masking**:

.. code-block:: python

    logger.info("Config loaded", api_key="sk-123")
    # Output: ... api_key="***MASKED***"

**Detection**:

- Case-insensitive
- Nested objects supported (dicts, lists)
- String values checked for sensitive patterns

Example::

    Input: {"api_key": "secret", "user": "john"}
    Output: {"api_key": "***MASKED***", "user": "john"}

JSON Output Format
==================

In production (LOG_JSON_FORMAT=true), logs are JSON:

.. code-block:: json

    {
        "timestamp": "2026-02-20T10:30:45.123Z",
        "level": "INFO",
        "logger": "src.main",
        "message": "WebSocket connection established",
        "session_id": "sess-abc123",
        "correlation_id": "trace-xyz789",
        "client_host": "192.168.1.100"
    }

Human-Readable Format
======================

In development (LOG_JSON_FORMAT=false):

.. code-block:: text

    2026-02-20 10:30:45,123 - INFO - src.main - 
    WebSocket connection established [session_id=sess-abc123] 
    [correlation_id=trace-xyz789]

Performance Considerations
===========================

Structured logging has minimal overhead:

- Serialization: < 1ms per log entry
- Filtering: < 0.1ms per entry
- I/O: Async (non-blocking)

Optimization:

- Avoid logging in tight loops
- Use appropriate log levels (less DEBUG in production)
- Filter sensitive fields early

Testing Logging
===============

**Capturing logs in tests**:

.. code-block:: python

    import logging
    
    def test_with_logs(caplog):
        with caplog.at_level(logging.DEBUG):
            function_under_test()
        
        assert "Expected log message" in caplog.text

**Verifying correlation IDs**:

.. code-block:: python

    from src.utils.logging import set_correlation_id, get_correlation_id
    
    def test_correlation_id():
        test_id = "test-123"
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id

**Mocking loggers**:

.. code-block:: python

    from unittest.mock import patch
    
    def test_logs_error(caplog):
        with caplog.at_level(logging.ERROR):
            # Code that should log error
            pass
        
        assert "expected error" in caplog.text

Troubleshooting
===============

**Logs not appearing**

::

    Solutions:
    - Check LOG_LEVEL environment variable
    - Verify logger is retrieved with get_logger()
    - Check log output destination (stdout for FastAPI)

**Sensitive data exposed**

::

    Solutions:
    - Check field names match protected list
    - Verify SensitiveDataFilter is active
    - Add field to protected list if needed

**Correlation ID not in logs**

::

    Solutions:
    - Verify set_correlation_id() called at request entry
    - Check middleware runs before handlers
    - Verify clear_correlation_id() called at request end

**Performance degradation with logging**

::

    Solutions:
    - Reduce LOG_LEVEL in production
    - Avoid logging in tight loops
    - Profile logging code with py-spy

See Also
========

- :doc:`../architecture` - Logging & Tracing section
- :doc:`../error_handling` - Error logging patterns
- :doc:`../testing` - Logging in tests
