===========
Deployment
===========

Deployment guides for different environments.

Development Environment
=======================

Local Monolithic Setup
----------------------

**Prerequisites**:

- Python 3.12+
- Node.js 18+
- SQLite (included with Python)

**Backend Setup**:

.. code-block:: bash

    cd backend
    cp .env.example .env.local
    # Edit .env.local with API keys
    
    # Install dependencies
    uv pip install -r requirements.txt
    
    # Initialize database (if needed)
    python scripts/init_db.py
    
    # Start backend
    uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

**Frontend Setup**:

.. code-block:: bash

    cd frontend
    npm install
    npm run dev
    # Open http://localhost:3000

**Agents** (Phase 2+):

Agents run as subprocesses in same Python process (stdio transport):

.. code-block:: bash

    # Backend automatically spawns agents as needed
    # No manual startup required

Docker Compose (Development)
-----------------------------

Local multi-container setup with Docker:

.. code-block:: bash

    docker-compose up -d
    # Frontend: http://localhost:3000
    # Backend: http://localhost:8000
    # Health check: http://localhost:8000/health

**Configuration** (``docker-compose.yml``):

- Frontend container (Next.js)
- Backend container (FastAPI)
- SQLite volume for persistence

Benefits over local setup:

- Consistent environment across computers
- Closer to production architecture
- Easy cleanup (docker-compose down)

Staging Environment
===================

Multi-container with HTTP/SSE A2A Transport
---------------------------------------------

**Architecture**:

.. code-block:: text

    Frontend -> Docker Network -> Chat Orchestrator
                                    |
                                    +-> Liturgy Agent
                                    +-> Homily Agent

**Deployment**:

.. code-block:: bash

    docker-compose -f docker-compose.staging.yml up -d

**Environment Variables** (``docker-compose.staging.yml``):

.. code-block:: yaml

    services:
      chat-orchestrator:
        environment:
          - A2A_TRANSPORT=http
          - LITURGY_AGENT_URL=http://liturgy-agent:8001
          - HOMILY_AGENT_URL=http://homily-agent:8002
          - LOG_LEVEL=INFO
          - LOG_JSON_FORMAT=true
      
      liturgy-agent:
        environment:
          - A2A_TRANSPORT=http
          - A2A_PORT=8001
      
      homily-agent:
        environment:
          - A2A_TRANSPORT=http
          - A2A_PORT=8002

Production Environment (Phase 7)
================================

Kubernetes or Managed Platform
-------------------------------

**Prerequisites**:

- Kubernetes cluster (EKS, GKE, etc.) OR
- Managed platform account (Railway, Render, Fly.io)

**Services** (each independent):

1. **Frontend** (Next.js)
   - CPU: 0.5
   - Memory: 512Mi
   - Replicas: 2+

2. **Chat Orchestrator** (FastAPI)
   - CPU: 1.0
   - Memory: 1Gi
   - Replicas: 2+

3. **Liturgy Agent** (FastAPI)
   - CPU: 0.5
   - Memory: 512Mi
   - Replicas: 1-3 (scale based on load)

4. **Homily Agent** (FastAPI + LLM)
   - CPU: 2.0
   - Memory: 2Gi
   - Replicas: 1-3 (GPU accelerated optional)

5. **Vector Database** (Chroma or Pinecone)
   - Managed service (recommend Pinecone)

6. **PostgreSQL** (if scaling beyond SQLite)
   - Managed RDS service
   - 10GB+ storage
   - Daily backups

Kubernetes Deployment Example
=============================

**K8s Manifests** (``k8s/`` directory):

.. code-block:: yaml

    # k8s/deployment.yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: chat-orchestrator
    spec:
      replicas: 2
      selector:
        matchLabels:
          app: chat-orchestrator
      template:
        metadata:
          labels:
            app: chat-orchestrator
        spec:
          containers:
          - name: chat-orchestrator
            image: chat-orchestrator:latest
            ports:
            - containerPort: 8000
            env:
            - name: A2A_TRANSPORT
              value: "http"
            - name: LITURGY_AGENT_URL
              value: "http://liturgy-agent:8001"
            resources:
              requests:
                cpu: "1"
                memory: "1Gi"
              limits:
                cpu: "2"
                memory: "2Gi"

**Service** (expose endpoints):

.. code-block:: yaml

    # k8s/service.yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: chat-orchestrator
    spec:
      selector:
        app: chat-orchestrator
      ports:
      - protocol: TCP
        port: 8000
        targetPort: 8000
      type: ClusterIP

**Ingress** (external access):

.. code-block:: yaml

    # k8s/ingress.yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: prete-ingress
    spec:
      rules:
      - host: api.example.com
        http:
          paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: chat-orchestrator
                port:
                  number: 8000

Managed Platform Deployment (Railway/Render)
=============================================

**Railway Example** (``railway.json``):

.. code-block:: json

    {
      "services": [
        {
          "name": "frontend",
          "builder": "nixpacks",
          "startCommand": "npm run start",
          "root": "frontend"
        },
        {
          "name": "backend",
          "builder": "nixpacks",
          "startCommand": "uvicorn src.main:app --host 0.0.0.0 --port 8000",
          "root": "backend",
          "environmentVariables": {
            "LOG_JSON_FORMAT": "true",
            "A2A_TRANSPORT": "http"
          }
        }
      ]
    }

Environment Configuration
==========================

**Development (.env.local)**:

::

    ANTHROPIC_API_KEY=sk-...
    GOOGLE_API_KEY=...
    DATABASE_PATH=data/chat_orchestrator.db
    LOG_LEVEL=DEBUG
    LOG_JSON_FORMAT=false
    TEST_MODE=false

**Production (.env.production)**:

::

    ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}  # from secrets
    GOOGLE_API_KEY=${GOOGLE_API_KEY}        # from secrets
    DATABASE_PATH=/data/chat_orchestrator.db
    LOG_LEVEL=WARNING
    LOG_JSON_FORMAT=true
    TEST_MODE=false
    A2A_TRANSPORT=http
    LITURGY_AGENT_URL=http://liturgy-agent:8001
    HOMILY_AGENT_URL=http://homily-agent:8002

SSL/TLS Configuration
=====================

**Let's Encrypt** (via reverse proxy):

.. code-block:: nginx

    server {
        listen 443 ssl http2;
        server_name api.example.com;
        
        ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
        
        location / {
            proxy_pass http://localhost:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }

**Auto-renewal**:

.. code-block:: bash

    # Install certbot
    sudo apt-get install certbot python3-certbot-nginx
    
    # Get certificate
    sudo certbot --nginx -d api.example.com
    
    # Auto-renewal (installed by certbot)
    sudo systemctl enable certbot.timer

Health Checks
=============

**Kubernetes Liveness Probe**:

.. code-block:: yaml

    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 30

**Readiness Probe**:

.. code-block:: yaml

    readinessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 10

Database Migration
==================

From SQLite to PostgreSQL (if needed):

.. code-block:: python

    # Migration script (to be created if PostgreSQL migration is needed)
    # - Read SQLite database
    # - Create PostgreSQL schema
    # - Migrate session data
    # - Update checkpointer configuration

Scaling Considerations
======================

**Horizontal Scaling**:

- Frontend: Stateless, scale freely
- Chat Orchestrator: Sticky sessions via load balancer
- Liturgy Agent: Stateless, scale per load
- Homily Agent: Cache results (RAG results persist)

**Vertical Scaling**:

- Homily Agent benefits from GPU acceleration (LLM inference)
- More memory for vector embeddings

**Load Balancing**:

- Round-robin for stateless services
- Sticky sessions (cookie-based) for Chat Orchestrator
- HTTP/2 for efficient multiplexing

Monitoring & Logging
====================

**Prometheus Metrics**:

- Request latency (p50, p95, p99)
- Error rates per service
- Agent response times
- Tool execution times

**ELK Stack** (Elasticsearch, Logstash, Kibana):

- Centralized logging
- Log analysis and search
- Alerting on error patterns

**Jaeger** (distributed tracing):

- End-to-end request tracing
- Correlation ID tracking
- Service dependency visualization

Backup & Disaster Recovery
===========================

**Database Backups**:

.. code-block:: bash

    # SQLite backup
    sqlite3 /data/chat_orchestrator.db ".backup /backups/chat_orchestrator.db"
    
    # PostgreSQL backup
    pg_dump -h localhost -U user db > /backups/db.dump

**Frequency**: Daily, kept for 30 days

**Recovery**:

.. code-block:: bash

    # Restore SQLite
    sqlite3 /data/chat_orchestrator.db ".restore /backups/chat_orchestrator.db"
    
    # Restore PostgreSQL
    psql -h localhost -U user < /backups/db.dump

Troubleshooting Deployment
===========================

**Container won't start**

::

    Solutions:
    - Check Docker logs: docker logs container-name
    - Verify environment variables set
    - Check port conflicts
    - Verify directory permissions

**WebSocket connection fails**

::

    Solutions:
    - Check firewall (port 8000 open)
    - Verify WebSocket support in reverse proxy
    - Check CORS configuration
    - Check connection retry logic

**High latency**

::

    Solutions:
    - Monitor service metrics
    - Check database query performance
    - Optimize LLM API latency
    - Consider caching

See Also
========

- :doc:`architecture` - System architecture
- :doc:`testing` - Testing before deployment
- :doc:`troubleshooting` - Runtime troubleshooting
