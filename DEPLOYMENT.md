# PydanticAI Agent - Deployment Guide

## Quick Start

### 1. Clone and Configure

```bash
git clone <repository>
cd pydanticai-poc
cp .env.example .env
```

### 2. Choose Your AI Provider

Edit `.env` and configure your preferred AI provider:

#### **Azure OpenAI** (Default)
```bash
AI_PROVIDER=azure
AZURE_OPENAI_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

#### **OpenRouter**
```bash
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

#### **OpenAI**
```bash
AI_PROVIDER=openai
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o
```

#### **Anthropic**
```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 3. Deploy with Docker Compose

```bash
docker-compose up -d
```

### 4. Access Your Application

After deployment, the services will be available at:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics (Prometheus format)
- **API Docs**: http://localhost:8000/docs (Swagger UI)

## Deployment Options

### Option 1: Nginx Proxy Manager (NPM)

Nginx Proxy Manager provides a simple web UI for managing reverse proxy and SSL certificates.

#### Setup NPM
```bash
# Create a docker-compose.npm.yml
cat > docker-compose.npm.yml << 'EOF'
version: '3.8'
services:
  npm:
    image: jc21/nginx-proxy-manager:latest
    ports:
      - "80:80"
      - "81:81"
      - "443:443"
    volumes:
      - npm-data:/data
      - npm-ssl:/etc/letsencrypt
    restart: unless-stopped

volumes:
  npm-data:
  npm-ssl:
EOF

# Start NPM
docker-compose -f docker-compose.npm.yml up -d
```

#### Configure NPM
1. Access NPM web UI at http://your-server-ip:81
2. Default login: admin@example.com / changeme
3. Create a new proxy host:
   - Domain: ai.yourcompany.com
   - Scheme: http
   - Forward Hostname: localhost
   - Forward Port: 3000 (frontend)
   - Enable WebSockets Support
   - Enable Block Common Exploits
4. Request SSL certificate through NPM UI

#### Configure Backend Proxy
Create a second proxy host for the backend:
- Domain: api.yourcompany.com (or use a sub-path)
- Forward Port: 8000
- Enable WebSockets Support

### Option 2: Cloudflare Tunnel

Cloudflare Tunnel provides secure, zero-trust access without opening firewall ports.

#### Setup Cloudflare Tunnel
```bash
# Install cloudflared
# On Ubuntu/Debian:
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflare.list
sudo apt update
sudo apt install cloudflared

# Login to Cloudflare
cloudflared tunnel login

# Create a tunnel
cloudflared tunnel create pydanticai-agent

# Create tunnel configuration
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: pydanticai-agent
credentials-file: /root/.cloudflared/pydanticai-agent.json

ingress:
  - hostname: ai.yourcompany.com
    service: http://localhost:3000
  - hostname: ai.yourcompany.com
    path: /ws
    service: http://localhost:8000
  - hostname: ai.yourcompany.com
    path: /api/*
    service: http://localhost:8000
  - hostname: ai.yourcompany.com
    path: /auth/*
    service: http://localhost:8000
  - hostname: ai.yourcompany.com
    path: /health
    service: http://localhost:8000
  - service: http_status:404
EOF

# Run the tunnel
cloudflared tunnel run pydanticai-agent
```

#### Configure DNS in Cloudflare Dashboard
1. Go to Cloudflare Dashboard > Your Domain > DNS
2. Create a CNAME record:
   - Name: ai
   - Target: `<tunnel-uuid>.cfargotunnel.com`
   - Proxy status: Proxied

#### Run as a Service (Optional)
```bash
# Create systemd service
sudo nano /etc/systemd/system/cloudflared.service
```

Add:
```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cloudflared tunnel run pydanticai-agent
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Option 3: Direct with SSL (Self-managed)

If you have your own SSL certificates:

```bash
# Update frontend/nginx.conf to include SSL
# Then mount certificates in docker-compose.yml

  frontend:
    build: ./frontend
    ports:
      - "443:443"
    volumes:
      - ./ssl/cert.pem:/etc/nginx/ssl/cert.pem
      - ./ssl/key.pem:/etc/nginx/ssl/key.pem
    # ... rest of config
```

## Configuration Options

## Configuration Options

### Core Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `AI_PROVIDER` | AI provider to use: `azure`, `openrouter`, `openai`, `anthropic` | Yes | `azure` |
| `APP_HOST` | Domain name for your application | Yes | `ai.yourcompany.com` |
| `APP_SECRET` | Secret key for session encryption | Yes | `change-this-secret` |
| `LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | No | `INFO` |

### Provider-Specific Configuration

#### Azure OpenAI
- `AZURE_OPENAI_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT`: Deployment name (e.g., `gpt-4o`)

#### OpenRouter
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `OPENROUTER_MODEL`: Model name (e.g., `anthropic/claude-3.5-sonnet`)

#### OpenAI
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_MODEL`: Model name (e.g., `gpt-4o`)

#### Anthropic
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `ANTHROPIC_MODEL`: Model name (e.g., `claude-3-5-sonnet-20241022`)

### Optional Configuration

#### MCP (Model Context Protocol)
```bash
MCP_HTTP_URL=http://mcp-server:8000
MCP_HTTP_API_KEY=your-mcp-key
```

#### Redis
```bash
REDIS_URL=redis://redis:6379
```

## Monitoring

### Health Checks

All services include health checks:

- **Backend**: `GET /health` - Returns service status, Redis connectivity, MCP status
- **Redis**: Redis CLI ping test
- **Frontend**: HTTP connectivity test

### Prometheus Metrics

Access metrics at `https://ai.yourcompany.com/metrics`:

- `http_requests_total`: Total HTTP requests by method and endpoint
- `http_request_duration_seconds`: HTTP request duration histogram
- `messages_processed_total`: Total messages processed
- `ai_provider_errors_total`: AI provider errors by provider
- `websocket_connections_total`: Total WebSocket connections
- `active_websockets`: Currently active WebSocket connections

### Logging

Structured JSON logging is enabled by default. View logs:

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

## Security Considerations

### Production Deployment

1. **Change Default Secrets**
   ```bash
   APP_SECRET=$(openssl rand -base64 32)
   ```

2. **Use Docker Secrets** (for sensitive data)
   ```bash
   echo "your-secret" | docker secret create app_secret -
   ```

3. **Enable Traefik Secure Mode**
   - Remove `--api.insecure=true` from Traefik command
   - Use Docker secrets for ACME storage

4. **Firewall Configuration**
   ```bash
   # Only expose ports 80 and 443
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

5. **SSL/TLS**
   - Traefik automatically provisions Let's Encrypt certificates
   - Update `ACME_EMAIL` in docker-compose.yml

### Input Validation

- Messages limited to 10,000 characters
- Session IDs validated and sanitized
- WebSocket messages validated before processing

## Scaling

### Horizontal Scaling

Scale backend instances:
```bash
docker-compose up -d --scale backend=3
```

Redis automatically shares sessions between instances.

### Vertical Scaling

Adjust resources in `docker-compose.yml`:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Troubleshooting

### Common Issues

#### 1. Backend fails to start
```bash
# Check logs
docker-compose logs backend

# Test configuration
docker-compose run backend python -c "from config import settings; print(settings.ai_provider)"
```

#### 2. WebSocket connection fails
```bash
# Check WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Host: ai.yourcompany.com" -H "Origin: https://ai.yourcompany.com" \
  http://localhost:8000/ws
```

#### 3. AI provider errors
```bash
# Check provider configuration
docker-compose exec backend python -c "from ai_provider import get_ai_model; print(get_ai_model())"
```

#### 4. Redis connection issues
```bash
# Test Redis connectivity
docker-compose exec backend redis-cli -h redis ping
```

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG docker-compose up
```

## Development

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm start
```

### Testing

```bash
# Test AI providers
python -c "from ai_provider import create_agent; agent = create_agent(); print('AI provider ready')"

# Test MCP client
python -c "from mcp_client import mcp_client; import asyncio; print(asyncio.run(mcp_client.list_tools()))"
```

## API Reference

### Authentication
- `POST /auth/login` - Create new session
- Returns: `{ "session_id": "uuid", "message": "Authentication successful" }`

### WebSocket
- `WS /ws` - Real-time chat endpoint
- Authenticate with: `{ "session_id": "your-session-id" }`

### Health & Monitoring
- `GET /health` - Service health check
- `GET /metrics` - Prometheus metrics

## Support

For issues and feature requests, please check:
- Application logs: `docker-compose logs`
- Health endpoint: `https://ai.yourcompany.com/health`
- Metrics endpoint: `https://ai.yourcompany.com/metrics`

## License

MIT License - see LICENSE file for details