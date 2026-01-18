"""
JUGGERNAUT Tool Execution Framework
Phase 2.4: Tool interface, registry, execution wrapper, error handling
"""

import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone
import traceback

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"


def _query(sql: str) -> Dict[str, Any]:
    """Execute SQL query."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": NEON_CONNECTION_STRING
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _format_value(v: Any) -> str:
    """Format value for SQL."""
    if v is None:
        return "NULL"
    elif isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, (dict, list)):
        json_str = json.dumps(v).replace("'", "''")
        return f"'{json_str}'"
    else:
        escaped = str(v).replace("'", "''")
        return f"'{escaped}'"


# ============================================================
# TOOL INTERFACE STANDARD
# ============================================================

class ToolResult:
    """Standard result object from tool execution."""
    def __init__(self, success: bool, data: Any = None, error: str = None, 
                 cost_cents: int = 0, tokens_used: int = 0, metadata: Dict = None):
        self.success = success
        self.data = data
        self.error = error
        self.cost_cents = cost_cents
        self.tokens_used = tokens_used
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "cost_cents": self.cost_cents,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class Tool:
    """Base class for all tools."""
    
    def __init__(self, name: str, description: str, category: str = "general",
                 required_permissions: List[str] = None,
                 max_cost_cents: int = 100,
                 requires_approval: bool = False):
        self.name = name
        self.description = description
        self.category = category
        self.required_permissions = required_permissions or []
        self.max_cost_cents = max_cost_cents
        self.requires_approval = requires_approval
        self.version = "1.0.0"
    
    def execute(self, params: Dict, worker_id: str = None) -> ToolResult:
        """Override this method in subclasses."""
        raise NotImplementedError("Tool must implement execute()")
    
    def validate_params(self, params: Dict) -> tuple[bool, str]:
        """Validate input parameters. Override in subclasses."""
        return True, ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "required_permissions": self.required_permissions,
            "max_cost_cents": self.max_cost_cents,
            "requires_approval": self.requires_approval,
            "version": self.version
        }


# ============================================================
# TOOL REGISTRY
# ============================================================

# In-memory tool registry (for fast lookups)
_TOOL_REGISTRY: Dict[str, Tool] = {}


def register_tool(tool: Tool) -> bool:
    """Register a tool in the registry."""
    _TOOL_REGISTRY[tool.name] = tool
    
    # Also persist to database for discovery
    sql = f"""
    INSERT INTO tool_registry (
        name, description, category, required_permissions,
        max_cost_cents, requires_approval, version, status,
        created_at, updated_at
    ) VALUES (
        {_format_value(tool.name)},
        {_format_value(tool.description)},
        {_format_value(tool.category)},
        {_format_value(tool.required_permissions)},
        {tool.max_cost_cents},
        {_format_value(tool.requires_approval)},
        {_format_value(tool.version)},
        'active',
        NOW(), NOW()
    )
    ON CONFLICT (name) DO UPDATE SET
        description = EXCLUDED.description,
        category = EXCLUDED.category,
        required_permissions = EXCLUDED.required_permissions,
        max_cost_cents = EXCLUDED.max_cost_cents,
        requires_approval = EXCLUDED.requires_approval,
        version = EXCLUDED.version,
        updated_at = NOW()
    """
    try:
        _query(sql)
        return True
    except Exception as e:
        print(f"Failed to register tool in DB: {e}")
        return False


def get_tool(name: str) -> Optional[Tool]:
    """Get tool from registry."""
    return _TOOL_REGISTRY.get(name)


def list_tools(category: str = None, status: str = "active") -> List[Dict]:
    """List all registered tools from database."""
    conditions = [f"status = {_format_value(status)}"]
    if category:
        conditions.append(f"category = {_format_value(category)}")
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM tool_registry {where} ORDER BY name"
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to list tools: {e}")
        return []


def find_tools_by_permission(permission: str) -> List[Dict]:
    """Find tools that require a specific permission."""
    sql = f"""
    SELECT * FROM tool_registry
    WHERE required_permissions @> {_format_value([permission])}
      AND status = 'active'
    ORDER BY name
    """
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to find tools: {e}")
        return []


# ============================================================
# TOOL EXECUTION WRAPPER
# ============================================================

def execute_tool(
    tool_name: str,
    params: Dict,
    worker_id: str,
    task_id: str = None,
    dry_run: bool = False
) -> ToolResult:
    """
    Execute a tool with full logging, permission checking, and error handling.
    
    Args:
        tool_name: Name of the tool to execute
        params: Parameters to pass to the tool
        worker_id: ID of the worker executing the tool
        task_id: Optional task ID for tracking
        dry_run: If True, validate but don't execute
    
    Returns:
        ToolResult with execution outcome
    """
    execution_id = None
    start_time = datetime.now(timezone.utc)
    
    try:
        # Get tool
        tool = get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False, 
                error=f"Tool '{tool_name}' not found in registry"
            )
        
        # Check permissions
        permission_result = _check_tool_permission(worker_id, tool)
        if not permission_result["allowed"]:
            return ToolResult(
                success=False,
                error=f"Permission denied: {permission_result['reason']}"
            )
        
        # Check if approval required
        if tool.requires_approval and not permission_result.get("pre_approved"):
            return ToolResult(
                success=False,
                error="Tool requires approval before execution",
                metadata={"requires_approval": True}
            )
        
        # Validate parameters
        valid, error = tool.validate_params(params)
        if not valid:
            return ToolResult(success=False, error=f"Invalid parameters: {error}")
        
        # Log execution start
        execution_id = _log_execution_start(tool_name, params, worker_id, task_id)
        
        # Dry run - just validate
        if dry_run:
            return ToolResult(
                success=True,
                data={"dry_run": True, "validated": True},
                metadata={"execution_id": execution_id}
            )
        
        # Execute tool
        result = tool.execute(params, worker_id)
        
        # Log execution result
        _log_execution_result(execution_id, result, start_time)
        
        result.metadata["execution_id"] = execution_id
        return result
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        tb = traceback.format_exc()
        
        # Log error
        if execution_id:
            _log_execution_error(execution_id, error_msg, tb)
        
        return ToolResult(
            success=False,
            error=error_msg,
            metadata={"traceback": tb, "execution_id": execution_id}
        )


def _check_tool_permission(worker_id: str, tool: Tool) -> Dict[str, Any]:
    """Check if worker has permission to use tool."""
    sql = f"""
    SELECT permissions, forbidden_actions, approval_required_for,
           current_day_cost_cents, max_cost_per_day_cents
    FROM worker_registry
    WHERE worker_id = {_format_value(worker_id)}
    """
    try:
        result = _query(sql)
        rows = result.get("rows", [])
        if not rows:
            return {"allowed": False, "reason": "Worker not found"}
        
        worker = rows[0]
        forbidden = worker.get("forbidden_actions") or []
        approval_for = worker.get("approval_required_for") or []
        
        # Check forbidden
        if tool.name in forbidden or tool.category in forbidden:
            return {"allowed": False, "reason": f"Tool '{tool.name}' is forbidden for this worker"}
        
        # Check required permissions
        for perm in tool.required_permissions:
            worker_perms = worker.get("permissions") or {}
            if perm not in worker_perms:
                return {"allowed": False, "reason": f"Missing required permission: {perm}"}
        
        # Check cost limit
        if tool.max_cost_cents > 0:
            current = worker.get("current_day_cost_cents") or 0
            max_daily = worker.get("max_cost_per_day_cents") or 1000
            if current + tool.max_cost_cents > max_daily:
                return {"allowed": False, "reason": "Daily cost limit would be exceeded"}
        
        # Check if approval required
        pre_approved = tool.name not in approval_for and tool.category not in approval_for
        
        return {"allowed": True, "pre_approved": pre_approved}
        
    except Exception as e:
        return {"allowed": False, "reason": f"Permission check failed: {e}"}


def _log_execution_start(tool_name: str, params: Dict, worker_id: str, task_id: str = None) -> str:
    """Log tool execution start and return execution ID."""
    sql = f"""
    INSERT INTO tool_executions (
        tool_name, worker_id, task_id, params, status, started_at
    ) VALUES (
        {_format_value(tool_name)},
        {_format_value(worker_id)},
        {_format_value(task_id)},
        {_format_value(params)},
        'running',
        NOW()
    ) RETURNING id
    """
    try:
        result = _query(sql)
        if result.get("rows"):
            return result["rows"][0].get("id")
    except Exception as e:
        print(f"Failed to log execution start: {e}")
    return None


def _log_execution_result(execution_id: str, result: ToolResult, start_time: datetime):
    """Log tool execution result."""
    if not execution_id:
        return
    
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    
    sql = f"""
    UPDATE tool_executions SET
        status = {_format_value('success' if result.success else 'failed')},
        result_data = {_format_value(result.data)},
        error_message = {_format_value(result.error)},
        cost_cents = {result.cost_cents},
        tokens_used = {result.tokens_used},
        duration_ms = {duration_ms},
        completed_at = NOW()
    WHERE id = {_format_value(execution_id)}
    """
    try:
        _query(sql)
    except Exception as e:
        print(f"Failed to log execution result: {e}")


def _log_execution_error(execution_id: str, error: str, traceback: str):
    """Log tool execution error."""
    if not execution_id:
        return
    
    sql = f"""
    UPDATE tool_executions SET
        status = 'error',
        error_message = {_format_value(error)},
        error_traceback = {_format_value(traceback)},
        completed_at = NOW()
    WHERE id = {_format_value(execution_id)}
    """
    try:
        _query(sql)
    except Exception as e:
        print(f"Failed to log execution error: {e}")


# ============================================================
# TOOL RESULT LOGGING
# ============================================================

def get_tool_executions(
    tool_name: str = None,
    worker_id: str = None,
    task_id: str = None,
    status: str = None,
    limit: int = 50
) -> List[Dict]:
    """Get tool execution history with filters."""
    conditions = []
    if tool_name:
        conditions.append(f"tool_name = {_format_value(tool_name)}")
    if worker_id:
        conditions.append(f"worker_id = {_format_value(worker_id)}")
    if task_id:
        conditions.append(f"task_id = {_format_value(task_id)}")
    if status:
        conditions.append(f"status = {_format_value(status)}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM tool_executions {where} ORDER BY started_at DESC LIMIT {limit}"
    
    try:
        result = _query(sql)
        return result.get("rows", [])
    except Exception as e:
        print(f"Failed to get executions: {e}")
        return []


def get_execution_stats(worker_id: str = None, days: int = 7) -> Dict[str, Any]:
    """Get tool execution statistics."""
    worker_filter = f"AND worker_id = {_format_value(worker_id)}" if worker_id else ""
    
    sql = f"""
    SELECT 
        tool_name,
        COUNT(*) as total_executions,
        COUNT(*) FILTER (WHERE status = 'success') as successful,
        COUNT(*) FILTER (WHERE status IN ('failed', 'error')) as failed,
        AVG(duration_ms) as avg_duration_ms,
        SUM(cost_cents) as total_cost_cents,
        SUM(tokens_used) as total_tokens
    FROM tool_executions
    WHERE started_at > NOW() - INTERVAL '{days} days'
    {worker_filter}
    GROUP BY tool_name
    ORDER BY total_executions DESC
    """
    try:
        result = _query(sql)
        return {
            "period_days": days,
            "tools": result.get("rows", [])
        }
    except Exception as e:
        print(f"Failed to get stats: {e}")
        return {"error": str(e)}


# ============================================================
# BUILT-IN TOOLS
# ============================================================

class WebSearchTool(Tool):
    """Web search tool using available search APIs."""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for information",
            category="research",
            required_permissions=["web_access"],
            max_cost_cents=5,
            requires_approval=False
        )
    
    def execute(self, params: Dict, worker_id: str = None) -> ToolResult:
        query = params.get("query")
        if not query:
            return ToolResult(success=False, error="Missing required parameter: query")
        
        # Placeholder - would integrate with actual search API
        return ToolResult(
            success=True,
            data={"message": "Web search placeholder - integrate with search API"},
            cost_cents=1
        )


class DatabaseQueryTool(Tool):
    """Execute read-only database queries."""
    
    def __init__(self):
        super().__init__(
            name="db_query",
            description="Execute read-only database queries",
            category="data",
            required_permissions=["db_read"],
            max_cost_cents=1,
            requires_approval=False
        )
    
    def validate_params(self, params: Dict) -> tuple[bool, str]:
        sql = params.get("sql", "").upper()
        # Only allow SELECT queries
        if not sql.strip().startswith("SELECT"):
            return False, "Only SELECT queries are allowed"
        # Block dangerous patterns
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
        for d in dangerous:
            if d in sql:
                return False, f"Query contains forbidden keyword: {d}"
        return True, ""
    
    def execute(self, params: Dict, worker_id: str = None) -> ToolResult:
        sql = params.get("sql")
        try:
            result = _query(sql)
            return ToolResult(
                success=True,
                data=result.get("rows", []),
                metadata={"row_count": len(result.get("rows", []))}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# Register built-in tools
def initialize_builtin_tools():
    """Register all built-in tools."""
    register_tool(WebSearchTool())
    register_tool(DatabaseQueryTool())
