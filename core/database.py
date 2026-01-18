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


def query_db(sql: str) -> Dict[str, Any]:
    """Execute raw SQL query."""
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
        print(f"Failed to log execution: {e}")
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
        conditions.append(f"worker_id = '{worker_id}'")
    if action:
        conditions.append(f"action LIKE '{action}%'")
    if level:
        conditions.append(f"level = '{level}'")
    
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
    sql = f"DELETE FROM execution_logs WHERE created_at < '{cutoff}' AND level NOT IN ('error', 'critical')"
    
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
        print(f"Failed to cleanup logs: {e}")
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
        WHERE created_at >= '{cutoff}' 
        GROUP BY level
    """
    
    # Count by worker
    worker_sql = f"""
        SELECT worker_id, COUNT(*) as count 
        FROM execution_logs 
        WHERE created_at >= '{cutoff}' 
        GROUP BY worker_id
        ORDER BY count DESC
        LIMIT 10
    """
    
    # Count by action
    action_sql = f"""
        SELECT action, COUNT(*) as count 
        FROM execution_logs 
        WHERE created_at >= '{cutoff}' 
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
        print(f"Failed to get log summary: {e}")
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
        print(f"Failed to create opportunity: {e}")
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
    
    sql = f"UPDATE opportunities SET {', '.join(set_clauses)} WHERE id = '{opportunity_id}'"
    
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
        print(f"Failed to update opportunity: {e}")
        return False


def get_opportunities(status: str = None, limit: int = 50) -> List[Dict]:
    """Get opportunities, optionally filtered by status."""
    where = f"WHERE status = '{status}'" if status else ""
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
        print(f"Failed to record revenue: {e}")
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
        WHERE occurred_at >= '{cutoff}'
        AND event_type != 'refund'
    """
    
    # By source
    source_sql = f"""
        SELECT source, SUM(gross_amount) as total 
        FROM revenue_events 
        WHERE occurred_at >= '{cutoff}'
        AND event_type != 'refund'
        GROUP BY source
        ORDER BY total DESC
    """
    
    # By type
    type_sql = f"""
        SELECT revenue_type, SUM(gross_amount) as total 
        FROM revenue_events 
        WHERE occurred_at >= '{cutoff}'
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
        print(f"Failed to get revenue summary: {e}")
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
    conditions = [f"occurred_at >= '{cutoff}'"]
    
    if source:
        conditions.append(f"source = '{source}'")
    if event_type:
        conditions.append(f"event_type = '{event_type}'")
    
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
        print(f"Failed to write memory: {e}")
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
        conditions.append(f"category = '{category}'")
    if worker_id:
        conditions.append(f"worker_id = '{worker_id}'")
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
    sql = f"UPDATE memories SET importance = {new_importance}, updated_at = '{datetime.now(timezone.utc).isoformat()}' WHERE id = '{memory_id}'"
    try:
        _db.query(sql)
        return True
    except Exception as e:
        print(f"Failed to update memory: {e}")
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
        print(f"Failed to send message: {e}")
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
        WHERE (to_worker = '{to_worker}' OR to_worker = 'ALL')
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
        WHERE id = '{message_id}'
    """
    try:
        _db.query(sql)
        return True
    except Exception as e:
        print(f"Failed to acknowledge message: {e}")
        return False


def mark_message_read(message_id: str) -> bool:
    """Mark a message as read."""
    sql = f"UPDATE communications SET status = 'read', read_at = '{datetime.now(timezone.utc).isoformat()}' WHERE id = '{message_id}'"
    try:
        _db.query(sql)
        return True
    except Exception as e:
        print(f"Failed to mark message read: {e}")
        return False
