"""
JUGGERNAUT MCP Server - Full Stack (v10)

Complete autonomous capabilities:
- Database: Neon PostgreSQL
- GitHub: Full repo management
- Railway: Deployment management
- Vercel: Frontend deployment
- Slack: Team messaging
- Puppeteer: Browser automation
- Perplexity: AI-powered search
- ServiceTitan: Plumbing business operations
- MS Graph: Office 365 email & calendar
- Storage: File storage (DB fallback)
- AI: OpenRouter (Claude, GPT, etc.)
- Webhooks: Event receiver
- MCP Factory: Create new MCPs
- NEW: Image Generation (OpenRouter)
- NEW: Vector DB (Pinecone)
- NEW: Social Media (Meta, Twitter)
- NEW: PDF Generation
- NEW: Google Maps/Geocoding
- NEW: Google Sheets
"""
import asyncio
import base64
import json
import logging
import os
import time
import uuid
from typing import Any, Optional
from urllib.parse import urlencode, quote

import aiohttp
import uvicorn

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# Puppeteer
PUPPETEER_URL = os.environ.get('PUPPETEER_URL', '')

# Perplexity (AI search)
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

# ServiceTitan
ST_CLIENT_ID = os.environ.get('ST_CLIENT_ID', '')
ST_CLIENT_SECRET = os.environ.get('ST_CLIENT_SECRET', '')
ST_TENANT_ID = os.environ.get('ST_TENANT_ID', '')
ST_APP_KEY = os.environ.get('ST_APP_KEY', '')

# MS Graph (Office 365)
MSGRAPH_CLIENT_ID = os.environ.get('MSGRAPH_CLIENT_ID', '')
MSGRAPH_CLIENT_SECRET = os.environ.get('MSGRAPH_CLIENT_SECRET', '')
MSGRAPH_TENANT_ID = os.environ.get('MSGRAPH_TENANT_ID', '')
MSGRAPH_USER_EMAIL = os.environ.get('MSGRAPH_USER_EMAIL', '')

# OpenRouter (AI + Image Gen)
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

# Pinecone (Vector DB)
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY', '')
PINECONE_INDEX = os.environ.get('PINECONE_INDEX', '')
PINECONE_HOST = os.environ.get('PINECONE_HOST', '')

# Social Media
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN', '')
META_PAGE_ID = os.environ.get('META_PAGE_ID', '')
TWITTER_API_KEY = os.environ.get('TWITTER_API_KEY', '')
TWITTER_API_SECRET = os.environ.get('TWITTER_API_SECRET', '')
TWITTER_ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN', '')
TWITTER_ACCESS_SECRET = os.environ.get('TWITTER_ACCESS_SECRET', '')

# Google Maps
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

# Google Sheets
GOOGLE_SERVICE_ACCOUNT = os.environ.get('GOOGLE_SERVICE_ACCOUNT', '')  # JSON string
GOOGLE_SHEETS_TOKEN = os.environ.get('GOOGLE_SHEETS_TOKEN', '')

# Neon
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"

# Token caches
_st_token = {"token": None, "expires": 0}
_msgraph_token = {"token": None, "expires": 0}
_google_token = {"token": None, "expires": 0}

# Webhook storage
webhook_events = []

# Create MCP Server
mcp = Server("juggernaut-mcp")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def execute_sql(query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute SQL against Neon database."""
    async with aiohttp.ClientSession() as session:
        async with session.post(NEON_ENDPOINT, headers={"Content-Type": "application/json", "Neon-Connection-String": DATABASE_URL}, json={"query": query, "params": params or []}) as resp:
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


async def get_servicetitan_token() -> str:
    """Get ServiceTitan OAuth token."""
    if _st_token["token"] and time.time() < _st_token["expires"]:
        return _st_token["token"]
    if not ST_CLIENT_ID or not ST_CLIENT_SECRET:
        return ""
    async with aiohttp.ClientSession() as session:
        async with session.post("https://auth.servicetitan.io/connect/token", data={"grant_type": "client_credentials", "client_id": ST_CLIENT_ID, "client_secret": ST_CLIENT_SECRET}) as resp:
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
    headers = {"Authorization": f"Bearer {token}", "ST-App-Key": ST_APP_KEY, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                return await resp.json()


async def get_msgraph_token() -> str:
    """Get MS Graph OAuth token."""
    if _msgraph_token["token"] and time.time() < _msgraph_token["expires"]:
        return _msgraph_token["token"]
    if not MSGRAPH_CLIENT_ID or not MSGRAPH_CLIENT_SECRET or not MSGRAPH_TENANT_ID:
        return ""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://login.microsoftonline.com/{MSGRAPH_TENANT_ID}/oauth2/v2.0/token",
            data={"grant_type": "client_credentials", "client_id": MSGRAPH_CLIENT_ID, "client_secret": MSGRAPH_CLIENT_SECRET, "scope": "https://graph.microsoft.com/.default"}
        ) as resp:
            data = await resp.json()
            _msgraph_token["token"] = data.get("access_token", "")
            _msgraph_token["expires"] = time.time() + data.get("expires_in", 3600) - 60
            return _msgraph_token["token"]


async def msgraph_api(method: str, endpoint: str, data: dict = None, user: str = None) -> dict[str, Any]:
    """Make MS Graph API request."""
    token = await get_msgraph_token()
    if not token:
        return {"error": "Could not get MS Graph token"}
    user_email = user or MSGRAPH_USER_EMAIL
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url, headers=headers) as resp:
                return await resp.json()
        elif method == "POST":
            async with session.post(url, headers=headers, json=data) as resp:
                if resp.status == 202:
                    return {"success": True, "status": "accepted"}
                return await resp.json()


async def perplexity_search(query: str, model: str = "sonar") -> dict[str, Any]:
    """Search with Perplexity AI."""
    if not PERPLEXITY_API_KEY:
        return {"error": "Perplexity not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": query}], "return_citations": True}
        ) as resp:
            return await resp.json()


# =============================================================================
# NEW HELPER FUNCTIONS
# =============================================================================

async def generate_image(prompt: str, model: str = "openai/dall-e-3", size: str = "1024x1024") -> dict[str, Any]:
    """Generate image via OpenRouter."""
    if not OPENROUTER_API_KEY:
        return {"error": "OpenRouter not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/images/generations",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "prompt": prompt, "size": size, "n": 1}
        ) as resp:
            return await resp.json()


async def pinecone_upsert(vectors: list, namespace: str = "") -> dict[str, Any]:
    """Upsert vectors to Pinecone."""
    if not PINECONE_API_KEY or not PINECONE_HOST:
        return {"error": "Pinecone not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://{PINECONE_HOST}/vectors/upsert",
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
            json={"vectors": vectors, "namespace": namespace}
        ) as resp:
            return await resp.json()


async def pinecone_query(vector: list, top_k: int = 10, namespace: str = "", include_metadata: bool = True) -> dict[str, Any]:
    """Query Pinecone for similar vectors."""
    if not PINECONE_API_KEY or not PINECONE_HOST:
        return {"error": "Pinecone not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://{PINECONE_HOST}/query",
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
            json={"vector": vector, "topK": top_k, "namespace": namespace, "includeMetadata": include_metadata}
        ) as resp:
            return await resp.json()


async def meta_post(message: str, link: str = None, image_url: str = None) -> dict[str, Any]:
    """Post to Facebook/Instagram via Meta Graph API."""
    if not META_ACCESS_TOKEN or not META_PAGE_ID:
        return {"error": "Meta not configured"}
    async with aiohttp.ClientSession() as session:
        data = {"message": message, "access_token": META_ACCESS_TOKEN}
        if link:
            data["link"] = link
        endpoint = f"https://graph.facebook.com/v18.0/{META_PAGE_ID}/feed"
        if image_url:
            endpoint = f"https://graph.facebook.com/v18.0/{META_PAGE_ID}/photos"
            data["url"] = image_url
        async with session.post(endpoint, data=data) as resp:
            return await resp.json()


async def twitter_post(text: str) -> dict[str, Any]:
    """Post to Twitter/X using OAuth 1.0a."""
    if not TWITTER_API_KEY or not TWITTER_ACCESS_TOKEN:
        return {"error": "Twitter not configured"}
    import hashlib
    import hmac
    import urllib.parse
    
    url = "https://api.twitter.com/2/tweets"
    oauth_timestamp = str(int(time.time()))
    oauth_nonce = str(uuid.uuid4()).replace("-", "")
    
    oauth_params = {
        "oauth_consumer_key": TWITTER_API_KEY,
        "oauth_nonce": oauth_nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": oauth_timestamp,
        "oauth_token": TWITTER_ACCESS_TOKEN,
        "oauth_version": "1.0"
    }
    
    param_string = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted(oauth_params.items()))
    base_string = f"POST&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
    signing_key = f"{urllib.parse.quote(TWITTER_API_SECRET, safe='')}&{urllib.parse.quote(TWITTER_ACCESS_SECRET, safe='')}"
    signature = base64.b64encode(hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()).decode()
    
    oauth_params["oauth_signature"] = signature
    auth_header = "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(str(v), safe="")}"' for k, v in oauth_params.items())
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers={"Authorization": auth_header, "Content-Type": "application/json"}, json={"text": text}) as resp:
            return await resp.json()


async def google_maps_geocode(address: str) -> dict[str, Any]:
    """Geocode an address using Google Maps."""
    if not GOOGLE_MAPS_API_KEY:
        return {"error": "Google Maps not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": GOOGLE_MAPS_API_KEY}
        ) as resp:
            return await resp.json()


async def google_maps_directions(origin: str, destination: str, mode: str = "driving") -> dict[str, Any]:
    """Get directions using Google Maps."""
    if not GOOGLE_MAPS_API_KEY:
        return {"error": "Google Maps not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params={"origin": origin, "destination": destination, "mode": mode, "key": GOOGLE_MAPS_API_KEY}
        ) as resp:
            return await resp.json()


async def google_maps_distance(origins: str, destinations: str) -> dict[str, Any]:
    """Get distance matrix using Google Maps."""
    if not GOOGLE_MAPS_API_KEY:
        return {"error": "Google Maps not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={"origins": origins, "destinations": destinations, "key": GOOGLE_MAPS_API_KEY}
        ) as resp:
            return await resp.json()


async def get_google_token() -> str:
    """Get Google OAuth token from service account."""
    if _google_token["token"] and time.time() < _google_token["expires"]:
        return _google_token["token"]
    if GOOGLE_SHEETS_TOKEN:
        return GOOGLE_SHEETS_TOKEN
    if not GOOGLE_SERVICE_ACCOUNT:
        return ""
    # JWT-based auth for service account
    try:
        import jwt
        sa = json.loads(GOOGLE_SERVICE_ACCOUNT)
        now = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": "https://www.googleapis.com/auth/spreadsheets",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600
        }
        signed_jwt = jwt.encode(payload, sa["private_key"], algorithm="RS256")
        async with aiohttp.ClientSession() as session:
            async with session.post("https://oauth2.googleapis.com/token", data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed_jwt}) as resp:
                data = await resp.json()
                _google_token["token"] = data.get("access_token", "")
                _google_token["expires"] = time.time() + 3500
                return _google_token["token"]
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        return ""


async def sheets_read(spreadsheet_id: str, range_name: str) -> dict[str, Any]:
    """Read from Google Sheets."""
    token = await get_google_token()
    if not token:
        return {"error": "Google Sheets not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}",
            headers={"Authorization": f"Bearer {token}"}
        ) as resp:
            return await resp.json()


async def sheets_write(spreadsheet_id: str, range_name: str, values: list) -> dict[str, Any]:
    """Write to Google Sheets."""
    token = await get_google_token()
    if not token:
        return {"error": "Google Sheets not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params={"valueInputOption": "USER_ENTERED"},
            json={"values": values}
        ) as resp:
            return await resp.json()


async def sheets_append(spreadsheet_id: str, range_name: str, values: list) -> dict[str, Any]:
    """Append to Google Sheets."""
    token = await get_google_token()
    if not token:
        return {"error": "Google Sheets not configured"}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}:append",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            json={"values": values}
        ) as resp:
            return await resp.json()


# MCP Factory helpers
async def mcp_create_from_spec(name: str, description: str, tools: list, owner: str = None) -> dict:
    mcp_id = str(uuid.uuid4())
    auth_token = str(uuid.uuid4()).replace("-", "")[:32]
    sql = f"""INSERT INTO mcp_registry (id, name, description, status, owner_worker_id, auth_token, tools_config) VALUES ('{mcp_id}', '{name}', '{description.replace("'", "''")}', 'pending', {'NULL' if not owner else f"'{owner}'"}, '{auth_token}', '{json.dumps(tools)}'::jsonb) ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, tools_config = EXCLUDED.tools_config RETURNING id, auth_token"""
    result = await execute_sql(sql)
    return {"mcp_id": result["rows"][0]["id"], "auth_token": result["rows"][0]["auth_token"], "status": "registered"} if result.get("rows") else {"error": "Failed"}


async def mcp_list_all(status: str = None) -> list:
    where = f"WHERE status = '{status}'" if status else ""
    result = await execute_sql(f"SELECT id, name, description, status, endpoint_url, health_status, created_at FROM mcp_registry {where} ORDER BY created_at DESC")
    return result.get("rows", [])


async def mcp_get_status(mcp_id: str) -> dict:
    result = await execute_sql(f"SELECT * FROM mcp_registry WHERE id = '{mcp_id}' OR name = '{mcp_id}'")
    return result["rows"][0] if result.get("rows") else {"error": "MCP not found"}


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # DATABASE
        Tool(name="sql_query", description="Execute SQL query", inputSchema={"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}),
        Tool(name="hq_query", description="Query governance DB", inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
        Tool(name="hq_execute", description="Execute governance action", inputSchema={"type": "object", "properties": {"action": {"type": "string"}, "params": {"type": "object"}}, "required": ["action"]}),
        
        # GITHUB
        Tool(name="github_get_file", description="Get file from repo", inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "branch": {"type": "string"}}, "required": ["path"]}),
        Tool(name="github_put_file", description="Create/update file", inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "message": {"type": "string"}, "branch": {"type": "string"}, "sha": {"type": "string"}}, "required": ["path", "content", "message", "branch"]}),
        Tool(name="github_list_files", description="List files", inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "branch": {"type": "string"}}}),
        Tool(name="github_create_branch", description="Create branch", inputSchema={"type": "object", "properties": {"branch_name": {"type": "string"}, "from_branch": {"type": "string"}}, "required": ["branch_name"]}),
        Tool(name="github_create_pr", description="Create PR", inputSchema={"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "head": {"type": "string"}, "base": {"type": "string"}}, "required": ["title", "head"]}),
        Tool(name="github_merge_pr", description="Merge PR", inputSchema={"type": "object", "properties": {"pr_number": {"type": "integer"}, "merge_method": {"type": "string"}}, "required": ["pr_number"]}),
        Tool(name="github_list_prs", description="List PRs", inputSchema={"type": "object", "properties": {"state": {"type": "string"}}}),
        
        # RAILWAY
        Tool(name="railway_list_services", description="List services", inputSchema={"type": "object", "properties": {}}),
        Tool(name="railway_get_deployments", description="Get deployments", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "limit": {"type": "integer"}}}),
        Tool(name="railway_get_logs", description="Get logs", inputSchema={"type": "object", "properties": {"deployment_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["deployment_id"]}),
        Tool(name="railway_redeploy", description="Redeploy service", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}}, "required": ["service_id"]}),
        Tool(name="railway_set_env", description="Set env var", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "name": {"type": "string"}, "value": {"type": "string"}}, "required": ["service_id", "name", "value"]}),
        Tool(name="railway_create_service", description="Create service", inputSchema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
        
        # VERCEL
        Tool(name="vercel_list_deployments", description="List deployments", inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        Tool(name="vercel_check_domain", description="Check domain", inputSchema={"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}),
        
        # PUPPETEER
        Tool(name="browser_navigate", description="Navigate to URL", inputSchema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
        Tool(name="browser_screenshot", description="Take screenshot", inputSchema={"type": "object", "properties": {"full_page": {"type": "boolean"}}}),
        Tool(name="browser_click", description="Click element", inputSchema={"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}),
        Tool(name="browser_type", description="Type text", inputSchema={"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}),
        Tool(name="browser_get_text", description="Get text", inputSchema={"type": "object", "properties": {"selector": {"type": "string"}}}),
        Tool(name="browser_eval", description="Eval JS", inputSchema={"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}),
        Tool(name="browser_pdf", description="Generate PDF from page", inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "format": {"type": "string"}}, "required": ["url"]}),
        
        # PERPLEXITY (AI Search)
        Tool(name="web_search", description="AI-powered web search via Perplexity", inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "detailed": {"type": "boolean"}}, "required": ["query"]}),
        
        # SERVICETITAN
        Tool(name="st_list_customers", description="List customers", inputSchema={"type": "object", "properties": {"page": {"type": "integer"}, "name": {"type": "string"}}}),
        Tool(name="st_get_customer", description="Get customer", inputSchema={"type": "object", "properties": {"customer_id": {"type": "integer"}}, "required": ["customer_id"]}),
        Tool(name="st_create_customer", description="Create customer", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "address": {"type": "object"}, "phones": {"type": "array"}, "email": {"type": "string"}}, "required": ["name"]}),
        Tool(name="st_list_jobs", description="List jobs", inputSchema={"type": "object", "properties": {"page": {"type": "integer"}, "status": {"type": "string"}}}),
        Tool(name="st_get_job", description="Get job", inputSchema={"type": "object", "properties": {"job_id": {"type": "integer"}}, "required": ["job_id"]}),
        Tool(name="st_list_invoices", description="List invoices", inputSchema={"type": "object", "properties": {"page": {"type": "integer"}, "status": {"type": "string"}}}),
        Tool(name="st_list_technicians", description="List technicians", inputSchema={"type": "object", "properties": {}}),
        
        # MS GRAPH (Email)
        Tool(name="email_list", description="List emails from inbox", inputSchema={"type": "object", "properties": {"folder": {"type": "string"}, "top": {"type": "integer"}, "filter": {"type": "string"}}}),
        Tool(name="email_read", description="Read email by ID", inputSchema={"type": "object", "properties": {"message_id": {"type": "string"}}, "required": ["message_id"]}),
        Tool(name="email_send", description="Send email", inputSchema={"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "cc": {"type": "string"}}, "required": ["to", "subject", "body"]}),
        Tool(name="email_search", description="Search emails", inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "top": {"type": "integer"}}, "required": ["query"]}),
        Tool(name="email_reply", description="Reply to email", inputSchema={"type": "object", "properties": {"message_id": {"type": "string"}, "body": {"type": "string"}}, "required": ["message_id", "body"]}),
        
        # MS GRAPH (Calendar)
        Tool(name="calendar_list", description="List calendar events", inputSchema={"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}, "top": {"type": "integer"}}}),
        Tool(name="calendar_create", description="Create calendar event", inputSchema={"type": "object", "properties": {"subject": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "body": {"type": "string"}, "attendees": {"type": "array"}}, "required": ["subject", "start", "end"]}),
        
        # STORAGE
        Tool(name="storage_upload", description="Upload file", inputSchema={"type": "object", "properties": {"key": {"type": "string"}, "content": {"type": "string"}, "content_type": {"type": "string"}}, "required": ["key", "content"]}),
        Tool(name="storage_download", description="Download file", inputSchema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}),
        Tool(name="storage_list", description="List files", inputSchema={"type": "object", "properties": {"prefix": {"type": "string"}}}),
        Tool(name="storage_delete", description="Delete file", inputSchema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}),
        
        # AI (OpenRouter)
        Tool(name="ai_chat", description="Chat with AI", inputSchema={"type": "object", "properties": {"messages": {"type": "array"}, "model": {"type": "string"}, "max_tokens": {"type": "integer"}}, "required": ["messages"]}),
        Tool(name="ai_complete", description="AI completion", inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}}, "required": ["prompt"]}),
        
        # IMAGE GENERATION (NEW)
        Tool(name="image_generate", description="Generate image from prompt", inputSchema={"type": "object", "properties": {"prompt": {"type": "string"}, "model": {"type": "string"}, "size": {"type": "string"}}, "required": ["prompt"]}),
        
        # VECTOR DB - PINECONE (NEW)
        Tool(name="vector_upsert", description="Upsert vectors to Pinecone", inputSchema={"type": "object", "properties": {"vectors": {"type": "array"}, "namespace": {"type": "string"}}, "required": ["vectors"]}),
        Tool(name="vector_query", description="Query similar vectors", inputSchema={"type": "object", "properties": {"vector": {"type": "array"}, "top_k": {"type": "integer"}, "namespace": {"type": "string"}}, "required": ["vector"]}),
        Tool(name="vector_delete", description="Delete vectors", inputSchema={"type": "object", "properties": {"ids": {"type": "array"}, "namespace": {"type": "string"}}, "required": ["ids"]}),
        
        # SOCIAL MEDIA (NEW)
        Tool(name="social_post_facebook", description="Post to Facebook", inputSchema={"type": "object", "properties": {"message": {"type": "string"}, "link": {"type": "string"}, "image_url": {"type": "string"}}, "required": ["message"]}),
        Tool(name="social_post_twitter", description="Post to Twitter/X", inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
        
        # PDF GENERATION (NEW)
        Tool(name="pdf_from_html", description="Generate PDF from HTML", inputSchema={"type": "object", "properties": {"html": {"type": "string"}, "filename": {"type": "string"}}, "required": ["html"]}),
        Tool(name="pdf_from_url", description="Generate PDF from URL", inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "filename": {"type": "string"}}, "required": ["url"]}),
        
        # GOOGLE MAPS (NEW)
        Tool(name="maps_geocode", description="Geocode address to coordinates", inputSchema={"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}),
        Tool(name="maps_directions", description="Get directions between locations", inputSchema={"type": "object", "properties": {"origin": {"type": "string"}, "destination": {"type": "string"}, "mode": {"type": "string"}}, "required": ["origin", "destination"]}),
        Tool(name="maps_distance", description="Get distance matrix", inputSchema={"type": "object", "properties": {"origins": {"type": "string"}, "destinations": {"type": "string"}}, "required": ["origins", "destinations"]}),
        
        # GOOGLE SHEETS (NEW)
        Tool(name="sheets_read", description="Read from Google Sheet", inputSchema={"type": "object", "properties": {"spreadsheet_id": {"type": "string"}, "range": {"type": "string"}}, "required": ["spreadsheet_id", "range"]}),
        Tool(name="sheets_write", description="Write to Google Sheet", inputSchema={"type": "object", "properties": {"spreadsheet_id": {"type": "string"}, "range": {"type": "string"}, "values": {"type": "array"}}, "required": ["spreadsheet_id", "range", "values"]}),
        Tool(name="sheets_append", description="Append to Google Sheet", inputSchema={"type": "object", "properties": {"spreadsheet_id": {"type": "string"}, "range": {"type": "string"}, "values": {"type": "array"}}, "required": ["spreadsheet_id", "range", "values"]}),
        
        # WEBHOOKS
        Tool(name="webhook_list", description="List webhooks", inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}, "source": {"type": "string"}}}),
        Tool(name="webhook_get", description="Get webhook", inputSchema={"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]}),
        
        # SLACK
        Tool(name="war_room_post", description="Post to Slack", inputSchema={"type": "object", "properties": {"bot": {"type": "string"}, "message": {"type": "string"}}, "required": ["bot", "message"]}),
        Tool(name="war_room_history", description="Slack history", inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        
        # MCP FACTORY
        Tool(name="mcp_create", description="Create MCP", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "tools": {"type": "array"}}, "required": ["name", "description", "tools"]}),
        Tool(name="mcp_list", description="List MCPs", inputSchema={"type": "object", "properties": {"status": {"type": "string"}}}),
        Tool(name="mcp_status", description="MCP status", inputSchema={"type": "object", "properties": {"mcp_id": {"type": "string"}}, "required": ["mcp_id"]}),
        
        # GENERIC
        Tool(name="fetch_url", description="Fetch URL", inputSchema={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "headers": {"type": "object"}, "body": {"type": "string"}}, "required": ["url"]})
    ]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info(f"Tool call: {name}")
    try:
        # DATABASE
        if name == "sql_query":
            result = await execute_sql(arguments.get("sql"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "hq_query":
            query_type = arguments.get("query", "")
            queries = {"workers.all": "SELECT * FROM workers ORDER BY created_at DESC", "tasks.pending": "SELECT id, title, priority FROM governance_tasks WHERE status = 'pending' ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END LIMIT 20", "tasks.recent": "SELECT id, title, status FROM governance_tasks ORDER BY created_at DESC LIMIT 20", "schema.tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"}
            result = await execute_sql(queries.get(query_type, query_type))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "hq_execute":
            action, params = arguments.get("action"), arguments.get("params", {})
            if action == "task.create":
                result = await execute_sql("INSERT INTO governance_tasks (title, description, priority, task_type, assigned_worker, status) VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id", [params.get("title"), params.get("description"), params.get("priority", "medium"), params.get("task_type", "code"), params.get("assigned_worker", "claude-chat")])
            elif action == "task.complete":
                result = await execute_sql("UPDATE governance_tasks SET status = 'completed', completed_at = NOW(), completion_evidence = $1 WHERE id = $2", [params.get("evidence", ""), params.get("id")])
            else:
                result = {"error": f"Unknown action: {action}"}
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # GITHUB
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
            result = await github_api("POST", "pulls", {"title": arguments.get("title"), "body": arguments.get("body", ""), "head": arguments.get("head"), "base": arguments.get("base", "main")})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_merge_pr":
            result = await github_api("PUT", f"pulls/{arguments.get('pr_number')}/merge", {"merge_method": arguments.get("merge_method", "squash")})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "github_list_prs":
            result = await github_api("GET", f"pulls?state={arguments.get('state', 'open')}")
            if isinstance(result, list):
                result = [{"number": p["number"], "title": p["title"], "state": p["state"], "head": p["head"]["ref"]} for p in result]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # RAILWAY
        elif name == "railway_list_services":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            result = await railway_graphql(f'query {{ project(id: "{RAILWAY_PROJECT_ID}") {{ services {{ edges {{ node {{ id name }} }} }} }} }}')
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_get_deployments":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            service_filter = f', serviceId: "{arguments.get("service_id")}"' if arguments.get("service_id") else ""
            result = await railway_graphql(f'query {{ deployments(first: {arguments.get("limit", 5)}, input: {{ projectId: "{RAILWAY_PROJECT_ID}"{service_filter} }}) {{ edges {{ node {{ id status staticUrl service {{ name }} }} }} }} }}')
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_get_logs":
            result = await railway_graphql(f'query {{ deploymentLogs(deploymentId: "{arguments.get("deployment_id")}", limit: {arguments.get("limit", 100)}) {{ message timestamp }} }}')
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_redeploy":
            if not RAILWAY_ENV_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_ENV_ID not set"}))]
            result = await railway_graphql("mutation ServiceRedeploy($input: ServiceRedeployInput!) { serviceRedeploy(input: $input) { id status } }", {"input": {"serviceId": arguments.get("service_id"), "environmentId": RAILWAY_ENV_ID}})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_set_env":
            if not RAILWAY_ENV_ID or not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "Railway not configured"}))]
            result = await railway_graphql("mutation VariableUpsert($input: VariableUpsertInput!) { variableUpsert(input: $input) }", {"input": {"name": arguments.get("name"), "value": arguments.get("value"), "serviceId": arguments.get("service_id"), "environmentId": RAILWAY_ENV_ID, "projectId": RAILWAY_PROJECT_ID}})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "railway_create_service":
            if not RAILWAY_PROJECT_ID:
                return [TextContent(type="text", text=json.dumps({"error": "RAILWAY_PROJECT_ID not set"}))]
            result = await railway_graphql("mutation { serviceCreate(input: { name: \"" + arguments.get("name") + "\", projectId: \"" + RAILWAY_PROJECT_ID + "\" }) { id name } }")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # VERCEL
        elif name == "vercel_list_deployments":
            result = await vercel_api("GET", f"/v6/deployments?limit={arguments.get('limit', 10)}")
            if "deployments" in result:
                result = [{"uid": d["uid"], "name": d.get("name"), "state": d["state"], "url": d.get("url")} for d in result["deployments"]]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "vercel_check_domain":
            result = await vercel_api("GET", f"/v4/domains/status?name={arguments.get('domain')}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # PUPPETEER
        elif name.startswith("browser_"):
            if not PUPPETEER_URL:
                return [TextContent(type="text", text=json.dumps({"error": "Puppeteer not configured"}))]
            action = name.replace("browser_", "")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{PUPPETEER_URL}/action",
                    json={"action": action, **arguments},
                    headers={"Authorization": "Bearer jug-pup-auth-2024"},
                ) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # PERPLEXITY (Web Search)
        elif name == "web_search":
            query = arguments.get("query")
            model = "sonar-pro" if arguments.get("detailed") else "sonar"
            result = await perplexity_search(query, model)
            if "choices" in result and result["choices"]:
                answer = result["choices"][0].get("message", {}).get("content", "")
                citations = result.get("citations", [])
                return [TextContent(type="text", text=json.dumps({"answer": answer, "citations": citations}, default=str))]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # SERVICETITAN
        elif name == "st_list_customers":
            endpoint = f"crm/v2/tenant/{ST_TENANT_ID}/customers?page={arguments.get('page', 1)}&pageSize=50"
            if arguments.get("name"):
                endpoint += f"&name={quote(arguments.get('name'))}"
            result = await servicetitan_api("GET", endpoint)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_get_customer":
            result = await servicetitan_api("GET", f"crm/v2/tenant/{ST_TENANT_ID}/customers/{arguments.get('customer_id')}")
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
            endpoint = f"jpm/v2/tenant/{ST_TENANT_ID}/jobs?page={arguments.get('page', 1)}"
            if arguments.get("status"):
                endpoint += f"&status={arguments.get('status')}"
            result = await servicetitan_api("GET", endpoint)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_get_job":
            result = await servicetitan_api("GET", f"jpm/v2/tenant/{ST_TENANT_ID}/jobs/{arguments.get('job_id')}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_list_invoices":
            endpoint = f"accounting/v2/tenant/{ST_TENANT_ID}/invoices?page={arguments.get('page', 1)}"
            if arguments.get("status"):
                endpoint += f"&status={arguments.get('status')}"
            result = await servicetitan_api("GET", endpoint)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "st_list_technicians":
            result = await servicetitan_api("GET", f"dispatch/v2/tenant/{ST_TENANT_ID}/technicians")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # MS GRAPH (Email)
        elif name == "email_list":
            folder = arguments.get("folder", "inbox")
            top = arguments.get("top", 20)
            endpoint = f"mailFolders/{folder}/messages?$top={top}&$orderby=receivedDateTime desc"
            if arguments.get("filter"):
                endpoint += f"&$filter={arguments.get('filter')}"
            result = await msgraph_api("GET", endpoint)
            if "value" in result:
                result = [{"id": m["id"], "subject": m["subject"], "from": m.get("from", {}).get("emailAddress", {}).get("address"), "receivedDateTime": m["receivedDateTime"], "isRead": m["isRead"]} for m in result["value"]]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "email_read":
            result = await msgraph_api("GET", f"messages/{arguments.get('message_id')}")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "email_send":
            message = {"message": {"subject": arguments.get("subject"), "body": {"contentType": "HTML", "content": arguments.get("body")}, "toRecipients": [{"emailAddress": {"address": addr.strip()}} for addr in arguments.get("to").split(",")]}}
            if arguments.get("cc"):
                message["message"]["ccRecipients"] = [{"emailAddress": {"address": addr.strip()}} for addr in arguments.get("cc").split(",")]
            result = await msgraph_api("POST", "sendMail", message)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "email_search":
            query = arguments.get("query")
            top = arguments.get("top", 20)
            result = await msgraph_api("GET", f"messages?$search=\"{query}\"&$top={top}")
            if "value" in result:
                result = [{"id": m["id"], "subject": m["subject"], "from": m.get("from", {}).get("emailAddress", {}).get("address"), "receivedDateTime": m["receivedDateTime"]} for m in result["value"]]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "email_reply":
            result = await msgraph_api("POST", f"messages/{arguments.get('message_id')}/reply", {"comment": arguments.get("body")})
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # MS GRAPH (Calendar)
        elif name == "calendar_list":
            start = arguments.get("start", "")
            end = arguments.get("end", "")
            top = arguments.get("top", 20)
            endpoint = f"calendar/events?$top={top}&$orderby=start/dateTime"
            if start and end:
                endpoint = f"calendar/calendarView?startDateTime={start}&endDateTime={end}&$top={top}"
            result = await msgraph_api("GET", endpoint)
            if "value" in result:
                result = [{"id": e["id"], "subject": e["subject"], "start": e["start"], "end": e["end"], "location": e.get("location", {}).get("displayName")} for e in result["value"]]
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "calendar_create":
            event = {"subject": arguments.get("subject"), "start": {"dateTime": arguments.get("start"), "timeZone": "America/Chicago"}, "end": {"dateTime": arguments.get("end"), "timeZone": "America/Chicago"}}
            if arguments.get("body"):
                event["body"] = {"contentType": "HTML", "content": arguments.get("body")}
            if arguments.get("attendees"):
                event["attendees"] = [{"emailAddress": {"address": a}, "type": "required"} for a in arguments.get("attendees")]
            result = await msgraph_api("POST", "calendar/events", event)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # STORAGE
        elif name == "storage_upload":
            key, content = arguments.get("key"), arguments.get("content")
            await execute_sql("INSERT INTO file_storage (key, content, content_type, created_at) VALUES ($1, $2, $3, NOW()) ON CONFLICT (key) DO UPDATE SET content = $2, content_type = $3 RETURNING key", [key, content, arguments.get("content_type", "application/octet-stream")])
            return [TextContent(type="text", text=json.dumps({"success": True, "key": key}))]
        
        elif name == "storage_download":
            result = await execute_sql("SELECT content, content_type FROM file_storage WHERE key = $1", [arguments.get("key")])
            return [TextContent(type="text", text=json.dumps(result["rows"][0] if result.get("rows") else {"error": "Not found"}, default=str))]
        
        elif name == "storage_list":
            result = await execute_sql("SELECT key, content_type, created_at FROM file_storage WHERE key LIKE $1 ORDER BY key", [f"{arguments.get('prefix', '')}%"])
            return [TextContent(type="text", text=json.dumps(result.get("rows", []), default=str))]
        
        elif name == "storage_delete":
            await execute_sql("DELETE FROM file_storage WHERE key = $1", [arguments.get("key")])
            return [TextContent(type="text", text=json.dumps({"success": True}))]
        
        # AI (OpenRouter)
        elif name == "ai_chat":
            if not OPENROUTER_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "OpenRouter not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}, json={"model": arguments.get("model", "anthropic/claude-3.5-sonnet"), "messages": arguments.get("messages"), "max_tokens": arguments.get("max_tokens", 4096)}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "ai_complete":
            if not OPENROUTER_API_KEY:
                return [TextContent(type="text", text=json.dumps({"error": "OpenRouter not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}, json={"model": arguments.get("model", "anthropic/claude-3.5-sonnet"), "messages": [{"role": "user", "content": arguments.get("prompt")}], "max_tokens": arguments.get("max_tokens", 4096)}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # IMAGE GENERATION (NEW)
        elif name == "image_generate":
            result = await generate_image(arguments.get("prompt"), arguments.get("model", "openai/dall-e-3"), arguments.get("size", "1024x1024"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # VECTOR DB - PINECONE (NEW)
        elif name == "vector_upsert":
            result = await pinecone_upsert(arguments.get("vectors"), arguments.get("namespace", ""))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "vector_query":
            result = await pinecone_query(arguments.get("vector"), arguments.get("top_k", 10), arguments.get("namespace", ""))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "vector_delete":
            if not PINECONE_API_KEY or not PINECONE_HOST:
                return [TextContent(type="text", text=json.dumps({"error": "Pinecone not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post(f"https://{PINECONE_HOST}/vectors/delete", headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"}, json={"ids": arguments.get("ids"), "namespace": arguments.get("namespace", "")}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # SOCIAL MEDIA (NEW)
        elif name == "social_post_facebook":
            result = await meta_post(arguments.get("message"), arguments.get("link"), arguments.get("image_url"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "social_post_twitter":
            result = await twitter_post(arguments.get("text"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # PDF GENERATION (NEW)
        elif name == "pdf_from_html":
            if not PUPPETEER_URL:
                return [TextContent(type="text", text=json.dumps({"error": "Puppeteer not configured for PDF generation"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{PUPPETEER_URL}/action", json={"action": "html_to_pdf", "html": arguments.get("html"), "filename": arguments.get("filename", "document.pdf")}, headers={"Authorization": "Bearer jug-pup-auth-2024"}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "pdf_from_url":
            if not PUPPETEER_URL:
                return [TextContent(type="text", text=json.dumps({"error": "Puppeteer not configured for PDF generation"}))]
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{PUPPETEER_URL}/action", json={"action": "pdf", "url": arguments.get("url"), "filename": arguments.get("filename", "document.pdf")}, headers={"Authorization": "Bearer jug-pup-auth-2024"}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # GOOGLE MAPS (NEW)
        elif name == "maps_geocode":
            result = await google_maps_geocode(arguments.get("address"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "maps_directions":
            result = await google_maps_directions(arguments.get("origin"), arguments.get("destination"), arguments.get("mode", "driving"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "maps_distance":
            result = await google_maps_distance(arguments.get("origins"), arguments.get("destinations"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # GOOGLE SHEETS (NEW)
        elif name == "sheets_read":
            result = await sheets_read(arguments.get("spreadsheet_id"), arguments.get("range"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "sheets_write":
            result = await sheets_write(arguments.get("spreadsheet_id"), arguments.get("range"), arguments.get("values"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "sheets_append":
            result = await sheets_append(arguments.get("spreadsheet_id"), arguments.get("range"), arguments.get("values"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # WEBHOOKS
        elif name == "webhook_list":
            limit, source = arguments.get("limit", 20), arguments.get("source")
            filtered = webhook_events[-limit:] if not source else [e for e in webhook_events if e.get("source") == source][-limit:]
            return [TextContent(type="text", text=json.dumps(filtered, default=str))]
        
        elif name == "webhook_get":
            for event in webhook_events:
                if event.get("id") == arguments.get("event_id"):
                    return [TextContent(type="text", text=json.dumps(event, default=str))]
            return [TextContent(type="text", text=json.dumps({"error": "Not found"}))]
        
        # SLACK
        elif name == "war_room_post":
            if not SLACK_BOT_TOKEN or not WAR_ROOM_CHANNEL:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            bot_names = {"otto": "Otto", "devin": "Devin", "juggernaut": "JUGGERNAUT"}
            async with aiohttp.ClientSession() as session:
                async with session.post("https://slack.com/api/chat.postMessage", headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}, json={"channel": WAR_ROOM_CHANNEL, "text": arguments.get("message"), "username": bot_names.get(arguments.get("bot", "").lower(), "JUGGERNAUT")}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "war_room_history":
            if not SLACK_BOT_TOKEN or not WAR_ROOM_CHANNEL:
                return [TextContent(type="text", text=json.dumps({"error": "Slack not configured"}))]
            async with aiohttp.ClientSession() as session:
                async with session.get("https://slack.com/api/conversations.history", headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}, params={"channel": WAR_ROOM_CHANNEL, "limit": arguments.get("limit", 20)}) as resp:
                    result = await resp.json()
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # MCP FACTORY
        elif name == "mcp_create":
            result = await mcp_create_from_spec(arguments.get("name"), arguments.get("description"), arguments.get("tools", []), arguments.get("owner_worker_id"))
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "mcp_list":
            result = await mcp_list_all(arguments.get("status"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        elif name == "mcp_status":
            result = await mcp_get_status(arguments.get("mcp_id"))
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        
        # GENERIC FETCH
        elif name == "fetch_url":
            url, method = arguments.get("url"), arguments.get("method", "GET").upper()
            headers, body = arguments.get("headers", {}), arguments.get("body")
            async with aiohttp.ClientSession() as session:
                kwargs = {"headers": headers}
                if body:
                    try:
                        kwargs["json"] = json.loads(body)
                    except Exception:
                        kwargs["data"] = body
                async with session.request(method, url, **kwargs) as resp:
                    try:
                        result = await resp.json()
                    except Exception:
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
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body"):
            break
    try:
        data = json.loads(body.decode())
    except Exception:
        data = {"raw": body.decode()}
    path = scope.get("path", "")
    source = path.split("/")[-1] if path.count("/") > 2 else "unknown"
    event = {"id": str(uuid.uuid4()), "source": source, "timestamp": time.time(), "data": data}
    webhook_events.append(event)
    if len(webhook_events) > 1000:
        webhook_events.pop(0)
    try:
        await execute_sql(
            "INSERT INTO webhook_events (id, source, data, created_at) VALUES ($1, $2, $3, NOW())",
            [event["id"], source, json.dumps(data)],
        )
    except Exception:
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
    
    if path == "/health":
        tool_count = len(await list_tools())
        config = {
            "github": bool(GITHUB_TOKEN), "railway": bool(RAILWAY_TOKEN), "vercel": bool(VERCEL_TOKEN),
            "slack": bool(SLACK_BOT_TOKEN), "database": bool(DATABASE_URL), "puppeteer": bool(PUPPETEER_URL),
            "search": bool(PERPLEXITY_API_KEY), "servicetitan": bool(ST_CLIENT_ID), "email": bool(MSGRAPH_CLIENT_ID),
            "ai": bool(OPENROUTER_API_KEY), "image_gen": bool(OPENROUTER_API_KEY), "pinecone": bool(PINECONE_API_KEY),
            "facebook": bool(META_ACCESS_TOKEN), "twitter": bool(TWITTER_API_KEY),
            "google_maps": bool(GOOGLE_MAPS_API_KEY), "google_sheets": bool(GOOGLE_SERVICE_ACCOUNT or GOOGLE_SHEETS_TOKEN)
        }
        await send_response(send, 200, json.dumps({"status": "healthy", "tools": tool_count, "version": "10.0", "configured": config}).encode())
        return
    
    if path.startswith("/webhook") and method == "POST":
        await handle_webhook(scope, receive, send)
        return
    
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
        await send_response(send, 200, json.dumps({"name": "juggernaut-mcp", "version": "10.0", "tools": tool_count}).encode())
        return
    
    await send_response(send, 404, b'{"error":"Not found"}')

if __name__ == "__main__":
    logger.info(f"Starting JUGGERNAUT MCP Server v10 on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
