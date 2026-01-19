"""
JUGGERNAUT Database Operations
Neon PostgreSQL via SQL over HTTP
"""

import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

import logging

# Configure module logger
logger = logging.getLogger(__name__)

# Database configuration
NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
NEON_CONNECTION_STRING = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
)


class Database:
    """Neon PostgreSQL client using SQL over HTTP."""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or NEON_CONNECTION_STRING
        self.endpoint = NEON_ENDPOINT
    
    def query(self, sql: str) -> Dict[str, Any]:
        """Execute a SQL query and return results."""
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": self.connection_string
        }
        
        data = json.dumps({"query": sql}).encode('utf-8')
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                if "message" in result and "error" in str(result.get("severity", "")).lower():
                    raise Exception(f"Database error: {result['message']}")
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
    
    def insert(self, table: str, data: Dict[str, Any]) -> Optional[str]:
        """Insert a row and return the ID."""
        columns = ", ".join(data.keys())
        values = ", ".join([self._format_value(v) for v in data.values()])
        
        sql = f"INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING id"
        result = self.query(sql)
        
        if result.get("rows"):
            return result["rows"][0].get("id")
        return None
    
    def _format_value(self, v: Any) -> str:
        """Format a value for SQL insertion."""
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


# Singleton instance
_db = Database()


def escape_sql_value(v: Any) -> str:
    """
    Escape a value for safe SQL interpolation.
    
    Use this function for all user-provided values in WHERE clauses
    and other SQL statements to prevent SQL injection.
    
    Args:
        v: Value to escape (string, int, float, bool, dict, list, or None)
    
    Returns:
        SQL-safe string representation of the value
    """
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



def query_db(sql: str, params: Optional[List] = None) -> Dict[str, Any]:
    """
    Execute SQL query with optional parameterized values.
    
    Args:
        sql: SQL query with optional $1, $2, etc. placeholders
        params: List of parameter values to substitute
        
    Returns:
        Query result dict with 'rows', 'rowCount', etc.
    """
    if params:
        # Substitute $1, $2, etc. with formatted values
        formatted_sql = sql
        for i, param in enumerate(params, 1):
            placeholder = f"${i}"
            formatted_value = _db._format_value(param)
            formatted_sql = formatted_sql.replace(placeholder, formatted_value, 1)
        return _db.query(formatted_sql)
    return _db.query(sql)


# ============================================================
# LOGGING FUNCTIONS
# ============================================================

def log_execution(
    worker_id: str,
    action: str,
    message: str,
    level: str = "info",
    goal_id: str = None,
    task_id: str = None,
    input_data: Dict = None,
    output_data: Dict = None,
    error_data: Dict = None,
    duration_ms: int = None,
    tokens_used: int = None,
    cost_cents: int = None,
    source: str = "system"
) -> Optional[str]:
    """
    Log an execution event.
    
    Args:
        worker_id: Which worker performed the action (e.g., 'ORCHESTRATOR', 'SARAH')
        action: Action type (e.g., 'opportunity.create', 'experiment.start')
        message: Human-readable description
        level: Log level (debug, info, warn, error, critical)
        goal_id: Associated goal UUID
        task_id: Associated task UUID
        input_data: JSON input to the action
        output_data: JSON output from the action
        error_data: JSON error details if failed
        duration_ms: How long the action took
        tokens_used: AI tokens consumed
        cost_cents: Cost in cents
        source: Source identifier (e.g., 'claude_main', 'api')
    
    Returns:
        Log entry UUID or None on failure
    """
    data = {
        "worker_id": worker_id,
        "action": action,
        "message": message,
        "level": level,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if goal_id:
        data["goal_id"] = goal_id
    if task_id:
        data["task_id"] = task_id
    if input_data:
        data["input_data"] = input_data
    if output_data:
        data["output_data"] = output_data
    if error_data:
        data["error_data"] = error_data
    if duration_ms is not None:
        data["duration_ms"] = duration_ms
    if tokens_used is not None:
        data["tokens_used"] = tokens_used
    if cost_cents is not None:
        data["cost_cents"] = cost_cents
    
    try:
        return _db.insert("execution_logs", data)
    except Exception as e:
        logger.error("Failed to log execution: %s", e)
        return None


def get_logs(
    worker_id: str = None,
    action: str = None,
    level: str = None,
    limit: int = 100
) -> List[Dict]:
    """
    Get execution logs, optionally filtered.
    
    Args:
        worker_id: Filter by worker
        action: Filter by action prefix
        level: Filter by log level
        limit: Max rows to return
    
    Returns:
        List of log entries
    """
    conditions = []
    if worker_id:
        conditions.append(f"worker_id = {escape_sql_value(worker_id)}")
    if action:
        conditions.append(f"action LIKE {escape_sql_value(action + '%')}")
    if level:
        conditions.append(f"level = {escape_sql_value(level)}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM execution_logs {where} ORDER BY created_at DESC LIMIT {limit}"
    result = _db.query(sql)
    return result.get("rows", [])


def cleanup_old_logs(days_to_keep: int = 30) -> int:
    """
    Delete logs older than specified days.
    
    Args:
        days_to_keep: Number of days of logs to retain (default: 30)
    
    Returns:
        Number of logs deleted
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
    sql = f"DELETE FROM execution_logs WHERE created_at < {escape_sql_value(cutoff)} AND level NOT IN ('error', 'critical')"
    
    try:
        result = _db.query(sql)
        deleted = result.get("rowCount", 0) or 0
        log_execution(
            worker_id="SYSTEM",
            action="logs.cleanup",
            message=f"Deleted {deleted} logs older than {days_to_keep} days",
            output_data={"deleted_count": deleted, "cutoff_date": cutoff}
        )
        return deleted
    except Exception as e:
        logger.error("Failed to cleanup logs: %s", e)
        return 0


def get_log_summary(days: int = 7) -> Dict[str, Any]:
    """
    Get summary statistics for logs.
    
    Args:
        days: Number of days to analyze
    
    Returns:
        Summary dict with counts by level, worker, action
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Count by level
    level_sql = f"""
        SELECT level, COUNT(*) as count 
        FROM execution_logs 
        WHERE created_at >= {escape_sql_value(cutoff)} 
        GROUP BY level
    """
    
    # Count by worker
    worker_sql = f"""
        SELECT worker_id, COUNT(*) as count 
        FROM execution_logs 
        WHERE created_at >= {escape_sql_value(cutoff)} 
        GROUP BY worker_id
        ORDER BY count DESC
        LIMIT 10
    """
    
    # Count by action
    action_sql = f"""
        SELECT action, COUNT(*) as count 
        FROM execution_logs 
        WHERE created_at >= {escape_sql_value(cutoff)} 
        GROUP BY action
        ORDER BY count DESC
        LIMIT 10
    """
    
    try:
        levels = _db.query(level_sql).get("rows", [])
        workers = _db.query(worker_sql).get("rows", [])
        actions = _db.query(action_sql).get("rows", [])
        
        return {
            "period_days": days,
            "by_level": {r["level"]: int(r["count"]) for r in levels},
            "by_worker": {r["worker_id"]: int(r["count"]) for r in workers},
            "by_action": {r["action"]: int(r["count"]) for r in actions}
        }
    except Exception as e:
        logger.error("Failed to get log summary: %s", e)
        return {}


# ============================================================
# OPPORTUNITY FUNCTIONS
# ============================================================

def create_opportunity(
    opportunity_type: str,
    category: str,
    description: str,
    estimated_value: float = 0,
    confidence_score: float = 0.5,
    source_id: str = None,
    external_id: str = None,
    customer_name: str = None,
    customer_contact: Dict = None,
    metadata: Dict = None,
    assigned_to: str = None,
    created_by: str = "ORCHESTRATOR",
    expires_at: str = None
) -> Optional[str]:
    """
    Create a new opportunity in the pipeline.
    
    Args:
        opportunity_type: Type (e.g., 'domain', 'saas', 'digital_product', 'api_service')
        category: Category within type (e.g., 'ai_tools', 'automation', 'templates')
        description: What this opportunity is
        estimated_value: Expected revenue in dollars
        confidence_score: 0.0-1.0 confidence in success
        source_id: UUID of the source that generated this
        external_id: ID in external system
        customer_name: Customer/lead name if applicable
        customer_contact: Contact info dict
        metadata: Additional JSON data
        assigned_to: Worker assigned to pursue this
        created_by: Who created this opportunity
        expires_at: When this opportunity expires (ISO timestamp)
    
    Returns:
        Opportunity UUID or None on failure
    """
    data = {
        "opportunity_type": opportunity_type,
        "category": category,
        "description": description,
        "estimated_value": estimated_value,
        "confidence_score": confidence_score,
        "status": "new",
        "stage": "identified",
        "created_by": created_by,
        "identified_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if source_id:
        data["source_id"] = source_id
    if external_id:
        data["external_id"] = external_id
    if customer_name:
        data["customer_name"] = customer_name
    if customer_contact:
        data["customer_contact"] = customer_contact
    if metadata:
        data["metadata"] = metadata
    if assigned_to:
        data["assigned_to"] = assigned_to
    if expires_at:
        data["expires_at"] = expires_at
    
    try:
        opp_id = _db.insert("opportunities", data)
        
        log_execution(
            worker_id=created_by,
            action="opportunity.create",
            message=f"Created opportunity: {description[:100]}",
            output_data={"opportunity_id": opp_id, "type": opportunity_type, "value": estimated_value}
        )
        
        return opp_id
    except Exception as e:
        logger.error("Failed to create opportunity: %s", e)
        return None


def update_opportunity(
    opportunity_id: str,
    updates: Dict[str, Any],
    updated_by: str = "ORCHESTRATOR"
) -> bool:
    """Update an existing opportunity."""
    set_clauses = []
    for key, value in updates.items():
        set_clauses.append(f"{key} = {_db._format_value(value)}")
    
    set_clauses.append(f"updated_at = '{datetime.now(timezone.utc).isoformat()}'")
    
    sql = f"UPDATE opportunities SET {', '.join(set_clauses)} WHERE id = {escape_sql_value(opportunity_id)}"
    
    try:
        _db.query(sql)
        log_execution(
            worker_id=updated_by,
            action="opportunity.update",
            message=f"Updated opportunity {opportunity_id}",
            input_data=updates
        )
        return True
    except Exception as e:
        logger.error("Failed to update opportunity: %s", e)
        return False


def get_opportunities(status: str = None, limit: int = 50) -> List[Dict]:
    """Get opportunities, optionally filtered by status."""
    where = f"WHERE status = {escape_sql_value(status)}" if status else ""
    sql = f"SELECT * FROM opportunities {where} ORDER BY created_at DESC LIMIT {limit}"
    result = _db.query(sql)
    return result.get("rows", [])


# ============================================================
# REVENUE TRACKING FUNCTIONS
# ============================================================

def record_revenue(
    event_type: str,
    gross_amount: float,
    source: str,
    description: str,
    net_amount: float = None,
    revenue_type: str = "one_time",
    currency: str = "USD",
    opportunity_id: str = None,
    external_id: str = None,
    attribution: Dict = None,
    metadata: Dict = None,
    occurred_at: str = None,
    recorded_by: str = "ORCHESTRATOR"
) -> Optional[str]:
    """
    Record a revenue event.
    
    Args:
        event_type: Type of event (sale, refund, subscription, commission, etc.)
        gross_amount: Total amount before fees/costs
        source: Where the revenue came from (e.g., 'gumroad', 'stripe', 'servicetitan')
        description: Human-readable description
        net_amount: Amount after fees (defaults to gross if not specified)
        revenue_type: one_time, recurring, commission
        currency: Currency code (default: USD)
        opportunity_id: Associated opportunity UUID
        external_id: ID in external system (e.g., Stripe payment ID)
        attribution: JSON with attribution data (worker, experiment, campaign)
        metadata: Additional JSON data
        occurred_at: When the revenue occurred (default: now)
        recorded_by: Who recorded this
    
    Returns:
        Revenue event UUID or None on failure
    """
    if net_amount is None:
        net_amount = gross_amount
    
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc).isoformat()
    
    data = {
        "event_type": event_type,
        "gross_amount": gross_amount,
        "net_amount": net_amount,
        "source": source,
        "description": description,
        "revenue_type": revenue_type,
        "currency": currency,
        "occurred_at": occurred_at,
        "recorded_by": recorded_by,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if opportunity_id:
        data["opportunity_id"] = opportunity_id
    if external_id:
        data["external_id"] = external_id
    if attribution:
        data["attribution"] = attribution
    if metadata:
        data["metadata"] = metadata
    
    try:
        rev_id = _db.insert("revenue_events", data)
        
        log_execution(
            worker_id=recorded_by,
            action="revenue.record",
            message=f"Recorded ${gross_amount} {event_type} from {source}",
            output_data={"revenue_id": rev_id, "amount": gross_amount, "source": source}
        )
        
        return rev_id
    except Exception as e:
        logger.error("Failed to record revenue: %s", e)
        return None


def get_revenue_summary(days: int = 30) -> Dict[str, Any]:
    """
    Get revenue summary for a period.
    
    Args:
        days: Number of days to summarize
    
    Returns:
        Summary dict with totals by source, type, and period
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Total revenue
    total_sql = f"""
        SELECT 
            COALESCE(SUM(gross_amount), 0) as gross_total,
            COALESCE(SUM(net_amount), 0) as net_total,
            COUNT(*) as event_count
        FROM revenue_events 
        WHERE occurred_at >= {escape_sql_value(cutoff)}
        AND event_type != 'refund'
    """
    
    # By source
    source_sql = f"""
        SELECT source, SUM(gross_amount) as total 
        FROM revenue_events 
        WHERE occurred_at >= {escape_sql_value(cutoff)}
        AND event_type != 'refund'
        GROUP BY source
        ORDER BY total DESC
    """
    
    # By type
    type_sql = f"""
        SELECT revenue_type, SUM(gross_amount) as total 
        FROM revenue_events 
        WHERE occurred_at >= {escape_sql_value(cutoff)}
        AND event_type != 'refund'
        GROUP BY revenue_type
    """
    
    try:
        totals = _db.query(total_sql).get("rows", [{}])[0]
        by_source = _db.query(source_sql).get("rows", [])
        by_type = _db.query(type_sql).get("rows", [])
        
        return {
            "period_days": days,
            "gross_total": float(totals.get("gross_total", 0)),
            "net_total": float(totals.get("net_total", 0)),
            "event_count": int(totals.get("event_count", 0)),
            "by_source": {r["source"]: float(r["total"]) for r in by_source},
            "by_type": {r["revenue_type"]: float(r["total"]) for r in by_type}
        }
    except Exception as e:
        logger.error("Failed to get revenue summary: %s", e)
        return {}


def get_revenue_events(
    source: str = None,
    event_type: str = None,
    days: int = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Get revenue events with optional filters.
    
    Args:
        source: Filter by source
        event_type: Filter by event type
        days: Only events from last N days
        limit: Max rows to return
    
    Returns:
        List of revenue events
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conditions = [f"occurred_at >= {escape_sql_value(cutoff)}"]
    
    if source:
        conditions.append(f"source = {escape_sql_value(source)}")
    if event_type:
        conditions.append(f"event_type = {escape_sql_value(event_type)}")
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM revenue_events {where} ORDER BY occurred_at DESC LIMIT {limit}"
    result = _db.query(sql)
    return result.get("rows", [])


# ============================================================
# MEMORY FUNCTIONS (Phase 1.2)
# ============================================================

def write_memory(
    category: str,
    content: str,
    importance: float = 0.5,
    worker_id: str = "SYSTEM",
    related_to: str = None,
    metadata: Dict = None,
    expires_at: str = None
) -> Optional[str]:
    """
    Store a memory in the database.
    
    Args:
        category: Memory type (fact, preference, learning, context)
        content: The memory content
        importance: 0.0-1.0 importance score
        worker_id: Who created this memory
        related_to: UUID of related memory
        metadata: Additional JSON data
        expires_at: When this memory expires
    
    Returns:
        Memory UUID or None on failure
    """
    data = {
        "category": category,
        "content": content,
        "importance": importance,
        "worker_id": worker_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if related_to:
        data["related_to"] = related_to
    if metadata:
        data["metadata"] = metadata
    if expires_at:
        data["expires_at"] = expires_at
    
    try:
        return _db.insert("memories", data)
    except Exception as e:
        logger.error("Failed to write memory: %s", e)
        return None


def read_memories(
    category: str = None,
    worker_id: str = None,
    min_importance: float = None,
    search_text: str = None,
    limit: int = 50
) -> List[Dict]:
    """
    Read memories with optional filters.
    
    Args:
        category: Filter by category
        worker_id: Filter by worker
        min_importance: Minimum importance score
        search_text: Text to search in content
        limit: Max memories to return
    
    Returns:
        List of memory records
    """
    conditions = ["(expires_at IS NULL OR expires_at > NOW())"]
    
    if category:
        conditions.append(f"category = {escape_sql_value(category)}")
    if worker_id:
        conditions.append(f"worker_id = {escape_sql_value(worker_id)}")
    if min_importance is not None:
        conditions.append(f"importance >= {min_importance}")
    if search_text:
        escaped = search_text.replace("'", "''")
        conditions.append(f"content ILIKE '%{escaped}%'")
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM memories {where} ORDER BY importance DESC, created_at DESC LIMIT {limit}"
    result = _db.query(sql)
    return result.get("rows", [])


def update_memory_importance(memory_id: str, new_importance: float) -> bool:
    """Update a memory's importance score."""
    sql = f"UPDATE memories SET importance = {new_importance}, updated_at = '{datetime.now(timezone.utc).isoformat()}' WHERE id = {escape_sql_value(memory_id)}"
    try:
        _db.query(sql)
        return True
    except Exception as e:
        logger.error("Failed to update memory: %s", e)
        return False


# ============================================================
# COMMUNICATION FUNCTIONS (Phase 1.3)
# ============================================================

def send_message(
    from_worker: str,
    to_worker: str,
    message_type: str,
    content: str,
    priority: str = "normal",
    payload: Dict = None,
    requires_ack: bool = False
) -> Optional[str]:
    """
    Send a message between workers.
    
    Args:
        from_worker: Sender worker ID
        to_worker: Recipient worker ID (or 'ALL' for broadcast)
        message_type: Type of message (task, query, response, alert)
        content: Message content
        priority: low, normal, high, urgent
        payload: Additional JSON data
        requires_ack: Whether acknowledgment is required
    
    Returns:
        Message UUID or None on failure
    """
    data = {
        "from_worker": from_worker,
        "to_worker": to_worker,
        "message_type": message_type,
        "content": content,
        "priority": priority,
        "requires_ack": requires_ack,
        "status": "sent",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if payload:
        data["payload"] = payload
    
    try:
        return _db.insert("communications", data)
    except Exception as e:
        logger.error("Failed to send message: %s", e)
        return None


def get_messages(
    to_worker: str,
    status: str = "sent",
    limit: int = 50
) -> List[Dict]:
    """
    Get messages for a worker.
    
    Args:
        to_worker: Worker to get messages for
        status: Filter by status (sent, read, acknowledged)
        limit: Max messages to return
    
    Returns:
        List of messages
    """
    sql = f"""
        SELECT * FROM communications 
        WHERE (to_worker = {escape_sql_value(to_worker)} OR to_worker = 'ALL')
        AND status = '{status}'
        ORDER BY 
            CASE priority 
                WHEN 'urgent' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'normal' THEN 3 
                ELSE 4 
            END,
            created_at DESC
        LIMIT {limit}
    """
    result = _db.query(sql)
    return result.get("rows", [])


def acknowledge_message(message_id: str, worker_id: str) -> bool:
    """Mark a message as acknowledged."""
    sql = f"""
        UPDATE communications 
        SET status = 'acknowledged', 
            acknowledged_at = '{datetime.now(timezone.utc).isoformat()}',
            acknowledged_by = '{worker_id}'
        WHERE id = {escape_sql_value(message_id)}
    """
    try:
        _db.query(sql)
        return True
    except Exception as e:
        logger.error("Failed to acknowledge message: %s", e)
        return False


def mark_message_read(message_id: str) -> bool:
    """Mark a message as read."""
    sql = f"UPDATE communications SET status = 'read', read_at = '{datetime.now(timezone.utc).isoformat()}' WHERE id = {escape_sql_value(message_id)}"
    try:
        _db.query(sql)
        return True
    except Exception as e:
        logger.error("Failed to mark message read: %s", e)
        return False


# ============================================================
# COST TRACKING FUNCTIONS (Phase 3.3)
# ============================================================

def record_cost(
    cost_type: str,
    category: str,
    amount_cents: int,
    description: str = None,
    source: str = None,
    attribution: Dict = None,
    experiment_id: str = None,
    goal_id: str = None,
    external_id: str = None,
    metadata: Dict = None,
    occurred_at: str = None,
    recorded_by: str = "SYSTEM"
) -> Optional[str]:
    """
    Record a cost event.
    
    Args:
        cost_type: Type of cost - 'api', 'infrastructure', 'service', 'labor', 'other'
        category: Specific category within type:
            - api: 'openai', 'anthropic', 'retell', 'deepgram', 'elevenlabs'
            - infrastructure: 'railway', 'vercel', 'neon', 'cloudflare'
            - service: 'github', 'stripe', 'twilio'
            - other: 'domain', 'tool', 'subscription'
        amount_cents: Cost in cents (e.g., $1.50 = 150)
        description: What the cost was for
        source: What triggered this cost (e.g., 'sarah_call', 'api_request')
        attribution: JSON dict for attribution tracking
            e.g., {"worker": "SARAH", "experiment": "digital_products_v1"}
        experiment_id: UUID of associated experiment
        goal_id: UUID of associated goal
        external_id: ID in external system (e.g., Stripe charge ID)
        metadata: Additional JSON data
        occurred_at: When the cost occurred (ISO timestamp, defaults to now)
        recorded_by: Who recorded this cost
    
    Returns:
        Cost event UUID
    """
    data = {
        "cost_type": cost_type,
        "category": category,
        "amount_cents": amount_cents,
        "occurred_at": occurred_at or datetime.now(timezone.utc).isoformat(),
        "recorded_by": recorded_by
    }
    
    if description:
        data["description"] = description
    if source:
        data["source"] = source
    if attribution:
        data["attribution"] = attribution
    if experiment_id:
        data["experiment_id"] = experiment_id
    if goal_id:
        data["goal_id"] = goal_id
    if external_id:
        data["external_id"] = external_id
    if metadata:
        data["metadata"] = metadata
    
    try:
        return _db.insert("cost_events", data)
    except Exception as e:
        logger.error("Failed to record cost: %s", e)
        return None


def record_api_cost(
    provider: str,
    tokens_used: int = None,
    amount_cents: int = None,
    model: str = None,
    worker_id: str = None,
    action: str = None
) -> Optional[str]:
    """
    Convenience function to record API costs with auto-pricing.
    
    Args:
        provider: API provider (openai, anthropic, retell, deepgram, elevenlabs, cartesia)
        tokens_used: Number of tokens consumed
        amount_cents: Cost in cents (auto-calculated if not provided)
        model: Model used (e.g., 'gpt-4', 'claude-3.5-sonnet')
        worker_id: Which worker made the call
        action: What action triggered this
    
    Returns:
        Cost event UUID
    """
    # Token pricing per 1M tokens (in cents) - rough estimates
    PRICING = {
        "openai": {"gpt-4": 3000, "gpt-4-turbo": 1000, "gpt-3.5-turbo": 50, "default": 1000},
        "anthropic": {"claude-3.5-sonnet": 300, "claude-3-haiku": 25, "default": 300},
        "retell": {"per_minute": 10},
        "deepgram": {"per_minute": 3},
        "elevenlabs": {"per_char": 3},
        "cartesia": {"per_char": 2},
    }
    
    # Auto-calculate cost if not provided
    if amount_cents is None and tokens_used:
        provider_pricing = PRICING.get(provider, {})
        rate = provider_pricing.get(model, provider_pricing.get("default", 100))
        amount_cents = int((tokens_used / 1_000_000) * rate)
        amount_cents = max(1, amount_cents)  # Minimum 1 cent
    
    attribution = {}
    if worker_id:
        attribution["worker"] = worker_id
    if action:
        attribution["action"] = action
    
    return record_cost(
        cost_type="api",
        category=provider,
        amount_cents=amount_cents or 0,
        description=f"{provider} API: {tokens_used} tokens" if tokens_used else f"{provider} API call",
        source=action or worker_id,
        attribution=attribution if attribution else None,
        metadata={"model": model, "tokens": tokens_used} if model or tokens_used else None
    )


def record_infrastructure_cost(
    provider: str,
    amount_cents: int,
    period: str = "monthly",
    service_name: str = None,
    description: str = None
) -> Optional[str]:
    """
    Record infrastructure costs (Railway, Vercel, Neon, etc.)
    
    Args:
        provider: Infrastructure provider
        amount_cents: Cost in cents
        period: 'monthly', 'daily', 'hourly'
        service_name: Specific service within provider
        description: Additional details
    """
    return record_cost(
        cost_type="infrastructure",
        category=provider,
        amount_cents=amount_cents,
        description=description or f"{provider} {period} cost",
        source=service_name,
        metadata={"period": period, "service": service_name}
    )


def get_cost_summary(
    days: int = 30,
    cost_type: str = None,
    category: str = None
) -> Dict[str, Any]:
    """
    Get cost summary for a time period.
    
    Args:
        days: Number of days to analyze
        cost_type: Filter by cost type
        category: Filter by category
    
    Returns:
        Summary dict with totals, breakdown by type and category
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    conditions = [f"occurred_at >= {escape_sql_value(cutoff)}"]
    if cost_type:
        conditions.append(f"cost_type = {escape_sql_value(cost_type)}")
    if category:
        conditions.append(f"category = {escape_sql_value(category)}")
    
    where = f"WHERE {' AND '.join(conditions)}"
    
    # Total costs
    total_sql = f"SELECT COUNT(*) as count, SUM(amount_cents) as total FROM cost_events {where}"
    
    # By type
    type_sql = f"""
        SELECT cost_type, SUM(amount_cents) as total
        FROM cost_events {where}
        GROUP BY cost_type ORDER BY total DESC
    """
    
    # By category
    cat_sql = f"""
        SELECT category, SUM(amount_cents) as total
        FROM cost_events {where}
        GROUP BY category ORDER BY total DESC
    """
    
    try:
        total = _db.query(total_sql).get("rows", [{}])[0]
        by_type = _db.query(type_sql).get("rows", [])
        by_cat = _db.query(cat_sql).get("rows", [])
        
        return {
            "period_days": days,
            "total_cents": int(total.get("total") or 0),
            "total_dollars": round(int(total.get("total") or 0) / 100, 2),
            "event_count": int(total.get("count") or 0),
            "by_type": {r["cost_type"]: int(r["total"]) for r in by_type},
            "by_category": {r["category"]: int(r["total"]) for r in by_cat}
        }
    except Exception as e:
        logger.error("Failed to get cost summary: %s", e)
        return {}


def get_cost_events(
    days: int = 30,
    cost_type: str = None,
    category: str = None,
    limit: int = 100
) -> List[Dict]:
    """Get recent cost events."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    conditions = [f"occurred_at >= {escape_sql_value(cutoff)}"]
    if cost_type:
        conditions.append(f"cost_type = {escape_sql_value(cost_type)}")
    if category:
        conditions.append(f"category = {escape_sql_value(category)}")
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM cost_events {where} ORDER BY occurred_at DESC LIMIT {limit}"
    
    try:
        return _db.query(sql).get("rows", [])
    except Exception as e:
        logger.error("Failed to get cost events: %s", e)
        return []


# ============================================================
# BUDGET MANAGEMENT FUNCTIONS
# ============================================================

def create_budget(
    budget_name: str,
    monthly_limit_cents: int,
    cost_type: str = None,
    category: str = None,
    daily_limit_cents: int = None,
    alert_threshold_percent: int = 80
) -> Optional[str]:
    """
    Create a cost budget for alerting.
    
    Args:
        budget_name: Unique name for budget (e.g., 'openai_api', 'total_infrastructure')
        monthly_limit_cents: Monthly spending limit in cents
        cost_type: Optional filter for specific cost type
        category: Optional filter for specific category
        daily_limit_cents: Optional daily limit
        alert_threshold_percent: Alert when this % of budget is used (default 80)
    
    Returns:
        Budget UUID
    """
    data = {
        "budget_name": budget_name,
        "monthly_limit_cents": monthly_limit_cents,
        "alert_threshold_percent": alert_threshold_percent,
        "is_active": True
    }
    
    if cost_type:
        data["cost_type"] = cost_type
    if category:
        data["category"] = category
    if daily_limit_cents:
        data["daily_limit_cents"] = daily_limit_cents
    
    try:
        return _db.insert("cost_budgets", data)
    except Exception as e:
        logger.error("Failed to create budget: %s", e)
        return None


def check_budget_status() -> List[Dict]:
    """
    Check all active budgets and return status with alerts.
    
    Returns:
        List of budget statuses with usage and alert status
    """
    # Get all active budgets
    budgets_sql = "SELECT * FROM cost_budgets WHERE is_active = TRUE"
    budgets = _db.query(budgets_sql).get("rows", [])
    
    # Get current month's start
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    results = []
    
    for budget in budgets:
        # Build query for this budget's costs
        conditions = [f"occurred_at >= {escape_sql_value(month_start)}"]
        if budget.get("cost_type"):
            conditions.append(f"cost_type = {escape_sql_value(budget['cost_type'])}")
        if budget.get("category"):
            conditions.append(f"category = {escape_sql_value(budget['category'])}")
        
        where = f"WHERE {' AND '.join(conditions)}"
        
        # Get monthly total
        month_sql = f"SELECT COALESCE(SUM(amount_cents), 0) as total FROM cost_events {where}"
        month_total = int(_db.query(month_sql).get("rows", [{}])[0].get("total") or 0)
        
        # Get daily total if daily limit exists
        daily_total = 0
        if budget.get("daily_limit_cents"):
            daily_conditions = conditions.copy()
            daily_conditions[0] = f"occurred_at >= {escape_sql_value(today_start)}"
            daily_where = f"WHERE {' AND '.join(daily_conditions)}"
            daily_sql = f"SELECT COALESCE(SUM(amount_cents), 0) as total FROM cost_events {daily_where}"
            daily_total = int(_db.query(daily_sql).get("rows", [{}])[0].get("total") or 0)
        
        monthly_limit = budget["monthly_limit_cents"]
        usage_percent = round((month_total / monthly_limit) * 100, 1) if monthly_limit > 0 else 0
        
        status = {
            "budget_name": budget["budget_name"],
            "monthly_limit_cents": monthly_limit,
            "monthly_spent_cents": month_total,
            "usage_percent": usage_percent,
            "alert_triggered": usage_percent >= budget["alert_threshold_percent"],
            "over_budget": month_total > monthly_limit
        }
        
        if budget.get("daily_limit_cents"):
            status["daily_limit_cents"] = budget["daily_limit_cents"]
            status["daily_spent_cents"] = daily_total
            status["daily_over"] = daily_total > budget["daily_limit_cents"]
        
        results.append(status)
    
    return results


# ============================================================
# PROFIT/LOSS FUNCTIONS
# ============================================================

def get_profit_loss(days: int = 30) -> Dict[str, Any]:
    """
    Get profit/loss summary.
    
    Args:
        days: Number of days to analyze
    
    Returns:
        Dict with revenue, costs, and profit
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Get revenue
    rev_sql = f"""
        SELECT COALESCE(SUM(gross_amount), 0) as gross, 
               COALESCE(SUM(COALESCE(net_amount, gross_amount)), 0) as net
        FROM revenue_events 
        WHERE occurred_at >= {escape_sql_value(cutoff)}
    """
    
    # Get costs
    cost_sql = f"""
        SELECT COALESCE(SUM(amount_cents), 0) as total
        FROM cost_events 
        WHERE occurred_at >= {escape_sql_value(cutoff)}
    """
    
    try:
        rev = _db.query(rev_sql).get("rows", [{}])[0]
        cost = _db.query(cost_sql).get("rows", [{}])[0]
        
        gross_revenue = float(rev.get("gross") or 0)
        net_revenue = float(rev.get("net") or 0)
        total_cost_cents = int(cost.get("total") or 0)
        total_cost_dollars = total_cost_cents / 100
        
        return {
            "period_days": days,
            "revenue": {
                "gross": round(gross_revenue, 2),
                "net": round(net_revenue, 2)
            },
            "costs": {
                "total_cents": total_cost_cents,
                "total_dollars": round(total_cost_dollars, 2)
            },
            "profit": {
                "gross_profit": round(gross_revenue - total_cost_dollars, 2),
                "net_profit": round(net_revenue - total_cost_dollars, 2)
            },
            "margin_percent": round(((net_revenue - total_cost_dollars) / net_revenue) * 100, 1) if net_revenue > 0 else 0
        }
    except Exception as e:
        logger.error("Failed to get profit/loss: %s", e)
        return {}


def get_experiment_roi(experiment_id: str) -> Dict[str, Any]:
    """
    Get ROI for a specific experiment.
    
    Args:
        experiment_id: UUID of the experiment
    
    Returns:
        Dict with experiment revenue, costs, and ROI
    """
    # Revenue attributed to experiment
    rev_sql = f"""
        SELECT COALESCE(SUM(gross_amount), 0) as gross
        FROM revenue_events 
        WHERE attribution->>'experiment' = {escape_sql_value(experiment_id)}
           OR metadata->>'experiment_id' = '{experiment_id}'
    """
    
    # Costs attributed to experiment  
    cost_sql = f"""
        SELECT COALESCE(SUM(amount_cents), 0) as total
        FROM cost_events 
        WHERE experiment_id = {escape_sql_value(experiment_id)}
           OR attribution->>'experiment' = '{experiment_id}'
    """
    
    try:
        rev = _db.query(rev_sql).get("rows", [{}])[0]
        cost = _db.query(cost_sql).get("rows", [{}])[0]
        
        revenue = float(rev.get("gross") or 0)
        cost_cents = int(cost.get("total") or 0)
        cost_dollars = cost_cents / 100
        
        roi = ((revenue - cost_dollars) / cost_dollars * 100) if cost_dollars > 0 else 0
        
        return {
            "experiment_id": experiment_id,
            "revenue": round(revenue, 2),
            "cost_cents": cost_cents,
            "cost_dollars": round(cost_dollars, 2),
            "profit": round(revenue - cost_dollars, 2),
            "roi_percent": round(roi, 1)
        }
    except Exception as e:
        logger.error("Failed to get experiment ROI: %s", e)
        return {}


# ============================================================
# SCORING MODELS FUNCTIONS (Phase 3.4)
# ============================================================

def create_model(
    name: str,
    model_type: str,
    config: Dict,
    created_by: str = "SYSTEM"
) -> Optional[str]:
    """
    Create a new scoring model.
    
    Args:
        name: Unique model name (e.g., 'opportunity_scorer', 'lead_qualifier')
        model_type: Type of model ('classifier', 'regressor', 'ranker', 'rule_based')
        config: Model configuration JSON containing:
            - features: list of feature names
            - weights: dict of feature weights (for rule-based)
            - thresholds: classification thresholds
            - algorithm: algorithm name (for ML models)
            - hyperparameters: model hyperparameters
        created_by: Who created the model
    
    Returns:
        Model UUID
    """
    data = {
        "name": name,
        "model_type": model_type,
        "config": config,
        "version": 1,
        "active": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        return _db.insert("scoring_models", data)
    except Exception as e:
        logger.error("Failed to create model: %s", e)
        return None


def get_model(model_id: str = None, name: str = None, active_only: bool = False) -> Optional[Dict]:
    """
    Get a model by ID or name.
    
    Args:
        model_id: Model UUID
        name: Model name
        active_only: If True, only return if model is active
    
    Returns:
        Model dict or None
    """
    conditions = []
    if model_id:
        conditions.append(f"id = {escape_sql_value(model_id)}")
    if name:
        conditions.append(f"name = {escape_sql_value(name)}")
    if active_only:
        conditions.append("active = TRUE")
    
    if not conditions:
        return None
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM scoring_models {where} ORDER BY version DESC LIMIT 1"
    
    try:
        result = _db.query(sql)
        rows = result.get("rows", [])
        return rows[0] if rows else None
    except Exception as e:
        logger.error("Failed to get model: %s", e)
        return None


def list_models(model_type: str = None, active_only: bool = False) -> List[Dict]:
    """List all models, optionally filtered."""
    conditions = []
    if model_type:
        conditions.append(f"model_type = {escape_sql_value(model_type)}")
    if active_only:
        conditions.append("active = TRUE")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM scoring_models {where} ORDER BY name, version DESC"
    
    try:
        return _db.query(sql).get("rows", [])
    except Exception as e:
        logger.error("Failed to list models: %s", e)
        return []


def create_model_version(
    model_id: str,
    config: Dict,
    created_by: str = "SYSTEM"
) -> Optional[str]:
    """
    Create a new version of an existing model.
    
    Args:
        model_id: ID of the model to version
        config: New configuration
        created_by: Who created this version
    
    Returns:
        New model version UUID
    """
    # Get current model
    current = get_model(model_id=model_id)
    if not current:
        logger.warning("Model %s not found", model_id)
        return None
    
    # Create new version
    data = {
        "name": current["name"],
        "model_type": current["model_type"],
        "config": config,
        "version": current["version"] + 1,
        "active": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        new_id = _db.insert("scoring_models", data)
        log_execution(
            worker_id="SYSTEM",
            action="model.version_created",
            message=f"Created version {data['version']} of model {current['name']}",
            output_data={"model_id": new_id, "version": data["version"]}
        )
        return new_id
    except Exception as e:
        logger.error("Failed to create model version: %s", e)
        return None


def activate_model(model_id: str) -> bool:
    """
    Activate a model (and deactivate other versions with same name).
    
    Args:
        model_id: Model UUID to activate
    
    Returns:
        True if successful
    """
    model = get_model(model_id=model_id)
    if not model:
        return False
    
    try:
        # Deactivate other versions
        _db.query(f"UPDATE scoring_models SET active = FALSE WHERE name = {escape_sql_value(model['name'])}")
        
        # Activate this version
        _db.query(f"UPDATE scoring_models SET active = TRUE, updated_at = '{datetime.now(timezone.utc).isoformat()}' WHERE id = {escape_sql_value(model_id)}")
        
        log_execution(
            worker_id="SYSTEM",
            action="model.activated",
            message=f"Activated model {model['name']} version {model['version']}",
            output_data={"model_id": model_id, "version": model["version"]}
        )
        return True
    except Exception as e:
        logger.error("Failed to activate model: %s", e)
        return False


def rollback_model(name: str, to_version: int = None) -> bool:
    """
    Rollback a model to a previous version.
    
    Args:
        name: Model name
        to_version: Version to rollback to (default: previous version)
    
    Returns:
        True if successful
    """
    # Get current active version
    current = get_model(name=name, active_only=True)
    if not current:
        logger.warning("No active model found for %s", name)
        return False
    
    # Find target version
    if to_version:
        sql = f"SELECT id FROM scoring_models WHERE name = {escape_sql_value(name)} AND version = {to_version}"
    else:
        # Get previous version
        sql = f"SELECT id FROM scoring_models WHERE name = {escape_sql_value(name)} AND version < {current['version']} ORDER BY version DESC LIMIT 1"
    
    try:
        result = _db.query(sql)
        rows = result.get("rows", [])
        if not rows:
            logger.warning("No previous version found for %s", name)
            return False
        
        target_id = rows[0]["id"]
        return activate_model(target_id)
    except Exception as e:
        logger.error("Failed to rollback model: %s", e)
        return False


# ============================================================
# PREDICTION TRACKING FUNCTIONS
# ============================================================

def record_prediction(
    model_id: str,
    predicted_score: float,
    predicted_outcome: str = None,
    opportunity_id: str = None,
    prediction_factors: Dict = None
) -> Optional[str]:
    """
    Record a prediction made by a model.
    
    Args:
        model_id: Model that made the prediction
        predicted_score: Numeric score (0.0-1.0 for classifiers)
        predicted_outcome: Categorical outcome (e.g., 'convert', 'churn')
        opportunity_id: Related opportunity UUID
        prediction_factors: JSON explaining factors that influenced prediction
    
    Returns:
        Prediction outcome UUID
    """
    data = {
        "model_id": model_id,
        "predicted_score": predicted_score,
        "predicted_at": datetime.now(timezone.utc).isoformat()
    }
    
    if predicted_outcome:
        data["predicted_outcome"] = predicted_outcome
    if opportunity_id:
        data["opportunity_id"] = opportunity_id
    if prediction_factors:
        data["prediction_factors"] = prediction_factors
    
    try:
        return _db.insert("prediction_outcomes", data)
    except Exception as e:
        logger.error("Failed to record prediction: %s", e)
        return None


def resolve_prediction(
    prediction_id: str,
    actual_outcome: str,
    actual_value: float = None
) -> bool:
    """
    Record the actual outcome of a prediction.
    
    Args:
        prediction_id: Prediction UUID
        actual_outcome: What actually happened
        actual_value: Numeric actual value (for regression)
    
    Returns:
        True if successful
    """
    # Get the prediction
    sql = f"SELECT predicted_score, predicted_outcome FROM prediction_outcomes WHERE id = {escape_sql_value(prediction_id)}"
    result = _db.query(sql)
    rows = result.get("rows", [])
    if not rows:
        return False
    
    prediction = rows[0]
    
    # Calculate correctness
    correct = prediction.get("predicted_outcome") == actual_outcome if prediction.get("predicted_outcome") else None
    error_magnitude = abs(float(prediction["predicted_score"]) - actual_value) if actual_value is not None else None
    
    update_sql = f"""
        UPDATE prediction_outcomes 
        SET actual_outcome = '{actual_outcome}',
            actual_value = {actual_value if actual_value is not None else 'NULL'},
            correct = {str(correct).upper() if correct is not None else 'NULL'},
            error_magnitude = {error_magnitude if error_magnitude is not None else 'NULL'},
            resolved_at = '{datetime.now(timezone.utc).isoformat()}'
        WHERE id = {escape_sql_value(prediction_id)}
    """
    
    try:
        _db.query(update_sql)
        return True
    except Exception as e:
        logger.error("Failed to resolve prediction: %s", e)
        return False


def get_model_accuracy(model_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Calculate accuracy metrics for a model.
    
    Args:
        model_id: Model UUID
        days: Days to analyze
    
    Returns:
        Accuracy metrics dict
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    sql = f"""
        SELECT 
            COUNT(*) as total_predictions,
            COUNT(resolved_at) as resolved_predictions,
            SUM(CASE WHEN correct = TRUE THEN 1 ELSE 0 END) as correct_count,
            AVG(CASE WHEN correct IS NOT NULL THEN (CASE WHEN correct THEN 1.0 ELSE 0.0 END) END) as accuracy,
            AVG(ABS(error_magnitude)) as mean_absolute_error,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ABS(error_magnitude)) as median_error
        FROM prediction_outcomes
        WHERE model_id = {escape_sql_value(model_id)}
          AND predicted_at >= '{cutoff}'
    """
    
    try:
        result = _db.query(sql)
        row = result.get("rows", [{}])[0]
        
        return {
            "model_id": model_id,
            "period_days": days,
            "total_predictions": int(row.get("total_predictions") or 0),
            "resolved_predictions": int(row.get("resolved_predictions") or 0),
            "correct_count": int(row.get("correct_count") or 0),
            "accuracy": round(float(row.get("accuracy") or 0) * 100, 2),
            "mean_absolute_error": round(float(row.get("mean_absolute_error") or 0), 4),
            "median_error": round(float(row.get("median_error") or 0), 4) if row.get("median_error") else None
        }
    except Exception as e:
        logger.error("Failed to get model accuracy: %s", e)
        return {}


def update_model_accuracy(model_id: str) -> bool:
    """Update a model's accuracy based on resolved predictions."""
    accuracy = get_model_accuracy(model_id)
    if not accuracy:
        return False
    
    sql = f"""
        UPDATE scoring_models 
        SET accuracy = {accuracy['accuracy']},
            sample_count = {accuracy['resolved_predictions']},
            updated_at = '{datetime.now(timezone.utc).isoformat()}'
        WHERE id = {escape_sql_value(model_id)}
    """
    
    try:
        _db.query(sql)
        return True
    except Exception as e:
        logger.error("Failed to update model accuracy: %s", e)
        return False


# ============================================================
# A/B TESTING FUNCTIONS
# ============================================================

def create_ab_test(
    experiment_name: str,
    model_a_id: str,
    model_b_id: str,
    traffic_split: float = 0.5,
    metric_name: str = "accuracy",
    created_by: str = "SYSTEM",
    metadata: Dict = None
) -> Optional[str]:
    """
    Create an A/B test between two models.
    
    Args:
        experiment_name: Name for the experiment
        model_a_id: Control model UUID
        model_b_id: Challenger model UUID
        traffic_split: Fraction of traffic to model B (0.0-1.0)
        metric_name: Metric to optimize (accuracy, conversion, revenue)
        created_by: Who created this test
        metadata: Additional experiment metadata
    
    Returns:
        Experiment UUID
    """
    data = {
        "experiment_name": experiment_name,
        "model_a_id": model_a_id,
        "model_b_id": model_b_id,
        "traffic_split": traffic_split,
        "metric_name": metric_name,
        "status": "running",
        "model_a_samples": 0,
        "model_b_samples": 0,
        "created_by": created_by
    }
    
    if metadata:
        data["metadata"] = metadata
    
    try:
        exp_id = _db.insert("model_experiments", data)
        log_execution(
            worker_id="SYSTEM",
            action="ab_test.created",
            message=f"Started A/B test: {experiment_name}",
            output_data={"experiment_id": exp_id, "model_a": model_a_id, "model_b": model_b_id}
        )
        return exp_id
    except Exception as e:
        logger.error("Failed to create A/B test: %s", e)
        return None


def get_ab_test_model(experiment_id: str) -> Optional[str]:
    """
    Get which model to use for a prediction in an A/B test.
    Uses traffic_split to randomly assign.
    
    Args:
        experiment_id: Experiment UUID
    
    Returns:
        Model UUID to use, or None if experiment not found/running
    """
    import random
    
    sql = f"SELECT * FROM model_experiments WHERE id = {escape_sql_value(experiment_id)} AND status = 'running'"
    result = _db.query(sql)
    rows = result.get("rows", [])
    
    if not rows:
        return None
    
    exp = rows[0]
    
    # Random assignment based on traffic split
    if random.random() < float(exp["traffic_split"]):
        model_id = exp["model_b_id"]
        update_sql = f"UPDATE model_experiments SET model_b_samples = model_b_samples + 1 WHERE id = {escape_sql_value(experiment_id)}"
    else:
        model_id = exp["model_a_id"]
        update_sql = f"UPDATE model_experiments SET model_a_samples = model_a_samples + 1 WHERE id = {escape_sql_value(experiment_id)}"
    
    try:
        _db.query(update_sql)
    except Exception:
        pass
    
    return model_id


def update_ab_test_metrics(experiment_id: str) -> Dict[str, Any]:
    """
    Update metrics for an A/B test based on prediction outcomes.
    
    Args:
        experiment_id: Experiment UUID
    
    Returns:
        Updated metrics dict
    """
    sql = f"SELECT * FROM model_experiments WHERE id = {escape_sql_value(experiment_id)}"
    result = _db.query(sql)
    rows = result.get("rows", [])
    
    if not rows:
        return {}
    
    exp = rows[0]
    
    # Get accuracy for both models (only for predictions during this experiment)
    model_a_accuracy = get_model_accuracy(exp["model_a_id"])
    model_b_accuracy = get_model_accuracy(exp["model_b_id"])
    
    model_a_metric = model_a_accuracy.get("accuracy", 0)
    model_b_metric = model_b_accuracy.get("accuracy", 0)
    
    # Calculate statistical significance (simple z-test approximation)
    n_a = exp["model_a_samples"] or 1
    n_b = exp["model_b_samples"] or 1
    p_a = model_a_metric / 100
    p_b = model_b_metric / 100
    
    pooled_se = ((p_a * (1 - p_a) / n_a) + (p_b * (1 - p_b) / n_b)) ** 0.5
    z_score = (p_b - p_a) / pooled_se if pooled_se > 0 else 0
    
    # Approximate confidence level from z-score
    confidence = min(0.99, abs(z_score) / 3)  # Simplified
    
    update_sql = f"""
        UPDATE model_experiments 
        SET model_a_metric = {model_a_metric},
            model_b_metric = {model_b_metric},
            confidence_level = {confidence}
        WHERE id = {escape_sql_value(experiment_id)}
    """
    
    try:
        _db.query(update_sql)
    except Exception:
        pass
    
    return {
        "experiment_id": experiment_id,
        "model_a_samples": n_a,
        "model_b_samples": n_b,
        "model_a_metric": model_a_metric,
        "model_b_metric": model_b_metric,
        "confidence_level": round(confidence, 3),
        "winner": "B" if model_b_metric > model_a_metric else "A" if model_a_metric > model_b_metric else "TIE"
    }


def conclude_ab_test(experiment_id: str, winner: str = None) -> bool:
    """
    Conclude an A/B test and optionally declare a winner.
    
    Args:
        experiment_id: Experiment UUID
        winner: 'A', 'B', or None to auto-determine
    
    Returns:
        True if successful
    """
    sql = f"SELECT * FROM model_experiments WHERE id = {escape_sql_value(experiment_id)}"
    result = _db.query(sql)
    rows = result.get("rows", [])
    
    if not rows:
        return False
    
    exp = rows[0]
    
    # Auto-determine winner if not specified
    if not winner:
        metrics = update_ab_test_metrics(experiment_id)
        if metrics.get("confidence_level", 0) >= 0.95:
            winner = metrics.get("winner")
        else:
            winner = "INCONCLUSIVE"
    
    winner_id = None
    if winner == "A":
        winner_id = exp["model_a_id"]
    elif winner == "B":
        winner_id = exp["model_b_id"]
    
    update_sql = f"""
        UPDATE model_experiments 
        SET status = 'completed',
            winner_id = {f"'{winner_id}'" if winner_id else "NULL"},
            ended_at = '{datetime.now(timezone.utc).isoformat()}'
        WHERE id = {escape_sql_value(experiment_id)}
    """
    
    try:
        _db.query(update_sql)
        
        # Auto-activate winner if conclusive
        if winner_id:
            activate_model(winner_id)
            log_execution(
                worker_id="SYSTEM",
                action="ab_test.concluded",
                message=f"A/B test concluded. Winner: Model {winner}",
                output_data={"experiment_id": experiment_id, "winner": winner, "winner_model_id": winner_id}
            )
        
        return True
    except Exception as e:
        logger.error("Failed to conclude A/B test: %s", e)
        return False


def list_ab_tests(status: str = None) -> List[Dict]:
    """List A/B tests, optionally filtered by status."""
    where = f"WHERE status = {escape_sql_value(status)}" if status else ""
    sql = f"SELECT * FROM model_experiments {where} ORDER BY started_at DESC"
    
    try:
        return _db.query(sql).get("rows", [])
    except Exception as e:
        logger.error("Failed to list A/B tests: %s", e)
        return []


# ============================================================
# MODEL TRAINING FUNCTIONS
# ============================================================

def start_training_run(
    model_id: str,
    training_config: Dict,
    training_data_query: str = None,
    feature_columns: List[str] = None,
    target_column: str = None,
    created_by: str = "SYSTEM"
) -> Optional[str]:
    """
    Start a model training run.
    
    Args:
        model_id: Model to train
        training_config: Training configuration (hyperparameters, etc.)
        training_data_query: SQL query to get training data
        feature_columns: List of feature column names
        target_column: Target variable column name
        created_by: Who initiated training
    
    Returns:
        Training run UUID
    """
    model = get_model(model_id=model_id)
    if not model:
        return None
    
    data = {
        "model_id": model_id,
        "version": model["version"],
        "status": "running",
        "training_config": training_config,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "created_by": created_by
    }
    
    if training_data_query:
        data["training_data_query"] = training_data_query
    if feature_columns:
        data["feature_columns"] = feature_columns
    if target_column:
        data["target_column"] = target_column
    
    try:
        run_id = _db.insert("model_training_runs", data)
        log_execution(
            worker_id="SYSTEM",
            action="training.started",
            message=f"Started training run for model {model['name']}",
            output_data={"run_id": run_id, "model_id": model_id}
        )
        return run_id
    except Exception as e:
        logger.error("Failed to start training run: %s", e)
        return None


def complete_training_run(
    run_id: str,
    train_accuracy: float,
    test_accuracy: float = None,
    validation_accuracy: float = None,
    sample_count: int = None,
    metrics: Dict = None,
    new_config: Dict = None
) -> bool:
    """
    Complete a training run with results.
    
    Args:
        run_id: Training run UUID
        train_accuracy: Training set accuracy
        test_accuracy: Test set accuracy
        validation_accuracy: Validation set accuracy
        sample_count: Number of training samples
        metrics: Additional metrics dict
        new_config: Updated model config (weights, etc.)
    
    Returns:
        True if successful
    """
    update_parts = [
        "status = 'completed'",
        f"train_accuracy = {train_accuracy}",
        f"completed_at = '{datetime.now(timezone.utc).isoformat()}'"
    ]
    
    if test_accuracy is not None:
        update_parts.append(f"test_accuracy = {test_accuracy}")
    if validation_accuracy is not None:
        update_parts.append(f"validation_accuracy = {validation_accuracy}")
    if sample_count is not None:
        update_parts.append(f"sample_count = {sample_count}")
    if metrics:
        metrics_json = json.dumps(metrics).replace("'", "''")
        update_parts.append(f"metrics = {escape_sql_value(metrics_json)}")
    
    sql = f"UPDATE model_training_runs SET {', '.join(update_parts)} WHERE id = {escape_sql_value(run_id)}"
    
    try:
        _db.query(sql)
        
        # Get run details to update model
        run_sql = f"SELECT model_id FROM model_training_runs WHERE id = {escape_sql_value(run_id)}"
        run = _db.query(run_sql).get("rows", [{}])[0]
        
        if run.get("model_id"):
            # Update model with training results
            model_update = f"""
                UPDATE scoring_models 
                SET accuracy = {test_accuracy or train_accuracy},
                    sample_count = {sample_count or 0},
                    last_trained_at = '{datetime.now(timezone.utc).isoformat()}'
                WHERE id = {escape_sql_value(run['model_id'])}
            """
            _db.query(model_update)
            
            # Create new version if config changed
            if new_config:
                create_model_version(run["model_id"], new_config)
        
        return True
    except Exception as e:
        logger.error("Failed to complete training run: %s", e)
        return False


def fail_training_run(run_id: str, error_message: str) -> bool:
    """Mark a training run as failed."""
    sql = f"""
        UPDATE model_training_runs 
        SET status = 'failed',
            error_message = '{error_message.replace("'", "''")}',
            completed_at = '{datetime.now(timezone.utc).isoformat()}'
        WHERE id = {escape_sql_value(run_id)}
    """
    
    try:
        _db.query(sql)
        return True
    except Exception as e:
        logger.error("Failed to fail training run: %s", e)
        return False


def get_training_history(model_id: str = None, limit: int = 20) -> List[Dict]:
    """Get training run history for a model or all models."""
    where = f"WHERE model_id = {escape_sql_value(model_id)}" if model_id else ""
    sql = f"SELECT * FROM model_training_runs {where} ORDER BY created_at DESC LIMIT {limit}"
    
    try:
        return _db.query(sql).get("rows", [])
    except Exception as e:
        logger.error("Failed to get training history: %s", e)
        return []


def get_model_performance() -> List[Dict]:
    """Get performance metrics for all models using the view."""
    try:
        return _db.query("SELECT * FROM v_model_performance").get("rows", [])
    except Exception as e:
        logger.error("Failed to get model performance: %s", e)
        return []


# ============================================================
# L5: ORG-WIDE LEARNINGS FUNCTIONS
# ============================================================

def record_learning(
    summary: str,
    category: str,
    worker_id: str = "SYSTEM",
    task_id: Optional[str] = None,
    goal_id: Optional[str] = None,
    details: Optional[Dict] = None,
    evidence_task_ids: Optional[List[str]] = None,
    confidence: float = 0.7
) -> Optional[str]:
    """
    Record an organizational learning from task execution.
    
    L5 Requirement: Org-Wide Memory - Persistent, auditable memory across years.
    
    Args:
        summary: Brief description of the learning
        category: Category (e.g., 'bug', 'pattern', 'optimization', 'failure', 'success')
        worker_id: Which worker discovered this learning
        task_id: Associated task UUID
        goal_id: Associated goal UUID
        details: Additional JSON details
        evidence_task_ids: List of task IDs that support this learning
        confidence: Confidence score (0.0-1.0)
    
    Returns:
        Learning UUID or None on failure
    """
    data = {
        "summary": summary,
        "category": category,
        "worker_id": worker_id,
        "confidence": confidence,
        "applied_count": 0,
        "is_validated": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if task_id:
        data["task_id"] = task_id
    if goal_id:
        data["goal_id"] = goal_id
    if details:
        data["details"] = details
    if evidence_task_ids:
        data["evidence_task_ids"] = evidence_task_ids
    
    try:
        learning_id = _db.insert("learnings", data)
        
        log_execution(
            worker_id=worker_id,
            action="learning.recorded",
            message=f"Recorded learning: {summary[:100]}",
            output_data={"learning_id": learning_id, "category": category, "confidence": confidence}
        )
        
        return learning_id
    except Exception as e:
        log_execution(
            worker_id=worker_id,
            action="learning.record_error",
            message=f"Failed to record learning: {e}",
            level="error"
        )
        return None


def search_learnings(
    category: Optional[str] = None,
    worker_id: Optional[str] = None,
    search_text: Optional[str] = None,
    min_confidence: Optional[float] = None,
    validated_only: bool = False,
    limit: int = 50
) -> List[Dict]:
    """
    Search organizational learnings.
    
    L5 Requirement: Memory searchable by topic/date/worker.
    
    Args:
        category: Filter by category
        worker_id: Filter by worker who discovered it
        search_text: Text to search in summary
        min_confidence: Minimum confidence score
        validated_only: Only return validated learnings
        limit: Max learnings to return
    
    Returns:
        List of learning records
    """
    conditions = []
    
    if category:
        conditions.append(f"category = {escape_sql_value(category)}")
    if worker_id:
        conditions.append(f"worker_id = {escape_sql_value(worker_id)}")
    if min_confidence is not None:
        conditions.append(f"confidence >= {min_confidence}")
    if validated_only:
        conditions.append("is_validated = TRUE")
    if search_text:
        conditions.append(f"summary ILIKE {escape_sql_value('%' + search_text + '%')}")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM learnings {where} ORDER BY created_at DESC LIMIT {limit}"
    
    try:
        result = _db.query(sql)
        return result.get("rows", [])
    except Exception as e:
        log_execution(
            worker_id="SYSTEM",
            action="learning.search_error",
            message=f"Failed to search learnings: {e}",
            level="error"
        )
        return []


def get_learning_categories() -> List[Dict]:
    """
    Get summary of learnings by category.
    
    Returns:
        List of categories with counts and avg confidence
    """
    sql = """
        SELECT 
            category,
            COUNT(*) as count,
            AVG(confidence) as avg_confidence,
            SUM(applied_count) as total_applications
        FROM learnings
        GROUP BY category
        ORDER BY count DESC
    """
    
    try:
        result = _db.query(sql)
        return result.get("rows", [])
    except Exception as e:
        log_execution(
            worker_id="SYSTEM",
            action="learning.categories_error",
            message=f"Failed to get learning categories: {e}",
            level="error"
        )
        return []


def apply_learning(learning_id: str) -> bool:
    """
    Mark a learning as applied (increment applied_count).
    
    Args:
        learning_id: UUID of the learning to mark as applied
    
    Returns:
        True if successful, False otherwise
    """
    sql = f"""
        UPDATE learnings 
        SET applied_count = applied_count + 1,
            updated_at = {escape_sql_value(datetime.now(timezone.utc).isoformat())}
        WHERE id = {escape_sql_value(learning_id)}
    """
    
    try:
        _db.query(sql)
        return True
    except Exception as e:
        log_execution(
            worker_id="SYSTEM",
            action="learning.apply_error",
            message=f"Failed to apply learning: {e}",
            level="error"
        )
        return False


def validate_learning(learning_id: str, validated_by: str) -> bool:
    """
    Mark a learning as validated by a human or higher authority.
    
    Args:
        learning_id: UUID of the learning to validate
        validated_by: Who validated it (worker_id or 'human')
    
    Returns:
        True if successful, False otherwise
    """
    sql = f"""
        UPDATE learnings 
        SET is_validated = TRUE,
            validated_by = {escape_sql_value(validated_by)},
            updated_at = {escape_sql_value(datetime.now(timezone.utc).isoformat())}
        WHERE id = {escape_sql_value(learning_id)}
    """
    
    try:
        _db.query(sql)
        return True
    except Exception as e:
        log_execution(
            worker_id=validated_by,
            action="learning.validate_error",
            message=f"Failed to validate learning: {e}",
            level="error"
        )
        return False
# ==============================================================================
# REVENUE TRACKING FUNCTIONS
# Add this section to the end of core/database.py
# PR: BUILD REVENUE TRACKING (HIGH-04)
# Worker: claude-chat-OPUS45
# ==============================================================================

def record_revenue(
    event_type: str,
    gross_amount: float,
    revenue_type: str = "one_time",
    net_amount: float = None,
    currency: str = "USD",
    source: str = None,
    opportunity_id: str = None,
    attribution: Dict = None,
    occurred_at: str = None,
    created_by: str = "SYSTEM"
) -> Optional[str]:
    """
    Record a revenue event.
    
    Args:
        event_type: Type of event ('sale', 'refund', 'recurring')
        gross_amount: Gross revenue amount in dollars
        revenue_type: Revenue classification ('one_time', 'recurring', 'usage')
        net_amount: Net amount after fees/costs (defaults to gross if not specified)
        currency: Currency code (default: 'USD')
        source: Revenue source identifier (e.g., 'gumroad', 'stripe', 'manual')
        opportunity_id: Related opportunity UUID
        attribution: JSON dict with attribution details (e.g., campaign, channel)
        occurred_at: When the transaction occurred (ISO timestamp, defaults to now)
        created_by: Who recorded this event
    
    Returns:
        Revenue event UUID or None on failure
    
    Example:
        >>> record_revenue(
        ...     event_type="sale",
        ...     gross_amount=49.99,
        ...     revenue_type="one_time",
        ...     net_amount=42.50,
        ...     source="gumroad",
        ...     attribution={"campaign": "twitter_launch", "product": "prompt_pack"}
        ... )
        'a1b2c3d4-e5f6-...'
    """
    # Validate event_type
    valid_event_types = ("sale", "refund", "recurring")
    if event_type not in valid_event_types:
        logger.error("Invalid event_type '%s'. Must be one of: %s", event_type, valid_event_types)
        return None
    
    # Validate revenue_type
    valid_revenue_types = ("one_time", "recurring", "usage")
    if revenue_type not in valid_revenue_types:
        logger.error("Invalid revenue_type '%s'. Must be one of: %s", revenue_type, valid_revenue_types)
        return None
    
    # Default net_amount to gross_amount if not specified
    if net_amount is None:
        net_amount = gross_amount
    
    # Default occurred_at to now if not specified
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc).isoformat()
    
    data = {
        "event_type": event_type,
        "revenue_type": revenue_type,
        "gross_amount": gross_amount,
        "net_amount": net_amount,
        "currency": currency,
        "occurred_at": occurred_at,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if source:
        data["source"] = source
    if opportunity_id:
        data["opportunity_id"] = opportunity_id
    if attribution:
        data["attribution"] = attribution
    
    try:
        revenue_id = _db.insert("revenue_events", data)
        
        log_execution(
            worker_id=created_by,
            action="revenue.recorded",
            message=f"Recorded {event_type}: ${gross_amount:.2f} ({revenue_type})",
            output_data={
                "revenue_id": revenue_id,
                "event_type": event_type,
                "gross_amount": gross_amount,
                "net_amount": net_amount,
                "source": source
            }
        )
        
        return revenue_id
    except Exception as e:
        logger.error("Failed to record revenue: %s", e)
        log_execution(
            worker_id=created_by,
            action="revenue.record_error",
            message=f"Failed to record revenue: {e}",
            level="error",
            error_data={"error": str(e), "event_type": event_type, "gross_amount": gross_amount}
        )
        return None


def get_revenue_summary(
    period_type: str = "daily",
    start_date: str = None,
    end_date: str = None,
    source: str = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get revenue summary for a specified period.
    
    Args:
        period_type: Aggregation period ('daily', 'weekly', 'monthly')
        start_date: Start date in YYYY-MM-DD format (defaults to 'days' ago)
        end_date: End date in YYYY-MM-DD format (defaults to today)
        source: Filter by revenue source
        days: Number of days to look back if start_date not specified (default: 30)
    
    Returns:
        Dict containing:
            - total_gross: Total gross revenue
            - total_net: Total net revenue  
            - event_count: Number of revenue events
            - by_type: Revenue broken down by event_type
            - by_source: Revenue broken down by source
            - by_period: Revenue broken down by period
            - avg_transaction: Average transaction amount
            - period_start: Start of period analyzed
            - period_end: End of period analyzed
    
    Example:
        >>> get_revenue_summary(period_type="weekly", days=7)
        {
            'total_gross': 1250.00,
            'total_net': 1062.50,
            'event_count': 15,
            'avg_transaction': 83.33,
            'by_type': {'sale': {'count': 14, 'gross': 1300.00, 'net': 1105.00}, 
                       'refund': {'count': 1, 'gross': -50.00, 'net': -42.50}},
            'by_source': {'gumroad': {...}, 'stripe': {...}},
            'by_period': [{'period': '2026-01-13', 'count': 5, 'gross': 400.00, 'net': 340.00}, ...],
            ...
        }
    """
    # Set default date range
    if end_date is None:
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Build base WHERE conditions
    conditions = [
        f"occurred_at >= {escape_sql_value(start_date)}",
        f"occurred_at < {escape_sql_value(end_date + 'T23:59:59Z')}"
    ]
    if source:
        conditions.append(f"source = {escape_sql_value(source)}")
    
    where_clause = f"WHERE {' AND '.join(conditions)}"
    
    # Query: Total summary
    total_sql = f"""
        SELECT 
            COALESCE(SUM(gross_amount), 0) as total_gross,
            COALESCE(SUM(net_amount), 0) as total_net,
            COUNT(*) as event_count,
            COALESCE(AVG(gross_amount), 0) as avg_transaction
        FROM revenue_events
        {where_clause}
    """
    
    # Query: By event type
    by_type_sql = f"""
        SELECT 
            event_type,
            COUNT(*) as count,
            COALESCE(SUM(gross_amount), 0) as gross,
            COALESCE(SUM(net_amount), 0) as net
        FROM revenue_events
        {where_clause}
        GROUP BY event_type
        ORDER BY gross DESC
    """
    
    # Query: By source
    by_source_sql = f"""
        SELECT 
            COALESCE(source, 'unknown') as source,
            COUNT(*) as count,
            COALESCE(SUM(gross_amount), 0) as gross,
            COALESCE(SUM(net_amount), 0) as net
        FROM revenue_events
        {where_clause}
        GROUP BY source
        ORDER BY gross DESC
    """
    
    # Query: By period (date truncation based on period_type)
    if period_type == "daily":
        date_trunc = "DATE(occurred_at)"
    elif period_type == "weekly":
        date_trunc = "DATE_TRUNC('week', occurred_at)"
    elif period_type == "monthly":
        date_trunc = "DATE_TRUNC('month', occurred_at)"
    else:
        date_trunc = "DATE(occurred_at)"
    
    by_period_sql = f"""
        SELECT 
            {date_trunc} as period,
            COUNT(*) as count,
            COALESCE(SUM(gross_amount), 0) as gross,
            COALESCE(SUM(net_amount), 0) as net
        FROM revenue_events
        {where_clause}
        GROUP BY {date_trunc}
        ORDER BY period ASC
    """
    
    try:
        # Execute all queries
        total_result = _db.query(total_sql).get("rows", [{}])[0]
        by_type_result = _db.query(by_type_sql).get("rows", [])
        by_source_result = _db.query(by_source_sql).get("rows", [])
        by_period_result = _db.query(by_period_sql).get("rows", [])
        
        summary = {
            "total_gross": float(total_result.get("total_gross", 0) or 0),
            "total_net": float(total_result.get("total_net", 0) or 0),
            "event_count": int(total_result.get("event_count", 0) or 0),
            "avg_transaction": round(float(total_result.get("avg_transaction", 0) or 0), 2),
            "by_type": {
                r["event_type"]: {
                    "count": int(r["count"]),
                    "gross": float(r["gross"]),
                    "net": float(r["net"])
                }
                for r in by_type_result
            },
            "by_source": {
                r["source"]: {
                    "count": int(r["count"]),
                    "gross": float(r["gross"]),
                    "net": float(r["net"])
                }
                for r in by_source_result
            },
            "by_period": [
                {
                    "period": str(r["period"])[:10],  # Truncate to date only
                    "count": int(r["count"]),
                    "gross": float(r["gross"]),
                    "net": float(r["net"])
                }
                for r in by_period_result
            ],
            "period_type": period_type,
            "period_start": start_date,
            "period_end": end_date
        }
        
        return summary
    except Exception as e:
        logger.error("Failed to get revenue summary: %s", e)
        return {
            "error": str(e),
            "total_gross": 0,
            "total_net": 0,
            "event_count": 0,
            "period_start": start_date,
            "period_end": end_date
        }


def get_revenue_by_opportunity(opportunity_id: str) -> Dict[str, Any]:
    """
    Get all revenue events for a specific opportunity.
    
    Args:
        opportunity_id: Opportunity UUID
    
    Returns:
        Dict with total revenue and list of events
    """
    sql = f"""
        SELECT *
        FROM revenue_events
        WHERE opportunity_id = {escape_sql_value(opportunity_id)}
        ORDER BY occurred_at DESC
    """
    
    total_sql = f"""
        SELECT 
            COALESCE(SUM(gross_amount), 0) as total_gross,
            COALESCE(SUM(net_amount), 0) as total_net,
            COUNT(*) as event_count
        FROM revenue_events
        WHERE opportunity_id = {escape_sql_value(opportunity_id)}
    """
    
    try:
        events = _db.query(sql).get("rows", [])
        totals = _db.query(total_sql).get("rows", [{}])[0]
        
        return {
            "opportunity_id": opportunity_id,
            "total_gross": float(totals.get("total_gross", 0) or 0),
            "total_net": float(totals.get("total_net", 0) or 0),
            "event_count": int(totals.get("event_count", 0) or 0),
            "events": events
        }
    except Exception as e:
        logger.error("Failed to get revenue for opportunity %s: %s", opportunity_id, e)
        return {
            "opportunity_id": opportunity_id,
            "error": str(e),
            "total_gross": 0,
            "total_net": 0,
            "event_count": 0,
            "events": []
        }


def get_recent_revenue(limit: int = 20, event_type: str = None) -> List[Dict]:
    """
    Get recent revenue events.
    
    Args:
        limit: Max number of events to return (default: 20)
        event_type: Filter by event type ('sale', 'refund', 'recurring')
    
    Returns:
        List of recent revenue events
    """
    conditions = []
    if event_type:
        conditions.append(f"event_type = {escape_sql_value(event_type)}")
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sql = f"""
        SELECT *
        FROM revenue_events
        {where_clause}
        ORDER BY occurred_at DESC
        LIMIT {limit}
    """
    
    try:
        return _db.query(sql).get("rows", [])
    except Exception as e:
        logger.error("Failed to get recent revenue: %s", e)
        return []
