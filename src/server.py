# core/mcp_client.py
"""
MCP Server HTTP Client for tool execution via Streamable HTTP transport.
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from functools import wraps
import httpx
from httpx import HTTPStatusError, ConnectError, ReadTimeout, TimeOutException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

MCP_SERVER_URL: str = "https://juggernaut-mcp-production.up.railway.app/mcp"
DEFAULT_TIMEOUT: float = 30.0
MAX_RETRIES: int = 3
MCP_AUTH_TOKEN: str = os.getenv("MCP_AUTH_TOKEN", "")

# Validate auth token exists
if not MCP_AUTH_TOKEN:
    raise ValueError("MCP_AUTH_TOKEN environment variable must be set")


def test_connectivity() -> bool:
    """Test connectivity to MCP server before initialization."""
    try:
        client = httpx.Client(timeout=5.0, headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"})
        response = client.head(MCP_SERVER_URL)
        logger.info(f"MCP server connectivity test successful: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"MCP server connectivity test failed: {e}")
        return False


class MCPClient:
    """HTTP client for MCP server using SSE transport with retry logic."""
    
    def __init__(self) -> None:
        self._session: Optional[ClientSession] = None
        self._client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
        )
        self._connected = False
        
        if not test_connectivity():
            logger.warning("MCP server connectivity test failed, proceeding anyway")

    async def __aenter__(self) -> 'MCPClient':
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to MCP server via streamable HTTP."""
        if self._connected:
            return
            
        try:
            async with streamablehttp_client(
                MCP_SERVER_URL,
                client=self._client
            ) as (read_stream, write_stream, get_session_id):
                self._session = ClientSession(
                    read=read_stream,
                    write=write_stream,
                    get_session_id=get_session_id
                )
                await self._session.initialize()
                self._connected = True
                logger.info("Connected to MCP server successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise ConnectionError(f"MCP server connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self._session:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning(f"Error during MCP session close: {e}")
        if self._client:
            await self._client.aclose()
        self._connected = False
        logger.info("Disconnected from MCP server")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((HTTPStatusError, ConnectError, ReadTimeout)),
        reraise=True
    )
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool on the MCP server.

        Args:
            tool_name: Name of the tool to execute
            parameters: Dictionary of parameters for the tool

        Returns:
            Dictionary containing tool execution result

        Raises:
            ValueError: If not connected to server
            KeyError: If tool execution fails
            ConnectionError: If server connection issues occur
        """
        if not self._connected:
            raise ValueError("MCPClient must be connected before executing tools")

        try:
            # Call tool using MCP client session
            result = await self._session.call_tool(tool_name, arguments=parameters)
            
            logger.info(f"Successfully executed tool '{tool_name}'")
            return {
                "success": True,
                "tool_name": tool_name,
                "result": result.content if hasattr(result, 'content') else result,
                "parameters": parameters
            }
            
        except KeyError as e:
            logger.error(f"Tool '{tool_name}' not found or execution failed: {e}")
            raise KeyError(f"Tool execution failed: {e}") from e
        except TimeOutException:
            logger.error(f"Tool '{tool_name}' execution timed out")
            raise ConnectionError("Tool execution timed out") from None
        except Exception as e:
            logger.error(f"Unexpected error executing tool '{tool_name}': {e}")
            raise ConnectionError(f"Tool execution error: {e}") from e


# core/brain.py (updated import and usage)
"""
BrainService integration with MCP client for tool execution.
Add this to your existing BrainService class.
"""

# Add these imports at the top of brain.py (after existing imports)
from typing import Dict, Any
from core.mcp_client import MCPClient

# Add this as a class attribute or instance variable in your BrainService class
class BrainService:
    # ... existing code ...
    
    def __init__(self):
        # ... existing init code ...
        self.mcp_client: Optional[MCPClient] = None

    async def initialize_mcp_client(self) -> None:
        """Initialize MCP client connection."""
        self.mcp_client = MCPClient()
        async with self.mcp_client:
            # Test connection
            await self.mcp_client.connect()
            logger.info("MCP client initialized in BrainService")

    async def execute_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute MCP tool through BrainService.

        Args:
            tool_name: MCP tool name
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        if not self.mcp_client:
            await self.initialize_mcp_client()
            
        async with self.mcp_client:
            return await self.mcp_client.execute_tool(tool_name, parameters)

    # Example usage method
    async def process_with_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """High-level method for MCP tool execution with logging."""
        logger.info(f"BrainService executing MCP tool: {tool_name} with params: {params}")
        try:
            result = await self.execute_mcp_tool(tool_name, params)
            logger.info(f"MCP tool '{tool_name}' completed successfully")
            return result
        except Exception as e:
            logger.error(f"MCP tool '{tool_name}' failed: {e}")
            raise

# Usage example:
"""
async def example():
    brain = BrainService()
    result = await brain.process_with_mcp_tool(
        "calculator",
        {"expression": "2 + 2 * 3"}
    )
    print(result)
"""