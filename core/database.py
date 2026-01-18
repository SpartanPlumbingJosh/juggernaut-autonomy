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
        print(f"Failed to record cost: {e}")
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
    
    conditions = [f"occurred_at >= '{cutoff}'"]
    if cost_type:
        conditions.append(f"cost_type = '{cost_type}'")
    if category:
        conditions.append(f"category = '{category}'")
    
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
        print(f"Failed to get cost summary: {e}")
        return {}


def get_cost_events(
    days: int = 30,
    cost_type: str = None,
    category: str = None,
    limit: int = 100
) -> List[Dict]:
    """Get recent cost events."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    conditions = [f"occurred_at >= '{cutoff}'"]
    if cost_type:
        conditions.append(f"cost_type = '{cost_type}'")
    if category:
        conditions.append(f"category = '{category}'")
    
    where = f"WHERE {' AND '.join(conditions)}"
    sql = f"SELECT * FROM cost_events {where} ORDER BY occurred_at DESC LIMIT {limit}"
    
    try:
        return _db.query(sql).get("rows", [])
    except Exception as e:
        print(f"Failed to get cost events: {e}")
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
        print(f"Failed to create budget: {e}")
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
        conditions = [f"occurred_at >= '{month_start}'"]
        if budget.get("cost_type"):
            conditions.append(f"cost_type = '{budget['cost_type']}'")
        if budget.get("category"):
            conditions.append(f"category = '{budget['category']}'")
        
        where = f"WHERE {' AND '.join(conditions)}"
        
        # Get monthly total
        month_sql = f"SELECT COALESCE(SUM(amount_cents), 0) as total FROM cost_events {where}"
        month_total = int(_db.query(month_sql).get("rows", [{}])[0].get("total") or 0)
        
        # Get daily total if daily limit exists
        daily_total = 0
        if budget.get("daily_limit_cents"):
            daily_conditions = conditions.copy()
            daily_conditions[0] = f"occurred_at >= '{today_start}'"
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
        WHERE occurred_at >= '{cutoff}'
    """
    
    # Get costs
    cost_sql = f"""
        SELECT COALESCE(SUM(amount_cents), 0) as total
        FROM cost_events 
        WHERE occurred_at >= '{cutoff}'
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
        print(f"Failed to get profit/loss: {e}")
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
        WHERE attribution->>'experiment' = '{experiment_id}'
           OR metadata->>'experiment_id' = '{experiment_id}'
    """
    
    # Costs attributed to experiment  
    cost_sql = f"""
        SELECT COALESCE(SUM(amount_cents), 0) as total
        FROM cost_events 
        WHERE experiment_id = '{experiment_id}'
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
        print(f"Failed to get experiment ROI: {e}")
        return {}
