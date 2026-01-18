"""
JUGGERNAUT Database Operations
Neon PostgreSQL via SQL over HTTP
"""

import os
import json
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from uuid import uuid4

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
    
    def query(self, sql: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a SQL query and return results."""
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": self.connection_string
        }
        
        # Simple parameter substitution (for basic cases)
        if params:
            for key, value in params.items():
                if isinstance(value, str):
                    sql = sql.replace(f"${key}", f"'{value}'")
                elif value is None:
                    sql = sql.replace(f"${key}", "NULL")
                else:
                    sql = sql.replace(f"${key}", str(value))
        
        response = httpx.post(
            self.endpoint,
            headers=headers,
            json={"query": sql},
            timeout=30.0
        )
        
        result = response.json()
        if "message" in result and "error" in result.get("severity", "").lower():
            raise Exception(f"Database error: {result['message']}")
        
        return result
    
    def insert(self, table: str, data: Dict[str, Any]) -> Optional[str]:
        """Insert a row and return the ID."""
        columns = ", ".join(data.keys())
        values = ", ".join([
            f"'{v}'" if isinstance(v, str) else 
            "NULL" if v is None else
            f"'{json.dumps(v)}'" if isinstance(v, (dict, list)) else
            str(v)
            for v in data.values()
        ])
        
        sql = f"INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING id"
        result = self.query(sql)
        
        if result.get("rows"):
            return result["rows"][0].get("id")
        return None


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
    customer_contact: str = None,
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
        customer_contact: Contact info
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
        "status": "identified",
        "stage": "new",
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
        if isinstance(value, str):
            set_clauses.append(f"{key} = '{value}'")
        elif value is None:
            set_clauses.append(f"{key} = NULL")
        elif isinstance(value, (dict, list)):
            set_clauses.append(f"{key} = '{json.dumps(value)}'")
        else:
            set_clauses.append(f"{key} = {value}")
    
    set_clauses.append(f"updated_at = '{datetime.now(timezone.utc).isoformat()}'")
    
    sql = f"UPDATE opportunities SET {', '.join(set_clauses)} WHERE id = '{opportunity_id}'"
    
    try:
        result = _db.query(sql)
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
