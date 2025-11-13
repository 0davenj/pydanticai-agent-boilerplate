import httpx
from typing import Optional, Dict, Any, List
from config import settings
from logger import logger

class MCPClient:
    def __init__(self):
        self.base_url = settings.mcp_http_url
        self.api_key = settings.mcp_http_api_key
        self.client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the HTTP client"""
        if self._initialized:
            return
        
        if self.base_url:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
            self._initialized = True
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools - supports both REST and JSON-RPC protocols"""
        if not self.base_url or not self._initialized:
            return []
        
        try:
            await self.initialize()
            
            # Try JSON-RPC first (more common for streamable MCP like Microsoft's)
            json_rpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            response = await self.client.post("/", json=json_rpc_request)
            response.raise_for_status()
            
            # Check if response has content
            if not response.content:
                logger.info(f"MCP endpoint returned empty response (200 OK but no content) - this is normal for some MCP implementations: {self.base_url}")
                return []
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                logger.info(f"MCP endpoint returned non-JSON content type: {content_type}")
                return []
            
            result = response.json()
            
            # Extract tools from JSON-RPC response
            if "result" in result and isinstance(result["result"], list):
                logger.info(f"MCP JSON-RPC successful, found {len(result['result'])} tools")
                return result["result"]
            elif "result" in result and isinstance(result["result"], dict) and "tools" in result["result"]:
                # Some implementations wrap tools in a dict
                logger.info(f"MCP JSON-RPC successful, found {len(result['result']['tools'])} tools")
                return result["result"]["tools"]
            else:
                logger.warning(f"MCP JSON-RPC returned unexpected format: {result}")
                return []
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                # Try legacy REST approach as fallback
                logger.info(f"MCP JSON-RPC returned 405, trying legacy REST approach: {self.base_url}")
                try:
                    response = await self.client.get("/tools")
                    response.raise_for_status()
                    tools = response.json()
                    logger.info(f"MCP REST successful, found {len(tools)} tools")
                    return tools
                except Exception as rest_e:
                    logger.warning(f"MCP REST approach also failed: {rest_e}")
            else:
                logger.warning(f"MCP HTTP error: {e}")
            return []
        except Exception as e:
            # Log error but don't crash the app
            logger.warning(f"Error listing MCP tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool"""
        if not self.base_url or not self._initialized:
            return {"error": "MCP not configured"}
        
        try:
            await self.initialize()
            response = await self.client.post(
                f"/tools/{tool_name}/call",
                json=arguments
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                # MCP endpoint exists but doesn't support POST /tools/{tool}/call
                logger.info(f"MCP endpoint returned 405 for tool call - may use different protocol: {self.base_url}")
            else:
                logger.warning(f"MCP HTTP error calling tool {tool_name}: {e}")
            return {"error": f"MCP tool call failed: {e}"}
        except Exception as e:
            error_msg = f"Error calling MCP tool {tool_name}: {e}"
            logger.warning(error_msg)
            return {"error": error_msg}
    
    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
    
    def is_configured(self) -> bool:
        """Check if MCP is configured"""
        return bool(self.base_url)

# Global MCP client instance
mcp_client = MCPClient()