"""
JUGGERNAUT MCP Server

SSE-based Model Context Protocol server for Claude.ai integration.
Provides tools for governance, web fetch, war room, browser, and research.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

import aiohttp
from aiohttp import web
from aiohttp_sse import sse_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MCP_AUTH_TOKEN = os.environ.get('MCP_AUTH_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
WAR_ROOM_CHANNEL = os.environ.get('WAR_ROOM_CHANNEL', 'C0A5WTBHX1A')
PORT = int(os.environ.get('PORT', 8080))

# CORS headers for Claude.ai
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
}


class MCPServer:
    """SSE-based MCP Server for JUGGERNAUT tools."""

    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.tools = self._register_tools()
        logger.info("MCP Server initialized with %d tools", len(self.tools))

    def _register_tools(self) -> dict[str, dict[str, Any]]:
        """Register all available MCP tools."""
        return {
            "hq_query": {
                "description": "Query governance database.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query type"},
                        "params": {"type": "object", "description": "Query parameters"}
                    },
                    "required": ["query"]
                }
            },
            "hq_execute": {
                "description": "Execute governance actions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "Action to execute"},
                        "params": {"type": "object", "description": "Action parameters"}
                    },
                    "required": ["action"]
                }
            },
            "fetch_url": {
                "description": "Fetch content from a URL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                        "method": {"type": "string", "default": "GET"},
                        "headers": {"type": "object"},
                        "body": {"type": "string"},
                        "timeout": {"type": "integer", "default": 30}
                    },
                    "required": ["url"]
                }
            },
            "war_room_post": {
                "description": "Post a message to #war-room.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "bot": {"type": "string"},
                        "message": {"type": "string"}
                    },
                    "required": ["bot", "message"]
                }
            },
            "war_room_history": {
                "description": "Get recent messages from #war-room.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20}
                    }
                }
            }
        }

    async def handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle a tool call and return the result."""
        logger.info("Tool call: %s with args: %s", tool_name, arguments)

        handlers = {
            "hq_query": self._handle_hq_query,
            "hq_execute": self._handle_hq_execute,
            "fetch_url": self._handle_fetch_url,
            "war_room_post": self._handle_war_room_post,
            "war_room_history": self._handle_war_room_history,
        }

        handler = handlers.get(tool_name)
        if handler:
            try:
                return await handler(arguments)
            except Exception as e:
                logger.exception("Error in tool %s", tool_name)
                return {"error": str(e)}
        return {"error": f"Unknown tool: {tool_name}"}

    async def _execute_sql(
        self, query: str, params: list[Any] | None = None
    ) -> dict[str, Any]:
        """Execute a SQL query against the governance database."""
        neon_url = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                neon_url,
                headers={
                    "Content-Type": "application/json",
                    "Neon-Connection-String": DATABASE_URL
                },
                json={"query": query, "params": params or []}
            ) as resp:
                return await resp.json()

    async def _handle_hq_query(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle governance database queries."""
        query_type = args.get("query", "")
        queries = {
            "workers.all": "SELECT * FROM workers ORDER BY created_at DESC",
            "workers.active": "SELECT * FROM workers WHERE status = 'active'",
            "tasks.pending": "SELECT * FROM governance_tasks WHERE status = 'pending'",
            "tasks.recent": "SELECT * FROM governance_tasks ORDER BY created_at DESC LIMIT 20",
            "schema.tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
        }
        sql = queries.get(query_type)
        if not sql:
            return {"error": f"Unknown query type: {query_type}"}
        return await self._execute_sql(sql)

    async def _handle_hq_execute(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle governance action execution."""
        action = args.get("action", "")
        params = args.get("params", {})

        if action == "task.create":
            sql = """
                INSERT INTO governance_tasks (title, description, priority, task_type, assigned_worker, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING id
            """
            return await self._execute_sql(sql, [
                params.get("title"),
                params.get("description"),
                params.get("priority", "medium"),
                params.get("task_type", "code"),
                params.get("assigned_worker", "claude-chat")
            ])
        return {"error": f"Unknown action: {action}"}

    async def _handle_fetch_url(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle URL fetch requests."""
        url = args.get("url")
        method = args.get("method", "GET").upper()
        headers = args.get("headers", {})
        body = args.get("body")
        timeout = args.get("timeout", 30)

        if not url:
            return {"error": "URL is required"}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    data=body if method in ("POST", "PUT", "PATCH") else None,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    content = await resp.text()
                    return {
                        "success": True,
                        "status_code": resp.status,
                        "content": content[:50000],
                        "headers": dict(resp.headers)
                    }
            except asyncio.TimeoutError:
                return {"error": "Request timed out"}
            except aiohttp.ClientError as e:
                return {"error": str(e)}

    async def _handle_war_room_post(self, args: dict[str, Any]) -> dict[str, Any]:
        """Post to war room Slack channel."""
        bot = args.get("bot", "juggernaut")
        message = args.get("message", "")

        if not SLACK_BOT_TOKEN:
            return {"error": "Slack bot token not configured"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "channel": WAR_ROOM_CHANNEL,
                    "text": message,
                    "username": bot.upper()
                }
            ) as resp:
                return await resp.json()

    async def _handle_war_room_history(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get war room history."""
        limit = args.get("limit", 20)

        if not SLACK_BOT_TOKEN:
            return {"error": "Slack bot token not configured"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                params={"channel": WAR_ROOM_CHANNEL, "limit": limit}
            ) as resp:
                return await resp.json()


# Global server instance
mcp_server = MCPServer()


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Add CORS headers to all responses."""
    if request.method == 'OPTIONS':
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    
    response.headers.update(CORS_HEADERS)
    return response


async def handle_sse(request: web.Request) -> web.StreamResponse:
    """Handle SSE connections for MCP protocol (GET requests)."""
    token = request.query.get('token')
    if token != MCP_AUTH_TOKEN:
        return web.Response(status=401, text="Unauthorized", headers=CORS_HEADERS)

    async with sse_response(request, headers=CORS_HEADERS) as resp:
        tools_message = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {"tools": [
                {"name": name, **tool}
                for name, tool in mcp_server.tools.items()
            ]}
        }
        await resp.send(json.dumps(tools_message))

        while True:
            await asyncio.sleep(30)
            await resp.send(json.dumps({"type": "ping"}))


async def handle_mcp_post(request: web.Request) -> web.Response:
    """Handle MCP tool calls via POST to /mcp/sse endpoint."""
    token = request.query.get('token')
    if not token:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token != MCP_AUTH_TOKEN:
        return web.Response(status=401, text="Unauthorized", headers=CORS_HEADERS)

    try:
        data = await request.json()
        logger.info("MCP POST received: %s", json.dumps(data)[:500])

        # Handle JSON-RPC format
        method = data.get('method', '')
        params = data.get('params', {})
        request_id = data.get('id')

        if method == 'tools/list':
            return web.json_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {"name": name, **tool}
                        for name, tool in mcp_server.tools.items()
                    ]
                }
            }, headers=CORS_HEADERS)

        if method == 'tools/call':
            tool_name = params.get('name')
            arguments = params.get('arguments', {})
            result = await mcp_server.handle_tool_call(tool_name, arguments)
            return web.json_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
            }, headers=CORS_HEADERS)

        # Legacy format support
        if 'name' in data:
            tool_name = data.get('name')
            arguments = data.get('arguments', {})
            result = await mcp_server.handle_tool_call(tool_name, arguments)
            return web.json_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }, headers=CORS_HEADERS)

        return web.json_response({
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}
        }, headers=CORS_HEADERS)

    except json.JSONDecodeError:
        return web.Response(status=400, text="Invalid JSON", headers=CORS_HEADERS)
    except Exception as e:
        logger.exception("Error handling MCP POST")
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)}
        }, status=500, headers=CORS_HEADERS)


async def handle_tool_call(request: web.Request) -> web.Response:
    """Handle tool call requests at /mcp/tools/call."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token != MCP_AUTH_TOKEN:
        return web.Response(status=401, text="Unauthorized", headers=CORS_HEADERS)

    try:
        data = await request.json()
        tool_name = data.get('name')
        arguments = data.get('arguments', {})

        result = await mcp_server.handle_tool_call(tool_name, arguments)

        return web.json_response({
            "jsonrpc": "2.0",
            "id": data.get('id'),
            "result": result
        }, headers=CORS_HEADERS)
    except json.JSONDecodeError:
        return web.Response(status=400, text="Invalid JSON", headers=CORS_HEADERS)
    except Exception as e:
        logger.exception("Error handling tool call")
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)}
        }, status=500, headers=CORS_HEADERS)


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "tools": len(mcp_server.tools)
    }, headers=CORS_HEADERS)


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get('/mcp/sse', handle_sse)
    app.router.add_post('/mcp/sse', handle_mcp_post)
    app.router.add_options('/mcp/sse', lambda r: web.Response(status=204))  # CORS preflight
    app.router.add_post('/mcp/tools/call', handle_tool_call)
    app.router.add_options('/mcp/tools/call', lambda r: web.Response(status=204))
    app.router.add_get('/health', handle_health)
    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting MCP Server on port %d", PORT)
    web.run_app(app, port=PORT)
