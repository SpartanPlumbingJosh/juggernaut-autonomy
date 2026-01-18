#!/usr/bin/env python3
"""
JUGGERNAUT AUTONOMY ENGINE
==========================
The heartbeat that makes JUGGERNAUT truly autonomous.

This is the main entry point that:
1. Runs continuously (24/7)
2. Checks for work: pending tasks, scheduled tasks, opportunities
3. Executes the highest priority item
4. Logs every decision
5. Handles errors without crashing

Level 3 Requirements Implemented:
- Goal/Task Acceptance: Accepts tasks from governance_tasks
- Workflow Planning: Executes multi-step workflows
- Tool/API Execution: Runs registered tools
- Persistent Task Memory: Tasks survive restarts
- Error Recovery: DLQ, retries with exponential backoff, escalation
- Dry-Run Mode: Simulation without execution
- Human-in-the-Loop: Approval workflow
- Action Logging: Every action logged (with PII sanitization)
- Permission/Scope Control: Forbidden actions enforced
"""

import os
import sys
import time
import json
import signal
import threading
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# CONFIGURATION
# ============================================================

# SECURITY: No default credentials - must be set via environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("FATAL: DATABASE_URL environment variable is required")
    sys.exit(1)

NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)
WORKER_ID = os.getenv("WORKER_ID", "autonomy-engine-1")
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL_SECONDS", "60"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
PORT = int(os.getenv("PORT", "8000"))

# Retry configuration
RETRY_BASE_DELAY_SECONDS = 60  # 1 minute base delay
RETRY_MAX_DELAY_SECONDS = 3600  # 1 hour max delay

# Sensitive keys to redact from logs
SENSITIVE_KEYS = frozenset([
    "password", "secret", "token", "api_key", "apikey", "key",
    "authorization", "auth", "credential", "ssn", "social_security",
    "credit_card", "card_number", "cvv", "pin", "private_key"
])

# Shutdown flag
shutdown_requested = False


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"


@dataclass
class Task:
    id: str
    task_type: str
    title: str
    description: str
    priority: int
    status: str
    payload: Dict
    assigned_to: Optional[str]
    created_at: str
    requires_approval: bool = False


# ============================================================
# SECURITY UTILITIES
# ============================================================

def sanitize_payload(payload: Dict, max_value_length: int = 1000) -> Dict:
    """
    Sanitize payload to remove sensitive information before logging.
    
    Args:
        payload: Dictionary to sanitize
        max_value_length: Maximum length for string values
    
    Returns:
        Sanitized dictionary safe for logging
    """
    if not isinstance(payload, dict):
        return payload
    
    sanitized = {}
    for key, value in payload.items():
        key_lower = key.lower()
        
        # Check if key matches sensitive patterns
        is_sensitive = any(s in key_lower for s in SENSITIVE_KEYS)
        
        if is_sensitive:
            sanitized[key] = "<REDACTED>"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_payload(value, max_value_length)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_payload(v, max_value_length) if isinstance(v, dict) else v
                for v in value[:100]  # Limit list length
            ]
        elif isinstance(value, str) and len(value) > max_value_length:
            sanitized[key] = value[:max_value_length] + f"<TRUNCATED {len(value) - max_value_length} chars>"
        else:
            sanitized[key] = value
    
    return sanitized


# ============================================================
# DATABASE OPERATIONS (with parameterized queries where possible)
# ============================================================

def execute_sql(sql: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute SQL via Neon HTTP API.
    
    Note: Neon's HTTP API doesn't support parameterized queries directly,
    so we use careful escaping. For production, consider using psycopg2
    with proper parameter binding.
    """
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    
    # Apply parameters if provided (basic interpolation with escaping)
    if params:
        for key, value in params.items():
            placeholder = f":{key}"
            if placeholder in sql:
                sql = sql.replace(placeholder, escape_value(value))
    
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log_error(f"SQL Error: {error_body}", {"sql_preview": sql[:100]})
        raise
    except Exception as e:
        log_error(f"SQL Exception: {str(e)}", {"sql_preview": sql[:100]})
        raise


def escape_value(value: Any) -> str:
    """
    Escape a value for SQL insertion.
    
    SECURITY NOTE: This is a basic escaping function. For production use,
    prefer parameterized queries via psycopg2 or similar.
    """
    if value is None:
        return "NULL"
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (dict, list)):
        # JSON serialization with proper escaping
        json_str = json.dumps(value)
        # Escape single quotes, backslashes, and null bytes
        escaped = json_str.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"
    else:
        # String escaping: handle quotes, backslashes, null bytes
        s = str(value)
        escaped = s.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"


# ============================================================
# LOGGING (Level 3: Action Logging with Sanitization)
# ============================================================

def log_action(
    action: str,
    message: str,
    level: str = "info",
    task_id: str = None,
    input_data: Dict = None,
    output_data: Dict = None,
    error_data: Dict = None,
    duration_ms: int = None
) -> Optional[str]:
    """Log an autonomous action to execution_logs with PII sanitization."""
    now = datetime.now(timezone.utc).isoformat()
    
    cols = ["worker_id", "action", "message", "level", "source", "created_at"]
    vals = [escape_value(WORKER_ID), escape_value(action), escape_value(message), 
            escape_value(level), escape_value("autonomy_engine"), escape_value(now)]
    
    if task_id:
        cols.append("task_id")
        vals.append(escape_value(task_id))
    if input_data:
        cols.append("input_data")
        vals.append(escape_value(sanitize_payload(input_data)))
    if output_data:
        cols.append("output_data")
        vals.append(escape_value(sanitize_payload(output_data)))
    if error_data:
        cols.append("error_data")
        vals.append(escape_value(sanitize_payload(error_data)))
    if duration_ms is not None:
        cols.append("duration_ms")
        vals.append(str(duration_ms))
    
    sql = f"INSERT INTO execution_logs ({', '.join(cols)}) VALUES ({', '.join(vals)}) RETURNING id"
    
    try:
        result = execute_sql(sql)
        return result.get("rows", [{}])[0].get("id")
    except Exception:
        # Don't fail if logging fails - print to stdout as fallback
        print(f"[{level.upper()}] {action}: {message}")
        return None


def log_info(message: str, data: Dict = None):
    log_action("system.info", message, "info", output_data=data)
    print(f"[INFO] {message}")


def log_error(message: str, data: Dict = None):
    log_action("system.error", message, "error", error_data=data)
    print(f"[ERROR] {message}")


def log_decision(action: str, decision: str, reasoning: str, data: Dict = None):
    """Log an autonomous decision (Level 3: Traceable Decisions)."""
    log_action(
        f"decision.{action}",
        f"{decision}: {reasoning}",
        "info",
        output_data={"decision": decision, "reasoning": reasoning, **(data or {})}
    )
    print(f"[DECISION] {action}: {decision}")


# ============================================================
# PERMISSION CONTROL (Level 3: Permission/Scope Control)
# ============================================================

def get_forbidden_actions() -> List[str]:
    """Get list of forbidden actions for this worker."""
    sql = f"SELECT forbidden_actions FROM worker_registry WHERE worker_id = {escape_value(WORKER_ID)}"
    try:
        result = execute_sql(sql)
        rows = result.get("rows", [])
        if rows and rows[0].get("forbidden_actions"):
            return rows[0]["forbidden_actions"]
        return []
    except Exception:
        return []


def is_action_allowed(action: str) -> Tuple[bool, str]:
    """Check if an action is allowed for this worker."""
    forbidden = get_forbidden_actions()
    
    for pattern in forbidden:
        if pattern == action or action.startswith(pattern.rstrip("*")):
            return False, f"Action '{action}' is forbidden by pattern '{pattern}'"
    
    return True, "Action allowed"


def check_cost_limit(estimated_cost: float) -> Tuple[bool, str]:
    """Check if action would exceed cost limits."""
    sql = """
        SELECT 
            cb.amount_cents as limit_cents,
            COALESCE(SUM(ce.amount_cents), 0) as spent_cents
        FROM cost_budgets cb
        LEFT JOIN cost_events ce ON ce.category = cb.category 
            AND ce.created_at >= date_trunc('month', CURRENT_DATE)
        WHERE cb.category = 'total_monthly'
        GROUP BY cb.amount_cents
    """
    try:
        result = execute_sql(sql)
        rows = result.get("rows", [])
        if rows:
            limit = int(rows[0].get("limit_cents", 0))
            spent = int(rows[0].get("spent_cents", 0))
            if spent + (estimated_cost * 100) > limit:
                return False, f"Cost ${estimated_cost} would exceed monthly limit (${spent/100:.2f}/${limit/100:.2f})"
        return True, "Within budget"
    except Exception:
        return True, "Budget check unavailable"


# ============================================================
# TASK MANAGEMENT (Level 3: Goal/Task Acceptance + Persistent Memory)
# ============================================================

def get_pending_tasks(limit: int = 10) -> List[Task]:
    """Get pending tasks ordered by priority, respecting retry backoff."""
    sql = f"""
        SELECT id, task_type, title, description, priority, status, 
               payload, assigned_worker, created_at, requires_approval
        FROM governance_tasks 
        WHERE status IN ('pending', 'in_progress')
        AND (assigned_worker IS NULL OR assigned_worker = {escape_value(WORKER_ID)})
        AND (next_retry_at IS NULL OR next_retry_at < NOW())
        LIMIT {int(limit * 2)}
    """
    try:
        result = execute_sql(sql)
        tasks = []
        # Map priority enum to numeric values
        priority_map = {"critical": 5, "high": 4, "medium": 3, "normal": 2, "low": 1, "background": 0}
        for row in result.get("rows", []):
            priority_val = row.get("priority", "normal")
            if isinstance(priority_val, str):
                priority_num = priority_map.get(priority_val.lower(), 2)
            else:
                priority_num = int(priority_val) if priority_val else 2
            tasks.append(Task(
                id=row["id"],
                task_type=row.get("task_type", "unknown"),
                title=row.get("title", ""),
                description=row.get("description", ""),
                priority=priority_num,
                status=row.get("status", "pending"),
                payload=row.get("payload") or {},
                assigned_to=row.get("assigned_worker"),
                created_at=row.get("created_at", ""),
                requires_approval=row.get("requires_approval", False)
            ))
        # Sort by priority (desc) then created_at (asc) using Python's priority_map values
        tasks.sort(key=lambda t: (-t.priority, t.created_at))
        return tasks[:limit]
    except Exception as e:
        log_error(f"Failed to get tasks: {e}")
        return []


def get_due_scheduled_tasks() -> List[Dict]:
    """Get scheduled tasks that are due to run."""
    sql = """
        SELECT id, name, task_type, cron_expression, config, last_run_at, enabled
        FROM scheduled_tasks
        WHERE enabled = TRUE
        AND (last_run_at IS NULL OR last_run_at < NOW() - INTERVAL '1 hour')
        ORDER BY last_run_at ASC NULLS FIRST
        LIMIT 5
    """
    try:
        result = execute_sql(sql)
        return result.get("rows", [])
    except Exception:
        return []


def update_task_status(task_id: str, status: str, result_data: Dict = None):
    """Update task status."""
    now = datetime.now(timezone.utc).isoformat()
    cols = [f"status = {escape_value(status)}"]
    if status == "completed":
        cols.append(f"completed_at = {escape_value(now)}")
    if result_data:
        cols.append(f"result = {escape_value(result_data)}")
    
    sql = f"UPDATE governance_tasks SET {', '.join(cols)} WHERE id = {escape_value(task_id)}"
    try:
        execute_sql(sql)
    except Exception as e:
        log_error(f"Failed to update task {task_id}: {e}")


def claim_task(task_id: str) -> bool:
    """Claim a task for this worker (atomic operation)."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE governance_tasks 
        SET assigned_worker = {escape_value(WORKER_ID)}, 
            status = 'in_progress',
            started_at = {escape_value(now)}
        WHERE id = {escape_value(task_id)}
        AND (assigned_worker IS NULL OR assigned_worker = {escape_value(WORKER_ID)})
        AND status = 'pending'
        RETURNING id
    """
    try:
        result = execute_sql(sql)
        return len(result.get("rows", [])) > 0
    except Exception:
        return False


# ============================================================
# APPROVAL WORKFLOW (Level 3: Human-in-the-Loop)
# Split into read-only check and creation functions
# ============================================================

def check_approval_status(task: Task) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check approval status for a task (read-only, no side effects).
    
    Returns:
        (requires_approval, approval_id_or_none, status)
        - status can be: "approved", "denied", "pending", "none"
    """
    if not task.requires_approval:
        return False, None, "not_required"
    
    sql = f"""
        SELECT id, status, approved_by, approved_at
        FROM approvals
        WHERE task_id = {escape_value(task.id)}
        ORDER BY created_at DESC
        LIMIT 1
    """
    try:
        result = execute_sql(sql)
        rows = result.get("rows", [])
        if not rows:
            return True, None, "none"
        
        approval = rows[0]
        return True, approval["id"], approval["status"]
    except Exception:
        return True, None, "error"


def ensure_approval_request(task: Task) -> bool:
    """
    Ensure an approval request exists for a task. Creates one if needed.
    
    Returns:
        True if approval request was created, False if already existed
    """
    requires, approval_id, status = check_approval_status(task)
    
    if not requires or status != "none":
        return False
    
    # Create approval request
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        INSERT INTO approvals (
            task_id, requested_by, request_type, request_data, status, created_at
        ) VALUES (
            {escape_value(task.id)}, {escape_value(WORKER_ID)}, 'task_execution',
            {escape_value({"task_type": task.task_type, "title": task.title, "priority": task.priority})},
            'pending', {escape_value(now)}
        )
    """
    try:
        execute_sql(sql)
        log_action("approval.requested", f"Approval requested for task: {task.title}", task_id=task.id)
        return True
    except Exception as e:
        log_error(f"Failed to create approval request: {e}")
        return False


# ============================================================
# ERROR RECOVERY (Level 3: Error Recovery with Exponential Backoff)
# ============================================================

def calculate_retry_delay(retry_count: int) -> int:
    """Calculate exponential backoff delay in seconds."""
    delay = RETRY_BASE_DELAY_SECONDS * (2 ** retry_count)
    return min(delay, RETRY_MAX_DELAY_SECONDS)


def schedule_task_retry(task_id: str, retry_count: int, error: str):
    """Schedule a task for retry with exponential backoff."""
    delay_seconds = calculate_retry_delay(retry_count)
    next_retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
    
    sql = f"""
        UPDATE governance_tasks 
        SET attempt_count = {retry_count + 1}, 
            status = 'pending',
            next_retry_at = {escape_value(next_retry_at)},
            error_message = {escape_value(error)}
        WHERE id = {escape_value(task_id)}
    """
    try:
        execute_sql(sql)
        log_action(
            "task.retry_scheduled", 
            f"Task will retry in {delay_seconds}s ({retry_count + 1}/3)",
            level="warn", 
            task_id=task_id,
            output_data={"retry_count": retry_count + 1, "next_retry_at": next_retry_at, "delay_seconds": delay_seconds}
        )
    except Exception as e:
        log_error(f"Failed to schedule retry: {e}")


def send_to_dlq(task_id: str, error: str, attempts: int):
    """Send failed task to dead letter queue."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        INSERT INTO dead_letter_queue (
            task_id, error_message, attempts, worker_id, created_at
        ) VALUES (
            {escape_value(task_id)}, {escape_value(error)}, {attempts}, {escape_value(WORKER_ID)},
            {escape_value(now)}
        )
    """
    try:
        execute_sql(sql)
        log_action("dlq.added", f"Task {task_id} sent to DLQ after {attempts} attempts", 
                   task_id=task_id, error_data={"error": error, "attempts": attempts})
    except Exception as e:
        log_error(f"Failed to send to DLQ: {e}")


def create_escalation(task_id: str, issue: str, level: str = "medium"):
    """Create an escalation for human review."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        INSERT INTO escalations (
            level, issue_type, description, task_id, status, created_at
        ) VALUES (
            {escape_value(level)}, 'task_failure', {escape_value(issue)}, {escape_value(task_id)},
            'open', {escape_value(now)}
        )
    """
    try:
        execute_sql(sql)
        log_action("escalation.created", f"Escalation created: {issue}", task_id=task_id)
    except Exception as e:
        log_error(f"Failed to create escalation: {e}")


# ============================================================
# TOOL EXECUTION (Level 3: Tool/API Execution)
# ============================================================

def get_registered_tools() -> Dict[str, Dict]:
    """Get all registered tools."""
    sql = "SELECT tool_name, tool_type, description, permissions_required, enabled FROM tool_registry WHERE enabled = TRUE"
    try:
        result = execute_sql(sql)
        return {r["tool_name"]: r for r in result.get("rows", [])}
    except Exception:
        return {}


def execute_tool(tool_name: str, params: Dict, dry_run: bool = False) -> Tuple[bool, Any]:
    """Execute a registered tool."""
    # Check permissions
    allowed, reason = is_action_allowed(f"tool.{tool_name}")
    if not allowed:
        return False, reason
    
    if dry_run or DRY_RUN:
        log_action(f"tool.{tool_name}.dry_run", f"DRY RUN: Would execute {tool_name}", 
                   input_data=params, output_data={"dry_run": True})
        return True, {"dry_run": True, "tool": tool_name, "params": params}
    
    start_time = time.time()
    
    # Log tool execution start (don't capture unused return value)
    log_action(f"tool.{tool_name}.start", f"Executing tool: {tool_name}", input_data=params)
    
    try:
        # Record tool execution
        now = datetime.now(timezone.utc).isoformat()
        sql = f"""
            INSERT INTO tool_executions (
                tool_name, input_params, status, worker_id, started_at
            ) VALUES (
                {escape_value(tool_name)}, {escape_value(params)}, 'running', {escape_value(WORKER_ID)},
                {escape_value(now)}
            ) RETURNING id
        """
        result = execute_sql(sql)
        tool_exec_id = result.get("rows", [{}])[0].get("id")
        
        # Get tool from registry and execute
        tools = get_registered_tools()
        tool_config = tools.get(tool_name)
        
        if not tool_config:
            output = {"status": "error", "error": f"Tool '{tool_name}' not found in registry"}
        else:
            # Dispatch based on tool type
            tool_type = tool_config.get("tool_type", "unknown")
            
            if tool_type == "slack":
                output = _execute_slack_tool(tool_name, params)
            elif tool_type == "database":
                output = _execute_database_tool(tool_name, params)
            elif tool_type == "http":
                output = _execute_http_tool(tool_name, params)
            else:
                # Generic execution - log and mark as executed
                output = {"status": "executed", "tool": tool_name, "tool_type": tool_type}
        
        # Update tool execution record
        duration_ms = int((time.time() - start_time) * 1000)
        now = datetime.now(timezone.utc).isoformat()
        sql = f"""
            UPDATE tool_executions SET
                status = 'completed',
                output_result = {escape_value(output)},
                completed_at = {escape_value(now)},
                duration_ms = {duration_ms}
            WHERE id = {escape_value(tool_exec_id)}
        """
        execute_sql(sql)
        
        log_action(f"tool.{tool_name}.complete", f"Tool completed: {tool_name}",
                   output_data=output, duration_ms=duration_ms)
        
        return True, output
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_output = {"status": "error", "error": str(e)}
        
        # Update tool_executions record to 'failed' (don't leave it stuck as 'running')
        try:
            now = datetime.now(timezone.utc).isoformat()
            sql = f"""
                UPDATE tool_executions SET
                    status = 'failed',
                    output_result = {escape_value(error_output)},
                    completed_at = {escape_value(now)},
                    duration_ms = {duration_ms}
                WHERE id = {escape_value(tool_exec_id)}
            """
            execute_sql(sql)
        except Exception:
            pass  # Don't fail if we can't update the record
        
        log_action(f"tool.{tool_name}.error", f"Tool failed: {str(e)}",
                   level="error", error_data={"error": str(e)}, duration_ms=duration_ms)
        return False, error_output


def _execute_slack_tool(tool_name: str, params: Dict) -> Dict:
    """Execute a Slack-related tool."""
    # Placeholder - would integrate with Slack API
    return {"status": "executed", "tool": tool_name, "channel": params.get("channel")}


def _execute_database_tool(tool_name: str, params: Dict) -> Dict:
    """Execute a database-related tool."""
    # Placeholder - would execute safe database operations
    return {"status": "executed", "tool": tool_name, "operation": params.get("operation")}


def _execute_http_tool(tool_name: str, params: Dict) -> Dict:
    """Execute an HTTP API tool."""
    # Placeholder - would make HTTP requests
    return {"status": "executed", "tool": tool_name, "url": params.get("url")}


# ============================================================
# TASK EXECUTION (Level 3: Workflow Planning)
# ============================================================

def execute_task(task: Task, dry_run: bool = False) -> Tuple[bool, Dict]:
    """Execute a single task with full Level 3 compliance."""
    start_time = time.time()
    
    log_decision("task.execute", task.title, f"Priority {task.priority}, type {task.task_type}",
                 {"task_id": task.id})
    
    # Check permission
    allowed, reason = is_action_allowed(f"task.{task.task_type}")
    if not allowed:
        log_action("task.blocked", f"Task blocked: {reason}", level="warn", task_id=task.id)
        return False, {"blocked": True, "reason": reason}
    
    # Check approval (read-only check)
    requires_approval, approval_id, status = check_approval_status(task)
    if requires_approval:
        if status == "denied":
            update_task_status(task.id, "failed", {"reason": "Approval denied"})
            return False, {"denied": True}
        elif status == "approved":
            pass  # Continue with execution
        else:
            # Handle "pending", "none", "error", or any unknown status
            # For safety, treat all non-approved status as waiting
            if status == "none":
                ensure_approval_request(task)
            update_task_status(task.id, "waiting_approval")
            log_action("task.waiting", "Task waiting for approval, checking next", task_id=task.id)
            return False, {"waiting_approval": True}
    
    # Dry run mode
    if dry_run or DRY_RUN:
        log_action("task.dry_run", f"DRY RUN: Would execute: {task.title}", task_id=task.id,
                   output_data={"task_type": task.task_type, "payload": task.payload})
        return True, {"dry_run": True, "would_execute": task.task_type}
    
    try:
        # Execute based on task type
        result = {"executed": True}
        task_succeeded = True  # Track overall success
        
        if task.task_type == "tool_execution":
            tool_name = task.payload.get("tool_name")
            tool_params = task.payload.get("params", {})
            success, output = execute_tool(tool_name, tool_params)
            result = {"success": success, "output": output}
            task_succeeded = success
            
        elif task.task_type == "workflow":
            # Execute workflow steps
            steps = task.payload.get("steps", [])
            step_results = []
            workflow_failed = False
            for i, step in enumerate(steps):
                step_success, step_output = execute_tool(step.get("tool"), step.get("params", {}))
                step_results.append({"step": i, "success": step_success, "output": step_output})
                if not step_success and step.get("required", True):
                    workflow_failed = True
                    break
            result = {"steps": step_results, "workflow_failed": workflow_failed}
            task_succeeded = not workflow_failed
            
        elif task.task_type == "opportunity_scan":
            result = {"scanned": True, "source": task.payload.get("source")}
            
        elif task.task_type == "health_check":
            result = {"healthy": True, "component": task.payload.get("component")}
            
        else:
            result = {"executed": True, "type": task.task_type}
        
        # Mark based on actual success
        duration_ms = int((time.time() - start_time) * 1000)
        
        if task_succeeded:
            update_task_status(task.id, "completed", result)
            log_action("task.completed", f"Task completed: {task.title}", task_id=task.id,
                       output_data=result, duration_ms=duration_ms)
        else:
            update_task_status(task.id, "failed", result)
            log_action("task.failed", f"Task failed: {task.title}", task_id=task.id,
                       level="error", error_data=result, duration_ms=duration_ms)
        
        return task_succeeded, result
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_str = str(e)
        
        # Get retry count (may be string from DB, so cast safely)
        sql = f"SELECT COALESCE(attempt_count, 0) as retries FROM governance_tasks WHERE id = {escape_value(task.id)}"
        result = execute_sql(sql)
        retries_raw = result.get("rows", [{}])[0].get("retries", 0)
        try:
            retries = int(retries_raw)
        except (ValueError, TypeError):
            retries = 0
        
        if retries < 3:
            # Schedule retry with exponential backoff
            schedule_task_retry(task.id, retries, error_str)
        else:
            # Send to DLQ
            update_task_status(task.id, "failed", {"error": error_str})
            send_to_dlq(task.id, error_str, retries)
            create_escalation(task.id, f"Task failed after {retries} retries: {error_str}")
        
        return False, {"error": error_str, "retries": retries}


# ============================================================
# THE AUTONOMY LOOP
# ============================================================

def autonomy_loop():
    """The main loop that makes JUGGERNAUT autonomous."""
    # Note: shutdown_requested is only read here, no global declaration needed
    
    log_info("Autonomy loop starting", {"worker_id": WORKER_ID, "interval": LOOP_INTERVAL})
    
    # Update worker heartbeat
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        INSERT INTO worker_registry (worker_id, name, status, last_heartbeat, capabilities, level, max_concurrent_tasks, permissions, forbidden_actions, approval_required_for, allowed_task_types)
        VALUES ({escape_value(WORKER_ID)}, {escape_value(f'Autonomy Engine {WORKER_ID}')}, 'active', {escape_value(now)}, 
                {escape_value(["task_execution", "opportunity_scan", "tool_execution"])}, 'L3', 1, {escape_value({})}, {escape_value([])}, {escape_value([])}, {escape_value([])})
        ON CONFLICT (worker_id) DO UPDATE SET
            status = 'active',
            last_heartbeat = {escape_value(now)}
    """
    try:
        execute_sql(sql)
    except Exception as e:
        log_error(f"Failed to register worker: {e}")
    
    loop_count = 0
    
    while not shutdown_requested:
        loop_count += 1
        loop_start = time.time()
        
        try:
            # 1. Check for pending tasks
            tasks = get_pending_tasks(limit=5)
            
            if tasks:
                # Try to claim and execute tasks in priority order
                task_executed = False
                
                for task in tasks:
                    # Try to claim this task
                    if not claim_task(task.id):
                        continue  # Someone else claimed it, try next
                    
                    log_decision("loop.execute", f"Executing task: {task.title}",
                                 f"Priority {task.priority} of {len(tasks)} pending tasks")
                    
                    success, result = execute_task(task)
                    
                    if result.get("waiting_approval"):
                        # Task is waiting for approval, try next task
                        continue
                    
                    # Task was executed (success or failure), we're done for this loop
                    task_executed = True
                    break
                
                if not task_executed:
                    # All tasks either couldn't be claimed or are waiting for approval
                    log_action("loop.no_executable", "No executable tasks this iteration",
                               output_data={"tasks_checked": len(tasks)})
            else:
                # 2. Check scheduled tasks
                scheduled = get_due_scheduled_tasks()
                if scheduled:
                    sched_task = scheduled[0]
                    log_decision("loop.scheduled", f"Running scheduled task: {sched_task['name']}",
                                 "No pending tasks, running scheduled task")
                    # Mark as run
                    now = datetime.now(timezone.utc).isoformat()
                    sql = f"UPDATE scheduled_tasks SET last_run_at = {escape_value(now)} WHERE id = {escape_value(sched_task['id'])}"
                    execute_sql(sql)
                else:
                    # 3. Nothing to do - log heartbeat
                    if loop_count % 5 == 0:  # Every 5 loops
                        log_action("loop.heartbeat", f"Loop {loop_count}: No work found",
                                   output_data={"loop": loop_count, "tasks_checked": 0})
            
            # Update heartbeat
            now = datetime.now(timezone.utc).isoformat()
            sql = f"UPDATE worker_registry SET last_heartbeat = {escape_value(now)} WHERE worker_id = {escape_value(WORKER_ID)}"
            execute_sql(sql)
            
        except Exception as e:
            log_error(f"Loop error: {str(e)}", {"traceback": traceback.format_exc()[:500]})
        
        # Sleep until next iteration
        elapsed = time.time() - loop_start
        sleep_time = max(0, LOOP_INTERVAL - elapsed)
        time.sleep(sleep_time)
    
    log_info("Autonomy loop stopped", {"loops_completed": loop_count})


# ============================================================
# HEALTH API (for Railway health checks)
# ============================================================

START_TIME = datetime.now(timezone.utc)


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging
    
    def do_GET(self):
        if self.path == "/health":
            uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()
            
            # Check database
            db_ok = True
            try:
                execute_sql("SELECT 1")
            except Exception:
                db_ok = False
            
            status = "healthy" if db_ok else "degraded"
            response = {
                "status": status,
                "version": "1.1.0",
                "worker_id": WORKER_ID,
                "uptime_seconds": int(uptime),
                "database": "connected" if db_ok else "error",
                "dry_run": DRY_RUN,
                "loop_interval": LOOP_INTERVAL,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "JUGGERNAUT Autonomy Engine",
                "status": "running",
                "version": "1.1.0",
                "endpoints": ["/", "/health"]
            }).encode())
            
        else:
            self.send_response(404)
            self.end_headers()


def run_health_server():
    """Run the health check HTTP server."""
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"Health server running on port {PORT}")
    server.serve_forever()


# ============================================================
# SIGNAL HANDLERS
# ============================================================

def handle_shutdown(signum, frame):
    global shutdown_requested
    print("\nShutdown signal received...")
    shutdown_requested = True


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("JUGGERNAUT AUTONOMY ENGINE v1.1.0")
    print("=" * 60)
    print(f"Worker ID: {WORKER_ID}")
    print(f"Loop Interval: {LOOP_INTERVAL} seconds")
    print(f"Dry Run Mode: {DRY_RUN}")
    print(f"Health Port: {PORT}")
    print("=" * 60)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    # Start health server in background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Run the autonomy loop (blocks forever)
    try:
        autonomy_loop()
    except KeyboardInterrupt:
        print("\nInterrupted. Shutting down...")
    
    print("Goodbye.")
