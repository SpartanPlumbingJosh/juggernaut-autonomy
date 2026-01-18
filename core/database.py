"""
JUGGERNAUT Database Operations
Neon PostgreSQL via SQL over HTTP
"""

import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

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
            # Escape single quotes in JSON
            json_str = json.dumps(v).replace("'", "''")
            return f"'{json_str}'"
        else:
            # Escape single quotes in strings
            escaped = str(v).replace("'", "''")
            return f"'{escaped}'"


# Singleton instance
_db = Database()


def query_db(sql: str) -> Dict[str, Any]:
    """Execute raw SQL query."""
    return _db.query(sql)


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
        
        # Log the creation
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


def get_logs(worker_id: str = None, action: str = None, limit: int = 100) -> List[Dict]:
    """Get execution logs, optionally filtered."""
    conditions = []
    if worker_id:
        conditions.append(f"worker_id = '{worker_id}'")
    if action:
        conditions.append(f"action LIKE '{action}%'")
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM execution_logs {where} ORDER BY created_at DESC LIMIT {limit}"
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
        event_type: Type of event ('sale', 'refund', 'subscription', 'payout')
        gross_amount: Total amount before fees (positive for income, negative for refunds)
        source: Where revenue came from ('gumroad', 'stripe', 'manual', etc.)
        description: Human-readable description
        net_amount: Amount after platform fees (defaults to gross_amount)
        revenue_type: 'one_time', 'recurring', 'affiliate'
        currency: Currency code (default USD)
        opportunity_id: Link to opportunity that generated this revenue
        external_id: ID in external system (e.g., Gumroad sale ID)
        attribution: JSON with attribution data (experiment_id, source, campaign, etc.)
        metadata: Additional JSON data
        occurred_at: When the revenue actually occurred (ISO timestamp, defaults to now)
        recorded_by: Who/what recorded this event
    
    Returns:
        Revenue event UUID or None on failure
    """
    now = datetime.now(timezone.utc).isoformat()
    
    data = {
        "event_type": event_type,
        "gross_amount": gross_amount,
        "net_amount": net_amount if net_amount is not None else gross_amount,
        "source": source,
        "description": description,
        "revenue_type": revenue_type,
        "currency": currency,
        "occurred_at": occurred_at or now,
        "recorded_at": now
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
        revenue_id = _db.insert("revenue_events", data)
        
        # Log the revenue event
        log_execution(
            worker_id=recorded_by,
            action=f"revenue.{event_type}",
            message=f"Recorded {event_type}: ${gross_amount:.2f} from {source}",
            output_data={
                "revenue_id": revenue_id,
                "gross_amount": gross_amount,
                "net_amount": data["net_amount"],
                "source": source
            }
        )
        
        return revenue_id
    except Exception as e:
        print(f"Failed to record revenue: {e}")
        return None


def get_revenue_summary(
    days: int = 30,
    source: str = None,
    revenue_type: str = None
) -> Dict[str, Any]:
    """
    Get revenue summary for a time period.
    
    Args:
        days: Number of days to look back (default 30)
        source: Filter by source (optional)
        revenue_type: Filter by revenue type (optional)
    
    Returns:
        Dictionary with total_gross, total_net, event_count, by_source, by_type
    """
    conditions = [f"occurred_at > NOW() - INTERVAL '{days} days'"]
    if source:
        conditions.append(f"source = '{source}'")
    if revenue_type:
        conditions.append(f"revenue_type = '{revenue_type}'")
    
    where = f"WHERE {' AND '.join(conditions)}"
    
    # Total summary
    sql = f"""
        SELECT 
            COALESCE(SUM(gross_amount), 0) as total_gross,
            COALESCE(SUM(net_amount), 0) as total_net,
            COUNT(*) as event_count
        FROM revenue_events
        {where}
    """
    result = _db.query(sql)
    summary = result.get("rows", [{}])[0]
    
    # By source
    sql_by_source = f"""
        SELECT source, SUM(gross_amount) as gross, SUM(net_amount) as net, COUNT(*) as count
        FROM revenue_events
        {where}
        GROUP BY source
        ORDER BY gross DESC
    """
    result_by_source = _db.query(sql_by_source)
    
    # By type
    sql_by_type = f"""
        SELECT revenue_type, SUM(gross_amount) as gross, SUM(net_amount) as net, COUNT(*) as count
        FROM revenue_events
        {where}
        GROUP BY revenue_type
        ORDER BY gross DESC
    """
    result_by_type = _db.query(sql_by_type)
    
    return {
        "period_days": days,
        "total_gross": float(summary.get("total_gross", 0)),
        "total_net": float(summary.get("total_net", 0)),
        "event_count": int(summary.get("event_count", 0)),
        "by_source": result_by_source.get("rows", []),
        "by_type": result_by_type.get("rows", [])
    }


def get_recent_revenue(limit: int = 20, source: str = None) -> List[Dict]:
    """Get recent revenue events."""
    where = f"WHERE source = '{source}'" if source else ""
    sql = f"""
        SELECT * FROM revenue_events 
        {where}
        ORDER BY occurred_at DESC 
        LIMIT {limit}
    """
    result = _db.query(sql)
    return result.get("rows", [])


if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    result = query_db("SELECT COUNT(*) as count FROM execution_logs")
    print(f"Execution logs count: {result['rows'][0]['count']}")
    
    # Test logging
    log_id = log_execution(
        worker_id="ORCHESTRATOR",
        action="system.test",
        message="Database module test successful",
        source="db_test"
    )
    print(f"Created test log: {log_id}")
    
    # Test revenue summary
    print("\nTesting revenue functions...")
    summary = get_revenue_summary(days=30)
    print(f"Revenue summary (30 days): ${summary['total_gross']:.2f} gross, {summary['event_count']} events")
