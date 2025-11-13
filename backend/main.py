from typing import Optional, Dict, List
import os
import sys
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

# Session chat history storage (last 10 messages per session)
session_chat_history: Dict[str, List] = {}
session_tool_calls: Dict[str, List] = {}
MAX_CHAT_HISTORY = 10

def add_to_chat_history(session_id: str, role: str, content: str):
    """Add a message to the chat history for a session"""
    if session_id not in session_chat_history:
        session_chat_history[session_id] = []
    
    session_chat_history[session_id].append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })
    
    # Keep only the last MAX_CHAT_HISTORY messages
    if len(session_chat_history[session_id]) > MAX_CHAT_HISTORY:
        session_chat_history[session_id] = session_chat_history[session_id][-MAX_CHAT_HISTORY:]

def get_chat_history_context(session_id: str) -> str:
    """Get formatted chat history context for the agent"""
    if session_id not in session_chat_history or not session_chat_history[session_id]:
        return ""
    
    history = session_chat_history[session_id]
    context_lines = []
    
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
        context_lines.append(f"{role}: {content}")
    
    return "\n".join(context_lines)

# Import FastMCPToolset for simple MCP integration
from pydantic_ai.toolsets.fastmcp import FastMCPToolset

# Hardcode MCP server URL (as requested)
MCP_SERVER_URL = "https://learn.microsoft.com/api/mcp"

# Create MCP toolset
try:
    mcp_toolset = FastMCPToolset(MCP_SERVER_URL)
    logger.info(f"MCP toolset created successfully for {MCP_SERVER_URL}")
except Exception as e:
    logger.error(f"Failed to create MCP toolset: {e}")
    mcp_toolset = None

# Create agent with MCP tools
if mcp_toolset:
    agent = create_agent(
        system_prompt="""You are an Expert Microsoft assistant with access to Microsoft Learn knowledge base tools via MCP.

IMPORTANT: Always use your MCP tools when:
- The user asks about Microsoft products, services, or technologies
- You need to find specific documentation or articles
- The question requires up-to-date technical information
- You're unsure about Microsoft-specific details

After using MCP tools, provide a comprehensive answer with:
1. The information found
2. Relevant links to the documentation (ALWAYS include the actual URLs from the MCP tool responses)
3. Any important notes or caveats

ALWAYS include the source links in your response. Format them as markdown links like [Title](URL). If the MCP tool returns multiple sources, include all of them.

Always cite your sources and provide links to Microsoft Learn documentation.""",
        toolsets=[mcp_toolset],
        memory_context=""
    )
    logger.info("Agent created with MCP toolset")
else:
    agent = create_agent(
        system_prompt="You are a helpful assistant. MCP tools are not available.",
        toolsets=[],
        memory_context=""
    )
    logger.warning("Agent created without MCP tools")

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
        "mcp_configured": mcp_toolset is not None,
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
        if mcp_toolset is not None:
            try:
                # Test MCP toolset by attempting to access it
                # Note: FastMCPToolset doesn't have a direct list_tools method
                # We'll just check if it's initialized
                mcp_status = "connected"
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
        
        # Initialize tool calls storage for this session
        session_tool_calls[session_id] = []
        
        # Session is valid, proceed with chat
        from config import get_model_name
        await websocket.send_json({
            "type": "auth_success",
            "message": "Authenticated successfully",
            "ai_provider": settings.ai_provider,
            "model_name": get_model_name()
        })
        logger.info(f"WebSocket authenticated for session: {session_id}")
        
        # Log provider info for debugging
        logger.info(f"Provider: {settings.ai_provider}, Model: {get_model_name()}")
        
        async for data in websocket.iter_json():
            try:
                message = data.get("message", "")
                if not message:
                    await websocket.send_json({"type": "error", "message": "Empty message"})
                    continue
                
                # Add user message to chat history
                add_to_chat_history(session_id, "user", message)
                
                MESSAGES_PROCESSED.inc()
                logger.info(f"Processing message for session {session_id}", extra={
                    "session_id": session_id,
                    "message_length": len(message)
                })
                
                # Get chat history context for memory
                memory_context = get_chat_history_context(session_id)
                
                # Create a new agent with memory context
                memory_agent = create_agent(
                    system_prompt="""You are an Expert Microsoft assistant with access to Microsoft Learn knowledge base tools via MCP.

IMPORTANT: Always use your MCP tools when:
- The user asks about Microsoft products, services, or technologies
- You need to find specific documentation or articles
- The question requires up-to-date technical information
- You're unsure about Microsoft-specific details

After using MCP tools, provide a comprehensive answer with:
1. The information found
2. Relevant links to the documentation (ALWAYS include the actual URLs from the MCP tool responses)
3. Any important notes or caveats

ALWAYS include the source links in your response. Format them as markdown links like [Title](URL). If the MCP tool returns multiple sources, include all of them.

Always cite your sources and provide links to Microsoft Learn documentation.""",
                    toolsets=[mcp_toolset] if mcp_toolset else [],
                    memory_context=f"\n\nPrevious conversation context:\n{memory_context}" if memory_context else ""
                )
                
                # Stream response from agent
                chunk_count = 0
                response_id = str(uuid.uuid4())
                previous_content = ""  # Track previous content to extract delta
                full_response = ""  # Track full response for chat history
                
                async with memory_agent.run_stream(message) as result:
                    async for chunk in result.stream():
                        chunk_count += 1
                        
                        # Extract content from chunk object
                        if hasattr(chunk, 'text'):
                            current_content = chunk.text
                        elif hasattr(chunk, 'content'):
                            current_content = chunk.content
                        elif hasattr(chunk, 'data'):
                            current_content = chunk.data
                        else:
                            current_content = str(chunk)
                        
                        # Extract delta (new content only)
                        if not previous_content:
                            # First chunk - delta is the entire content
                            delta = current_content
                        elif current_content.startswith(previous_content):
                            # Cumulative chunk - extract the delta
                            delta = current_content[len(previous_content):]
                        else:
                            # Unexpected pattern - log warning but use full content
                            logger.warning(f"Non-cumulative chunk {chunk_count}. Prev: '{previous_content[:30]}...', Curr: '{current_content[:30]}...'")
                            delta = current_content
                        
                        # Update previous content tracker
                        previous_content = current_content
                        full_response += delta
                        
                        # Send the delta
                        if delta:
                            await websocket.send_json({
                                "type": "chunk",
                                "content": delta,
                                "chunk_id": chunk_count,
                                "response_id": response_id
                            })
                
                # Add assistant response to chat history
                if full_response:
                    add_to_chat_history(session_id, "assistant", full_response)
                
                # Try to extract sources from MCP tool responses
                sources_found = False
                try:
                    # Check if result has data with tool calls that might contain source information
                    if hasattr(result, 'get_data'):
                        final_data = await result.get_data()
                        
                        # Look for tool calls that might contain source information
                        if hasattr(final_data, 'tool_calls') and final_data.tool_calls:
                            logger.info(f"Found {len(final_data.tool_calls)} tool calls")
                            
                            # Extract source information from MCP tool responses
                            sources_list = []
                            for tool_call in final_data.tool_calls:
                                logger.info(f"Processing tool call: {tool_call}")
                                
                                # Check if this is an MCP tool call with response data
                                if hasattr(tool_call, 'response') and tool_call.response:
                                    response_data = tool_call.response
                                    
                                    # Look for source links in the response
                                    if isinstance(response_data, dict):
                                        # Check for common source field names in MCP responses
                                        source_fields = ['sources', 'links', 'references', 'urls', 'source', 'link', 'url']
                                        
                                        for field in source_fields:
                                            if field in response_data:
                                                field_data = response_data[field]
                                                logger.info(f"Found {field} in response: {field_data}")
                                                
                                                if isinstance(field_data, list):
                                                    for item in field_data:
                                                        if isinstance(item, dict):
                                                            # Look for URL or link information
                                                            if 'url' in item or 'link' in item:
                                                                url = item.get('url') or item.get('link')
                                                                title = item.get('title', 'Documentation')
                                                                if url:
                                                                    sources_list.append(f"- [{title}]({url})")
                                                        elif isinstance(item, str) and ('http' in item or 'https' in item):
                                                            # Direct URL
                                                            sources_list.append(f"- {item}")
                                                        else:
                                                            sources_list.append(f"- {item}")
                                                elif isinstance(field_data, str) and ('http' in field_data or 'https' in field_data):
                                                    # Direct URL
                                                    sources_list.append(f"- {field_data}")
                                                elif isinstance(field_data, dict):
                                                    # Check for URL in dict
                                                    url = field_data.get('url') or field_data.get('link') or field_data.get('url')
                                                    title = field_data.get('title', 'Documentation')
                                                    if url:
                                                        sources_list.append(f"- [{title}]({url})")
                                
                                # Also check for direct source information in tool call
                                if hasattr(tool_call, 'source') and tool_call.source:
                                    sources_list.append(f"- Source: {tool_call.source}")
                                
                                # Check for any URLs in the response data
                                if isinstance(response_data, dict):
                                    for key, value in response_data.items():
                                        if 'url' in key.lower() or 'link' in key.lower():
                                            if isinstance(value, str) and ('http' in value or 'https' in value):
                                                sources_list.append(f"- {value}")
                                        elif isinstance(value, list):
                                            for item in value:
                                                if isinstance(item, dict) and ('url' in item or 'link' in item):
                                                    url = item.get('url') or item.get('link')
                                                    title = item.get('title', 'Documentation')
                                                    if url:
                                                        sources_list.append(f"- [{title}]({url})")
                            
                            if sources_list:
                                sources_text = "\n\n**Sources:**\n" + "\n".join(sources_list)
                                
                                # Send sources BEFORE done message
                                await websocket.send_json({
                                    "type": "sources",
                                    "content": sources_text,
                                    "chunk_id": chunk_count + 1,
                                    "response_id": response_id
                                })
                                sources_found = True
                                logger.info(f"Found and sent {len(sources_list)} sources")
                            else:
                                logger.info("No source links found in tool responses")
                        else:
                            logger.info("No tool calls found in result")
                        
                except Exception as e:
                    logger.error(f"Error extracting sources: {e}")
                    logger.error(f"Error details: {str(e)}")
                
                # Send completion message
                await websocket.send_json({"type": "done"})
                
                if not sources_found:
                    logger.info("No sources were found to send")
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
        
        # Log MCP configuration status
        if mcp_toolset is not None:
            logger.info("MCP toolset initialized successfully")
        else:
            logger.info("MCP not configured, skipping initialization")
            
    except Exception as e:
        logger.error(f"Startup error: {e}")
        # Don't crash the app, but log the error

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
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