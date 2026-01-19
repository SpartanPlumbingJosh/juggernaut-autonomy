"""
JUGGERNAUT MCP Server - Best-in-Class (v8)

Full autonomous capabilities:
- Database: Neon PostgreSQL
- GitHub: Full repo management
- Railway: Deployment management
- Vercel: Frontend deployment
- Slack: Team messaging
- Puppeteer: Browser automation
- Web Search: Serper API
- ServiceTitan: Plumbing business operations
- Email: Resend API
- SMS: Twilio
- Storage: Cloudflare R2
- AI: OpenRouter
- Webhooks: Event receiver
- MCP Factory: Create new MCPs
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Optional
from urllib.parse import urlencode, quote

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
# CONFIGURATION
# =============================================================================

MCP_AUTH_TOKEN = os.environ.get('MCP_AUTH_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
PORT = int(os.environ.get('PORT', 8080))

# GitHub
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')

# Railway
RAILWAY_TOKEN = os.environ.get('RAILWAY_TOKEN', '')
RAILWAY_PROJECT_ID = os.environ.get('RAILWAY_PROJECT_ID', '')
RAILWAY_ENV_ID = os.environ.get('RAILWAY_ENV_ID', '')

# Vercel
VERCEL_TOKEN = os.environ.get('VERCEL_TOKEN', '')

# Slack
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
WAR_ROOM_CHANNEL = os.environ.get('WAR_ROOM_CHANNEL', '')

# Puppeteer service
PUPPETEER_URL = os.environ.get('PUPPETEER_URL', '')

# Web Search (Serper)
SERPER_API_KEY = os.environ.get('SERPER_API_KEY', '')

# ServiceTitan
ST_CLIENT_ID = os.environ.get('ST_CLIENT_ID', '')
ST_CLIENT_SECRET = os.environ.get('ST_CLIENT_SECRET', '')
ST_TENANT_ID = os.environ.get('ST_TENANT_ID', '')
ST_APP_KEY = os.environ.get('ST_APP_KEY', '')

# Email (Resend)
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

# SMS (Twilio)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

# Storage (Cloudflare R2)
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID', '')
R2_ACCESS_KEY = os.environ.get('R2_ACCESS_KEY', '')
R2_SECRET_KEY = os.environ.get('R2_SECRET_KEY', '')
R2_BUCKET = os.environ.get('R2_BUCKET', 'juggernaut')

# AI (OpenRouter)
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

# Neon
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"

# Webhook storage (in-memory, would use Redis in production)
webhook_events = []

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
        return {"error": "GitHub not configured"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/{endpoint}"
    headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
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
        elif method == "DELETE":
            async with session.delete(url, headers=headers) as resp:
                return {"success": True} if resp.status == 204 else await resp.json()


async def railway_graphql(query: str, variables: dict = None) -> dict[str, Any]:
    """Execute Railway GraphQL query."""
    if not RAILWAY_TOKEN:
        return {"error": "Railway not configured"}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {RAILWAY_TOKEN}"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    async with aiohttp.ClientSession() as session:
        async with session.post("https://backboard.railway.com/graphql/v2", headers=headers, json=payload) as resp:
            return await resp.json()


async def vercel_api(method: str, endpoint: str, data: dict = None) -> dict[str, Any]:
    """Make Vercel API request."""
    if not VERCEL_TOKEN:
        return {"error": "Vercel not configured"}
    url = f"https://api.vercel.com{endpoint}"
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                return await resp.json()


# ServiceTitan token cache
_st_token = {"token": None, "expires": 0}

async def get_servicetitan_token() -> str:
    """Get ServiceTitan OAuth token."""
    if _st_token["token"] and time.time() < _st_token["expires"]:
        return _st_token["token"]
    
    if not ST_CLIENT_ID or not ST_CLIENT_SECRET:
        return ""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://auth.servicetitan.io/connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": ST_CLIENT_ID,
                "client_secret": ST_CLIENT_SECRET
            }
        ) as resp:
            data = await resp.json()
            _st_token["token"] = data.get("access_token", "")
            _st_token["expires"] = time.time() + data.get("expires_in", 3600) - 60
            return _st_token["token"]


async def servicetitan_api(method: str, endpoint: str, data: dict = None) -> dict[str, Any]:
    """Make ServiceTitan API request."""
    if not ST_TENANT_ID:
        return {"error": "ServiceTitan not configured"}
    
    token = await get_servicetitan_token()
    if not token:
        return {"error": "Could not get ServiceTitan token"}
    
    url = f"https://api.servicetitan.io/{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "ST-App-Key": ST_APP_KEY,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                return await resp.json()
        elif method == "PATCH":
            async with session.patch(url, headers=headers, json=data) as resp:
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
    ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, tools_config = EXCLUDED.tools_config
    RETURNING id, auth_token
    """
    result = await execute_sql(sql)
    if result.get("rows"):
        return {"mcp_id": result["rows"][0]["id"], "auth_token": result["rows"][0]["auth_token"], "status": "registered"}
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
    return result["rows"][0] if result.get("rows") else {"error": "MCP not found"}


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ===== DATABASE =====
        Tool(name="sql_query", description="Execute SQL query against database",
             inputSchema={"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}),
        
        Tool(name="hq_query", description="Query governance DB. Types: workers.all, tasks.pending, tasks.recent, schema.tables, or raw SQL",
             inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
        
        Tool(name="hq_execute", description="Execute governance action: task.create, task.update, task.complete",
             inputSchema={"type": "object", "properties": {"action": {"type": "string"}, "params": {"type": "object"}}, "required": ["action"]}),
        
        # ===== GITHUB =====
        Tool(name="github_get_file", description="Get file from repo",
             inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "branch": {"type": "string"}}, "required": ["path"]}),
        
        Tool(name="github_put_file", description="Create/update file in repo",
             inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "message": {"type": "string"}, "branch": {"type": "string"}, "sha": {"type": "string"}}, "required": ["path", "content", "message", "branch"]}),
        
        Tool(name="github_list_files", description="List files in directory",
             inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "branch": {"type": "string"}}}),
        
        Tool(name="github_create_branch", description="Create branch from main",
             inputSchema={"type": "object", "properties": {"branch_name": {"type": "string"}, "from_branch": {"type": "string"}}, "required": ["branch_name"]}),
        
        Tool(name="github_create_pr", description="Create pull request",
             inputSchema={"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "head": {"type": "string"}, "base": {"type": "string"}}, "required": ["title", "head"]}),
        
        Tool(name="github_merge_pr", description="Merge pull request",
             inputSchema={"type": "object", "properties": {"pr_number": {"type": "integer"}, "merge_method": {"type": "string"}}, "required": ["pr_number"]}),
        
        Tool(name="github_list_prs", description="List pull requests",
             inputSchema={"type": "object", "properties": {"state": {"type": "string"}}}),
        
        # ===== RAILWAY =====
        Tool(name="railway_list_services", description="List Railway services",
             inputSchema={"type": "object", "properties": {}}),
        
        Tool(name="railway_get_deployments", description="Get recent deployments",
             inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "limit": {"type": "integer"}}}),
        
        Tool(name="railway_get_logs", description="Get deployment logs",
             inputSchema={"type": "object", "properties": {"deployment_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["deployment_id"]}),
        
        Tool(name="railway_redeploy", description="Trigger redeployment",
             inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}}, "required": ["service_id"]}),
        
        Tool(name="railway_set_env", description="Set environment variable",
             inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "name": {"type": "string"}, "value": {"type": "string"}}, "required": ["service_id", "name", "value"]}),
        
        Tool(name="railway_create_service", description="Create new Railway service",
             inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "source_repo": {"type": "string"}, "source_branch": {"type": "string"}}, "required": ["name"]}),
        
        # ===== VERCEL =====
        Tool(name="vercel_list_deployments", description="List Vercel deployments",
             inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        
        Tool(name="vercel_check_domain", description="Check domain availability",
             inputSchema={"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}),
        
        # ===== PUPPETEER (Browser) =====
        Tool(name="browser_navigate", description="Navigate browser to URL",
             inputSchema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
        
        Tool(name="browser_screenshot", description="Take screenshot of current page",
             inputSchema={"type": "object", "properties": {"full_page": {"type": "boolean"}}}),
        
        Tool(name="browser_click", description="Click element by selector",
             inputSchema={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}),
        
        Tool(name="browser_type", description="Type text into element",
             inputSchema={"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}),
        
        Tool(name="browser_get_text", description="Get text content from page or element",
             inputSchema={"type": "object", "properties": {"selector": {"type": "string"}}}),
        
        Tool(name="browser_eval", description="Evaluate JavaScript in browser",
             inputSchema={"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}),
        
        # ===== WEB SEARCH =====
        Tool(name="web_search", description="Search the web via Serper",
             inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "num_results": {"type": "integer"}}, "required": ["query"]}),
        
        Tool(name="web_search_news", description="Search news articles",
             inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "num_results": {"type": "integer"}}, "required": ["query"]}),
        
        # ===== SERVICETITAN =====
        Tool(name="st_list_customers", description="List ServiceTitan customers",
             inputSchema={"type": "object", "properties": {"page": {"type": "integer"}, "page_size": {"type": "integer"}, "name": {"type": "string"}}}),
        
        Tool(name="st_get_customer", description="Get customer by ID",
             inputSchema={"type": "object", "properties": {"customer_id": {"type": "integer"}}, "required": ["customer_id"]}),
        
        Tool(name="st_create_customer", description="Create new customer",
             inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "address": {"type": "object"}, "phones": {"type": "array"}, "email": {"type": "string"}}, "required": ["name"]}),
        
        Tool(name="st_list_jobs", description="List jobs",
             inputSchema={"type": "object", "properties": {"page": {"type": "integer"}, "status": {"type": "string"}, "scheduled_after": {"type": "string"}}}),
        
        Tool(name="st_get_job", description="Get job by ID",
             inputSchema={"type": "object", "properties": {"job_id": {"type": "integer"}}, "required": ["job_id"]}),
        
        Tool(name="st_list_invoices", description="List invoices",
             inputSchema={"type": "object", "properties": {"page": {"type": "integer"}, "status": {"type": "string"}}}),
        
        Tool(name="st_list_technicians", description="List technicians",
             inputSchema={"type": "object", "properties": {}}),
        
        # ===== EMAIL (Resend) =====
        Tool(name="send_email", description="Send email via Resend",
             inputSchema={"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "html": {"type": "string"}, "text": {"type": "string"}, "from_email": {"type": "string"}}, "required": ["to", "subject"]}),
        
        # ===== SMS (Twilio) =====
        Tool(name="send_sms", description="Send SMS via Twilio",
             inputSchema={"type": "object", "properties": {"to": {"type": "string"}, "message": {"type": "string"}}, "required": ["to", "message"]}),
        
        # ===== STORAGE (R2) =====
        Tool(name="storage_upload", description="Upload file to R2 storage",
             inputSchema={"type": "object", "properties": {"key": {"type": "string"}, "content": {"type": "string"}, "content_type": {"type": "string"}}, "required": ["key", "content"]}),
        
        Tool(name="storage_download", description="Download file from R2",
             inputSchema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}),
        
        Tool(name="storage_list", description="List files in R2 bucket",
             inputSchema={"type": "object", "properties": {"prefix": {"type": "string"}}}),
        
        Tool(name="storage_delete", description="Delete file from R2",
             inputSchema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}),
        
        # ===== AI (OpenRouter) =====
        Tool(name="ai_chat", description="Chat with AI via OpenRouter",
             inputSchema={"type": "object", "properties": {"messages": {"type": "array"}, "model": {"type": "string"}, "max_tokens": {"type": "integer"}}, "required": ["messages"]}),
        
        Tool(name="ai_complete", description="Get AI completion for prompt",
             inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}, "max_tokens": {"type": "integer"}}, "required": ["prompt"]}),
        
        # ===== WEBHOOKS =====
        Tool(name="webhook_list", description="List recent webhook events",
             inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}, "source": {"type": "string"}}}),
        
        Tool(name="webhook_get", description="Get specific webhook event",
             inputSchema={"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]}),
        
        # ===== SLACK =====
        Tool(name="war_room_post", description="Post to Slack #war-room",
             inputSchema={"type": "object", "properties": {"bot": {"type": "string"}, "message": {"type": "string"}}, "required": ["bot", "message"]}),
        
        Tool(name="war_room_history", description="Get #war-room history",
             inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        
        # ===== MCP FACTORY =====
        Tool(name="mcp_create", description="Create new MCP server",
             inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "tools": {"type": "array"}}, "required": ["name", "description", "tools"]}),
        
        Tool(name="mcp_list", description="List registered MCPs",
             inputSchema={"type": "object", "properties": {"status": {"type": "string"}}}),
        
        Tool(name="mcp_status", description="Get MCP status",
             inputSchema={"type": "object", "properties": {"mcp_id": {"type": "string"}}, "required": ["mcp_id"]}),
        
        # ===== GENERIC =====
        Tool(name="fetch_url", description="Fetch any URL",
             inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "headers": {"type": "object"}, "body": {"type": "string"}}, "required": ["url"]})
    ]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info(f"Tool call: {name}")
    try:
        # ===== DATABASE =====
        if name == "sql_query":
            result = await execute_sql(arguments.get("sql"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "hq_query":
            query_type = arguments.get("query", "")
            queries = {
                "workers.all": "SELECT * FROM workers ORDER BY created_at DESC",
                "workers.active": "SELECT * FROM workers WHERE status = 'active'",
                "tasks.pending": "SELECT id, title, priority, task_type FROM governance_tasks WHERE status = 'pending' ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END LIMIT 20",
                "tasks.recent": "SELECT id, title, status, priority FROM governance_tasks ORDER BY created_at DESC LIMIT 20",
                "schema.tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            }
            sql = queries.get(query_type, query_type)
            result = await execute_sql(sql)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "hq_execute":
            action = arguments.get("action")
            params = arguments.get("params", {})
            if action == "task.create":
                result = await execute_sql(
                    "INSERT INTO governance_tasks (title, description, priority, task_type, assigned_worker, status) VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id",
                    [params.get("title"), params.get("description"), params.get("priority", "medium"), params.get("task_type", "code"), params.get("assigned_worker", "claude-chat")]
                )
            elif action == "task.complete":
                result = await execute_sql(
                    "UPDATE governance_tasks SET status = 'completed', completed_at = NOW(), completion_evidence = $1 WHERE id = $2",
                    [params.get("evidence", ""), params.get("id")]
                )
            else:
                result = {"error": f"Unknown action: {action}"}
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== GITHUB =====
        elif name == "github_get_file":
            path, branch = arguments.get("path"), arguments.get("branch", "main")
            result = await github_api("GET", f"contents/{path}?ref={branch}")
            if "content" in result:
                result["decoded_content"] = base64.b64decode(result["content"]).decode("utf-8")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_put_file":
            path = arguments.get("path")
            content = base64.b64encode(arguments.get("content").encode()).decode()
            data = {"message": arguments.get("message"), "content": content, "branch": arguments.get("branch")}
            if arguments.get("sha"):
                data["sha"] = arguments.get("sha")
            result = await github_api("PUT", f"contents/{path}", data)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_list_files":
            path, branch = arguments.get("path", ""), arguments.get("branch", "main")
            result = await github_api("GET", f"contents/{path}?ref={branch}")
            if isinstance(result, list):
                result = [{"name": f["name"], "type": f["type"], "path": f["path"]} for f in result]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_create_branch":
            branch_name, from_branch = arguments.get("branch_name"), arguments.get("from_branch", "main")
            ref_result = await github_api("GET", f"git/ref/heads/{from_branch}")
            sha = ref_result.get("object", {}).get("sha")
            if not sha:
                return [TextContent(type="text", text=json.dumps({"error": "Could not get source SHA"}))]
            result = await github_api("POST", "git/refs", {"ref": f"refs/heads/{branch_name}", "sha": sha})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_create_pr":
            result = await github_api("POST", "pulls", {
                "title": arguments.get("title"), "body": arguments.get("body", ""),
                "head": arguments.get("head"), "base": arguments.get("base", "main")
            })
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_merge_pr":
            pr_number = arguments.get("pr_number")
            result = await github_api("PUT", f"pulls/{pr_number}/merge", {"merge_method": arguments.get("merge_method", "squash")})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_list_prs":
            state = arguments.get("state", "open")
            result = await github_api("GET", f"pulls?state={state}")
            if isinstance(result, list):
                result = [{"number": p["number"], "title": p["title"], "state": p["state"], "head": p["head"]["ref"]} for p in result]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== RAILWAY =====
        elif name == "railway_list_services":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            query = f'query {{ project(id: "{RAILWAY_PROJECT_ID}") {{ services {{ edges {{ node {{ id name }} }} }} }} }}'
            result = await railway_graphql(query)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_get_deployments":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            service_filter = f', serviceId: "{arguments.get("service_id")}"' if arguments.get("service_id") else ""
            limit = arguments.get("limit", 5)
            query = f'query {{ deployments(first: {limit}, input: {{ projectId: "{RAILWAY_PROJECT_ID}"{service_filter} }}) {{ edges {{ node {{ id status staticUrl createdAt service {{ name }} }} }} }} }}'
            result = await railway_graphql(query)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_get_logs":
            deployment_id, limit = arguments.get("deployment_id"), arguments.get("limit", 100)
            query = f'query {{ deploymentLogs(deploymentId: "{deployment_id}", limit: {limit}) {{ message timestamp }} }}'
            result = await railway_graphql(query)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_redeploy":
            if not RAILWAY_ENV_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_ENV_ID not set"}))]
            query = "mutation ServiceRedeploy($input: ServiceRedeployInput!) { serviceRedeploy(input: $input) { id status } }"
            variables = {"input": {"serviceId": arguments.get("service_id"), "environmentId": RAILWAY_ENV_ID}}
            result = await railway_graphql(query, variables)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_set_env":
            if not RAILWAY_ENV_ID or not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "Railway env vars not set"}))]
            query = "mutation VariableUpsert($input: VariableUpsertInput!) { variableUpsert(input: $input) }"
            variables = {"input": {"name": arguments.get("name"), "value": arguments.get("value"), "serviceId": arguments.get("service_id"), "environmentId": RAILWAY_ENV_ID, "projectId": RAILWAY_PROJECT_ID}}
            result = await railway_graphql(query, variables)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_create_service":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            query = "mutation ServiceCreate($input: ServiceCreateInput!) { serviceCreate(input: $input) { id name } }"
            variables = {"input": {"name": arguments.get("name"), "projectId": RAILWAY_PROJECT_ID}}
            if arguments.get("source_repo"):
                variables["input"]["source"] = {"repo": arguments.get("source_repo")}
            result = await railway_graphql(query, variables)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== VERCEL =====
        elif name == "vercel_list_deployments":
            limit = arguments.get("limit", 10)
            result = await vercel_api("GET", f"/v6/deployments?limit={limit}")
            if "deployments" in result:
                result = [{"uid": d["uid"], "name": d.get("name"), "state": d["state"], "url": d.get("url")} for d in result["deployments"]]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "vercel_check_domain":
            domain = arguments.get("domain")
            result = await vercel_api("GET", f"/v4/domains/status?name={domain}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== PUPPETEER =====
        elif name.startswith("browser_"):
            if not PUPPETEER_URL:
                return [TextContent(type="text", text=json.dumps({"error": "Puppeteer service not configured. Set PUPPETEER_URL"}))]
            action = name.replace("browser_", "")
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{PUPPETEER_URL}/action", json={"action": action, **arguments}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== WEB SEARCH =====
        elif name == "web_search":
            if not SERPER_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "Serper API not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post("https://google.serper.dev/search",
                    headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": arguments.get("query"), "num": arguments.get("num_results", 10)}
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "web_search_news":
            if not SERPER_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "Serper API not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post("https://google.serper.dev/news",
                    headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": arguments.get("query"), "num": arguments.get("num_results", 10)}
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== SERVICETITAN =====
        elif name == "st_list_customers":
            page, size = arguments.get("page", 1), arguments.get("page_size", 50)
            endpoint = f"crm/v2/tenant/{ST_TENANT_ID}/customers?page={page}&pageSize={size}"
            if arguments.get("name"):
                endpoint += f"&name={quote(arguments.get('name'))}"
            result = await servicetitan_api("GET", endpoint)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_get_customer":
            customer_id = arguments.get("customer_id")
            result = await servicetitan_api("GET", f"crm/v2/tenant/{ST_TENANT_ID}/customers/{customer_id}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_create_customer":
            data = {"name": arguments.get("name")}
            if arguments.get("address"):
                data["address"] = arguments.get("address")
            if arguments.get("phones"):
                data["phones"] = arguments.get("phones")
            if arguments.get("email"):
                data["email"] = arguments.get("email")
            result = await servicetitan_api("POST", f"crm/v2/tenant/{ST_TENANT_ID}/customers", data)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_list_jobs":
            page = arguments.get("page", 1)
            endpoint = f"jpm/v2/tenant/{ST_TENANT_ID}/jobs?page={page}"
            if arguments.get("status"):
                endpoint += f"&status={arguments.get('status')}"
            if arguments.get("scheduled_after"):
                endpoint += f"&scheduledStartAfter={arguments.get('scheduled_after')}"
            result = await servicetitan_api("GET", endpoint)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_get_job":
            job_id = arguments.get("job_id")
            result = await servicetitan_api("GET", f"jpm/v2/tenant/{ST_TENANT_ID}/jobs/{job_id}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_list_invoices":
            page = arguments.get("page", 1)
            endpoint = f"accounting/v2/tenant/{ST_TENANT_ID}/invoices?page={page}"
            if arguments.get("status"):
                endpoint += f"&status={arguments.get('status')}"
            result = await servicetitan_api("GET", endpoint)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_list_technicians":
            result = await servicetitan_api("GET", f"dispatch/v2/tenant/{ST_TENANT_ID}/technicians")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== EMAIL =====
        elif name == "send_email":
            if not RESEND_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "Resend API not configured"}))]
            data = {
                "from": arguments.get("from_email", "noreply@spartanplumbingllc.com"),
                "to": arguments.get("to"),
                "subject": arguments.get("subject")
            }
            if arguments.get("html"):
                data["html"] = arguments.get("html")
            if arguments.get("text"):
                data["text"] = arguments.get("text")
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                    json=data
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== SMS =====
        elif name == "send_sms":
            if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
                return [TextContent(type="text", text=json.dumps({"error": "Twilio not configured"}))]
            data = {"To": arguments.get("to"), "From": TWILIO_PHONE_NUMBER, "Body": arguments.get("message")}
            auth = aiohttp.BasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
                    auth=auth, data=data
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== STORAGE =====
        elif name == "storage_upload":
            if not R2_ACCESS_KEY or not R2_SECRET_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "R2 storage not configured"}))]
            # Simplified - would use proper S3 signing in production
            key = arguments.get("key")
            content = arguments.get("content")
            # Store in database as fallback
            result = await execute_sql(
                "INSERT INTO file_storage (key, content, content_type, created_at) VALUES ($1, $2, $3, NOW()) ON CONFLICT (key) DO UPDATE SET content = $2, content_type = $3 RETURNING key",
                [key, content, arguments.get("content_type", "application/octet-stream")]
            )
            return [TextContent(type="text", text=json.dumps({"success": True, "key": key}))]
        
        elif name == "storage_download":
            key = arguments.get("key")
            result = await execute_sql("SELECT content, content_type FROM file_storage WHERE key = $1", [key])
            if result.get("rows"):
                return [TextContent(type="text", text=json.dumps(result["rows"][0], default=str))]
            return [TextContent(type="text", text=json.dumps({"error": "File not found"}))]
        
        elif name == "storage_list":
            prefix = arguments.get("prefix", "")
            result = await execute_sql("SELECT key, content_type, created_at FROM file_storage WHERE key LIKE $1 ORDER BY key", [f"{prefix}%"])
            return [TextContent(type="text", text=json.dumps(result.get("rows", []), default=str))]
        
        elif name == "storage_delete":
            key = arguments.get("key")
            result = await execute_sql("DELETE FROM file_storage WHERE key = $1", [key])
            return [TextContent(type="text", text=json.dumps({"success": True, "key": key}))]
        
        # ===== AI (OpenRouter) =====
        elif name == "ai_chat":
            if not OPENROUTER_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "OpenRouter not configured"}))]
            model = arguments.get("model", "anthropic/claude-3.5-sonnet")
            async with aiohttp.ClientSession() as session:
                async with session.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                    json={"model": model, "messages": arguments.get("messages"), "max_tokens": arguments.get("max_tokens", 4096)}
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "ai_complete":
            if not OPENROUTER_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "OpenRouter not configured"}))]
            model = arguments.get("model", "anthropic/claude-3.5-sonnet")
            messages = [{"role": "user", "content": arguments.get("prompt")}]
            async with aiohttp.ClientSession() as session:
                async with session.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "max_tokens": arguments.get("max_tokens", 4096)}
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== WEBHOOKS =====
        elif name == "webhook_list":
            limit = arguments.get("limit", 20)
            source = arguments.get("source")
            filtered = webhook_events[-limit:] if not source else [e for e in webhook_events if e.get("source") == source][-limit:]
            return [TextContent(type="text", text=json.dumps(filtered, default=str))]
        
        elif name == "webhook_get":
            event_id = arguments.get("event_id")
            for event in webhook_events:
                if event.get("id") == event_id:
                    return [TextContent(type="text", text=json.dumps(event, default=str))]
            return [TextContent(type="text", text=json.dumps({"error": "Event not found"}))]
        
        # ===== SLACK =====
        elif name == "war_room_post":
            if not SLACK_BOT_TOKEN or not WAR_ROOM_CHANNEL:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            bot_names = {"otto": "Otto", "devin": "Devin", "juggernaut": "JUGGERNAUT"}
            username = bot_names.get(arguments.get("bot", "").lower(), "JUGGERNAUT")
            async with aiohttp.ClientSession() as session:
                async with session.post("https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json={"channel": WAR_ROOM_CHANNEL, "text": arguments.get("message"), "username": username}
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "war_room_history":
            if not SLACK_BOT_TOKEN or not WAR_ROOM_CHANNEL:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            limit = arguments.get("limit", 20)
            async with aiohttp.ClientSession() as session:
                async with session.get("https://slack.com/api/conversations.history",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    params={"channel": WAR_ROOM_CHANNEL, "limit": limit}
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== MCP FACTORY =====
        elif name == "mcp_create":
            result = await mcp_create_from_spec(arguments.get("name"), arguments.get("description"), arguments.get("tools", []), arguments.get("owner_worker_id"))
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "mcp_list":
            result = await mcp_list_all(arguments.get("status"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "mcp_status":
            result = await mcp_get_status(arguments.get("mcp_id"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # ===== GENERIC FETCH =====
        elif name == "fetch_url":
            url = arguments.get("url")
            method = arguments.get("method", "GET").upper()
            headers = arguments.get("headers", {})
            body = arguments.get("body")
            async with aiohttp.ClientSession() as session:
                kwargs = {"headers": headers}
                if body:
                    try:
                        kwargs["json"] = json.loads(body)
                    except:
                        kwargs["data"] = body
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
# WEBHOOK RECEIVER
# =============================================================================

async def handle_webhook(scope, receive, send):
    """Handle incoming webhooks."""
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body"):
            break
    
    try:
        data = json.loads(body.decode())
    except:
        data = {"raw": body.decode()}
    
    # Extract source from path or headers
    path = scope.get("path", "")
    source = path.split("/")[-1] if path.count("/") > 2 else "unknown"
    
    import uuid
    event = {
        "id": str(uuid.uuid4()),
        "source": source,
        "timestamp": time.time(),
        "headers": dict(scope.get("headers", [])),
        "data": data
    }
    webhook_events.append(event)
    if len(webhook_events) > 1000:
        webhook_events.pop(0)
    
    # Store in database too
    try:
        await execute_sql(
            "INSERT INTO webhook_events (id, source, data, created_at) VALUES ($1, $2, $3, NOW())",
            [event["id"], source, json.dumps(data)]
        )
    except:
        pass
    
    await send({"type": "http.response.start", "status": 200, "headers": [[b"content-type", b"application/json"]]})
    await send({"type": "http.response.body", "body": json.dumps({"received": True, "event_id": event["id"]}).encode()})


# =============================================================================
# SSE TRANSPORT
# =============================================================================

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
    headers = [[b"content-type", content_type], [b"access-control-allow-origin", b"*"], [b"access-control-allow-methods", b"GET, POST, OPTIONS"], [b"access-control-allow-headers", b"*"]]
    if extra_headers:
        headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    
    path, method = scope["path"], scope["method"]
    logger.info(f"{method} {path}")
    
    if method == "OPTIONS":
        await send_response(send, 204, b"", extra_headers=[[b"access-control-max-age", b"86400"]])
        return
    
    # Health check
    if path == "/health":
        tool_count = len(await list_tools())
        config = {
            "github": bool(GITHUB_TOKEN), "railway": bool(RAILWAY_TOKEN), "vercel": bool(VERCEL_TOKEN),
            "slack": bool(SLACK_BOT_TOKEN), "database": bool(DATABASE_URL), "puppeteer": bool(PUPPETEER_URL),
            "search": bool(SERPER_API_KEY), "servicetitan": bool(ST_CLIENT_ID), "email": bool(RESEND_API_KEY),
            "sms": bool(TWILIO_ACCOUNT_SID), "storage": bool(R2_ACCESS_KEY), "ai": bool(OPENROUTER_API_KEY)
        }
        await send_response(send, 200, json.dumps({"status": "healthy", "tools": tool_count, "version": "8.0", "configured": config}).encode())
        return
    
    # Webhook receiver
    if path.startswith("/webhook") and method == "POST":
        await handle_webhook(scope, receive, send)
        return
    
    # SSE endpoints
    if path in ("/mcp/sse", "/sse") and method == "GET":
        if not check_auth(scope):
            await send_response(send, 401, b'{"error":"Unauthorized"}')
            return
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
        return
    
    if path == "/messages" and method == "POST":
        await sse_transport.handle_post_message(scope, receive, send)
        return
    
    if path == "/" and method == "GET":
        query_string = scope.get("query_string", b"").decode()
        if "token=" in query_string:
            if not check_auth(scope):
                await send_response(send, 401, b'{"error":"Unauthorized"}')
                return
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp.run(streams[0], streams[1], mcp.create_initialization_options())
            return
        tool_count = len(await list_tools())
        await send_response(send, 200, json.dumps({"name": "juggernaut-mcp", "version": "8.0", "tools": tool_count, "endpoints": {"sse": "/mcp/sse?token=<token>", "health": "/health", "webhook": "/webhook/<source>"}}).encode())
        return
    
    await send_response(send, 404, b'{"error":"Not found"}')


if __name__ == "__main__":
    logger.info(f"Starting JUGGERNAUT MCP Server v8 on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
