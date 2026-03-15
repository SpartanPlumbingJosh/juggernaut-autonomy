"""
JUGGERNAUT MCP Server - Full Stack (v10)

Complete autonomous capabilities:
- Database: Supabase PostgreSQL (spartan_ops)
- GitHub: Full repo management
- Railway: Deployment management
- Vercel: Frontend deployment
- Slack: Team messaging
- Puppeteer: Browser automation
- Perplexity: AI-powered search
- ServiceTitan: Plumbing business operations
- MS Graph: Office 365 email & calendar
- Storage: File storage (DB fallback)
- AI: OpenRouter
- Webhooks: Event receiver
- MCP Factory: Create new MCPs
- Image Generation (OpenRouter)
- Vector DB (Pinecone)
- Social Media (Meta, Twitter)
- PDF Generation
- Google Maps/Geocoding
- Google Sheets
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

# LLM API
_OPENROUTER_CHAT_DEFAULT = 'https://openrouter.ai/api/v1/chat/completions'
_OPENROUTER_IMAGE_DEFAULT = 'https://openrouter.ai/api/v1/images/generations'
_LLM_BASE = (os.environ.get('LLM_API_BASE') or os.environ.get('OPENROUTER_ENDPOINT') or '').strip().rstrip('/')
LLM_CHAT_ENDPOINT = f'{_LLM_BASE}/chat/completions' if _LLM_BASE else _OPENROUTER_CHAT_DEFAULT
LLM_IMAGE_ENDPOINT = f'{_LLM_BASE}/images/generations' if _LLM_BASE else _OPENROUTER_IMAGE_DEFAULT
OPENROUTER_API_KEY = os.environ.get('LLM_API_KEY') or os.environ.get('OPENROUTER_API_KEY') or ''
OPENROUTER_MAX_PRICE_PROMPT = os.environ.get('OPENROUTER_MAX_PRICE_PROMPT', '1')
OPENROUTER_MAX_PRICE_COMPLETION = os.environ.get('OPENROUTER_MAX_PRICE_COMPLETION', '2')

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
GOOGLE_SERVICE_ACCOUNT = os.environ.get('GOOGLE_SERVICE_ACCOUNT', '')
GOOGLE_SHEETS_TOKEN = os.environ.get('GOOGLE_SHEETS_TOKEN', '')

# Supabase (spartan_ops)
SUPABASE_RPC_URL = os.environ.get('SUPABASE_RPC_URL', 'https://kong.thejuggernaut.org/rest/v1/rpc/run_sql')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
CF_ACCESS_CLIENT_ID = os.environ.get('CF_ACCESS_CLIENT_ID', '')
CF_ACCESS_CLIENT_SECRET = os.environ.get('CF_ACCESS_CLIENT_SECRET', '')

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
    """Execute SQL against Supabase database via PostgREST RPC."""
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Profile": "spartan_ops",
        "Accept-Profile": "spartan_ops",
    }
    if CF_ACCESS_CLIENT_ID:
        headers["CF-Access-Client-Id"] = CF_ACCESS_CLIENT_ID
        headers["CF-Access-Client-Secret"] = CF_ACCESS_CLIENT_SECRET
    async with aiohttp.ClientSession() as session:
        async with session.post(SUPABASE_RPC_URL, headers=headers, json={"query": query}) as resp:
            data = await resp.json()
            # Wrap in Neon-compatible format for hq_query consumers
            if isinstance(data, list):
                fields = [{"name": k, "dataTypeID": 25, "tableID": 0, "columnID": 0, "dataTypeSize": -1, "dataTypeModifier": -1, "format": "text"} for k in (data[0].keys() if data else [])]
                return {"fields": fields, "rows": data, "command": "SELECT", "rowCount": len(data), "rowAsArray": False}
            elif isinstance(data, dict) and "command" in data:
                return data
            return {"fields": [], "rows": [], "command": "UNKNOWN", "rowCount": 0, "rowAsArray": False, "raw": data}


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
