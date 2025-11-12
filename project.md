This project is a boilerplate for a simple AI Agent with MCP access and presented over WebChat widget

Core Components
1. Traefik (Reverse Proxy & SSL)
Why: Automatic SSL certificates via Let's Encrypt, dynamic routing, no manual nginx config
Configuration: All via Docker labels - zero config files needed
Ports: 80/443 (HTTP/HTTPS)
Benefits: Handles public access, SSL termination, load balancing
2. Redis (Optional Session Store)
Why: Share sessions if you ever scale to 2+ backend replicas
For PoC: Can be skipped entirely - just store sessions in-memory
Persistence: Use Docker volume for data retention
3. Frontend (Static React/Vue App)
Build: Single static bundle served by Nginx or Node
Communication: WebSocket or SSE to backend
Update: Just rebuild Docker image with new npm build
4. Backend (PydanticAI + FastAPI)
Base Image: python:3.11-slim
Expose: Port 8000 (FastAPI)
Secrets: Loaded from .env file (for PoC simplicity)