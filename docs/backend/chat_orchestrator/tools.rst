======
Tools
======

Tool definitions and execution for the chat orchestrator.

Tool Registry
=============

Tools are registered in the TOOLS_REGISTRY dictionary:

.. code-block:: python

    TOOLS_REGISTRY = {
        "get_current_date": get_current_date,
        "calculate_date": calculate_date,
    }

Available Tools
===============

get_current_date
----------------

.. autofunction:: main.get_current_date

Returns the current date and time in human-readable format.

**Example**:

::

    Input: None
    Output: "Wednesday, February 20, 2026 at 10:30 AM"

**Use Cases**:

- User asks: "What time is it?"
- User asks: "Che ora è?"
- Establish current date for relative date calculations

calculate_date
--------------

.. autofunction:: main.calculate_date

Calculate dates based on natural language queries.

**Supported Queries** (English or Italian):

- Day names: "next Sunday", "prossima domenica"
- Relative: "tomorrow", "domani", "yesterday", "ieri"
- Intervals: "in 3 days", "tra 5 giorni"
- Weekly: "next week", "prossima settimana"

**Examples**:

::

    Input: "next Sunday"
    Output: "Sunday, February 23, 2026"
    
    Input: "in 3 days"
    Output: "Saturday, February 23, 2026"
    
    Input: "domani"
    Output: "Thursday, February 21, 2026"

**Implementation Details**:

- Maps Italian and English day names
- Calculates days ahead for coming weekdays
- Supports relative date arithmetic
- Case-insensitive parsing

Tool Execution in tools_node
============================

The tools_node executes tools from LLM responses:

.. autofunction:: main.tools_node

**Process**:

1. Extract tool_calls from last AIMessage
2. For each tool_call:
   a. Get function from TOOLS_REGISTRY
   b. Invoke with provided arguments
   c. Wrap result in ToolMessage
3. Return all ToolMessages

**Error Handling**:

- Unknown tool → ToolNotFoundException
- Execution failure → ToolExecutionException
- Both logged with context (session_id, tool_name)

Tool Binding to LLM
===================

Tools are bound to LLM in agent_node:

.. code-block:: python

    tools = [get_current_date, calculate_date]
    llm_with_tools = llm.bind_tools(tools)

This allows LLM to invoke tools by name.

**Tool Schema** (from LangChain @tool decorator):

::

    {
        "name": "get_current_date",
        "description": "Get the current date and time in a human-readable format.",
        "parameters": {}
    }
    
    {
        "name": "calculate_date",
        "description": "Calculate dates based on natural language queries...",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    }

Extending Tools (Phase 2+)
==========================

To add new tools:

1. **Define function** with @tool decorator:

   .. code-block:: python

       from langchain_core.tools import tool

       @tool
       def new_tool(param: str) -> str:
           """Tool description for LLM."""
           return result

2. **Register in TOOLS_REGISTRY**:

   .. code-block:: python

       TOOLS_REGISTRY["new_tool"] = new_tool

3. **Add to tools list** in agent_node:

   .. code-block:: python

       tools = [get_current_date, calculate_date, new_tool]

4. **Handle in tools_node** (already generic, works automatically)

Future Tools
============

**Phase 2**: Liturgical Data Tool

::

    @tool
    def get_liturgical_readings(date: str, occasion: str) -> dict:
        """Get liturgical readings for a specific date and occasion."""
        # Calls Liturgy Agent via A2A protocol

**Phase 4**: Homily Generation Tool

::

    @tool
    def generate_homily(occasion: str, readings: dict, preferences: dict) -> str:
        """Generate a homily for the given occasion."""
        # Calls Homily Agent via A2A protocol

Testing
=======

Tool testing includes:

- **Unit Tests**: Each tool with various inputs
- **Integration Tests**: Tools in conversation flow
- **Error Tests**: Invalid inputs and failures
- **Performance Tests**: Response time targets

Example test:

.. code-block:: python

    def test_calculate_date_next_sunday():
        # Set current date to Wednesday
        with freeze_time("2026-02-20"):
            result = calculate_date("next Sunday")
            assert result == "Sunday, February 23, 2026"

See :doc:`../testing` for comprehensive testing strategies.

Type Hints
==========

All tools are fully type-hinted:

.. code-block:: python

    @tool
    def get_current_date(**kwargs: object) -> str:
        """Get the current date and time."""
        ...

    @tool
    def calculate_date(query: str) -> str:
        """Calculate dates from natural language."""
        ...

Performance Targets
===================

**Tool Execution Time**:

- get_current_date: < 1ms
- calculate_date: < 10ms
- A2A tools (Phase 2+): < 1 second

**Validation**:

- Unit tests verify timing
- Load tests with concurrent tool calls

Troubleshooting
===============

**Tool not found**

::

    ToolNotFoundException: Unknown tool: tool_name

Solutions:
- Check tool is in TOOLS_REGISTRY
- Check spelling matches exactly
- Verify tool is bound in agent_node

**Tool execution failed**

::

    ToolExecutionException: Failed to execute {tool_name}: {error}

Solutions:
- Check tool arguments match schema
- Review tool implementation for bugs
- Check error logs for details

**Tool returns unexpected result**

::

    Solutions:
    - Add logging to tool implementation
    - Check tool implementation logic
    - Verify input validation

See Also
========

- :doc:`overview` - Architecture overview
- :doc:`agent` - Agent node (tool binding)
- :doc:`../error_handling` - Error handling patterns
