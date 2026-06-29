====================
Troubleshooting
====================

Common issues and solutions.

WebSocket Errors
================

Connection Refused
-------------------

**Error**:

::

    WebSocket connection failed: Connection refused

**Causes**:

1. Backend not running
2. Backend listening on wrong port
3. Firewall blocking port 8000

**Solutions**:

.. code-block:: bash

    # Start backend
    cd backend
    uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
    
    # Check if port is open
    lsof -i :8000
    
    # If needed, allow firewall
    sudo ufw allow 8000

Connection Closed Unexpectedly
-------------------------------

**Error**:

::

    WebSocket connection was closed

**Causes**:

1. Server restarted
2. Network timeout
3. Unhandled server exception

**Solutions**:

1. Check server logs for errors
2. Implement client-side reconnection retry
3. Increase WebSocket timeout settings

Message Processing Errors
==========================

Tool Not Found
---------------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "TOOL_NOT_FOUND",
            "message": "Tool 'tool_name' not found"
        }
    }

**Causes**:

1. Tool not registered in TOOLS_REGISTRY
2. Tool name mismatch in agent invocation

**Solutions**:

1. Verify tool is in TOOLS_REGISTRY
2. Check spelling matches exactly (case-sensitive)
3. Verify tool is bound in agent_node

Tool Execution Failed
---------------------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "TOOL_EXECUTION_ERROR",
            "message": "Failed to execute tool_name: {error}"
        }
    }

**Causes**:

1. Tool implementation bug
2. Invalid tool arguments
3. Tool dependency failure

**Solutions**:

1. Check server error logs (correlation_id in error)
2. Review tool implementation for bugs
3. Verify tool arguments match schema
4. Add debug logging to tool

Agent Execution Failed
----------------------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "AGENT_EXECUTION_ERROR",
            "message": "Agent execution failed: {error}"
        }
    }

**Causes**:

1. LLM API failure
2. Graph malformation
3. State inconsistency

**Solutions**:

.. code-block:: bash

    # Check logs with correlation_id
    grep "correlation_id" backend.log
    
    # Check LLM API status
    # For Anthropic: https://status.anthropic.com/
    # For Google: https://status.cloud.google.com/

LLM Errors
==========

LLM Not Configured
-------------------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "LLM_NOT_CONFIGURED",
            "message": "No LLM is configured"
        }
    }

**Causes**:

No API key set in environment

**Solutions**:

.. code-block:: bash

    # Set API key in .env.local or environment
    export ANTHROPIC_API_KEY="sk-..."
    # or
    export GOOGLE_API_KEY="..."
    
    # Restart backend
    uv run uvicorn src.main:app --reload

LLM Rate Limit Exceeded
------------------------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "LLM_RATE_LIMIT",
            "message": "Rate limit exceeded. Please retry after {seconds}"
        }
    }

**Causes**:

1. Too many requests to LLM API
2. API quota exhausted
3. Concurrent request spike

**Solutions**:

1. Implement client-side request throttling
2. Wait specified seconds before retrying
3. Check API usage dashboard
4. Upgrade API plan if quota too low

LLM Timeout
-----------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "LLM_TIMEOUT",
            "message": "LLM request timed out"
        }
    }

**Causes**:

1. LLM response slow
2. Network latency
3. Complex query takes long

**Solutions**:

1. Retry request (may be temporary)
2. Simplify query/prompt
3. Check network latency: `ping api.anthropic.com`

Database Errors
===============

Database Connection Failed
---------------------------

**Error**:

::

    {
        "type": "error",
        "error": {
            "code": "DATABASE_CONNECTION_ERROR",
            "message": "Cannot connect to database"
        }
    }

**Causes**:

1. SQLite file not accessible
2. File permissions issue
3. Disk full

**Solutions**:

.. code-block:: bash

    # Check database file exists
    ls -la packages/*/data/
    
    # Create if missing
    python -c "from pathlib import Path; Path('packages/chat-orchestrator/data').mkdir(parents=True, exist_ok=True)"
    
    # Check permissions (should be readable/writable)
    chmod 644 packages/chat-orchestrator/data/chat_orchestrator.db
    
    # Check disk space
    df -h

Session Not Found
------------------

**Error**:

::

    Session 'sess-xyz' not found in database

**Causes**:

1. Session expired
2. Database cleared
3. Session ID typo

**Solutions**:

1. Browser should auto-generate new session ID
2. Clear browser storage and reconnect
3. Check session ID in request logs

Logging Issues
==============

Logs Not Appearing
-------------------

**Causes**:

1. LOG_LEVEL too high
2. Log capture not configured
3. Async logs not flushed

**Solutions**:

.. code-block:: bash

    # Set LOG_LEVEL to DEBUG
    export LOG_LEVEL=DEBUG
    
    # Run with direct output
    uv run uvicorn src.main:app --log-level debug
    
    # Check output (should be on stdout)

JSON Logs Not Formatted
------------------------

**Causes**:

LOG_JSON_FORMAT environment variable not set

**Solutions**:

.. code-block:: bash

    # Enable JSON logging
    export LOG_JSON_FORMAT=true
    
    # Restart backend

Sensitive Data in Logs
-----------------------

**Issue**: API keys or passwords appearing in logs

**Solutions**:

1. Verify SensitiveDataFilter is active
2. Add field name to protected list in logging.py
3. Check log configuration: LOG_JSON_FORMAT=true

Performance Issues
==================

Slow Response Time
-------------------

**Symptoms**: Requests take > 15 seconds

**Diagnosis**:

1. Check logs for timing info
2. Profile LLM response time
3. Monitor HTTP network latency

.. code-block:: bash

    # Check service latency
    curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

**Solutions**:

1. If LLM slow: Use faster model or check API status
2. If tool slow: Optimize tool implementation
3. If DB slow: Check SQLite query performance

High Memory Usage
------------------

**Symptoms**: Process grows to gigabytes

**Causes**:

1. Memory leak in agent loop
2. Large message history in state
3. Unbounded cache growth

**Solutions**:

.. code-block:: bash

    # Monitor memory usage
    watch -n 1 'ps aux | grep uvicorn'
    
    # Profile with memory_profiler
    mprof run -n 1000 -m chat_orchestrator.main

1. Implement message history limit
2. Clear old sessions periodically
3. Monitor with profiler

Docker Issues
=============

Container Won't Start
-----------------------

**Error**:

::

    docker: Error response from daemon

**Solutions**:

.. code-block:: bash

    # Check logs
    docker logs container-name
    
    # Inspect image
    docker inspect image-name
    
    # Rebuild image
    docker build -t prete-backend:latest .

Port Already in Use
--------------------

**Error**:

::

    Bind for 0.0.0.0:8000 failed

**Solutions**:

.. code-block:: bash

    # Find process using port
    lsof -i :8000
    
    # Kill process
    kill -9 <PID>
    
    # Or use different port
    docker run -p 8001:8000 prete-backend

Network Issues
==============

Frontend Can't Reach Backend
------------------------------

**Causes**:

1. Firewall blocking
2. CORS not configured
3. Backend not running
4. Wrong URL

**Solutions**:

1. Check backend is running: `curl http://localhost:8000/health`
2. Check frontend connects to correct URL (check browser console)
3. Verify CORS origins in main.py
4. Check firewall: `sudo ufw status`

Getting Help
============

When Reporting Issues, Include
-------------------------------

1. **Error message**: Full error text and code
2. **Correlation ID**: From error response
3. **Steps to reproduce**: Exact sequence that fails
4. **Environment**: 
   - OS and Python/Node version
   - Backend/frontend log excerpts
   - Environment variables (without secrets)
5. **Timeline**: When did issue start?

Example Bug Report
~~~~~~~~~~~~~~~~~~~

::

    Title: WebSocket connection closes after 30 seconds
    
    Steps:
    1. Start backend (main branch, latest)
    2. Open frontend in browser
    3. Wait 30 seconds
    4. Observe connection closes
    
    Expected: Connection should remain open indefinitely
    Actual: Connection closes with no error message
    
    Environment:
    - Python 3.12.1
    - Node.js 18.17
    - macOS 13.5
    - ANTHROPIC_API_KEY set
    
    Server logs (correlation ID: trace-abc123):
    [Error log excerpt]
    
    Browser console logs:
    [Error excerpt]

Resources
=========

- **Backend Logs**: Check ``backend.log`` or stdout
- **Frontend Console**: Browser DevTools → Console tab
- **API Status**: 
  - Anthropic: https://status.anthropic.com/
  - Google: https://status.cloud.google.com/
- **Documentation**: :doc:`index`
- **Source Code**: `GitHub repository <https://github.com/...>`_
