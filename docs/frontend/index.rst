========
Frontend
========

React/TypeScript frontend for Prete-a-porter.

Overview
========

The frontend provides:

- WebSocket-based chat interface
- Real-time message streaming
- Session management
- Connection status tracking
- Message history

**Location**: ``frontend/src/``

Technology Stack
================

- **React 18** (via Next.js 14)
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **WebSocket API** for real-time communication

Project Structure
=================

.. code-block:: text

    frontend/
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx      # Root layout
    │   │   ├── page.tsx        # Home page
    │   │   └── globals.css     # Global styles
    │   ├── components/
    │   │   └── Chat.tsx        # Main chat component
    │   └── hooks/              # Custom hooks (Phase 5+)
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── next.config.js
    └── .gitignore

Chat Component
==============

**File**: ``src/components/Chat.tsx``

The main chat interface component.

**Features**:

- WebSocket connection management
- Message sending and receiving
- Auto-scroll to latest message
- Connection status indicator
- Error display

**Props**:

- None (uses session ID from browser storage)

**State**:

- ``messages``: Array of chat messages
- ``input``: Current input text
- ``connected``: Connection status
- ``sessionId``: User session ID
- ``isLoading``: Message sending state

**Usage**:

.. code-block:: tsx

    import Chat from '@/components/Chat'
    
    export default function Home() {
        return <Chat />
    }

WebSocket Protocol
==================

**Connection**:

.. code-block:: typescript

    const sessionId = generateSessionId()
    const ws = new WebSocket(`ws://localhost:8000/ws/chat/${sessionId}`)

**Send Message**:

.. code-block:: typescript

    ws.send(messageText)

**Receive Message**:

.. code-block:: typescript

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        // Handle message or error
    }

**Message Format** (Server → Client):

::

    {
        "type": "message",
        "content": "Response text",
        "session_id": "sess-abc123"
    }

**Error Format**:

::

    {
        "type": "error",
        "error": {
            "code": "ERROR_CODE",
            "message": "Error message in Italian",
            "correlation_id": "trace-xyz789"
        }
    }

Session Management
==================

Session ID is stored in browser localStorage:

.. code-block:: typescript

    const SESSION_STORAGE_KEY = 'prete_session_id'
    
    function getSessionId(): string {
        let sessionId = localStorage.getItem(SESSION_STORAGE_KEY)
        if (!sessionId) {
            sessionId = `sess-${generateUUID()}`
            localStorage.setItem(SESSION_STORAGE_KEY, sessionId)
        }
        return sessionId
    }

Benefits:

- Session persists across browser refreshes
- Server can retrieve message history
- Multiple tabs use same session
- Can be cleared by user

Styling
=======

Tailwind CSS for responsive design:

- Mobile-first approach
- Dark mode support (Phase 5+)
- Accessible color contrast
- Smooth animations

Example component styles::

    <div className="flex flex-col h-screen bg-white">
        <div className="flex-1 overflow-y-auto p-4">
            {/* Messages */}
        </div>
        <div className="border-t p-4">
            {/* Input */}
        </div>
    </div>

Building
========

**Development**:

.. code-block:: bash

    cd frontend
    npm install
    npm run dev
    # Open http://localhost:3000

**Production**:

.. code-block:: bash

    npm run build
    npm start
    # Or with Docker

**Environment**:

::

    # .env.local
    NEXT_PUBLIC_API_URL=http://localhost:8000

Type Safety
===========

Full TypeScript support:

.. code-block:: typescript

    interface ChatMessage {
        type: 'message' | 'error'
        content?: string
        error?: {
            code: string
            message: string
            correlation_id: string
        }
    }

Testing
=======

See :doc:`../testing` for frontend testing strategies:

- Component testing with React Testing Library
- E2E testing with Cypress
- Accessibility testing
- Cross-browser testing

Future Enhancements (Phase 5+)
==============================

**Rich Components**:

- LiturgicalCard component (readings display)
- PreferencePicker component (user preferences)
- HomilyDisplay component (formatted homily output)

**Localization**:

- Italian translations (next-intl)
- Language detection
- UI text localization

**Advanced Features**:

- Message streaming
- Loading indicators
- Syntax highlighting for readings
- Export to PDF

Configuration
=============

Next.js configuration in ``next.config.js``:

- Environment variables
- Build optimization
- Deployment settings

See Also
========

- :doc:`../architecture` - Frontend role in architecture
- :doc:`../deployment` - Deployment instructions
- :doc:`../testing` - Frontend testing
