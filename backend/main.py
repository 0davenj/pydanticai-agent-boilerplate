from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.responses import Response
import redis.asyncio as redis
import json
import uuid
import time

from config import settings
from ai_provider import create_agent
from mcp_client import mcp_client
from schemas import HealthResponse, ErrorResponse
from logger import logger

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
MESSAGES_PROCESSED = Counter('messages_processed_total', 'Total messages processed')
AI_PROVIDER_ERRORS = Counter('ai_provider_errors_total', 'AI provider errors', ['provider'])
WEBSOCKET_CONNECTIONS = Counter('websocket_connections_total', 'Total WebSocket connections')
ACTIVE_WEBSOCKETS = Gauge('active_websockets', 'Currently active WebSocket connections')

app = FastAPI(
    title="PydanticAI Agent API",
    version="1.0.0",
    description="A flexible AI agent with multi-provider support and MCP integration"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.app_host}", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Redis connection
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# AI Agent
agent = create_agent(system_prompt="You are a helpful AI assistant with access to various tools.")

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request, call_next):
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    REQUEST_DURATION.observe(process_time)
    
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", extra={
        "path": request.url.path,
        "method": request.method,
        "error": str(exc)
    })
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc)}
    )

async def verify_session(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verify session token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication")
    
    try:
        session_data = await redis_client.get(f"session:{credentials.credentials}")
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        return json.loads(session_data)
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        raise HTTPException(status_code=401, detail="Session verification failed")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "PydanticAI Agent API",
        "version": "1.0.0",
        "ai_provider": settings.ai_provider,
        "mcp_configured": mcp_client.is_configured(),
        "endpoints": {
            "health": "/health",
            "login": "/auth/login",
            "websocket": "/ws",
            "metrics": "/metrics"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        await redis_client.ping()
        redis_status = "connected"
        
        # Check MCP connection if configured
        mcp_status = "disabled"
        if mcp_client.is_configured():
            try:
                tools = await mcp_client.list_tools()
                mcp_status = "connected" if tools else "connected_no_tools"
            except Exception as e:
                mcp_status = "error"
                logger.warning(f"MCP health check failed: {e}")
        
        return HealthResponse(
            status="healthy",
            redis=redis_status,
            mcp=mcp_status,
            ai_provider=settings.ai_provider
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/auth/login")
async def login():
    """Create a new session"""
    try:
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "created_at": time.time(),
            "last_activity": time.time()
        }
        
        await redis_client.setex(
            f"session:{session_id}",
            3600,  # 1 hour expiry
            json.dumps(session_data)
        )
        
        logger.info(f"New session created: {session_id}")
        return {"session_id": session_id, "message": "Authentication successful"}
    except Exception as e:
        logger.error(f"Session creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    WEBSOCKET_CONNECTIONS.inc()
    ACTIVE_WEBSOCKETS.inc()
    
    try:
        # Wait for authentication message
        auth_data = await websocket.receive_json()
        session_id = auth_data.get("session_id")
        
        if not session_id:
            await websocket.close(code=1008, reason="Missing session_id")
            return
        
        # Verify session
        session_key = f"session:{session_id}"
        session_data = await redis_client.get(session_key)
        
        if not session_data:
            await websocket.close(code=1008, reason="Invalid session")
            return
        
        # Update session activity
        session_data = json.loads(session_data)
        session_data["last_activity"] = time.time()
        await redis_client.setex(session_key, 3600, json.dumps(session_data))
        
        # Session is valid, proceed with chat
        await websocket.send_json({"type": "auth_success", "message": "Authenticated successfully"})
        logger.info(f"WebSocket authenticated for session: {session_id}")
        
        async for data in websocket.iter_json():
            try:
                message = data.get("message", "")
                if not message:
                    await websocket.send_json({"type": "error", "message": "Empty message"})
                    continue
                
                MESSAGES_PROCESSED.inc()
                logger.info(f"Processing message for session {session_id}", extra={
                    "session_id": session_id,
                    "message_length": len(message)
                })
                
                # Stream response from agent
                async with agent.run_stream(message) as result:
                    async for chunk in result.stream():
                        # Debug logging
                        logger.debug(f"Chunk type: {type(chunk)}, value: {chunk}")
                        
                        # Handle both object-style and string-style chunks
                        if hasattr(chunk, 'text'):
                            content = chunk.text
                        elif hasattr(chunk, 'content'):
                            content = chunk.content
                        elif hasattr(chunk, 'data'):
                            content = chunk.data
                        else:
                            # If it's already a string or needs to be converted
                            content = str(chunk)
                        
                        await websocket.send_json({
                            "type": "chunk",
                            "content": content
                        })
                
                await websocket.send_json({"type": "done"})
                logger.info(f"Message processed successfully for session {session_id}")
                
            except Exception as e:
                AI_PROVIDER_ERRORS.labels(provider=settings.ai_provider).inc()
                logger.error(f"Error processing message for session {session_id}: {e}", extra={
                    "session_id": session_id,
                    "error": str(e)
                })
                await websocket.send_json({"type": "error", "message": "Failed to process message"})
                
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", extra={"error": str(e)})
    finally:
        ACTIVE_WEBSOCKETS.dec()

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type="text/plain")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # Initialize MCP client if configured
        if mcp_client.is_configured():
            await mcp_client.initialize()
            tools = await mcp_client.list_tools()
            logger.info(f"MCP client initialized with {len(tools)} tools")
        else:
            logger.info("MCP not configured, skipping initialization")
            
    except Exception as e:
        logger.error(f"Startup error: {e}")
        # Don't crash the app, but log the error

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        await mcp_client.close()
        await redis_client.close()
        logger.info("Services shutdown completed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=2,
        log_level=settings.log_level.lower()
    )