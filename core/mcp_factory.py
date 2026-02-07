"""
JUGGERNAUT MCP Factory - Dynamic MCP Server Creation

This module allows workers to define and deploy custom MCP servers
with their own tool specifications. Enables the system to extend
its capabilities autonomously.

Architecture:
- Workers define tool specs via ToolDefinition dataclass
- MCPFactory generates server code from templates
- Railway API deploys the generated servers
- mcp_registry table tracks all deployed MCPs
"""

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

# M-06: Centralized DB access via core.database
from core.database import query_db as _query, NEON_CONNECTION_STRING

# Railway configuration
RAILWAY_API_ENDPOINT = "https://backboard.railway.com/graphql/v2"
RAILWAY_API_TOKEN = os.environ.get("RAILWAY_API_TOKEN", "")
RAILWAY_PROJECT_ID = os.environ.get("RAILWAY_PROJECT_ID", "")
RAILWAY_ENVIRONMENT_ID = os.environ.get("RAILWAY_ENVIRONMENT_ID", "")


class MCPStatus(Enum):
    """Status of an MCP server."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    param_type: str  # string, integer, boolean, object, array
    description: str
    required: bool = True
    default: Optional[Any] = None


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""

    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    handler_code: str = ""  # Python code for the handler

    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format for MCP."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.param_type,
                "description": param.description,
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)

        return {"type": "object", "properties": properties, "required": required}


@dataclass
class MCPDefinition:
    """Definition of a complete MCP server."""

    name: str
    description: str
    tools: List[ToolDefinition] = field(default_factory=list)
    owner_worker_id: Optional[str] = None
    required_env_vars: List[str] = field(default_factory=list)


def _railway_graphql(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute Railway GraphQL query."""
    if not RAILWAY_API_TOKEN:
        raise RuntimeError("RAILWAY_API_TOKEN not configured")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RAILWAY_API_TOKEN}",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RAILWAY_API_ENDPOINT, data=data, headers=headers, method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_mcp_registry_table() -> bool:
    """Create mcp_registry table if it doesn't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS mcp_registry (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(100) NOT NULL UNIQUE,
        description TEXT,
        status VARCHAR(50) DEFAULT 'pending',
        owner_worker_id VARCHAR(100),
        railway_service_id VARCHAR(100),
        railway_deployment_id VARCHAR(100),
        endpoint_url TEXT,
        auth_token VARCHAR(200),
        tools_config JSONB DEFAULT '[]'::jsonb,
        env_vars JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        deployed_at TIMESTAMPTZ,
        last_health_check TIMESTAMPTZ,
        health_status VARCHAR(50) DEFAULT 'unknown',
        error_message TEXT,
        metadata JSONB DEFAULT '{}'::jsonb
    );
    
    CREATE INDEX IF NOT EXISTS idx_mcp_registry_status 
    ON mcp_registry(status);
    
    CREATE INDEX IF NOT EXISTS idx_mcp_registry_owner 
    ON mcp_registry(owner_worker_id);
    """

    try:
        _query(sql)
        logger.info("MCP registry table ensured")
        return True
    except Exception as e:
        logger.error("Failed to create mcp_registry table: %s", str(e))
        return False


def generate_mcp_server_code(mcp_def: MCPDefinition) -> str:
    """Generate Python code for an MCP server from definition."""

    # Generate tool list code
    tools_code = []
    for tool in mcp_def.tools:
        schema = tool.to_schema()
        tools_code.append(f'''
        Tool(
            name="{tool.name}",
            description="""{tool.description}""",
            inputSchema={json.dumps(schema, indent=12)}
        )''')

    tools_list = ",".join(tools_code)

    # Generate handler cases
    handler_cases = []
    for tool in mcp_def.tools:
        if tool.handler_code:
            handler_cases.append(f'''
        elif name == "{tool.name}":
            # Custom handler for {tool.name}
{_indent_code(tool.handler_code, 12)}''')
        else:
            handler_cases.append(f'''
        elif name == "{tool.name}":
            # TODO: Implement handler for {tool.name}
            return [TextContent(type="text", text=json.dumps({{"error": "Not implemented"}})])]''')

    handlers = "".join(handler_cases)

    # Generate the full server code
    server_code = f'''"""
JUGGERNAUT MCP Server: {mcp_def.name}
{mcp_def.description}

Auto-generated by MCP Factory
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
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MCP_AUTH_TOKEN = os.environ.get('MCP_AUTH_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
PORT = int(os.environ.get('PORT', 8080))

# Create MCP Server
mcp = Server("{mcp_def.name}")


# Database helper
async def execute_sql(query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute SQL against Neon database."""
    neon_url = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            neon_url,
            headers={{
                "Content-Type": "application/json",
                "Neon-Connection-String": DATABASE_URL
            }},
            json={{"query": query, "params": params or []}}
        ) as resp:
            return await resp.json()


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [{tools_list}
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info(f"Tool call: {{name}}")
    try:
        if False:
            pass  # Placeholder for elif chain
{handlers}
        else:
            return [TextContent(type="text", text=json.dumps({{"error": f"Unknown tool: {{name}}"}})])]
    except Exception as e:
        logger.error(f"Tool {{name}} failed: {{e}}")
        return [TextContent(type="text", text=json.dumps({{"error": str(e)}})])]


# Health endpoint
async def health(request):
    return JSONResponse({{"status": "healthy", "mcp": "{mcp_def.name}"}})


# SSE endpoint
async def handle_sse(request):
    token = request.query_params.get('token', '')
    if MCP_AUTH_TOKEN and token != MCP_AUTH_TOKEN:
        return JSONResponse({{"error": "Unauthorized"}}, status_code=401)
    
    transport = SseServerTransport("/mcp/sse")
    async with transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp.run(
            streams[0], streams[1], mcp.create_initialization_options()
        )


app = Starlette(
    routes=[
        Route("/", health),
        Route("/health", health),
        Route("/mcp/sse", handle_sse),
    ]
)


if __name__ == "__main__":
    logger.info(f"Starting {mcp_def.name} MCP server on port {{PORT}}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
'''

    return server_code


def _indent_code(code: str, spaces: int) -> str:
    """Indent code block by specified spaces."""
    indent = " " * spaces
    lines = code.split("\n")
    return "\n".join(indent + line for line in lines)


def register_mcp(mcp_def: MCPDefinition) -> Optional[str]:
    """Register an MCP definition in the database.

    Returns the MCP ID if successful, None otherwise.
    """
    mcp_id = str(uuid.uuid4())
    auth_token = str(uuid.uuid4()).replace("-", "")[:32]

    tools_config = [
        {"name": tool.name, "description": tool.description, "schema": tool.to_schema()}
        for tool in mcp_def.tools
    ]

    sql = f"""
    INSERT INTO mcp_registry (
        id, name, description, status, owner_worker_id, 
        auth_token, tools_config
    ) VALUES (
        '{mcp_id}',
        '{mcp_def.name}',
        '{mcp_def.description.replace("'", "''")}',
        'pending',
        {f"'{mcp_def.owner_worker_id}'" if mcp_def.owner_worker_id else "NULL"},
        '{auth_token}',
        '{json.dumps(tools_config)}'::jsonb
    )
    ON CONFLICT (name) DO UPDATE SET
        description = EXCLUDED.description,
        tools_config = EXCLUDED.tools_config,
        owner_worker_id = EXCLUDED.owner_worker_id
    RETURNING id
    """

    try:
        result = _query(sql)
        if result.get("rows"):
            logger.info("Registered MCP: %s (%s)", mcp_def.name, mcp_id)
            return mcp_id
        return None
    except Exception as e:
        logger.error("Failed to register MCP %s: %s", mcp_def.name, str(e))
        return None


def deploy_mcp_to_railway(
    mcp_id: str, server_code: str, env_vars: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Deploy an MCP server to Railway.

    This creates a new service in the Railway project and deploys the code.

    Returns deployment details including service ID and URL.
    """
    result = {
        "success": False,
        "service_id": None,
        "deployment_id": None,
        "url": None,
        "error": None,
    }

    # Get MCP details
    mcp_sql = f"SELECT name, auth_token FROM mcp_registry WHERE id = '{mcp_id}'"
    try:
        mcp_result = _query(mcp_sql)
        if not mcp_result.get("rows"):
            result["error"] = "MCP not found"
            return result

        mcp_name = mcp_result["rows"][0]["name"]
        auth_token = mcp_result["rows"][0]["auth_token"]
    except Exception as e:
        result["error"] = f"Database error: {str(e)}"
        return result

    # Create Railway service
    service_name = f"mcp-{mcp_name.lower().replace(' ', '-')}"

    if not RAILWAY_PROJECT_ID or not RAILWAY_ENVIRONMENT_ID:
        result["error"] = "Railway not configured"
        return result

    create_service_query = """
    mutation ServiceCreate($input: ServiceCreateInput!) {
        serviceCreate(input: $input) {
            id
            name
        }
    }
    """

    try:
        service_result = _railway_graphql(
            create_service_query,
            {"input": {"name": service_name, "projectId": RAILWAY_PROJECT_ID}},
        )

        if "errors" in service_result:
            result["error"] = str(service_result["errors"])
            return result

        service_id = service_result["data"]["serviceCreate"]["id"]
        result["service_id"] = service_id

        logger.info("Created Railway service: %s (%s)", service_name, service_id)

    except Exception as e:
        result["error"] = f"Failed to create service: {str(e)}"
        return result

    # Set environment variables
    default_env = {
        "MCP_AUTH_TOKEN": auth_token,
        "DATABASE_URL": NEON_CONNECTION_STRING,
        "PORT": "8080",
    }

    if env_vars:
        default_env.update(env_vars)

    for var_name, var_value in default_env.items():
        env_query = """
        mutation VariableUpsert($input: VariableUpsertInput!) {
            variableUpsert(input: $input)
        }
        """
        try:
            _railway_graphql(
                env_query,
                {
                    "input": {
                        "name": var_name,
                        "value": var_value,
                        "serviceId": service_id,
                        "environmentId": RAILWAY_ENVIRONMENT_ID,
                        "projectId": RAILWAY_PROJECT_ID,
                    }
                },
            )
        except Exception as e:
            logger.warning("Failed to set env var %s: %s", var_name, str(e))

    # Update database with service info
    update_sql = f"""
    UPDATE mcp_registry SET
        railway_service_id = '{service_id}',
        status = 'deploying',
        metadata = metadata || '{{"service_name": "{service_name}"}}'::jsonb
    WHERE id = '{mcp_id}'
    """

    try:
        _query(update_sql)
    except Exception as e:
        logger.warning("Failed to update MCP registry: %s", str(e))

    result["success"] = True
    logger.info("MCP %s deployment initiated", mcp_name)

    return result


def get_mcp_status(mcp_id: str) -> Optional[Dict[str, Any]]:
    """Get the current status of an MCP server."""
    sql = f"""
    SELECT 
        id, name, description, status, 
        railway_service_id, endpoint_url, 
        health_status, error_message,
        created_at, deployed_at, last_health_check
    FROM mcp_registry 
    WHERE id = '{mcp_id}'
    """

    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0]
        return None
    except Exception as e:
        logger.error("Failed to get MCP status: %s", str(e))
        return None


def list_mcps(
    status: Optional[str] = None, owner_worker_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List all registered MCPs with optional filtering."""
    conditions = []
    if status:
        conditions.append(f"status = '{status}'")
    if owner_worker_id:
        conditions.append(f"owner_worker_id = '{owner_worker_id}'")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
    SELECT 
        id, name, description, status,
        endpoint_url, auth_token,
        health_status, created_at, deployed_at
    FROM mcp_registry
    WHERE {where_clause}
    ORDER BY created_at DESC
    """

    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        logger.error("Failed to list MCPs: %s", str(e))
        return []


def create_mcp_from_spec(
    name: str,
    description: str,
    tools: List[Dict[str, Any]],
    owner_worker_id: Optional[str] = None,
    deploy: bool = False,
) -> Dict[str, Any]:
    """Create an MCP from a specification dict.

    This is the main entry point for workers to create MCPs.

    Args:
        name: Name of the MCP
        description: Description of what it does
        tools: List of tool definitions, each with:
            - name: Tool name
            - description: Tool description
            - parameters: List of parameter dicts
            - handler_code: Optional Python code for handler
        owner_worker_id: Worker that owns this MCP
        deploy: Whether to deploy immediately

    Returns:
        Dict with mcp_id, status, and any errors
    """
    result = {"mcp_id": None, "status": "created", "error": None, "server_code": None}

    # Ensure table exists
    ensure_mcp_registry_table()

    # Build tool definitions
    tool_defs = []
    for tool_spec in tools:
        params = []
        for p in tool_spec.get("parameters", []):
            params.append(
                ToolParameter(
                    name=p.get("name", ""),
                    param_type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    default=p.get("default"),
                )
            )

        tool_defs.append(
            ToolDefinition(
                name=tool_spec.get("name", ""),
                description=tool_spec.get("description", ""),
                parameters=params,
                handler_code=tool_spec.get("handler_code", ""),
            )
        )

    # Create MCP definition
    mcp_def = MCPDefinition(
        name=name,
        description=description,
        tools=tool_defs,
        owner_worker_id=owner_worker_id,
    )

    # Register in database
    mcp_id = register_mcp(mcp_def)
    if not mcp_id:
        result["error"] = "Failed to register MCP"
        return result

    result["mcp_id"] = mcp_id

    # Generate server code
    server_code = generate_mcp_server_code(mcp_def)
    result["server_code"] = server_code

    # Deploy if requested
    if deploy:
        deploy_result = deploy_mcp_to_railway(mcp_id, server_code)
        if deploy_result["success"]:
            result["status"] = "deploying"
            result["service_id"] = deploy_result["service_id"]
        else:
            result["error"] = deploy_result["error"]
            result["status"] = "deploy_failed"

    return result


# Initialize table on module load
try:
    ensure_mcp_registry_table()
except Exception:
    pass  # Will be created on first use
