"""
Self-Heal API Endpoints

REST API for triggering diagnosis and repair workflows.

Endpoints:
    POST /api/self-heal/diagnose - Run system diagnosis
    POST /api/self-heal/repair - Run repair workflow
    POST /api/self-heal/auto-heal - Run diagnosis + repair
    GET /api/self-heal/executions - Get execution history
    GET /api/self-heal/executions/{id} - Get execution details

Part of Milestone 2: Self-Heal Workflows
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.self_heal.playbooks.diagnose_system import DiagnoseSystemPlaybook
from core.self_heal.playbooks.repair_common_issues import RepairCommonIssuesPlaybook
from core.database import execute_sql, fetch_all

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _make_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body)
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create error response."""
    return _make_response(status_code, {"error": message, "success": False})


def _save_execution(
    playbook_name: str,
    execution_type: str,
    result: Dict[str, Any],
    trigger_reason: Optional[str] = None
) -> str:
    """
    Save execution to database.
    
    Returns:
        Execution ID
    """
    try:
        query = """
            INSERT INTO self_heal_executions (
                playbook_name,
                execution_type,
                status,
                trigger_reason,
                steps_completed,
                steps_total,
                results,
                findings,
                actions_taken,
                duration_ms,
                started_at,
                completed_at,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        status = "completed" if result.get("success") else "failed"
        findings = result.get("findings", {})
        actions_taken = result.get("actions_taken", [])
        
        params = (
            playbook_name,
            execution_type,
            status,
            trigger_reason,
            result.get("steps_completed", 0),
            result.get("steps_total", 0),
            json.dumps(result.get("steps", [])),
            json.dumps(findings),
            json.dumps(actions_taken),
            result.get("duration_ms", 0),
            result.get("started_at"),
            result.get("completed_at"),
            "api"
        )
        
        result_rows = fetch_all(query, params)
        return str(result_rows[0]["id"]) if result_rows else None
    except Exception as e:
        logger.exception(f"Error saving execution: {e}")
        return None


def handle_diagnose(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/self-heal/diagnose
    
    Run system diagnosis playbook.
    """
    try:
        trigger_reason = body.get("trigger_reason", "Manual diagnosis via API")
        
        # Execute diagnosis playbook
        playbook = DiagnoseSystemPlaybook()
        result = playbook.execute()
        
        # Save execution
        execution_id = _save_execution(
            playbook_name="diagnose_system",
            execution_type="diagnosis",
            result=result,
            trigger_reason=trigger_reason
        )
        
        return _make_response(200, {
            "success": True,
            "execution_id": execution_id,
            "playbook": "diagnose_system",
            "findings": result.get("findings", {}),
            "steps_completed": result.get("steps_completed", 0),
            "steps_total": result.get("steps_total", 0),
            "duration_ms": result.get("duration_ms", 0),
            "steps": result.get("steps", [])
        })
    except Exception as e:
        logger.exception(f"Error in diagnose: {e}")
        return _error_response(500, f"Diagnosis failed: {str(e)}")


def handle_repair(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/self-heal/repair
    
    Run repair playbook.
    """
    try:
        trigger_reason = body.get("trigger_reason", "Manual repair via API")
        
        # Execute repair playbook
        playbook = RepairCommonIssuesPlaybook()
        result = playbook.execute()
        
        # Save execution
        execution_id = _save_execution(
            playbook_name="repair_common_issues",
            execution_type="repair",
            result=result,
            trigger_reason=trigger_reason
        )
        
        return _make_response(200, {
            "success": True,
            "execution_id": execution_id,
            "playbook": "repair_common_issues",
            "actions_taken": playbook.actions_taken,
            "repairs_attempted": len(playbook.repairs_attempted),
            "steps_completed": result.get("steps_completed", 0),
            "steps_total": result.get("steps_total", 0),
            "duration_ms": result.get("duration_ms", 0),
            "steps": result.get("steps", [])
        })
    except Exception as e:
        logger.exception(f"Error in repair: {e}")
        return _error_response(500, f"Repair failed: {str(e)}")


def handle_auto_heal(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/self-heal/auto-heal
    
    Run diagnosis, then repair if issues found.
    """
    try:
        trigger_reason = body.get("trigger_reason", "Auto-heal via API")
        
        # Step 1: Diagnose
        diagnosis_playbook = DiagnoseSystemPlaybook()
        diagnosis_result = diagnosis_playbook.execute()
        
        diagnosis_id = _save_execution(
            playbook_name="diagnose_system",
            execution_type="diagnosis",
            result=diagnosis_result,
            trigger_reason=trigger_reason
        )
        
        # Check if critical issues found
        findings = diagnosis_result.get("findings", {})
        critical_issues = [
            k for k, v in findings.items() 
            if isinstance(v, dict) and v.get("severity") == "critical"
        ]
        
        warning_issues = [
            k for k, v in findings.items() 
            if isinstance(v, dict) and v.get("severity") == "warning"
        ]
        
        # Step 2: Repair if issues found
        repair_result = None
        repair_id = None
        
        if critical_issues or warning_issues:
            repair_playbook = RepairCommonIssuesPlaybook()
            repair_result = repair_playbook.execute()
            
            repair_id = _save_execution(
                playbook_name="repair_common_issues",
                execution_type="repair",
                result=repair_result,
                trigger_reason=f"Auto-heal triggered by: {', '.join(critical_issues + warning_issues)}"
            )
        
        return _make_response(200, {
            "success": True,
            "diagnosis": {
                "execution_id": diagnosis_id,
                "findings": findings,
                "critical_issues": critical_issues,
                "warning_issues": warning_issues
            },
            "repair": {
                "execution_id": repair_id,
                "executed": repair_result is not None,
                "actions_taken": repair_playbook.actions_taken if repair_result else [],
                "repairs_attempted": len(repair_playbook.repairs_attempted) if repair_result else 0
            } if repair_result else None
        })
    except Exception as e:
        logger.exception(f"Error in auto-heal: {e}")
        return _error_response(500, f"Auto-heal failed: {str(e)}")


def handle_get_executions(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle GET /api/self-heal/executions
    
    Get execution history.
    """
    try:
        limit = int(query_params.get("limit", ["20"])[0])
        execution_type = query_params.get("type", [None])[0]
        
        query = """
            SELECT 
                id,
                playbook_name,
                execution_type,
                status,
                trigger_reason,
                steps_completed,
                steps_total,
                duration_ms,
                started_at,
                completed_at,
                created_by
            FROM self_heal_executions
            WHERE 1=1
        """
        
        params = []
        if execution_type:
            query += " AND execution_type = %s"
            params.append(execution_type)
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        executions = fetch_all(query, tuple(params) if params else None)
        
        return _make_response(200, {
            "success": True,
            "executions": executions,
            "count": len(executions)
        })
    except Exception as e:
        logger.exception(f"Error getting executions: {e}")
        return _error_response(500, f"Failed to get executions: {str(e)}")


def handle_get_execution_detail(execution_id: str) -> Dict[str, Any]:
    """
    Handle GET /api/self-heal/executions/{id}
    
    Get execution details.
    """
    try:
        query = """
            SELECT 
                id,
                playbook_name,
                execution_type,
                status,
                trigger_reason,
                steps_completed,
                steps_total,
                results,
                findings,
                actions_taken,
                verification_result,
                error_message,
                duration_ms,
                started_at,
                completed_at,
                created_by
            FROM self_heal_executions
            WHERE id = %s
        """
        
        executions = fetch_all(query, (execution_id,))
        
        if not executions:
            return _error_response(404, "Execution not found")
        
        execution = executions[0]
        
        return _make_response(200, {
            "success": True,
            "execution": execution
        })
    except Exception as e:
        logger.exception(f"Error getting execution detail: {e}")
        return _error_response(500, f"Failed to get execution: {str(e)}")


__all__ = [
    "handle_diagnose",
    "handle_repair",
    "handle_auto_heal",
    "handle_get_executions",
    "handle_get_execution_detail"
]
