"""
JUGGERNAUT MCP Server - Using official MCP library (v4)

SSE-based Model Context Protocol server for Claude.ai integration.
"""
import asyncio
import json
import logging
import os
from typing import Any

import aiohttp
import uvicorn

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

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

# Create MCP Server
mcp = Server("juggernaut-mcp")

# Helper for SQL execution
async def execute_sql(query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute SQL against Neon database."""
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


# Register tools
@mcp.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="hq_query",
            description="Query governance database. Query types: workers.all, workers.active, tasks.pending, tasks.recent, schema.tables",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query type"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="hq_execute",
            description="Execute governance actions. Actions: task.create",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action to execute"},
                    "params": {"type": "object", "description": "Action parameters"}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="fetch_url",
            description="Fetch content from a URL with optional method, headers, body.",
            inputSchema={
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
        ),
        Tool(
            name="war_room_post",
            description="Post a message to Slack #war-room channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bot": {"type": "string", "description": "Bot name"},
                    "message": {"type": "string", "description": "Message content"}
                },
                "required": ["bot", "message"]
            }
        ),
        Tool(
            name="war_room_history",
            description="Get recent messages from #war-room Slack channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20}
                }
            }
        )
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call: {name} with args: {arguments}")
    
    try:
        if name == "hq_query":
            query_type = arguments.get("query", "")
            queries = {
                "workers.all": "SELECT * FROM workers ORDER BY created_at DESC",
                "workers.active": "SELECT * FROM workers WHERE status = 'active'",
                "tasks.pending": "SELECT * FROM governance_tasks WHERE status = 'pending'",
                "tasks.recent": "SELECT * FROM governance_tasks ORDER BY created_at DESC LIMIT 20",
                "schema.tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            }
            sql = queries.get(query_type)
            if not sql:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown query type: {query_type}"}))]
            result = await execute_sql(sql)
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "hq_execute":
            action = arguments.get("action", "")
            params = arguments.get("params", {})
            if action == "task.create":
                sql = """
                    INSERT INTO governance_tasks (title, description, priority, task_type, assigned_worker, status, created_by)
                    VALUES ($1, $2, $3, $4, $5, 'pending', 'mcp')
                    RETURNING id
                """
                result = await execute_sql(sql, [
                    params.get("title"),
                    params.get("description"),
                    params.get("priority", "medium"),
                    params.get("task_type", "code"),
                    params.get("assigned_worker", "claude-chat")
                ])
                return [TextContent(type="text", text=json.dumps(result))]
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown action: {action}"}))]

        elif name == "fetch_url":
            url = arguments.get("url")
            method = arguments.get("method", "GET").upper()
            headers = arguments.get("headers", {})
            body = arguments.get("body")
            timeout = arguments.get("timeout", 30)
            
            if not url:
                return [TextContent(type="text", text=json.dumps({"error": "URL required"}))]
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.request(
                        method, url, headers=headers,
                        data=body if method in ("POST", "PUT", "PATCH") else None,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        content = await resp.text()
                        return [TextContent(type="text", text=json.dumps({
                            "success": True,
                            "status_code": resp.status,
                            "content": content[:50000],
                            "headers": dict(resp.headers)
                        }))]
                except asyncio.TimeoutError:
                    return [TextContent(type="text", text=json.dumps({"error": "Timeout"}))]
                except Exception as e:
                    return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

        elif name == "war_room_post":
            if not SLACK_BOT_TOKEN:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
                    json={"channel": WAR_ROOM_CHANNEL, "text": arguments.get("message", ""), "username": arguments.get("bot", "JUGGERNAUT").upper()}
                ) as resp:
                    return [TextContent(type="text", text=json.dumps(await resp.json()))]

        elif name == "war_room_history":
            if not SLACK_BOT_TOKEN:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://slack.com/api/conversations.history",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    params={"channel": WAR_ROOM_CHANNEL, "limit": arguments.get("limit", 20)}
                ) as resp:
                    return [TextContent(type="text", text=json.dumps(await resp.json()))]

        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# SSE Transport - messages endpoint is relative to where it's mounted
sse_transport = SseServerTransport("/messages")


def check_auth(scope) -> bool:
    """Check token from query string."""
    query_string = scope.get("query_string", b"").decode()
    params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
    return params.get("token") == MCP_AUTH_TOKEN


async def send_json_response(send, status: int, body: dict):
    """Send a JSON response."""
    body_bytes = json.dumps(body).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"access-control-allow-origin", b"*"],
            [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
            [b"access-control-allow-headers", b"*"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body_bytes,
    })


async def send_cors_preflight(send):
    """Send CORS preflight response."""
    await send({
        "type": "http.response.start",
        "status": 204,
        "headers": [
            [b"access-control-allow-origin", b"*"],
            [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
            [b"access-control-allow-headers", b"*"],
            [b"access-control-max-age", b"86400"],
        ],
    })
    await send({"type": "http.response.body", "body": b""})


async def app(scope, receive, send):
    """Main ASGI application."""
    if scope["type"] != "http":
        return
    
    path = scope["path"]
    method = scope["method"]
    
    # CORS preflight
    if method == "OPTIONS":
        await send_cors_preflight(send)
        return
    
    # Health check
    if path == "/health" and method == "GET":
        await send_json_response(send, 200, {"status": "healthy", "tools": 5})
        return
    
    # SSE endpoint
    if path == "/mcp/sse" and method == "GET":
        if not check_auth(scope):
            await send_json_response(send, 401, {"error": "Unauthorized"})
            return
        
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp.run(
                streams[0],
                streams[1],
                mcp.create_initialization_options()
            )
        return
    
    # Messages endpoint (POST)
    if path == "/messages" and method == "POST":
        # Token is in query params from the endpoint URL sent to client
        if not check_auth(scope):
            await send_json_response(send, 401, {"error": "Unauthorized"})
            return
        
        await sse_transport.handle_post_message(scope, receive, send)
        return
    
    # 404
    await send_json_response(send, 404, {"error": "Not found"})


if __name__ == "__main__":
    logger.info(f"Starting MCP Server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
