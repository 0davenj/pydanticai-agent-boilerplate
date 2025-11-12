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

- **Web UI**: https://ai.yourcompany.com
- **Health Check**: https://ai.yourcompany.com/health
- **Metrics**: https://ai.yourcompany.com/metrics (Prometheus format)
- **API Docs**: https://ai.yourcompany.com/docs (Swagger UI)

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