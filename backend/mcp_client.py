import httpx
from typing import Optional, Dict, Any, List
from config import settings

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
        """List available MCP tools"""
        if not self.base_url or not self._initialized:
            return []
        
        try:
            await self.initialize()
            response = await self.client.get("/tools")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                # MCP endpoint exists but doesn't support GET /tools (not a real MCP server)
                logger.warning(f"MCP endpoint returned 405 - likely not a real MCP server: {self.base_url}")
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
        except Exception as e:
            error_msg = f"Error calling MCP tool {tool_name}: {e}"
            print(error_msg)
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