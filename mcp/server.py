"""
JUGGERNAUT MCP Server - Using official MCP library (v6)

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

# MCP Factory helpers
async def mcp_create_from_spec(name: str, description: str, tools: list, owner: str = None) -> dict:
    """Create a new MCP from specification."""
    import uuid
    mcp_id = str(uuid.uuid4())
    auth_token = str(uuid.uuid4()).replace("-", "")[:32]
    
    # Register in database
    sql = f"""
    INSERT INTO mcp_registry (id, name, description, status, owner_worker_id, auth_token, tools_config)
    VALUES ('{mcp_id}', '{name}', '{description.replace("'", "''")}', 'pending', 
            {'NULL' if not owner else f"'{owner}'"}, '{auth_token}', '{json.dumps(tools)}'::jsonb)
    ON CONFLICT (name) DO UPDATE SET
        description = EXCLUDED.description,
        tools_config = EXCLUDED.tools_config
    RETURNING id, auth_token
    """
    result = await execute_sql(sql)
    if result.get("rows"):
        return {
            "mcp_id": result["rows"][0]["id"],
            "auth_token": result["rows"][0]["auth_token"],
            "status": "registered",
            "message": f"MCP '{name}' registered. Deploy via Railway to activate."
        }
    return {"error": "Failed to register MCP"}


async def mcp_list_all(status: str = None) -> list:
    """List all registered MCPs."""
    where = f"WHERE status = '{status}'" if status else ""
    sql = f"""
    SELECT id, name, description, status, endpoint_url, health_status, created_at
    FROM mcp_registry {where}
    ORDER BY created_at DESC
    """
    result = await execute_sql(sql)
    return result.get("rows", [])


async def mcp_get_status(mcp_id: str) -> dict:
    """Get status of a specific MCP."""
    sql = f"""
    SELECT id, name, description, status, endpoint_url, auth_token,
           railway_service_id, health_status, error_message, 
           created_at, deployed_at, last_health_check
    FROM mcp_registry WHERE id = '{mcp_id}' OR name = '{mcp_id}'
    """
    result = await execute_sql(sql)
    if result.get("rows"):
        return result["rows"][0]
    return {"error": "MCP not found"}




@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="hq_query", description="Query governance database. Types: workers.all, workers.active, tasks.pending, tasks.recent, schema.tables",
             inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
        Tool(name="hq_execute", description="Execute governance actions. Actions: task.create",
             inputSchema={"type": "object", "properties": {"action": {"type": "string"}, "params": {"type": "object"}}, "required": ["action"]}),
        Tool(name="fetch_url", description="Fetch content from a URL",
             inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "headers": {"type": "object"}, "body": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["url"]}),
        Tool(name="war_room_post", description="Post to Slack #war-room",
             inputSchema={"type": "object", "properties": {"bot": {"type": "string"}, "message": {"type": "string"}}, "required": ["bot", "message"]}),
        Tool(name="war_room_history", description="Get #war-room history",
             inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        Tool(name="mcp_create", description="Create a new MCP server. Workers can define custom tools.",
             inputSchema={"type": "object", "properties": {
                 "name": {"type": "string", "description": "Unique name for the MCP"},
                 "description": {"type": "string", "description": "What this MCP does"},
                 "tools": {"type": "array", "description": "Array of tool definitions with name, description, parameters"},
                 "owner_worker_id": {"type": "string", "description": "Worker ID that owns this MCP"}
             }, "required": ["name", "description", "tools"]}),
        Tool(name="mcp_list", description="List all registered MCP servers",
             inputSchema={"type": "object", "properties": {"status": {"type": "string", "description": "Filter by status: pending, active, failed"}}}),
        Tool(name="mcp_status", description="Get status of a specific MCP server",
             inputSchema={"type": "object", "properties": {"mcp_id": {"type": "string", "description": "MCP ID or name"}}, "required": ["mcp_id"]})
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info(f"Tool call: {name}")
    try:
        if name == "hq_query":
            queries = {
                "workers.all": "SELECT * FROM workers ORDER BY created_at DESC",
                "workers.active": "SELECT * FROM workers WHERE status = 'active'",
                "tasks.pending": "SELECT * FROM governance_tasks WHERE status = 'pending'",
                "tasks.recent": "SELECT * FROM governance_tasks ORDER BY created_at DESC LIMIT 20",
                "schema.tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            }
            sql = queries.get(arguments.get("query", ""))
            if sql:
                result = await execute_sql(sql)
                return [TextContent(type="text", text=json.dumps(result))]
            return [TextContent(type="text", text=json.dumps({"error": "Unknown query"}))]
        
        elif name == "hq_execute":
            if arguments.get("action") == "task.create":
                params = arguments.get("params", {})
                result = await execute_sql(
                    "INSERT INTO governance_tasks (title, description, priority, task_type, assigned_worker, status) VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id",
                    [params.get("title"), params.get("description"), params.get("priority", "medium"), params.get("task_type", "code"), params.get("assigned_worker", "claude-chat")]
                )
                return [TextContent(type="text", text=json.dumps(result))]
            return [TextContent(type="text", text=json.dumps({"error": "Unknown action"}))]
        
        elif name == "fetch_url":
            url = arguments.get("url")
            if not url:
                return [TextContent(type="text", text=json.dumps({"error": "URL required"}))]
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    arguments.get("method", "GET").upper(), url,
                    headers=arguments.get("headers", {}),
                    data=arguments.get("body"),
                    timeout=aiohttp.ClientTimeout(total=arguments.get("timeout", 30))
                ) as resp:
                    content = await resp.text()
                    return [TextContent(type="text", text=json.dumps({"status": resp.status, "content": content[:50000]}))]
        
        elif name == "war_room_post":
            if not SLACK_BOT_TOKEN:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post("https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
                    json={"channel": WAR_ROOM_CHANNEL, "text": arguments.get("message", ""), "username": arguments.get("bot", "JUGGERNAUT").upper()}
                ) as resp:
                    return [TextContent(type="text", text=json.dumps(await resp.json()))]
        
        elif name == "war_room_history":
            if not SLACK_BOT_TOKEN:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.get("https://slack.com/api/conversations.history",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    params={"channel": WAR_ROOM_CHANNEL, "limit": arguments.get("limit", 20)}
                ) as resp:
                    return [TextContent(type="text", text=json.dumps(await resp.json()))]
        
        elif name == "mcp_create":
            result = await mcp_create_from_spec(
                name=arguments.get("name"),
                description=arguments.get("description"),
                tools=arguments.get("tools", []),
                owner=arguments.get("owner_worker_id")
            )
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "mcp_list":
            result = await mcp_list_all(status=arguments.get("status"))
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "mcp_status":
            result = await mcp_get_status(mcp_id=arguments.get("mcp_id"))
            return [TextContent(type="text", text=json.dumps(result))]
        
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    except Exception as e:
        logger.exception(f"Error in {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# SSE Transport
sse_transport = SseServerTransport("/messages")


def check_auth(scope) -> bool:
    query_string = scope.get("query_string", b"").decode()
    params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
    if params.get("token") == MCP_AUTH_TOKEN:
        return True
    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    return auth.startswith("Bearer ") and auth[7:] == MCP_AUTH_TOKEN


async def send_response(send, status: int, body: bytes, content_type: bytes = b"application/json", extra_headers=None):
    headers = [
        [b"content-type", content_type],
        [b"access-control-allow-origin", b"*"],
        [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
        [b"access-control-allow-headers", b"*"],
    ]
    if extra_headers:
        headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    
    path = scope["path"]
    method = scope["method"]
    
    logger.info(f"{method} {path}")
    
    # CORS
    if method == "OPTIONS":
        await send_response(send, 204, b"", extra_headers=[[b"access-control-max-age", b"86400"]])
        return
    
    # Health
    if path == "/health":
        await send_response(send, 200, json.dumps({"status": "healthy", "tools": 8}).encode())
        return
    
    # SSE - handle /mcp/sse OR just /sse OR root with token
    if path in ("/mcp/sse", "/sse") and method == "GET":
        if not check_auth(scope):
            await send_response(send, 401, b'{"error":"Unauthorized"}')
            return
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
        return
    
    # Messages
    if path == "/messages" and method == "POST":
        await sse_transport.handle_post_message(scope, receive, send)
        return
    
    # Root with token query param - serve SSE
    if path == "/" and method == "GET":
        query_string = scope.get("query_string", b"").decode()
        if "token=" in query_string:
            if not check_auth(scope):
                await send_response(send, 401, b'{"error":"Unauthorized"}')
                return
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
            return
        # No token - return info
        await send_response(send, 200, json.dumps({
            "name": "juggernaut-mcp",
            "version": "1.0",
            "endpoints": {
                "sse": "/mcp/sse?token=<token>",
                "health": "/health"
            }
        }).encode())
        return
    
    await send_response(send, 404, b'{"error":"Not found"}')


if __name__ == "__main__":
    logger.info(f"Starting MCP Server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
