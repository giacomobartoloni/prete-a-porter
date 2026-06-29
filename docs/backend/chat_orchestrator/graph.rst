================
Graph Construction
================

The graph module handles LangGraph StateGraph creation and compilation.

.. autofunction:: main.create_graph
.. autofunction:: main.get_graph

Overview
========

The graph is built using LangGraph's StateGraph with three components:

1. **Nodes**: agent_node, tools_node
2. **Edges**: Conditional routing and looping
3. **Checkpointer**: SQLite-based session persistence

Graph Structure
===============

.. code-block:: text

    START
      |
      v
    agent_node
      |
      v
    should_continue(state)
      |
      +-- "tools" --> tools_node
      |                 |
      |                 v
      |             agent_node (loop)
      |
      +-- "end" --> END

Node Definitions
================

**agent_node**
  Main reasoning node; calls LLM with tools.
  
  Inputs: ChatState with messages
  Outputs: Updated messages and next_action

**tools_node**
  Executes tool calls from LLM response.
  
  Inputs: ChatState with AIMessage containing tool_calls
  Outputs: ToolMessages with tool results

Conditional Edges
==================

The graph uses a conditional edge after agent_node:

.. code-block:: python

    def should_continue(state: ChatState) -> Literal["tools", "end"]:
        return "tools" if state["next_action"] == "continue" else "end"
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END}
    )

This allows:
- Flexible tool invocation (not every turn)
- Agent control over iteration
- Natural conversation flow

Loop Back
=========

After tools_node completes, execution returns to agent_node:

.. code-block:: python

    workflow.add_edge("tools", "agent")

This creates a loop for multi-turn tool interaction:

1. Agent decides to use tools
2. Tools execute
3. Agent processes tool results
4. Back to step 1 (if more tools needed)
5. Eventually agent ends conversation

SQLite Checkpointer
===================

The graph uses AsyncSqliteSaver for session persistence:

.. code-block:: python

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    
    checkpointer_context = AsyncSqliteSaver.from_conn_string(db_path)
    checkpointer = await checkpointer_context.__aenter__()
    graph = workflow.compile(checkpointer=checkpointer)

**Configuration**:

- **Database Path**: ``packages/chat-orchestrator/data/chat_orchestrator.db``
- **Thread ID**: ``session_id`` from ChatState
- **Storage**: Complete conversation history and state

**Persistence Guarantees**:

- State saved after each node execution
- State retrieved on graph invocation with same thread_id
- Full message history maintained
- Conversation survives server restarts

Graph Compilation
=================

The graph is compiled with:

.. code-block:: python

    graph = workflow.compile(checkpointer=checkpointer)

This produces a runnable graph with:

- Validated node and edge configuration
- Prepared execution plan
- Checkpointer integration

Graph Invocation
================

WebSocket handler invokes graph like this:

.. code-block:: python

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=data)], "session_id": session_id},
        config={
            "configurable": {"thread_id": session_id},
            "recursion_limit": 15
        }
    )

**Parameters**:

- ``input``: Initial state with user message and session_id
- ``config.configurable.thread_id``: Session identifier for checkpointing
- ``config.recursion_limit``: Max iterations (prevents infinite loops)

**Returns**:

- ``result``: Final state with all messages and metadata

Error Handling
==============

Graph execution is wrapped in try-catch:

.. code-block:: python

    try:
        result = await graph.ainvoke(...)
    except WebSocketDisconnect:
        # Client disconnected
        raise
    except Exception as e:
        # Log error and send to client
        await websocket.send_json({
            "type": "error",
            "error": {
                "code": "MESSAGE_PROCESSING_ERROR",
                "message": "Error message"
            }
        })

Performance
===========

**Graph Execution Metrics**:

- Compilation time: ~ 100ms (one-time)
- Invocation per turn: 2-15 seconds (depends on LLM + tools)
- State serialization: < 100ms

**Optimization**:

- Graph compiled once, reused for all sessions
- Async execution (non-blocking)
- Recursive limit prevents runaway execution

Testing
=======

Graph testing includes:

- Node execution isolation
- Edge routing correctness
- Loop termination
- State mutation
- Checkpointer integration

See :doc:`../testing` for comprehensive testing strategies.

Recursion Limit
===============

The recursion_limit prevents infinite loops:

.. code-block:: python

    config={"recursion_limit": 15}  # Max 15 iterations

Typical conversation:
- 1 agent call (no tools)
- 2 agent calls + 1 tools call (with tools)
- 3+ calls in complex scenarios

Recursion limit of 15 allows:
- Up to 7 tool invocation rounds
- Safety margin for edge cases

Troubleshooting
===============

**Graph won't compile**:
- Check node definitions match StateGraph type
- Verify edge endpoints exist
- Check state type consistency

**Infinite loops**:
- Review agent_node logic (should set next_action)
- Check should_continue function
- Monitor recursion_limit hits in logs

**State not persisting**:
- Verify DATABASE_PATH exists and is writable
- Check SQLite file permissions
- Review AsyncSqliteSaver initialization

See Also
========

- :doc:`overview` - Architecture overview
- :doc:`agent` - Agent node implementation
- :doc:`tools` - Tool definitions
