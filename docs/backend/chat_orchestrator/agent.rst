===========
Agent Node
===========

The agent node is the main node in the chat orchestrator graph. It handles LLM invocation with tool binding.

.. autofunction:: main.agent_node

Overview
========

The agent_node implementation:

1. Initializes or retrieves the LLM
2. Binds available tools to the LLM
3. Invokes the LLM with the conversation history + system prompt
4. Determines whether tools are needed in the response
5. Returns the updated state

Flow Diagram
============

.. code-block:: text

    agent_node(state)
        |
        +-- Get LLM (Anthropic or Google)
        |
        +-- Bind tools [get_current_date, calculate_date]
        |
        +-- Invoke LLM with:
        |   - System prompt
        |   - Message history
        |
        +-- Parse response
        |   - Extract tool_calls
        |   - Generate AIMessage
        |
        +-- Determine next_action
        |   - "continue" if tool_calls present
        |   - "end" if no tool_calls
        |
        +-- Return {messages, next_action}

LLM Selection
=============

The agent automatically selects the best available LLM:

.. code-block:: python

    # Priority order:
    1. Anthropic Claude 3.5 Sonnet (if ANTHROPIC_API_KEY set)
    2. Google Gemini Flash Lite (if GOOGLE_API_KEY set)
    3. Mock LLM (if TEST_MODE=true)
    4. Raise LLMNotConfiguredException (if none available)

Tool Binding
============

Tools are bound to the LLM using LangChain's mechanism:

.. code-block:: python

    tools = [get_current_date, calculate_date]
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(messages)

The LLM can then decide to call tools and includes tool_calls in the response.

System Prompt
=============

The agent uses a multi-language system prompt:

.. code-block:: text

    "You are a friendly homily assistant. You have access to tools 
    for date/time information.
    
    TOOL USAGE:
    - ALWAYS call get_current_date when users ask about today's date
    - ALWAYS call calculate_date with English query for other dates
    - You can call MULTIPLE tools in a single response
    - When calling calculate_date, translate user's request to English
    
    After receiving tool results, respond naturally in the user's language."

This prompt encourages:
- Tool usage for date queries
- Multi-turn tool invocation
- Language preservation (respond in user's language)

Error Handling
==============

The agent node handles and logs errors:

**Recoverable Errors**:
- LLMRateLimitException: Logged, re-raised (client handles retry)
- LLMTimeoutException: Logged, re-raised
- LLMContentException: Logged, re-raised

**Unrecoverable Errors**:
- LLMNotConfiguredException: Logged, re-raised to trigger error handler
- Other exceptions: Wrapped in AgentGraphException

All errors are logged with:
- session_id
- correlation_id
- error details
- Full stack trace (ERROR level)

Logging
=======

The agent logs key events:

.. code-block:: python

    logger.debug(
        "Agent node executing",
        session_id=state["session_id"],
        message_count=len(state["messages"])
    )
    
    logger.debug(
        "Agent node completed",
        session_id=state["session_id"],
        has_tool_calls=has_tool_calls,
        next_action=next_action
    )

Performance
===========

**Typical Response Times**:

- Tool-free response: 2-8 seconds (LLM latency)
- Tool execution: < 1 second
- Total round-trip: 2-8 seconds

**Optimization**:

- Async LLM invocation (non-blocking)
- Tool binding happens once
- No unnecessary message processing

Type Hints
==========

Full type hints for the agent_node:

.. code-block:: python

    def agent_node(state: ChatState) -> dict:
        """
        Agent node: calls LLM with tools bound.
        
        Args:
            state: ChatState with messages and session_id
            
        Returns:
            dict with updated messages and next_action
            
        Raises:
            AgentGraphException: On LLM initialization/invocation failure
            LLMNotConfiguredException: When no API key configured
        """

Testing
=======

See :doc:`../testing` for agent_node testing strategies:

- Mock LLM responses
- Test tool invocation detection
- Test error handling
- Test message history accumulation

See Also
========

- :doc:`graph` - Graph construction and execution
- :doc:`tools` - Tool definitions and execution
- :doc:`../error_handling` - Error handling patterns
