"""
Scan Task Handler
=================
Runs opportunity scanner using configured sources.
Checks opportunity_sources table and executes scans.
"""

import json
import urllib.request
import urllib.error
import os
from typing import Dict, Any, Tuple, List
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "")
NEON_ENDPOINT = os.getenv(
    "NEON_ENDPOINT",
    "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
)


def _execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL via Neon HTTP API."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    data = json.dumps({"query": sql}).encode('utf-8')
    req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _escape_value(value: Any) -> str:
    """Escape a value for SQL insertion."""
    if value is None:
        return "NULL"
    elif isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (dict, list)):
        json_str = json.dumps(value)
        escaped = json_str.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"
    else:
        s = str(value)
        escaped = s.replace("\\", "\\\\").replace("'", "''").replace("\x00", "")
        return f"'{escaped}'"


def _get_opportunity_sources() -> List[Dict]:
    """Get configured opportunity sources from database."""
    sql = "SELECT id, name, source_type, scan_config, enabled FROM opportunity_sources WHERE enabled = true"
    result = _execute_sql(sql)
    return result.get("rows", [])


def _save_opportunity(opportunity: Dict) -> str:
    """Save a discovered opportunity to the database."""
    now = datetime.now(timezone.utc).isoformat()
    
    sql = f"""
    INSERT INTO opportunities (name, source, score, data, status, discovered_at, created_at)
    VALUES (
        {_escape_value(opportunity.get('name', 'Unknown'))},
        {_escape_value(opportunity.get('source', 'scan'))},
        {_escape_value(opportunity.get('score', 0.5))},
        {_escape_value(opportunity.get('data', {}))},
        'discovered',
        {_escape_value(now)},
        {_escape_value(now)}
    )
    RETURNING id
    """
    result = _execute_sql(sql)
    rows = result.get("rows", [])
    return rows[0].get("id") if rows else None


def _scan_source(source: Dict, log_action_fn, task_id: str) -> List[Dict]:
    """
    Scan a single source for opportunities.
    Returns list of discovered opportunities.
    """
    source_name = source.get("name", "unknown")
    source_type = source.get("source_type", "unknown")
    scan_config = source.get("scan_config", {})
    
    if isinstance(scan_config, str):
        try:
            scan_config = json.loads(scan_config)
        except:
            scan_config = {}
    
    opportunities = []
    
    log_action_fn(
        "task.scan_source",
        f"Scanning source: {source_name} (type: {source_type})",
        level="info",
        task_id=task_id,
        input_data={"source_id": source.get("id"), "source_type": source_type}
    )
    
    # Placeholder: In production, this would call actual scanning logic
    # based on source_type (expired_domains, trends, product_hunt, etc.)
    # For now, log that we attempted the scan
    
    if source_type == "expired_domains":
        # Would call ExpiredDomains.net API
        log_action_fn(
            "task.scan_placeholder",
            f"Expired domains scan attempted for {source_name} - needs API config",
            level="info",
            task_id=task_id
        )
    elif source_type == "trends":
        # Would call Google Trends API
        log_action_fn(
            "task.scan_placeholder",
            f"Trends scan attempted for {source_name} - needs API config",
            level="info",
            task_id=task_id
        )
    elif source_type == "product_hunt":
        # Would call Product Hunt API
        log_action_fn(
            "task.scan_placeholder",
            f"Product Hunt scan attempted for {source_name} - needs API config",
            level="info",
            task_id=task_id
        )
    else:
        log_action_fn(
            "task.scan_unknown_type",
            f"Unknown source type: {source_type}",
            level="warn",
            task_id=task_id
        )
    
    return opportunities


def handle_scan_task(task_id: str, payload: Dict[str, Any], log_action_fn) -> Tuple[bool, Dict[str, Any]]:
    """
    Run opportunity scanner across configured sources.
    
    Args:
        task_id: Task identifier for logging
        payload: Task payload optionally containing 'source_id' to scan specific source
        log_action_fn: Function to log actions
    
    Returns:
        Tuple of (success: bool, result: dict)
    """
    source_id = payload.get("source_id")  # Optional: scan specific source
    
    try:
        log_action_fn(
            "task.scan_starting",
            "Starting opportunity scan",
            level="info",
            task_id=task_id,
            input_data={"specific_source": source_id}
        )
        
        # Get sources to scan
        sources = _get_opportunity_sources()
        
        if not sources:
            log_action_fn(
                "task.scan_no_sources",
                "No enabled opportunity sources found in database",
                level="warn",
                task_id=task_id
            )
            return True, {
                "executed": True,
                "sources_scanned": 0,
                "opportunities_found": 0,
                "message": "No sources configured - add sources to opportunity_sources table",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Filter to specific source if requested
        if source_id:
            sources = [s for s in sources if str(s.get("id")) == str(source_id)]
        
        all_opportunities = []
        sources_scanned = 0
        
        for source in sources:
            opportunities = _scan_source(source, log_action_fn, task_id)
            all_opportunities.extend(opportunities)
            sources_scanned += 1
            
            # Save discovered opportunities
            for opp in opportunities:
                opp_id = _save_opportunity(opp)
                if opp_id:
                    log_action_fn(
                        "task.scan_opportunity_saved",
                        f"Saved opportunity: {opp.get('name')}",
                        level="info",
                        task_id=task_id,
                        output_data={"opportunity_id": opp_id}
                    )
        
        log_action_fn(
            "task.scan_completed",
            f"Scan completed: {sources_scanned} sources, {len(all_opportunities)} opportunities",
            level="info",
            task_id=task_id,
            output_data={
                "sources_scanned": sources_scanned,
                "opportunities_found": len(all_opportunities)
            }
        )
        
        return True, {
            "executed": True,
            "sources_scanned": sources_scanned,
            "sources_available": len(sources),
            "opportunities_found": len(all_opportunities),
            "opportunities": all_opportunities[:10],  # First 10 only
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log_action_fn(
            "task.scan_error",
            f"Scan exception: {str(e)}",
            level="error",
            task_id=task_id,
            error_data={"exception": str(e)}
        )
        return False, {"error": str(e)}
