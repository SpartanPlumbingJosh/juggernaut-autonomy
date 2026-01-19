"""
Scan Task Handler
=================

Runs opportunity scanners to find new business opportunities.
Wraps the existing opportunity_scan_handler for consistency.
"""

import json
from typing import Dict, Any, Callable

# Import existing opportunity scanner
try:
    from core.opportunity_scan_handler import handle_opportunity_scan
    SCANNER_AVAILABLE = True
except ImportError:
    SCANNER_AVAILABLE = False


def handle_scan_task(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Execute a scan task to find opportunities.
    
    Payload format:
    {
        "scan_type": "opportunity|competitor|market",  # Default "opportunity"
        "sources": ["all"] or ["source1", "source2"],  # Optional
        "min_confidence": 0.7,                         # Optional, default 0.7
        "create_tasks": true                           # Optional, default true
    }
    
    Args:
        task: Task dict with scan configuration
        execute_sql: Function to execute SQL
        log_action: Function to log actions
        
    Returns:
        Result dict with scan findings
    """
    task_id = task.get("id", "unknown")
    payload = task.get("payload", {})
    
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    
    scan_type = payload.get("scan_type", "opportunity")
    
    log_action(
        "scan.handler.start",
        f"Starting {scan_type} scan",
        "info",
        task_id=task_id,
        input_data={"scan_type": scan_type}
    )
    
    if scan_type == "opportunity":
        return _run_opportunity_scan(task, execute_sql, log_action)
    elif scan_type == "competitor":
        return _run_competitor_scan(task, execute_sql, log_action)
    elif scan_type == "market":
        return _run_market_scan(task, execute_sql, log_action)
    else:
        return {
            "success": False,
            "error": f"Unknown scan_type: {scan_type}",
            "valid_types": ["opportunity", "competitor", "market"]
        }


def _run_opportunity_scan(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Run the opportunity scanner.
    
    Uses the existing handle_opportunity_scan if available.
    """
    task_id = task.get("id", "unknown")
    
    if not SCANNER_AVAILABLE:
        log_action(
            "scan.handler.warning",
            "Opportunity scanner not available, using basic scan",
            "warning",
            task_id=task_id
        )
        return _basic_opportunity_scan(task, execute_sql, log_action)
    
    try:
        # Convert task format for existing handler
        config = task.get("payload", {})
        if isinstance(config, str):
            config = json.loads(config) if config else {}
        
        scan_task = {
            "config": config
        }
        
        result = handle_opportunity_scan(scan_task, execute_sql, log_action)
        
        log_action(
            "scan.handler.complete",
            f"Opportunity scan complete: {result.get('opportunities_found', 0)} found",
            "info",
            task_id=task_id,
            output_data=result
        )
        
        return result
        
    except Exception as e:
        error_msg = str(e)[:500]
        log_action(
            "scan.handler.error",
            f"Opportunity scan failed: {error_msg}",
            "error",
            task_id=task_id
        )
        return {"success": False, "error": error_msg}


def _basic_opportunity_scan(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Basic opportunity scan when full scanner unavailable.
    
    Just queries the opportunity_sources table.
    """
    task_id = task.get("id", "unknown")
    
    try:
        result = execute_sql("""
            SELECT COUNT(*) as source_count 
            FROM opportunity_sources 
            WHERE active = true
        """)
        
        source_count = result.get("rows", [{}])[0].get("source_count", 0)
        
        log_action(
            "scan.handler.basic_scan",
            f"Basic scan: {source_count} active sources",
            "info",
            task_id=task_id
        )
        
        return {
            "success": True,
            "scan_type": "basic",
            "sources_scanned": source_count,
            "opportunities_found": 0,
            "note": "Full scanner unavailable, ran basic check"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)[:500]}


def _run_competitor_scan(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Run a competitor analysis scan.
    
    Placeholder for future implementation.
    """
    task_id = task.get("id", "unknown")
    
    log_action(
        "scan.handler.competitor",
        "Competitor scan not yet implemented",
        "warning",
        task_id=task_id
    )
    
    return {
        "success": True,
        "scan_type": "competitor",
        "note": "Competitor scanning not yet implemented",
        "competitors_found": 0
    }


def _run_market_scan(
    task: Dict[str, Any],
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Run a market trends scan.
    
    Placeholder for future implementation.
    """
    task_id = task.get("id", "unknown")
    
    log_action(
        "scan.handler.market",
        "Market scan not yet implemented",
        "warning",
        task_id=task_id
    )
    
    return {
        "success": True,
        "scan_type": "market",
        "note": "Market trend scanning not yet implemented",
        "trends_found": 0
    }
