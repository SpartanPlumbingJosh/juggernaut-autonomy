"""
JUGGERNAUT MCP Server - Full Toolset (v7)

SSE-based Model Context Protocol server with comprehensive tools:
- Database: Query/execute against Neon PostgreSQL
- GitHub: Full repo management (files, branches, PRs, merges)
- Railway: Deployment management and logs
- Vercel: Frontend deployment and domains
- Slack: War room messaging
- MCP Factory: Create new MCP servers

Required Environment Variables:
- MCP_AUTH_TOKEN: Auth token for MCP access
- DATABASE_URL: Neon PostgreSQL connection string
- GITHUB_TOKEN: GitHub personal access token
- GITHUB_REPO: GitHub repository (owner/repo format)
- RAILWAY_TOKEN: Railway API token
- RAILWAY_PROJECT_ID: Railway project ID
- RAILWAY_ENV_ID: Railway environment ID
- VERCEL_TOKEN: Vercel API token
- SLACK_BOT_TOKEN: Slack bot token
- WAR_ROOM_CHANNEL: Slack channel ID
"""
import asyncio
import base64
import json
import logging
import os
from typing import Any
from urllib.parse import urlencode

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

# =============================================================================
# CONFIGURATION (All from environment variables)
# =============================================================================

MCP_AUTH_TOKEN = os.environ.get('MCP_AUTH_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
WAR_ROOM_CHANNEL = os.environ.get('WAR_ROOM_CHANNEL', '')
PORT = int(os.environ.get('PORT', 8080))

# GitHub config
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')

# Railway config
RAILWAY_TOKEN = os.environ.get('RAILWAY_TOKEN', '')
RAILWAY_PROJECT_ID = os.environ.get('RAILWAY_PROJECT_ID', '')
RAILWAY_ENV_ID = os.environ.get('RAILWAY_ENV_ID', '')

# Vercel config
VERCEL_TOKEN = os.environ.get('VERCEL_TOKEN', '')

# Neon config
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"

# Create MCP Server
mcp = Server("juggernaut-mcp")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def execute_sql(query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute SQL against Neon database."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            NEON_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Neon-Connection-String": DATABASE_URL
            },
            json={"query": query, "params": params or []}
        ) as resp:
            return await resp.json()


async def github_api(method: str, endpoint: str, data: dict = None) -> dict[str, Any]:
    """Make GitHub API request."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"error": "GitHub not configured. Set GITHUB_TOKEN and GITHUB_REPO env vars."}
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/{endpoint}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}"
    }
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                return await resp.json()
        elif method == "PUT":
            async with session.put(url, headers=headers, json=data) as resp:
                return await resp.json()
        elif method == "PATCH":
            async with session.patch(url, headers=headers, json=data) as resp:
                return await resp.json()
        elif method == "DELETE":
            async with session.delete(url, headers=headers) as resp:
                if resp.status == 204:
                    return {"success": True}
                return await resp.json()


async def railway_graphql(query: str, variables: dict = None) -> dict[str, Any]:
    """Execute Railway GraphQL query."""
    if not RAILWAY_TOKEN:
        return {"error": "Railway not configured. Set RAILWAY_TOKEN env var."}
    
    url = "https://backboard.railway.com/graphql/v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RAILWAY_TOKEN}"
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            return await resp.json()


async def vercel_api(method: str, endpoint: str, data: dict = None) -> dict[str, Any]:
    """Make Vercel API request."""
    if not VERCEL_TOKEN:
        return {"error": "Vercel not configured. Set VERCEL_TOKEN env var."}
    
    url = f"https://api.vercel.com{endpoint}"
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                return await resp.json()


# =============================================================================
# MCP FACTORY HELPERS
# =============================================================================

async def mcp_create_from_spec(name: str, description: str, tools: list, owner: str = None) -> dict:
    """Create a new MCP from specification."""
    import uuid
    mcp_id = str(uuid.uuid4())
    auth_token = str(uuid.uuid4()).replace("-", "")[:32]
    
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
            "status": "registered"
        }
    return {"error": "Failed to register MCP"}


async def mcp_list_all(status: str = None) -> list:
    """List all registered MCPs."""
    where = f"WHERE status = '{status}'" if status else ""
    sql = f"SELECT id, name, description, status, endpoint_url, health_status, created_at FROM mcp_registry {where} ORDER BY created_at DESC"
    result = await execute_sql(sql)
    return result.get("rows", [])


async def mcp_get_status(mcp_id: str) -> dict:
    """Get status of a specific MCP."""
    sql = f"SELECT * FROM mcp_registry WHERE id = '{mcp_id}' OR name = '{mcp_id}'"
    result = await execute_sql(sql)
    if result.get("rows"):
        return result["rows"][0]
    return {"error": "MCP not found"}


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # Database Tools
        Tool(name="hq_query", 
             description="Query governance database. Types: workers.all, workers.active, tasks.pending, tasks.recent, schema.tables, OR pass raw SQL",
             inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
        
        Tool(name="hq_execute", 
             description="Execute governance actions. Actions: task.create, task.update, task.complete",
             inputSchema={"type": "object", "properties": {"action": {"type": "string"}, "params": {"type": "object"}}, "required": ["action"]}),
        
        Tool(name="sql_query",
             description="Execute raw SQL query against the database",
             inputSchema={"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}),
        
        # GitHub Tools
        Tool(name="github_get_file",
             description="Get file contents from GitHub repo",
             inputSchema={"type": "object", "properties": {
                 "path": {"type": "string", "description": "File path in repo"},
                 "branch": {"type": "string", "description": "Branch name (default: main)"}
             }, "required": ["path"]}),
        
        Tool(name="github_put_file",
             description="Create or update a file in GitHub repo",
             inputSchema={"type": "object", "properties": {
                 "path": {"type": "string", "description": "File path in repo"},
                 "content": {"type": "string", "description": "File content"},
                 "message": {"type": "string", "description": "Commit message"},
                 "branch": {"type": "string", "description": "Branch name"},
                 "sha": {"type": "string", "description": "File SHA for updates (omit for new files)"}
             }, "required": ["path", "content", "message", "branch"]}),
        
        Tool(name="github_list_files",
             description="List files in a directory",
             inputSchema={"type": "object", "properties": {
                 "path": {"type": "string", "description": "Directory path (default: root)"},
                 "branch": {"type": "string", "description": "Branch name (default: main)"}
             }}),
        
        Tool(name="github_create_branch",
             description="Create a new branch from main",
             inputSchema={"type": "object", "properties": {
                 "branch_name": {"type": "string", "description": "New branch name"},
                 "from_branch": {"type": "string", "description": "Source branch (default: main)"}
             }, "required": ["branch_name"]}),
        
        Tool(name="github_create_pr",
             description="Create a pull request",
             inputSchema={"type": "object", "properties": {
                 "title": {"type": "string"},
                 "body": {"type": "string"},
                 "head": {"type": "string", "description": "Branch with changes"},
                 "base": {"type": "string", "description": "Target branch (default: main)"}
             }, "required": ["title", "head"]}),
        
        Tool(name="github_merge_pr",
             description="Merge a pull request",
             inputSchema={"type": "object", "properties": {
                 "pr_number": {"type": "integer"},
                 "merge_method": {"type": "string", "description": "merge, squash, or rebase (default: squash)"}
             }, "required": ["pr_number"]}),
        
        Tool(name="github_get_pr",
             description="Get pull request details",
             inputSchema={"type": "object", "properties": {
                 "pr_number": {"type": "integer"}
             }, "required": ["pr_number"]}),
        
        Tool(name="github_list_prs",
             description="List pull requests",
             inputSchema={"type": "object", "properties": {
                 "state": {"type": "string", "description": "open, closed, or all (default: open)"}
             }}),
        
        # Railway Tools
        Tool(name="railway_list_services",
             description="List all services in the Railway project",
             inputSchema={"type": "object", "properties": {}}),
        
        Tool(name="railway_get_deployments",
             description="Get recent deployments for a service",
             inputSchema={"type": "object", "properties": {
                 "service_id": {"type": "string", "description": "Service ID (optional, gets all if omitted)"},
                 "limit": {"type": "integer", "description": "Number of deployments (default: 5)"}
             }}),
        
        Tool(name="railway_get_logs",
             description="Get deployment logs",
             inputSchema={"type": "object", "properties": {
                 "deployment_id": {"type": "string"},
                 "limit": {"type": "integer", "description": "Number of log lines (default: 100)"}
             }, "required": ["deployment_id"]}),
        
        Tool(name="railway_redeploy",
             description="Trigger a redeployment of a service",
             inputSchema={"type": "object", "properties": {
                 "service_id": {"type": "string"}
             }, "required": ["service_id"]}),
        
        Tool(name="railway_set_env",
             description="Set environment variable for a service",
             inputSchema={"type": "object", "properties": {
                 "service_id": {"type": "string"},
                 "name": {"type": "string"},
                 "value": {"type": "string"}
             }, "required": ["service_id", "name", "value"]}),
        
        # Vercel Tools
        Tool(name="vercel_list_deployments",
             description="List recent Vercel deployments",
             inputSchema={"type": "object", "properties": {
                 "limit": {"type": "integer", "description": "Number of deployments (default: 10)"}
             }}),
        
        Tool(name="vercel_get_deployment",
             description="Get deployment details",
             inputSchema={"type": "object", "properties": {
                 "deployment_id": {"type": "string"}
             }, "required": ["deployment_id"]}),
        
        Tool(name="vercel_check_domain",
             description="Check if a domain is available",
             inputSchema={"type": "object", "properties": {
                 "domain": {"type": "string"}
             }, "required": ["domain"]}),
        
        # Slack Tools
        Tool(name="war_room_post",
             description="Post message to Slack #war-room",
             inputSchema={"type": "object", "properties": {
                 "bot": {"type": "string", "description": "Bot name: otto, devin, or juggernaut"},
                 "message": {"type": "string"}
             }, "required": ["bot", "message"]}),
        
        Tool(name="war_room_history",
             description="Get recent #war-room messages",
             inputSchema={"type": "object", "properties": {
                 "limit": {"type": "integer", "description": "Number of messages (default: 20)"}
             }}),
        
        # MCP Factory Tools
        Tool(name="mcp_create",
             description="Create a new MCP server definition",
             inputSchema={"type": "object", "properties": {
                 "name": {"type": "string"},
                 "description": {"type": "string"},
                 "tools": {"type": "array"},
                 "owner_worker_id": {"type": "string"}
             }, "required": ["name", "description", "tools"]}),
        
        Tool(name="mcp_list",
             description="List all registered MCP servers",
             inputSchema={"type": "object", "properties": {
                 "status": {"type": "string"}
             }}),
        
        Tool(name="mcp_status",
             description="Get status of a specific MCP",
             inputSchema={"type": "object", "properties": {
                 "mcp_id": {"type": "string"}
             }, "required": ["mcp_id"]}),
        
        # Generic fetch
        Tool(name="fetch_url",
             description="Fetch content from any URL",
             inputSchema={"type": "object", "properties": {
                 "url": {"type": "string"},
                 "method": {"type": "string", "description": "GET, POST, PUT, DELETE"},
                 "headers": {"type": "object"},
                 "body": {"type": "string"},
                 "timeout": {"type": "integer"}
             }, "required": ["url"]})
    ]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info(f"Tool call: {name}")
    try:
        # ---------------------------------------------------------------------
        # DATABASE TOOLS
        # ---------------------------------------------------------------------
        if name == "hq_query":
            query_type = arguments.get("query", "")
            queries = {
                "workers.all": "SELECT * FROM workers ORDER BY created_at DESC",
                "workers.active": "SELECT * FROM workers WHERE status = 'active'",
                "tasks.pending": "SELECT id, title, priority, task_type, created_at FROM governance_tasks WHERE status = 'pending' ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at LIMIT 20",
                "tasks.recent": "SELECT id, title, status, priority, created_at FROM governance_tasks ORDER BY created_at DESC LIMIT 20",
                "schema.tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            }
            sql = queries.get(query_type, query_type)  # Allow raw SQL if not a preset
            result = await execute_sql(sql)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "hq_execute":
            action = arguments.get("action")
            params = arguments.get("params", {})
            
            if action == "task.create":
                result = await execute_sql(
                    "INSERT INTO governance_tasks (title, description, priority, task_type, assigned_worker, status) VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id",
                    [params.get("title"), params.get("description"), params.get("priority", "medium"), 
                     params.get("task_type", "code"), params.get("assigned_worker", "claude-chat")]
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "task.update":
                task_id = params.get("id")
                updates = []
                values = []
                for key in ["status", "assigned_worker", "completion_evidence"]:
                    if key in params:
                        updates.append(f"{key} = ${len(values)+1}")
                        values.append(params[key])
                if updates:
                    values.append(task_id)
                    sql = f"UPDATE governance_tasks SET {', '.join(updates)} WHERE id = ${len(values)}"
                    result = await execute_sql(sql, values)
                    return [TextContent(type="text", text=json.dumps(result))]
            
            elif action == "task.complete":
                result = await execute_sql(
                    "UPDATE governance_tasks SET status = 'completed', completed_at = NOW(), completion_evidence = $1 WHERE id = $2",
                    [params.get("evidence", ""), params.get("id")]
                )
                return [TextContent(type="text", text=json.dumps(result))]
            
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown action: {action}"}))]
        
        elif name == "sql_query":
            result = await execute_sql(arguments.get("sql"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ---------------------------------------------------------------------
        # GITHUB TOOLS
        # ---------------------------------------------------------------------
        elif name == "github_get_file":
            path = arguments.get("path")
            branch = arguments.get("branch", "main")
            result = await github_api("GET", f"contents/{path}?ref={branch}")
            if "content" in result:
                result["decoded_content"] = base64.b64decode(result["content"]).decode("utf-8")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_put_file":
            path = arguments.get("path")
            content = base64.b64encode(arguments.get("content").encode()).decode()
            data = {
                "message": arguments.get("message"),
                "content": content,
                "branch": arguments.get("branch")
            }
            if arguments.get("sha"):
                data["sha"] = arguments.get("sha")
            result = await github_api("PUT", f"contents/{path}", data)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_list_files":
            path = arguments.get("path", "")
            branch = arguments.get("branch", "main")
            result = await github_api("GET", f"contents/{path}?ref={branch}")
            if isinstance(result, list):
                # Simplify output
                files = [{"name": f["name"], "type": f["type"], "path": f["path"]} for f in result]
                return [TextContent(type="text", text=json.dumps(files))]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_create_branch":
            branch_name = arguments.get("branch_name")
            from_branch = arguments.get("from_branch", "main")
            # Get SHA of source branch
            ref_result = await github_api("GET", f"git/ref/heads/{from_branch}")
            sha = ref_result.get("object", {}).get("sha")
            if not sha:
                return [TextContent(type="text", text=json.dumps({"error": "Could not get source branch SHA"}))]
            # Create new branch
            result = await github_api("POST", "git/refs", {
                "ref": f"refs/heads/{branch_name}",
                "sha": sha
            })
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_create_pr":
            result = await github_api("POST", "pulls", {
                "title": arguments.get("title"),
                "body": arguments.get("body", ""),
                "head": arguments.get("head"),
                "base": arguments.get("base", "main")
            })
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_merge_pr":
            pr_number = arguments.get("pr_number")
            merge_method = arguments.get("merge_method", "squash")
            result = await github_api("PUT", f"pulls/{pr_number}/merge", {
                "merge_method": merge_method
            })
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_get_pr":
            pr_number = arguments.get("pr_number")
            result = await github_api("GET", f"pulls/{pr_number}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_list_prs":
            state = arguments.get("state", "open")
            result = await github_api("GET", f"pulls?state={state}")
            if isinstance(result, list):
                prs = [{"number": p["number"], "title": p["title"], "state": p["state"], 
                        "head": p["head"]["ref"], "user": p["user"]["login"]} for p in result]
                return [TextContent(type="text", text=json.dumps(prs))]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ---------------------------------------------------------------------
        # RAILWAY TOOLS
        # ---------------------------------------------------------------------
        elif name == "railway_list_services":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            query = f"""
            query {{
                project(id: "{RAILWAY_PROJECT_ID}") {{
                    services {{
                        edges {{
                            node {{
                                id
                                name
                                updatedAt
                            }}
                        }}
                    }}
                }}
            }}
            """
            result = await railway_graphql(query)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_get_deployments":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            service_filter = ""
            if arguments.get("service_id"):
                service_filter = f', serviceId: "{arguments.get("service_id")}"'
            limit = arguments.get("limit", 5)
            query = f"""
            query {{
                deployments(first: {limit}, input: {{ projectId: "{RAILWAY_PROJECT_ID}"{service_filter} }}) {{
                    edges {{
                        node {{
                            id
                            status
                            staticUrl
                            createdAt
                            service {{
                                name
                            }}
                        }}
                    }}
                }}
            }}
            """
            result = await railway_graphql(query)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_get_logs":
            deployment_id = arguments.get("deployment_id")
            limit = arguments.get("limit", 100)
            query = f"""
            query {{
                deploymentLogs(deploymentId: "{deployment_id}", limit: {limit}) {{
                    message
                    timestamp
                }}
            }}
            """
            result = await railway_graphql(query)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_redeploy":
            if not RAILWAY_ENV_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_ENV_ID not set"}))]
            service_id = arguments.get("service_id")
            query = """
            mutation ServiceRedeploy($input: ServiceRedeployInput!) {
                serviceRedeploy(input: $input) {
                    id
                    status
                }
            }
            """
            variables = {
                "input": {
                    "serviceId": service_id,
                    "environmentId": RAILWAY_ENV_ID
                }
            }
            result = await railway_graphql(query, variables)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_set_env":
            if not RAILWAY_ENV_ID or not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "Railway env vars not set"}))]
            query = """
            mutation VariableUpsert($input: VariableUpsertInput!) {
                variableUpsert(input: $input)
            }
            """
            variables = {
                "input": {
                    "name": arguments.get("name"),
                    "value": arguments.get("value"),
                    "serviceId": arguments.get("service_id"),
                    "environmentId": RAILWAY_ENV_ID,
                    "projectId": RAILWAY_PROJECT_ID
                }
            }
            result = await railway_graphql(query, variables)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ---------------------------------------------------------------------
        # VERCEL TOOLS
        # ---------------------------------------------------------------------
        elif name == "vercel_list_deployments":
            limit = arguments.get("limit", 10)
            result = await vercel_api("GET", f"/v6/deployments?limit={limit}")
            if "deployments" in result:
                deps = [{"uid": d["uid"], "name": d.get("name"), "state": d["state"], 
                         "url": d.get("url"), "created": d["created"]} for d in result["deployments"]]
                return [TextContent(type="text", text=json.dumps(deps))]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "vercel_get_deployment":
            deployment_id = arguments.get("deployment_id")
            result = await vercel_api("GET", f"/v13/deployments/{deployment_id}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "vercel_check_domain":
            domain = arguments.get("domain")
            result = await vercel_api("GET", f"/v4/domains/status?name={domain}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ---------------------------------------------------------------------
        # SLACK TOOLS
        # ---------------------------------------------------------------------
        elif name == "war_room_post":
            if not SLACK_BOT_TOKEN or not WAR_ROOM_CHANNEL:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            bot = arguments.get("bot", "juggernaut")
            message = arguments.get("message")
            bot_names = {"otto": "Otto", "devin": "Devin", "juggernaut": "JUGGERNAUT"}
            username = bot_names.get(bot.lower(), "JUGGERNAUT")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json={"channel": WAR_ROOM_CHANNEL, "text": message, "username": username}
                ) as resp:
                    return [TextContent(type="text", text=json.dumps(await resp.json()))]
        
        elif name == "war_room_history":
            if not SLACK_BOT_TOKEN or not WAR_ROOM_CHANNEL:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            limit = arguments.get("limit", 20)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://slack.com/api/conversations.history",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    params={"channel": WAR_ROOM_CHANNEL, "limit": limit}
                ) as resp:
                    return [TextContent(type="text", text=json.dumps(await resp.json()))]
        
        # ---------------------------------------------------------------------
        # MCP FACTORY TOOLS
        # ---------------------------------------------------------------------
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
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "mcp_status":
            result = await mcp_get_status(mcp_id=arguments.get("mcp_id"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ---------------------------------------------------------------------
        # GENERIC FETCH
        # ---------------------------------------------------------------------
        elif name == "fetch_url":
            url = arguments.get("url")
            method = arguments.get("method", "GET").upper()
            headers = arguments.get("headers", {})
            body = arguments.get("body")
            timeout = arguments.get("timeout", 30)
            
            async with aiohttp.ClientSession() as session:
                kwargs = {"headers": headers, "timeout": aiohttp.ClientTimeout(total=timeout)}
                if body:
                    if isinstance(body, str):
                        try:
                            kwargs["json"] = json.loads(body)
                        except json.JSONDecodeError:
                            kwargs["data"] = body
                    else:
                        kwargs["json"] = body
                
                async with session.request(method, url, **kwargs) as resp:
                    try:
                        result = await resp.json()
                    except:
                        result = {"text": await resp.text(), "status": resp.status}
                    return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    
    except Exception as e:
        logger.exception(f"Error in {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# =============================================================================
# SSE TRANSPORT
# =============================================================================

sse_transport = SseServerTransport("/messages")


def check_auth(scope) -> bool:
    """Check authentication from query params or headers."""
    query_string = scope.get("query_string", b"").decode()
    params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
    if params.get("token") == MCP_AUTH_TOKEN:
        return True
    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    return auth.startswith("Bearer ") and auth[7:] == MCP_AUTH_TOKEN


async def send_response(send, status: int, body: bytes, content_type: bytes = b"application/json", extra_headers=None):
    """Send HTTP response."""
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
    """Main ASGI application."""
    if scope["type"] != "http":
        return
    
    path = scope["path"]
    method = scope["method"]
    
    logger.info(f"{method} {path}")
    
    # CORS preflight
    if method == "OPTIONS":
        await send_response(send, 204, b"", extra_headers=[[b"access-control-max-age", b"86400"]])
        return
    
    # Health check
    if path == "/health":
        tool_count = len(await list_tools())
        await send_response(send, 200, json.dumps({
            "status": "healthy", 
            "tools": tool_count,
            "version": "7.0",
            "configured": {
                "github": bool(GITHUB_TOKEN),
                "railway": bool(RAILWAY_TOKEN),
                "vercel": bool(VERCEL_TOKEN),
                "slack": bool(SLACK_BOT_TOKEN),
                "database": bool(DATABASE_URL)
            }
        }).encode())
        return
    
    # SSE endpoints
    if path in ("/mcp/sse", "/sse") and method == "GET":
        if not check_auth(scope):
            await send_response(send, 401, b'{"error":"Unauthorized"}')
            return
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
        return
    
    # Messages endpoint
    if path == "/messages" and method == "POST":
        await sse_transport.handle_post_message(scope, receive, send)
        return
    
    # Root with token
    if path == "/" and method == "GET":
        query_string = scope.get("query_string", b"").decode()
        if "token=" in query_string:
            if not check_auth(scope):
                await send_response(send, 401, b'{"error":"Unauthorized"}')
                return
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
            return
        # Info response
        tool_count = len(await list_tools())
        await send_response(send, 200, json.dumps({
            "name": "juggernaut-mcp",
            "version": "7.0",
            "tools": tool_count,
            "endpoints": {
                "sse": "/mcp/sse?token=<token>",
                "health": "/health"
            }
        }).encode())
        return
    
    await send_response(send, 404, b'{"error":"Not found"}')


if __name__ == "__main__":
    logger.info(f"Starting JUGGERNAUT MCP Server v7 on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
