=======
Testing
=======

Comprehensive testing strategy and infrastructure.

Overview
========

Prete-a-porter follows the "Always Develop Tests" philosophy:

- Tests are written **before or concurrently** with implementation
- Every feature must have corresponding tests
- Minimum 70% code coverage for all new code
- Target 80% overall coverage
- 90% for critical paths (WebSocket, A2A, homily generation)

Testing Pyramid
===============

.. code-block:: text

        /\
       /  \      E2E Tests (Few, critical paths)
      /____\     
     /      \    Integration Tests (Service boundaries)
    /________\   
   /          \  Unit Tests (Many, fast, isolated)
  /____________\

Unit Tests (Many, Fast)
-----------------------

- Fast execution (< 100ms per test)
- Isolated (no external dependencies)
- Deterministic (same input → same output)
- Cover all code paths (happy path + error cases)

**Examples**:

- Tool argument validation
- State transitions
- Error message generation
- Date calculation logic

Integration Tests (Fewer, Slower)
---------------------------------

- Test component interactions
- Use test doubles for external services
- Verify data flow between modules
- Test database operations with test database

**Examples**:

- WebSocket → graph invocation
- Agent → LLM → Tool execution
- Session persistence across reconnections

E2E Tests (Few, Realistic)
--------------------------

- Test complete user workflows
- Run against staging environment
- Cover critical business paths
- Validate end-to-end data integrity

**Examples**:

- User sends message → tool executes → response received
- WebSocket reconnection preserves session
- Multi-turn conversation with tool invocation

Backend Testing
===============

Framework: **pytest**
```
pytest           # Test runner
pytest-asyncio   # Async test support
pytest-cov       # Coverage reporting
pytest-mock      # Mocking utilities
```

Test File Structure
~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    packages/*/tests/
    ├── __init__.py
    ├── conftest.py              # Shared fixtures
    ├── test_tools.py            # Tool function tests
    ├── test_database.py         # Database tests
    └── test_graph.py            # Graph tests

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

    # Run all tests
    pytest
    
    # Run with coverage
    pytest --cov=src --cov-report=html
    
    # Run specific test file
    pytest tests/test_tools.py
    
    # Run specific test
    pytest tests/test_tools.py::test_calculate_date
    
    # Run with verbose output
    pytest -v
    
    # Run with log output
    pytest -s
    
    # Run async tests with timeout
    pytest --timeout=10

Example Unit Test
~~~~~~~~~~~~~~~~~

.. code-block:: python

    from src.main import calculate_date
    from freezegun import freeze_time
    
    @freeze_time("2026-02-20")
    def test_calculate_date_next_sunday():
        """Test date calculation for next Sunday."""
        result = calculate_date("next Sunday")
        assert result == "Sunday, February 23, 2026"
    
    def test_calculate_date_invalid_query():
        """Test handling of invalid date query."""
        result = calculate_date("invalid query xyz")
        assert "Could not parse" in result

Example Integration Test
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import pytest
    from fastapi.testclient import TestClient
    from src.main import app, reset_graph
    
    @pytest.fixture
    def client():
        reset_graph()
        return TestClient(app)
    
    def test_health_endpoint(client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

Test Fixtures
~~~~~~~~~~~~~

**Shared fixtures** in ``conftest.py``:

.. code-block:: python

    import pytest
    from sqlalchemy import create_engine
    
    @pytest.fixture
    def test_db():
        """In-memory SQLite database for testing."""
        engine = create_engine("sqlite:///:memory:")
        # Create schema
        yield engine
    
    @pytest.fixture
    def mock_llm():
        """Mock LLM for testing without API calls."""
        from unittest.mock import AsyncMock
        llm = AsyncMock()
        # Configure mock responses
        yield llm

Frontend Testing
================

Framework: **Jest + React Testing Library**

```
jest                    # Test runner
@testing-library/react  # Component testing
cypress                 # E2E testing
```

Component Testing
~~~~~~~~~~~~~~~~~

.. code-block:: typescript

    import { render, screen } from '@testing-library/react'
    import Chat from '@/components/Chat'
    
    describe('Chat Component', () => {
      it('renders input field', () => {
        render(<Chat />)
        const input = screen.getByPlaceholderText(/send a message/i)
        expect(input).toBeInTheDocument()
      })
      
      it('sends message on button click', async () => {
        const { user } = render(<Chat />)
        const input = screen.getByRole('textbox')
        const button = screen.getByRole('button', { name: /send/i })
        
        await user.type(input, 'Hello')
        await user.click(button)
        
        expect(input).toHaveValue('')
      })
    })

E2E Testing
~~~~~~~~~~~

.. code-block:: typescript

    // cypress/e2e/chat-flow.cy.ts
    
    describe('Chat Flow', () => {
      beforeEach(() => {
        cy.visit('http://localhost:3000')
      })
      
      it('completes a full chat flow', () => {
        cy.get('[data-testid=message-input]').type('What time is it?')
        cy.get('[data-testid=send-button]').click()
        
        cy.get('[data-testid=message]').should('be.visible')
        cy.get('[data-testid=message]').should('contain', 'February')
      })
    })

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

    # Run all tests
    npm test
    
    # Run with coverage
    npm test -- --coverage
    
    # Run E2E tests
    npm run cypress:open
    
    # Run specific test file
    npm test Chat.test.tsx

Test Coverage Goals
===================

**Coverage Standards**:

- **Minimum**: 70% for all new code
- **Target**: 80% overall
- **Critical Paths**: 90% (WebSocket, A2A, homily generation)

**By Phase**:

- Phase 1.1: SQLite operations (75%+)
- Phase 1.2: Logging (80%+)
- Phase 1.3: Error handling (90%+)
- Phase 1.4: Chat Orchestrator (80%+)
- Phase 2: Liturgy Agent (75%+)
- Phase 3: A2A Protocol (85%+)
- Phase 4: Homily Agent (75%+)
- Phase 5: Frontend (70%+)

Coverage Reports
~~~~~~~~~~~~~~~~

After running tests with coverage:

.. code-block:: bash

    # Backend
    pytest --cov=src --cov-report=html
    open htmlcov/index.html
    
    # Frontend
    npm test -- --coverage
    # Coverage report in `coverage/` directory

Continuous Integration (CI)
============================

GitHub Actions Workflow (Pull Request)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    # .github/workflows/tests.yml
    name: Tests
    on:
      pull_request:
        branches: [main, develop]
    
    jobs:
      backend-tests:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v3
          - uses: actions/setup-python@v4
            with:
              python-version: '3.12'
          - run: |
              pip install -r packages/chat-orchestrator/requirements.txt
              pytest packages/chat-orchestrator/tests/ --cov=packages/chat-orchestrator.src
          - uses: codecov/codecov-action@v3
      
      frontend-tests:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v3
          - uses: actions/setup-node@v3
            with:
              node-version: '18'
          - run: |
              cd frontend
              npm install
              npm test -- --coverage
          - uses: codecov/codecov-action@v3

Coverage Gate
^^^^^^^^^^^^^

Tests fail if coverage drops below threshold:

.. code-block:: bash

    # Enforced in CI
    pytest --cov=src --cov-fail-under=70

Mocking & Test Doubles
======================

**LLM Mocking**:

.. code-block:: python

    from unittest.mock import AsyncMock
    
    @pytest.fixture
    def mock_llm():
        llm = AsyncMock()
        llm.invoke.return_value = MagicMock(
            content="Test response",
            tool_calls=[]
        )
        return llm

**WebSocket Mocking**:

.. code-block:: python

    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    with client.websocket_connect("/ws/chat/test-session") as ws:
        ws.send_text("Hello")
        data = ws.receive_text()
        assert "response" in data

**Database Mocking**:

.. code-block:: python

    @pytest.fixture
    def in_memory_db():
        engine = create_engine("sqlite:///:memory:")
        # Create schema
        return engine

Performance Testing
===================

Load Testing (using `locust`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # locustfile.py
    from locust import HttpUser, task, between
    
    class ChatUser(HttpUser):
        wait_time = between(1, 5)
        
        @task
        def send_message(self):
            session_id = "test-session"
            self.client.post(f"/ws/chat/{session_id}")

**Run load test**:

.. code-block:: bash

    locust -f locustfile.py --host=http://localhost:8000

Stress Testing
~~~~~~~~~~~~~~

- 100+ concurrent WebSocket connections
- Sustained load for 30 minutes
- Monitor response times and error rates
- Target: p95 latency < 15 seconds

Debugging Tests
===============

**Print debug output**:

.. code-block:: bash

    pytest -s  # Show print statements
    pytest -v  # Verbose output

**Use pdb debugger**:

.. code-block:: python

    import pdb; pdb.set_trace()
    # or pytest.set_trace()

**Increase timeout**:

.. code-block:: bash

    pytest --timeout=60

**Run single test**:

.. code-block:: bash

    pytest path/to/test.py::test_name -v

Best Practices
==============

1. **Test Names**: Clear and descriptive
   
   .. code-block:: python

       # Good
       def test_calculate_date_next_sunday_returns_correct_date():
       
       # Bad
       def test_date():

2. **AAA Pattern**: Arrange, Act, Assert
   
   .. code-block:: python

       def test_example():
           # Arrange
           input_data = prepare_data()
           
           # Act
           result = function_under_test(input_data)
           
           # Assert
           assert result == expected_value

3. **One Assertion Per Test**: Focus on single behavior
   
   .. code-block:: python

       # Good: Focused test
       def test_error_has_correct_code():
           error = DateValidationException("invalid")
           assert error.code == "DATE_INVALID"
       
       # Bad: Multiple assertions
       def test_error():
           error = DateValidationException("invalid")
           assert error.code == "DATE_INVALID"
           assert error.message != ""
           assert error.status_code == 400

4. **Test Independence**: No test relies on another test

5. **Mock External Dependencies**: Don't call real APIs/databases

6. **Test Error Cases**: Not just happy paths

See Also
========

- :doc:`architecture` - System design
- :doc:`backend/index` - Backend modules (see also `AGENTS.md <../AGENTS.md>`_ for agent architecture)
- :doc:`frontend/index` - Frontend components
- :doc:`deployment` - Deployment testing
