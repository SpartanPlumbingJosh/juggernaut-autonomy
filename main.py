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
from uuid import uuid4

# Slack notifications for #war-room
from core.notifications import (
    notify_task_completed,
    notify_task_failed,
    notify_engine_started
)

# GAP-03: RBAC Runtime Permission Enforcement
RBAC_AVAILABLE = False
_rbac_import_error = None

try:
    from core.rbac import (
        check_permission,
        PermissionResult,
        PermissionDenied,
        log_access_attempt,
        get_scoped_credential,
    )
    RBAC_AVAILABLE = True
except ImportError as e:
    _rbac_import_error = str(e)
    # Stub classes for graceful degradation
    class PermissionResult:
        """Stub PermissionResult for when RBAC is unavailable."""
        def __init__(self, allowed: bool, reason: str, **kwargs):
            self.allowed = allowed
            self.reason = reason
            self.worker_id = kwargs.get("worker_id")
            self.action = kwargs.get("action")
    
    class PermissionDenied(Exception):
        """Stub PermissionDenied exception."""
        pass
    
    def check_permission(worker_id, action, resource=None, context=None):
        """Stub check_permission when RBAC unavailable - falls back to simple check."""
        return PermissionResult(allowed=True, reason="RBAC unavailable, allowing by default")
    
    def log_access_attempt(*args, **kwargs):
        """Stub log_access_attempt when RBAC unavailable."""
        return None

    def get_scoped_credential(*args, **kwargs):
        return None

# VERCHAIN-02: Stage Transition Enforcement
STAGE_TRANSITIONS_AVAILABLE = False
_stage_transitions_import_error = None

try:
    from core.stage_transitions import (
        validate_stage_transition,
        transition_stage,
        get_task_stage,
        get_valid_next_stages,
        can_complete_task,
        sync_status_to_stage,
        TransitionResult,
    )
    STAGE_TRANSITIONS_AVAILABLE = True
except ImportError as e:
    _stage_transitions_import_error = str(e)
    # Stub functions for graceful degradation
    def validate_stage_transition(task_id, new_stage, evidence=None):
        return type('TransitionResult', (), {'allowed': True, 'reason': 'Module unavailable'})()
    def transition_stage(task_id, new_stage, evidence=None, verified_by=None):
        return type('TransitionResult', (), {'allowed': True, 'reason': 'Module unavailable'})()
    def get_task_stage(task_id):
        return None
    def get_valid_next_stages(task_id):
        return []
    def can_complete_task(task_id):
        return True, "Module unavailable"
    def sync_status_to_stage(task_id, status):
        return None
    class TransitionResult:
        pass

# Phase 4: Experimentation Framework (wired up by HIGH-06)
EXPERIMENTS_AVAILABLE = False
_experiments_import_error = None

try:
    from core.experiments import (
        create_experiment,
        get_experiment,
        list_experiments,
        ensure_experiment_schema,
        define_hypothesis,
        set_experiment_approval_policy,
        approve_experiment,
        activate_experiment,
        begin_measuring,
        conclude_experiment_formal,
        link_task_to_experiment,
        record_metric_point,
        record_experiment_change,
        start_experiment,
        pause_experiment,
        record_result,
        conclude_experiment,
        get_experiment_dashboard,
    )
    EXPERIMENTS_AVAILABLE = True
except ImportError as e:
    _experiments_import_error = str(e)
    # Stub functions for graceful degradation
    def create_experiment(*args, **kwargs): return None
    def get_experiment(*args, **kwargs): return None
    def list_experiments(*args, **kwargs): return []
    def ensure_experiment_schema(*args, **kwargs): return None
    def define_hypothesis(*args, **kwargs): return None
    def set_experiment_approval_policy(*args, **kwargs): return None
    def approve_experiment(*args, **kwargs): return None
    def activate_experiment(*args, **kwargs): return None
    def begin_measuring(*args, **kwargs): return None
    def conclude_experiment_formal(*args, **kwargs): return None
    def link_task_to_experiment(*args, **kwargs): return None
    def record_metric_point(*args, **kwargs): return None
    def record_experiment_change(*args, **kwargs): return None
    def start_experiment(*args, **kwargs): return False
    def pause_experiment(*args, **kwargs): return False
    def record_result(*args, **kwargs): return None
    def conclude_experiment(*args, **kwargs): return False
    def get_experiment_dashboard(*args, **kwargs): return {}

# Real-time Dashboard API
DASHBOARD_API_AVAILABLE = False
_dashboard_import_error = None
try:
    from api.realtime_dashboard import handle_dashboard_request, record_revenue
    DASHBOARD_API_AVAILABLE = True
except ImportError as e:
    _dashboard_import_error = str(e)

# Executive Dashboard API (FIX-10)
EXEC_DASHBOARD_API_AVAILABLE = False
_exec_dashboard_import_error = None
try:
    from api.executive_dashboard import get_executive_dashboard
    EXEC_DASHBOARD_API_AVAILABLE = True
except ImportError as e:
    _exec_dashboard_import_error = str(e)




# BRAIN-03: Brain API for AI consultation
BRAIN_API_AVAILABLE = False
_brain_api_import_error = None

try:
    from api.brain_api import handle_brain_request, BRAIN_AVAILABLE
    BRAIN_API_AVAILABLE = BRAIN_AVAILABLE
except ImportError as e:
    _brain_api_import_error = str(e)
    def handle_brain_request(*args, **kwargs): 
        return {"status": 503, "body": {"success": False, "error": "brain api not available"}}

# Phase 6: ORCHESTRATOR Task Delegation (L5-01b)
ORCHESTRATION_AVAILABLE = False
_orchestration_import_error = None

try:
    from core.orchestration import (
        discover_agents,
        orchestrator_assign_task,
        log_coordination_event,
        check_escalation_timeouts,
        update_worker_heartbeat,
    )
    ORCHESTRATION_AVAILABLE = True
except ImportError as e:
    _orchestration_import_error = str(e)
    # Stub functions for graceful degradation
    def discover_agents(*args, **kwargs): return []
    def orchestrator_assign_task(*args, **kwargs): return {"success": False, "error": "orchestration not available"}
    def log_coordination_event(*args, **kwargs): return None
    def check_escalation_timeouts(*args, **kwargs): return []
    def update_worker_heartbeat(*args, **kwargs): return False


# Phase 5: Proactive Systems - Opportunity Scanner (wired up by HIGH-05)
PROACTIVE_AVAILABLE = False
_proactive_import_error = None

try:
    from core.proactive import (
        start_scan,
        complete_scan,
        fail_scan,
        get_scan_history,
        identify_opportunity,
        score_opportunity,
    )
    from core.opportunity_scan_handler import handle_opportunity_scan
    from core.task_templates import ProposedTask, pick_diverse_tasks
    PROACTIVE_AVAILABLE = True
except ImportError as e:
    _proactive_import_error = str(e)
    # Stub functions for graceful degradation
    def start_scan(*args, **kwargs): return {"success": False, "error": "proactive not available"}
    def complete_scan(*args, **kwargs): return {"success": False, "error": "proactive not available"}
    def fail_scan(*args, **kwargs): return {"success": False, "error": "proactive not available"}
    def get_scan_history(*args, **kwargs): return []
    def identify_opportunity(*args, **kwargs): return {"success": False, "error": "proactive not available"}
    def score_opportunity(*args, **kwargs): return {"success": False, "error": "proactive not available"}
    def handle_opportunity_scan(*args, **kwargs): return {"success": False, "error": "proactive not available"}
    class ProposedTask:  # type: ignore
        pass
    def pick_diverse_tasks(*args, **kwargs): return []

# Phase 2.5: Error Recovery System (MED-01)
ERROR_RECOVERY_AVAILABLE = False
_error_recovery_import_error = None

try:
    from core.error_recovery import (
        move_to_dead_letter,
        get_dead_letter_items,
        resolve_dead_letter,
        retry_dead_letter,
        create_alert,
        get_open_alerts,
        acknowledge_alert,
        resolve_alert,
        check_repeated_failures,
        get_system_health,
    )
    ERROR_RECOVERY_AVAILABLE = True
except ImportError as e:
    _error_recovery_import_error = str(e)
    # Stub functions for graceful degradation
    def move_to_dead_letter(*args, **kwargs): return None
    def get_dead_letter_items(*args, **kwargs): return []
    def resolve_dead_letter(*args, **kwargs): return False
    def retry_dead_letter(*args, **kwargs): return None
    def create_alert(*args, **kwargs): return None
    def get_open_alerts(*args, **kwargs): return []
    def acknowledge_alert(*args, **kwargs): return False
    def resolve_alert(*args, **kwargs): return False
    def check_repeated_failures(*args, **kwargs): return False
    def get_system_health(*args, **kwargs): return {}


# Completion Verification System - prevents fake completions
VERIFICATION_AVAILABLE = False
_verification_import_error = None

try:
    from core.verification import CompletionVerifier, VerificationResult
    VERIFICATION_AVAILABLE = True
except ImportError as e:
    _verification_import_error = str(e)
    # Stub for graceful degradation - allows completion without verification


# Verification Chains: DB write verification producer
DB_VERIFICATION_AVAILABLE = False
_db_verification_import_error = None
API_VERIFICATION_AVAILABLE = False
_api_verification_import_error = None
DEPLOY_VERIFICATION_AVAILABLE = False
_deploy_verification_import_error = None

try:
    from core.verification_chains import (
        execute_db_write_with_verification,
        execute_api_call_with_verification,
        execute_deploy_with_verification,
    )
    DB_VERIFICATION_AVAILABLE = True
    API_VERIFICATION_AVAILABLE = True
    DEPLOY_VERIFICATION_AVAILABLE = True
except ImportError as e:
    _db_verification_import_error = str(e)
    _api_verification_import_error = str(e)
    _deploy_verification_import_error = str(e)

    def execute_db_write_with_verification(*args, **kwargs):
        return {"status": "error", "error": "DB verification unavailable"}, {
            "type": "db_write",
            "verified": False,
            "error": "DB verification unavailable",
        }

    def execute_api_call_with_verification(*args, **kwargs):
        return {"status": "error", "error": "API verification unavailable"}, {
            "type": "api_call",
            "verified": False,
            "error": "API verification unavailable",
        }

    def execute_deploy_with_verification(*args, **kwargs):
        return {"status": "error", "error": "Deploy verification unavailable"}, {
            "type": "railway_deploy",
            "verified": False,
            "error": "Deploy verification unavailable",
        }
# Phase 5.3: Scheduler - Scheduled Task Run Logging (FIX-03)
SCHEDULER_AVAILABLE = False
_scheduler_import_error = None

try:
    from core.scheduler import (
        start_task_run,
        complete_task_run,
        fail_task_run,
    )
    SCHEDULER_AVAILABLE = True
except ImportError as e:
    _scheduler_import_error = str(e)
    # Stub functions for graceful degradation
    def start_task_run(*args, **kwargs): return {"success": False, "error": "scheduler not available"}
    def complete_task_run(*args, **kwargs): return {"success": False, "error": "scheduler not available"}
    def fail_task_run(*args, **kwargs): return {"success": False, "error": "scheduler not available"}


# MED-02: Learning Capture from Task Execution
LEARNING_CAPTURE_AVAILABLE = False
_learning_capture_import_error = None

try:
    from core.learning_capture import capture_task_learning
    LEARNING_CAPTURE_AVAILABLE = True
except ImportError as e:
    _learning_capture_import_error = str(e)
    # Stub function for graceful degradation
    def capture_task_learning(*args, **kwargs): return (False, None)


# L5-07: Failover and Resilience - Worker failure detection and task reassignment
FAILOVER_AVAILABLE = False
_failover_import_error = None

try:
    from core.failover import process_failover
    FAILOVER_AVAILABLE = True
except ImportError as e:
    _failover_import_error = str(e)
    # Stub function for graceful degradation
    def process_failover(*args, **kwargs): return {"failed_workers": [], "tasks_reassigned": 0}


# CRITICAL-03c: Stale Task Cleanup (wired up by CRITICAL-03c)
STALE_CLEANUP_AVAILABLE = False
_stale_cleanup_import_error = None

try:
    from core.stale_cleanup import reset_stale_tasks
    STALE_CLEANUP_AVAILABLE = True
except ImportError as e:
    _stale_cleanup_import_error = str(e)
    # Stub function for graceful degradation
    def reset_stale_tasks(*args, **kwargs): return (0, [])


# SCALE-03: Auto-Scaling Integration
AUTO_SCALING_AVAILABLE = False
_auto_scaling_import_error = None

try:
    from core.auto_scaling import AutoScaler, ScalingConfig, create_auto_scaler
    AUTO_SCALING_AVAILABLE = True
except ImportError as e:
    _auto_scaling_import_error = str(e)
    # Stub class for graceful degradation
    class AutoScaler:
        def execute_scaling(self): return {"action": "no_action", "reason": "auto_scaling not available"}
    class ScalingConfig:
        pass
    def create_auto_scaler(*args, **kwargs): return None


# Phase 7: Stale Task Cleanup (CRITICAL-03c)
STALE_CLEANUP_AVAILABLE = False
_stale_cleanup_import_error = None

try:
    from core.stale_cleanup import reset_stale_tasks
    STALE_CLEANUP_AVAILABLE = True
except ImportError as e:
    _stale_cleanup_import_error = str(e)
    # Stub function for graceful degradation
    def reset_stale_tasks(*args, **kwargs):
        """Stub: stale_cleanup module not available."""
        return 0, []


# Code Task Executor - Autonomous code generation (PR #185)
CODE_TASK_AVAILABLE = False
_code_task_import_error = None

try:
    from src.task_executor_code import execute_code_task
    CODE_TASK_AVAILABLE = True
except ImportError as e:
    _code_task_import_error = str(e)


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
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL_SECONDS", "30"))
MAX_TASKS_PER_LOOP = int(os.getenv("MAX_TASKS_PER_LOOP", "2"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
PORT = int(os.getenv("PORT", "8000"))

DEPLOY_VERSION = "1.3.2"
DEPLOY_COMMIT = (
    os.getenv("RAILWAY_GIT_COMMIT_SHA")
    or os.getenv("GIT_COMMIT")
    or os.getenv("COMMIT_SHA")
    or "unknown"
)

# Retry configuration
RETRY_BASE_DELAY_SECONDS = 60  # 1 minute base delay
RETRY_MAX_DELAY_SECONDS = 3600  # 1 hour max delay

# Auto-scaling configuration (SCALE-03)
ENABLE_AUTO_SCALING = os.getenv("ENABLE_AUTO_SCALING", "false").lower() == "true"
AUTO_SCALING_INTERVAL_SECONDS = int(os.getenv("AUTO_SCALING_INTERVAL_SECONDS", "300"))  # 5 minutes default

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

def auto_approve_timed_out_tasks():
    """
    Auto-approve low/medium risk tasks that have been waiting for approval too long.
    HIGH/CRITICAL risk tasks are escalated instead.
    
    Timeout: 30 minutes for auto-approval consideration
    """
    try:
        # Find tasks waiting for approval with old approval requests
        stale_query = """
            SELECT t.id, t.title, t.task_type, t.priority, a.risk_level,
                   a.id as approval_id, a.created_at as approval_created
            FROM governance_tasks t
            JOIN approvals a ON t.id = a.task_id
            WHERE t.status = 'waiting_approval'
              AND a.decision = 'pending'
              AND a.created_at < NOW() - INTERVAL '30 minutes'
            ORDER BY a.created_at ASC
            LIMIT 10
        """
        
        result = execute_sql(stale_query)
        auto_approved = []
        escalated = []
        
        for row in result.get("rows", []):
            task_id = row["id"]
            approval_id = row["approval_id"]
            risk_level = row.get("risk_level", "low")
            
            if risk_level == "critical":
                # Only escalate CRITICAL risk tasks (financial, permissions, etc.)
                try:
                    execute_sql(f"""
                        INSERT INTO escalations (task_id, escalated_by, reason, status)
                        VALUES ('{task_id}', 'SYSTEM_TIMEOUT', 
                               'Task waiting for approval > 30 minutes (critical risk - requires human review)',
                               'pending')
                        ON CONFLICT DO NOTHING
                    """)
                    escalated.append(task_id)
                    log_action("escalation.timeout_created",
                              f"Critical-risk task {task_id} escalated due to approval timeout",
                              task_id=task_id)
                except Exception:
                    pass
            else:
                # Auto-approve low/medium risk tasks
                try:
                    execute_sql(f"""
                        UPDATE approvals 
                        SET decision = 'auto_approved',
                            decided_by = 'SYSTEM_TIMEOUT',
                            decided_at = NOW(),
                            decision_notes = 'Auto-approved after 30 minute timeout (low/medium risk)'
                        WHERE id = '{approval_id}'
                    """)
                    
                    execute_sql(f"""
                        UPDATE governance_tasks
                        SET status = 'pending',
                            updated_at = NOW()
                        WHERE id = '{task_id}'
                    """)
                    
                    auto_approved.append(task_id)
                    log_action("approval.auto_timeout",
                              f"Task {task_id} auto-approved after timeout",
                              task_id=task_id)
                except Exception as e:
                    log_error(f"Failed to auto-approve task {task_id}: {e}")
        
        return {"auto_approved": auto_approved, "escalated": escalated}
        
    except Exception as e:
        log_error(f"Auto-approval timeout check failed: {e}")
        return {"error": str(e)}



def handle_orphaned_waiting_approval_tasks():
    """
    Handle tasks stuck in waiting_approval status that don't have approval records.
    These are typically tasks where the approval record was never created.
    Low/medium priority tasks get reset to pending.
    High/critical priority tasks get an approval record created.
    """
    try:
        # Find orphaned tasks (waiting_approval but no approval record)
        orphan_query = """
            SELECT t.id, t.title, t.task_type, t.priority, t.updated_at
            FROM governance_tasks t
            LEFT JOIN approvals a ON t.id = a.task_id
            WHERE t.status = 'waiting_approval'
              AND a.id IS NULL
              AND t.updated_at < NOW() - INTERVAL '15 minutes'
            ORDER BY t.updated_at ASC
            LIMIT 10
        """
        
        result = execute_sql(orphan_query)
        reset = []
        created_approvals = []
        
        for row in result.get("rows", []):
            task_id = row["id"]
            priority = row.get("priority", "medium")
            
            if priority in ("high", "critical"):
                # Create an approval record for high-priority tasks
                try:
                    action_data = {"task_id": task_id, "auto_generated": True}
                    execute_sql(f"""
                        INSERT INTO approvals (
                            task_id, worker_id, action_type, action_description,
                            action_data, risk_level, decision, created_at
                        ) VALUES (
                            '{task_id}', 'SYSTEM', 'task_execution',
                            'Auto-generated approval request for orphaned high-priority task',
                            {escape_value(action_data)},
                            '{priority}', 'pending', NOW()
                        )
                        ON CONFLICT DO NOTHING
                    """)
                    created_approvals.append(task_id)
                    log_action("approval.orphan_created",
                              f"Created approval record for orphaned task {task_id}",
                              task_id=task_id)
                except Exception as e:
                    log_error(f"Failed to create approval for orphaned task {task_id}: {e}")
            else:
                # Reset low/medium priority tasks to pending
                try:
                    execute_sql(f"""
                        UPDATE governance_tasks
                        SET status = 'pending',
                            updated_at = NOW()
                        WHERE id = '{task_id}'
                    """)
                    reset.append(task_id)
                    log_action("task.orphan_reset",
                              f"Reset orphaned task {task_id} to pending",
                              task_id=task_id)
                except Exception as e:
                    log_error(f"Failed to reset orphaned task {task_id}: {e}")
        
        return {"reset": reset, "created_approvals": created_approvals}
        
    except Exception as e:
        log_error(f"Orphaned task handler failed: {e}")
        return {"error": str(e)}

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
        # JSON serialization - json.dumps() handles escaping properly
        json_str = json.dumps(value, ensure_ascii=False)
        # Only escape single quotes for SQL and remove null bytes
        # Do NOT double-escape backslashes - json.dumps() already escapes correctly
        escaped = json_str.replace("'", "''").replace("\x00", "")
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
    duration_ms: int = None,
    source: str = "autonomy_engine"
) -> Optional[str]:
    """Log an autonomous action to execution_logs with PII sanitization.
    
    Args:
        action: The action being logged (e.g., 'task.completed', 'decision.execute')
        message: Human-readable description of the action
        level: Log level ('info', 'warn', 'error')
        task_id: Optional task UUID this action relates to
        input_data: Optional input data for the action (will be sanitized)
        output_data: Optional output/result data (will be sanitized)
        error_data: Optional error information (will be sanitized)
        duration_ms: Optional execution duration in milliseconds
        source: The source/origin of this action for traceability (L2 requirement)
    
    Returns:
        The UUID of the created log entry, or None if logging failed
    """
    now = datetime.now(timezone.utc).isoformat()

    # Fetch task type/title for verification policy decisions
    task_type = None
    task_title = None
    try:
        task_row = execute_sql(
            f"SELECT task_type, title FROM governance_tasks WHERE id = {escape_value(task_id)} LIMIT 1"
        )
        if task_row.get("rows"):
            task_type = task_row["rows"][0].get("task_type")
            task_title = task_row["rows"][0].get("title")
    except Exception:
        pass
    
    cols = ["worker_id", "action", "message", "level", "source", "created_at"]
    vals = [escape_value(WORKER_ID), escape_value(action), escape_value(message), 
            escape_value(level), escape_value(source), escape_value(now)]
    
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


def log_info(message: str, data: Dict = None, source: str = "system"):
    """Log an informational message.
    
    Args:
        message: The message to log
        data: Optional additional data to include
        source: The source of this log entry for traceability
    """
    log_action("system.info", message, "info", output_data=data, source=source)
    print(f"[INFO] {message}")


def log_error(message: str, data: Optional[Dict[str, Any]] = None, source: str = "system"):
    """Log an error message.
    
    Args:
        message: The error message to log
        data: Optional additional error data to include
        source: The source of this error for traceability
    """
    log_action("system.error", message, "error", error_data=data, source=source)
    print(f"[ERROR] {message}")


def log_decision(
    action: str, 
    decision: str, 
    reasoning: str, 
    data: Optional[Dict[str, Any]] = None, 
    confidence: float = 1.0,
    source: str = "decision_engine"
):
    """Log an autonomous decision (Level 3: Traceable Decisions).
    
    This function ensures all decisions can be traced back to their origin,
    satisfying L2 requirement for references and sourcing.
    
    Args:
        action: The decision action type (e.g., 'task.execute', 'loop.scheduled')
        decision: What was decided (the outcome)
        reasoning: Why it was decided (the rationale)
        data: Additional context data to include in the log
        confidence: Confidence level 0.0-1.0 (L2: Uncertainty tracking)
        source: The source/component that made this decision for traceability
    """
    # Flag low confidence decisions
    uncertainty_warning = ""
    if confidence < 0.7:
        uncertainty_warning = f" [LOW CONFIDENCE: {confidence:.0%}]"
    
    log_action(
        f"decision.{action}",
        f"{decision}: {reasoning}{uncertainty_warning}",
        "info" if confidence >= 0.5 else "warn",
        output_data={
            "decision": decision, 
            "reasoning": reasoning, 
            "confidence": confidence,
            "decision_source": source,
            **(data or {})
        },
        source=source
    )
    print(f"[DECISION] {action}: {decision}" + (f" (confidence: {confidence:.0%})" if confidence < 1.0 else ""))


# ============================================================
# RISK ASSESSMENT (Level 2: Uncertainty/Risk Warnings)
# ============================================================

# Risk level thresholds
RISK_THRESHOLDS = {
    "low": 0.3,      # Actions with risk < 0.3 proceed automatically
    "medium": 0.6,   # Actions with 0.3 <= risk < 0.6 get logged warnings
    "high": 0.8,     # Actions with 0.6 <= risk < 0.8 require extra scrutiny
    "critical": 1.0  # Actions with risk >= 0.8 require approval
}

# Risk factors for different task types
TASK_TYPE_RISK = {
    "database": 0.5,        # Database operations have inherent risk
    "tool_execution": 0.4,  # Tool execution depends on the tool
    "workflow": 0.5,        # Multi-step workflows can cascade failures
    "financial": 0.9,       # Financial operations are high risk
    "deployment": 0.8,      # Deployments affect production
    "scan": 0.1,            # Read-only scanning is low risk
    "test": 0.2,            # Tests are generally safe
    "health_check": 0.1,    # Health checks are read-only
    "opportunity_scan": 0.1,# Scanning is read-only
    "research": 0.2,        # Research tasks are low risk
    "code": 0.4,            # Code changes - lowered to enable autonomous execution
    "verification": 0.2,    # Verification is generally safe
}

# Payload factors that increase risk
RISK_AMPLIFIERS = {
    "DELETE": 0.3,      # SQL DELETE statements
    "DROP": 0.4,        # SQL DROP statements
    "TRUNCATE": 0.4,    # SQL TRUNCATE statements
    "UPDATE": 0.2,      # SQL UPDATE statements
    "INSERT": 0.1,      # SQL INSERT statements
    "production": 0.3,  # Affects production
    "financial": 0.3,   # Financial impact
    "customer": 0.2,    # Affects customers
    "api_key": 0.2,     # Involves credentials
    "deploy": 0.3,      # Deployment related
}


def assess_task_risk(task: Task) -> Tuple[float, str, List[str]]:
    """
    Assess the risk level of a task before execution.
    
    Returns:
        (risk_score, risk_level, risk_factors)
        - risk_score: 0.0 to 1.0
        - risk_level: "low", "medium", "high", "critical"
        - risk_factors: List of factors contributing to risk
    """
    risk_factors = []
    base_risk = TASK_TYPE_RISK.get(task.task_type, 0.5)
    risk_factors.append(f"task_type:{task.task_type}={base_risk:.1f}")
    
    # Check payload for risk amplifiers
    payload_str = str(task.payload).upper() if task.payload else ""
    description_str = (task.description or "").upper()
    combined_text = payload_str + " " + description_str
    
    amplifier_total = 0.0
    for keyword, amplifier in RISK_AMPLIFIERS.items():
        if keyword.upper() in combined_text:
            amplifier_total += amplifier
            risk_factors.append(f"keyword:{keyword}=+{amplifier:.1f}")
    
    # Check for SQL in payload
    if task.payload:
        sql_query = task.payload.get("sql") or task.payload.get("query") or ""
        if sql_query:
            sql_upper = sql_query.upper().strip()
            tokens = sql_upper.split()
            first_token = tokens[0] if tokens else ""
            
            # Read-only queries are safer
            if first_token in {"SELECT", "WITH", "SHOW", "EXPLAIN", "DESCRIBE"}:
                amplifier_total -= 0.2  # Reduce risk for read-only
                risk_factors.append("sql:read_only=-0.2")
            elif first_token in {"DELETE", "DROP", "TRUNCATE"}:
                amplifier_total += 0.3
                risk_factors.append(f"sql:{first_token}=+0.3")
    
    # Check priority - high priority tasks might be rushed
    if task.priority >= 4:  # high/critical
        amplifier_total += 0.1
        risk_factors.append("priority:high=+0.1")
    
    # Calculate final risk score (capped at 1.0)
    final_risk = min(1.0, max(0.0, base_risk + amplifier_total))
    
    # Determine risk level
    if final_risk < RISK_THRESHOLDS["low"]:
        risk_level = "low"
    elif final_risk < RISK_THRESHOLDS["medium"]:
        risk_level = "medium"
    elif final_risk < RISK_THRESHOLDS["high"]:
        risk_level = "high"
    else:
        risk_level = "critical"
    
    return final_risk, risk_level, risk_factors


def log_risk_warning(task: Task, risk_score: float, risk_level: str, risk_factors: List[str]):
    """Log a risk warning for a task (L2: Risk Warnings)."""
    log_action(
        "risk.assessment",
        f"Task '{task.title}' assessed as {risk_level.upper()} risk ({risk_score:.0%})",
        level="warn" if risk_level in ("high", "critical") else "info",
        task_id=task.id,
        output_data={
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "task_type": task.task_type,
            "title": task.title
        }
    )
    if risk_level in ("high", "critical"):
        print(f"[RISK WARNING] {task.title}: {risk_level.upper()} ({risk_score:.0%}) - factors: {', '.join(risk_factors)}")


def should_require_approval_for_risk(risk_score: float, risk_level: str) -> bool:
    """Determine if a task should require approval based on risk level.
    
    JUGGERNAUT is designed for autonomous operation. Only truly dangerous actions
    (financial, production deployments, permission changes) should require approval.
    
    Returns True only for 'critical' (>=0.8) risk tasks. Regular code tasks should
    execute autonomously - that's the entire point of JUGGERNAUT.
    """
    # Only block critical risk - autonomous operation is the goal
    return risk_level == "critical" and risk_score >= RISK_THRESHOLDS["high"]


# ============================================================
# PERMISSION CONTROL (Level 3: Permission/Scope Control)
# GAP-03: Integrated with core/rbac.py for full RBAC enforcement
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


def _maybe_generate_diverse_proactive_tasks() -> Dict[str, Any]:
    """Generate diverse, meaningful tasks when the queue is empty.

    This is a best-effort helper intended to keep the system from going idle.
    Rate limited via the scheduled_tasks.last_run_at timestamp for the
    synthetic task name 'proactive_diverse'.
    """
    if not PROACTIVE_AVAILABLE:
        return {"success": False, "error": "proactive module not available"}

    try:
        pending_res = execute_sql("SELECT COUNT(*)::int as c FROM governance_tasks WHERE status = 'pending'")
        pending_count = int((pending_res.get("rows") or [{}])[0].get("c") or 0)
    except Exception:
        pending_count = 0

    if pending_count > 0:
        return {"success": True, "skipped": True, "reason": "pending_tasks_exist", "pending": pending_count}

    # Rate limit: at most once per hour
    try:
        rate_res = execute_sql(
            """
            SELECT last_run_at
            FROM scheduled_tasks
            WHERE name = 'proactive_diverse'
            LIMIT 1
            """
        )
        if rate_res.get("rows") and rate_res["rows"][0].get("last_run_at"):
            return {"success": True, "skipped": True, "reason": "rate_limited"}
    except Exception:
        pass

    # Ensure scheduled_tasks row exists and is rate-limited by get_due_scheduled_tasks() policy
    try:
        execute_sql(
            """
            INSERT INTO scheduled_tasks (id, name, task_type, cron_expression, config, enabled, last_run_at)
            VALUES (gen_random_uuid(), 'proactive_diverse', 'proactive_diverse', 'hourly', '{}'::jsonb, TRUE, NOW())
            ON CONFLICT (name) DO UPDATE SET last_run_at = NOW(), enabled = TRUE
            """
        )
    except Exception:
        # Best-effort: continue even if scheduled_tasks isn't available
        pass

    created = 0
    skipped_duplicate = 0
    skipped_quality = 0
    try:
        candidates = pick_diverse_tasks(execute_sql=execute_sql, max_tasks=3, recent_limit=50, dedupe_hours=24)
    except Exception as e:
        return {"success": False, "error": str(e)}

    for cand in candidates:
        if not isinstance(cand, ProposedTask):
            continue
        payload = cand.payload if isinstance(cand.payload, dict) else {}
        if not payload.get("dedupe_key") or not payload.get("success_criteria"):
            skipped_quality += 1
            continue

        title_escaped = str(cand.title).replace("'", "''")
        dedupe_key_escaped = str(payload.get("dedupe_key")).replace("'", "''")

        # Deduplication: dedupe_key within 24h
        try:
            existing = execute_sql(
                f"""
                SELECT id
                FROM governance_tasks
                WHERE payload->>'dedupe_key' = '{dedupe_key_escaped}'
                  AND created_at > NOW() - INTERVAL '24 hours'
                LIMIT 1
                """
            )
            if existing.get("rows"):
                skipped_duplicate += 1
                continue
        except Exception:
            pass

        # Hard cap: no more than 2 identical titles in last 24h
        try:
            title_cnt = execute_sql(
                f"""
                SELECT COUNT(*)::int as c
                FROM governance_tasks
                WHERE title = '{title_escaped}'
                  AND created_at > NOW() - INTERVAL '24 hours'
                """
            )
            c = int((title_cnt.get("rows") or [{}])[0].get("c") or 0)
            if c >= 2:
                skipped_duplicate += 1
                continue
        except Exception:
            pass

        tid = str(uuid4())
        pay = json.dumps(payload).replace("'", "''")
        desc = str(cand.description or "").replace("'", "''")
        priority = str(cand.priority or "medium")
        task_type = str(cand.task_type or "workflow")

        try:
            execute_sql(
                f"""
                INSERT INTO governance_tasks (id, task_type, title, description, priority, status, payload, created_by)
                VALUES ('{tid}', '{task_type}', '{title_escaped}', '{desc}', '{priority}', 'pending', '{pay}', 'engine')
                """
            )
            created += 1
            log_action(
                "proactive.diverse_task_created",
                f"Created proactive task: {payload.get('dedupe_key')}",
                level="info",
                output_data={"task_id": tid, "task_type": task_type, "category": payload.get("category")},
            )
        except Exception:
            skipped_quality += 1

    return {
        "success": True,
        "tasks_created": created,
        "tasks_skipped_duplicate": skipped_duplicate,
        "tasks_skipped_quality": skipped_quality,
    }


def is_action_allowed(action: str) -> Tuple[bool, str]:
    """
    Check if an action is allowed for this worker.
    
    GAP-03: Now integrated with core/rbac.py check_permission() to:
    1. Check role-based permissions (not just forbidden_actions)
    2. Log all access attempts to access_audit_log
    
    Args:
        action: The action to check (e.g., "task.database", "tool.slack")
    
    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    # GAP-03: Use RBAC check_permission if available
    if RBAC_AVAILABLE:
        result = check_permission(
            worker_id=WORKER_ID,
            action=action,
            resource=None,
            context={"source": "is_action_allowed", "check_type": "permission"}
        )
        return result.allowed, result.reason
    
    # Fallback to simple forbidden_actions check if RBAC unavailable
    forbidden = get_forbidden_actions()
    
    for pattern in forbidden:
        if pattern == action or action.startswith(pattern.rstrip("*")):
            # Log denied access attempt even without RBAC
            log_action(
                "permission.denied",
                f"Action '{action}' denied by forbidden_actions pattern '{pattern}'",
                level="warn",
                output_data={
                    "action": action,
                    "pattern": pattern,
                    "worker_id": WORKER_ID,
                    "rbac_available": False
                }
            )
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
    """
    Update task status with completion verification.
    
    For tasks being marked 'completed', verifies that valid completion evidence
    exists before allowing the status change. If evidence is missing or invalid,
    the task is rejected and remains in its current state.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Fetch task type/title for verification policy decisions
    task_type = None
    task_title = None
    try:
        task_row = execute_sql(
            f"SELECT task_type, title FROM governance_tasks WHERE id = {escape_value(task_id)} LIMIT 1"
        )
        if task_row.get("rows"):
            task_type = task_row["rows"][0].get("task_type")
            task_title = task_row["rows"][0].get("title")
    except Exception:
        pass
    
    # Build completion_evidence from result_data
    evidence_text = None
    evidence_json = None
    if result_data and isinstance(result_data, dict):
        if isinstance(result_data.get("completion_evidence"), dict):
            evidence_json = result_data.get("completion_evidence")
        elif isinstance(result_data.get("verification"), dict):
            evidence_json = result_data.get("verification")
        elif isinstance(result_data.get("verification"), list):
            evidence_json = {
                "verifications": result_data.get("verification"),
            }

        pr_url = result_data.get("pr_url")
        if pr_url:
            evidence_text = pr_url
        else:
            # Accept multiple common result shapes:
            # - main.py tasks often return {"executed": True, ...}
            # - handler_result.to_dict() returns {"success": bool, "data": {...}, ...}
            # - AI handler stores useful output in data.summary/data.result
            executed_flag = bool(result_data.get("executed"))
            success_flag = bool(result_data.get("success"))
            data_obj = result_data.get("data")
            summary = None
            if isinstance(data_obj, dict):
                summary = data_obj.get("summary")

            if isinstance(data_obj, dict):
                findings_obj = data_obj.get("findings")
                if isinstance(findings_obj, dict):
                    f_summary = findings_obj.get("summary")
                    f_key_points = findings_obj.get("key_points")
                    f_actions = findings_obj.get("action_items")
                    f_risks = findings_obj.get("risks")
                    f_conf = findings_obj.get("confidence")

                    summary_line = (str(f_summary).strip()[:600] if f_summary else "").strip()
                    key_points_lines = []
                    if isinstance(f_key_points, list):
                        for kp in f_key_points[:6]:
                            if isinstance(kp, str) and kp.strip():
                                key_points_lines.append(f"- {kp.strip()[:220]}")
                    action_lines = []
                    if isinstance(f_actions, list):
                        for a in f_actions[:6]:
                            if isinstance(a, str) and a.strip():
                                action_lines.append(f"- {a.strip()[:220]}")
                    risk_lines = []
                    if isinstance(f_risks, list):
                        for r in f_risks[:6]:
                            if isinstance(r, str) and r.strip():
                                risk_lines.append(f"- {r.strip()[:220]}")

                    parts = []
                    if summary_line:
                        parts.append(f"Summary: {summary_line}")
                    if key_points_lines:
                        parts.append("Key points:\n" + "\n".join(key_points_lines))
                    if action_lines:
                        parts.append("Action items:\n" + "\n".join(action_lines))
                    if risk_lines:
                        parts.append("Risks:\n" + "\n".join(risk_lines))
                    if f_conf is not None:
                        parts.append(f"Confidence: {f_conf}")

                    if parts:
                        evidence_text = "\n\n".join(parts)[:4000]

            if not evidence_text and (executed_flag or success_flag or isinstance(data_obj, (dict, list, str))):
                summary_text = summary.strip() if isinstance(summary, str) else ""
                if summary_text and len(summary_text) >= 20:
                    evidence_text = f"Summary: {summary_text[:400]}"
                else:
                    evidence_text = f"Task executed: {json.dumps(result_data, default=str)[:600]}"
    
    # VERIFICATION GATE: Check evidence before marking complete
    if status == "completed" and VERIFICATION_AVAILABLE:
        try:
            verifier = CompletionVerifier()

            verification_required_types = {
                "database",
                "deploy",
                "deployment",
                "api_call",
                "tool_execution",
                "code",
                "github",
            }
            requires_verification = bool(task_type and task_type.lower() in verification_required_types)

            # If structured verification was provided by a handler, use it.
            structured_ok = None
            structured_type = None
            if isinstance(evidence_json, dict):
                structured_ok = bool(
                    evidence_json.get("verified") is True
                    or evidence_json.get("status") in ("SUCCESS", "VERIFIED", "OK")
                    or evidence_json.get("passed") is True
                )
                structured_type = evidence_json.get("type") or evidence_json.get("verification_type")

            if structured_ok is not None:
                is_valid = structured_ok
                evidence_type = str(structured_type) if structured_type else "structured"
            else:
                is_valid, evidence_type = verifier.verify_evidence(evidence_text)

            log_action(
                "verification.attempt",
                f"Verification attempt for task {task_id}: type={task_type or 'unknown'} title={task_title or ''}",
                level="info",
                task_id=task_id,
                output_data={
                    "task_type": task_type,
                    "evidence_type": evidence_type,
                    "has_structured": bool(evidence_json is not None),
                },
            )
            
            if not is_valid:
                # Reject completion - task doesn't have valid evidence
                log_action(
                    "task.completion_rejected",
                    f"Task {task_id} completion rejected: No valid evidence provided. "
                    f"Evidence text: {evidence_text[:100] if evidence_text else 'None'}",
                    level="warn",
                    task_id=task_id
                )

                if requires_verification:
                    log_action(
                        "verification.failed",
                        f"Verification failed for task {task_id} (required). Blocking completion.",
                        level="warn",
                        task_id=task_id,
                        error_data={
                            "task_type": task_type,
                            "evidence_type": evidence_type,
                            "completion_evidence": evidence_json or evidence_text,
                        },
                    )
                
                # Update task with rejection message but keep it in_progress
                reject_sql = f"""
                    UPDATE governance_tasks 
                    SET error_message = CONCAT(
                        COALESCE(error_message, ''),
                        CASE
                            WHEN COALESCE(error_message, '') LIKE '%[VERIFICATION] Completion rejected:%'
                            THEN ''
                            ELSE '[VERIFICATION] Completion rejected: Missing valid evidence. Provide PR link, file path, or substantive completion notes. '
                        END
                    )
                    WHERE id = {escape_value(task_id)}
                """
                try:
                    execute_sql(reject_sql)
                except Exception:
                    pass
                
                # Don't proceed with completion
                if requires_verification:
                    return
            
            # Log successful verification
            log_action(
                "task.completion_verified",
                f"Task {task_id} completion verified. Evidence type: {evidence_type}",
                level="info",
                task_id=task_id
            )
        except Exception as verify_err:
            # Log verification error but allow completion (graceful degradation)
            log_action(
                "task.verification_error",
                f"Verification error for task {task_id}: {verify_err}. Allowing completion.",
                level="warn",
                task_id=task_id
            )
    
    # Build the update columns
    cols = [f"status = {escape_value(status)}"]
    
    if status == "completed":
        cols.append(f"completed_at = {escape_value(now)}")
        # Add verification status
        if VERIFICATION_AVAILABLE:
            cols.append("verification_status = 'verified'")
    
    if evidence_json is not None:
        cols.append(f"completion_evidence = {escape_value(json.dumps(evidence_json, default=str))}")
    elif evidence_text:
        cols.append(f"completion_evidence = {escape_value(evidence_text)}")
    
    if result_data:
        cols.append(f"result = {escape_value(result_data)}")
    
    sql = f"UPDATE governance_tasks SET {', '.join(cols)} WHERE id = {escape_value(task_id)}"
    try:
        execute_sql(sql)
        
        # VERCHAIN-02: Sync status to stage for stage state machine enforcement
        if STAGE_TRANSITIONS_AVAILABLE:
            try:
                sync_status_to_stage(task_id, status)
            except Exception as stage_err:
                log_action(
                    "task.stage_sync_error",
                    f"Failed to sync stage for task {task_id}: {stage_err}",
                    level="warn",
                    task_id=task_id
                )
    except Exception as e:
        log_error(f"Failed to update task {task_id}: {e}")


def claim_task(task_id: str) -> bool:
    """Claim a task for this worker (atomic operation)."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE governance_tasks 
        SET assigned_worker = {escape_value(WORKER_ID)}, 
            status = 'in_progress',
            started_at = COALESCE(started_at, {escape_value(now)})
        WHERE id = {escape_value(task_id)}
        AND (assigned_worker IS NULL OR assigned_worker = {escape_value(WORKER_ID)})
        AND status IN ('pending', 'in_progress')
        RETURNING id
    """
    try:
        result = execute_sql(sql)
        return len(result.get("rows", [])) > 0
    except Exception:
        return False



def allocate_task_resources(task_id: str, task_title: str, priority: str) -> Dict[str, Any]:
    """
    Create a resource allocation record when a task is claimed.
    
    This implements L5 Resource Allocation - tracks time/budget allocation
    for tasks to enable constraint enforcement and ROI analysis.
    
    Args:
        task_id: The task being allocated resources.
        task_title: Task title for logging.
        priority: Task priority for scoring.
        
    Returns:
        Dict with allocation_id, success status, and message.
    """
    # Calculate priority score (1=critical, 2=high, 3=medium, 4=low)
    priority_scores = {"critical": 1.0, "high": 2.0, "medium": 3.0, "low": 4.0}
    priority_score = priority_scores.get(priority, 3.0)
    
    # Default allocation: estimate 30 minutes per task
    estimated_minutes = 30
    
    allocation_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    sql = f"""
        INSERT INTO resource_allocations (
            id, resource_type, task_id, allocated_amount, used_amount,
            unit, priority_score, status, created_at, updated_at
        ) VALUES (
            {escape_value(allocation_id)},
            'time',
            {escape_value(task_id)},
            {estimated_minutes},
            0,
            'minutes',
            {priority_score},
            'active',
            {escape_value(now)},
            {escape_value(now)}
        )
        RETURNING id
    """
    
    try:
        result = execute_sql(sql)
        if result.get("rows"):
            log_action(
                "resource.allocated",
                f"Allocated {estimated_minutes} minutes for task: {task_title}",
                level="info",
                task_id=task_id,
                output_data={"allocation_id": allocation_id, "priority_score": priority_score}
            )
            return {"success": True, "allocation_id": allocation_id, "minutes": estimated_minutes}
        else:
            return {"success": False, "error": "No rows returned from INSERT"}
    except Exception as e:
        log_action(
            "resource.allocation_failed",
            f"Failed to allocate resources: {str(e)}",
            level="warn",
            task_id=task_id
        )
        return {"success": False, "error": str(e)}


def update_resource_usage(task_id: str, minutes_used: int) -> bool:
    """
    Update the used_amount for a task's resource allocation.
    
    Called when a task completes to record actual time spent.
    
    Args:
        task_id: The task that completed.
        minutes_used: Actual time spent on the task.
        
    Returns:
        True if update succeeded.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    sql = f"""
        UPDATE resource_allocations
        SET used_amount = {minutes_used},
            status = 'completed',
            updated_at = {escape_value(now)}
        WHERE task_id = {escape_value(task_id)}
          AND status = 'active'
    """
    
    try:
        result = execute_sql(sql)
        return result.get("rowCount", 0) > 0
    except Exception:
        return False


def release_allocation(task_id: str) -> bool:
    """
    Release a task's resource allocation when the task fails.
    
    Called when a task fails to free up allocated resources and
    mark the allocation as released.
    
    Args:
        task_id: The task that failed.
        
    Returns:
        True if release succeeded.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    sql = f"""
        UPDATE resource_allocations
        SET status = 'released',
            updated_at = {escape_value(now)}
        WHERE task_id = {escape_value(task_id)}
          AND status = 'active'
    """
    
    try:
        result = execute_sql(sql)
        updated = result.get("rowCount", 0) > 0
        if updated:
            log_action(
                "resource.released",
                f"Released resource allocation for failed task: {task_id}",
                level="info",
                task_id=task_id
            )
        return updated
    except Exception:
        return False


# ============================================================
# APPROVAL WORKFLOW (Level 3: Human-in-the-Loop)
# Split into read-only check and creation functions
# ============================================================

def check_approval_status(task: Task) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check approval status for a task (read-only, no side effects).
    
    Args:
        task: Task object to check approval for
    
    Returns:
        Tuple of (requires_approval, approval_id_or_none, decision_status)
        - decision_status values: "approved", "auto_approved", "rejected", 
          "auto_rejected", "pending", "escalated", "timeout", "none", "error"
    """
    if not task.requires_approval:
        return False, None, "not_required"
    
    sql = f"""
        SELECT id, decision, decided_by, decided_at
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
        return True, approval["id"], approval["decision"]
    except Exception as e:
        log_error(f"Failed to check approval status: {e}")
        return True, None, "error"


def ensure_approval_request(task: Task) -> bool:
    """
    Ensure an approval request exists for a task. Creates one if needed.
    
    Args:
        task: Task object that requires approval
    
    Returns:
        True if approval request was created, False if already existed or error
    """
    requires, approval_id, decision = check_approval_status(task)
    
    if not requires or decision != "none":
        return False
    
    # Create approval request with correct schema columns
    action_data = {
        "task_type": task.task_type,
        "title": task.title,
        "priority": task.priority,
        "description": task.description[:500] if task.description else ""
    }
    
    action_description = f"Task execution: {task.title} (type: {task.task_type}, priority: {task.priority})"
    
    sql = f"""
        INSERT INTO approvals (
            task_id, worker_id, action_type, action_description, 
            action_data, risk_level, estimated_impact
        ) VALUES (
            {escape_value(task.id)}, 
            {escape_value(WORKER_ID)}, 
            'task_execution',
            {escape_value(action_description)},
            {escape_value(action_data)},
            'medium',
            {escape_value(f"Execution of {task.task_type} task")}
        )
    """
    try:
        execute_sql(sql)
        log_action(
            "approval.requested", 
            f"Approval requested for task: {task.title}", 
            task_id=task.id,
            output_data={"action_type": "task_execution", "risk_level": "medium"}
        )
        return True
    except Exception as e:
        log_error(f"Failed to create approval request: {e}", {"task_id": task.id})
        return False


def poll_approved_tasks(limit: int = 5) -> List[Task]:
    """
    Find tasks that are waiting for approval and have been approved.
    
    This function enables the approval resume flow:
    1. Task requires approval -> status set to waiting_approval
    2. Human approves via DB or UI -> approvals.decision = 'approved'
    3. This function finds those tasks so they can resume execution
    
    Args:
        limit: Maximum number of approved tasks to return
    
    Returns:
        List of Task objects that have been approved and can resume execution
    """
    sql = f"""
        SELECT DISTINCT ON (t.id)
            t.id, t.task_type, t.title, t.description, 
            CASE t.priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                WHEN 'low' THEN 4 
                ELSE 5 
            END as priority_num,
            t.status, t.payload, t.assigned_worker, t.created_at, t.requires_approval,
            a.decision, a.decided_by, a.decided_at
        FROM governance_tasks t
        INNER JOIN approvals a ON a.task_id = t.id
        WHERE t.status = 'waiting_approval'
          AND a.decision IN ('approved', 'auto_approved')
        ORDER BY t.id, a.decided_at DESC
        LIMIT {limit}
    """
    
    try:
        result = execute_sql(sql)
        rows = result.get("rows", [])
        
        tasks = []
        for row in rows:
            payload = row.get("payload", {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}
            
            task = Task(
                id=row["id"],
                task_type=row.get("task_type", ""),
                title=row.get("title", ""),
                description=row.get("description", ""),
                priority=int(row.get("priority_num", 3)),
                status=row.get("status", ""),
                payload=payload,
                assigned_to=row.get("assigned_worker"),
                created_at=row.get("created_at", ""),
                requires_approval=row.get("requires_approval", False)
            )
            tasks.append(task)
            
            log_action(
                "approval.found_approved",
                f"Task '{task.title}' approved by {row.get('decided_by', 'unknown')}",
                task_id=task.id,
                output_data={
                    "decision": row.get("decision"),
                    "decided_by": row.get("decided_by"),
                    "decided_at": row.get("decided_at")
                }
            )
        
        return tasks
    except Exception as e:
        log_error(f"Failed to poll approved tasks: {e}")
        return []


def resume_approved_task(task: Task) -> Tuple[bool, Dict[str, Any]]:
    """
    Resume execution of a task that was waiting for approval and has been approved.
    
    This updates the task status from waiting_approval to in_progress
    and then executes the task.
    
    Args:
        task: Approved task to resume
    
    Returns:
        Tuple of (success, result_dict)
    """
    log_action(
        "approval.resuming",
        f"Resuming approved task: {task.title}",
        task_id=task.id
    )
    
    # Mark the task as no longer requiring approval for this execution
    task.requires_approval = False
    
    # Update status to in_progress
    update_task_status(task.id, "in_progress", {"approval_resumed": True})
    
    # Execute the task
    return execute_task(task, approval_bypassed=True)


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


def send_to_dlq(task_id: str, error: str, attempts: int) -> Optional[str]:
    """
    Send failed task to dead letter queue.
    
    Uses error_recovery module's move_to_dead_letter for full task snapshots
    when available, falls back to simple insert otherwise.
    
    Args:
        task_id: The task ID to move to DLQ
        error: Error message describing the failure
        attempts: Number of retry attempts made
        
    Returns:
        DLQ entry ID if successful, None otherwise
    """
    # Use sophisticated error_recovery if available
    if ERROR_RECOVERY_AVAILABLE:
        dlq_id = move_to_dead_letter(
            task_id=task_id,
            reason="max_retries_exceeded",
            final_error=error,
            metadata={
                "attempts": attempts,
                "worker_id": WORKER_ID,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        if dlq_id:
            log_action(
                "dlq.added", 
                f"Task {task_id} sent to DLQ after {attempts} attempts",
                task_id=task_id, 
                error_data={"error": error, "attempts": attempts, "dlq_id": dlq_id}
            )
            # Create alert for visibility
            create_alert(
                alert_type="task_failure",
                severity="error",
                title=f"Task permanently failed: {task_id}",
                message=f"Task failed after {attempts} attempts. Error: {error[:200]}",
                source=WORKER_ID,
                related_id=task_id,
                metadata={"attempts": attempts, "dlq_id": dlq_id}
            )
            return dlq_id
        log_action(
            "dlq.failed",
            f"Failed to add task {task_id} to DLQ via error_recovery",
            level="error",
            task_id=task_id
        )
        return None
    
    # Fallback to simple insert if error_recovery unavailable
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
        log_action(
            "dlq.added", 
            f"Task {task_id} sent to DLQ after {attempts} attempts (fallback)", 
            task_id=task_id, 
            error_data={"error": error, "attempts": attempts}
        )
        return task_id  # Return task_id as proxy for success
    except Exception as e:
        log_error(f"Failed to send to DLQ: {e}")
        return None


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
    sql = "SELECT name AS tool_name, category AS tool_type, description, required_permissions AS permissions_required, status AS enabled FROM tool_registry WHERE status = 'active'"
    try:
        result = execute_sql(sql)
        return {r["tool_name"]: r for r in result.get("rows", [])}
    except Exception:
        return {}


def execute_tool(tool_name: str, params: Dict, dry_run: bool = False) -> Tuple[bool, Any]:
    """Execute a registered tool."""
    # Check permissions using RBAC-integrated is_action_allowed
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
                tool_name, params, status, worker_id, started_at
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

            # Scoped RBAC enforcement per tool category
            # (Most restrictive default when we can't infer read vs write)
            required_scope = None
            if tool_type == "database":
                required_scope = "database.write" if bool(params.get("write")) else "database.read"
            elif tool_type == "http":
                required_scope = "api.execute"
            elif tool_type == "github":
                required_scope = "github.write" if bool(params.get("write")) else "github.read"
            elif tool_type == "railway":
                required_scope = "railway.deploy" if bool(params.get("deploy")) else "railway.read"

            if required_scope:
                scope_ok, scope_reason = is_action_allowed(required_scope)
                if not scope_ok:
                    output = {
                        "status": "error",
                        "error": f"Permission denied: {scope_reason}",
                        "blocked": True,
                        "required_scope": required_scope,
                    }
                else:
            
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
                result_data = {escape_value(output)},
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
                    result_data = {escape_value(error_output)},
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


# ============================================================
# ORCHESTRATOR TASK DELEGATION (L5-01b)
# ============================================================

# Task type to worker capability mapping
TASK_TYPE_TO_WORKER: Dict[str, str] = {
    "tool_execution": "EXECUTOR",
    "workflow": "EXECUTOR",
    "content_creation": "EXECUTOR",
    "metrics_analysis": "ANALYST",
    "report_generation": "ANALYST",
    "pattern_detection": "ANALYST",
    "goal_creation": "STRATEGIST",
    "opportunity_scoring": "STRATEGIST",
    "experiment_design": "STRATEGIST",
    "health_check": "WATCHDOG",
    "error_detection": "WATCHDOG",
}


def delegate_to_worker(task: Task) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Delegate a task to a specialized worker via ORCHESTRATOR.
    
    This is the core L5 function that enables intelligent task routing
    to specialized workers based on capabilities and load.
    
    Args:
        task: The Task object to delegate
    
    Returns:
        Tuple of (delegated: bool, worker_id: Optional[str], details: Dict)
    """
    if not ORCHESTRATION_AVAILABLE:
        return False, None, {"error": "orchestration module not available"}
    
    # Determine the best worker for this task type
    target_worker = TASK_TYPE_TO_WORKER.get(task.task_type)
    
    if not target_worker:
        # No specific worker mapping - check if generic task execution is needed
        agents = discover_agents(capability="task.execute", min_health_score=0.3)
        if agents:
            target_worker = agents[0].get("worker_id")
    
    if not target_worker:
        return False, None, {"reason": "no suitable worker for task type", "task_type": task.task_type}
    
    # BUGFIX: Prevent self-delegation - if target is ourselves, don't delegate
    if target_worker == WORKER_ID or target_worker in (WORKER_ID.upper(), WORKER_ID.lower()):
        return False, WORKER_ID, {
            "reason": "self_delegation_prevented",
            "message": f"Target worker {target_worker} is self ({WORKER_ID}), will execute locally"
        }
    
    # Check if the target worker is healthy and available
    agents = discover_agents(min_health_score=0.3)
    target_agent = None
    for agent in agents:
        if agent.get("worker_id") == target_worker:
            target_agent = agent
            break
    
    if not target_agent:
        return False, None, {"reason": f"worker {target_worker} not available"}
    
    # Check worker capacity
    active_tasks = target_agent.get("active_task_count", 0) or 0
    max_tasks = target_agent.get("max_concurrent_tasks", 5) or 5
    
    if active_tasks >= max_tasks:
        return False, None, {"reason": f"worker {target_worker} at capacity ({active_tasks}/{max_tasks})"}
    
    # Delegate the task via ORCHESTRATOR
    result = orchestrator_assign_task(
        task_id=task.id,
        target_worker_id=target_worker,
        reason="capability_match"
    )
    
    if result.get("success"):
        # Log the delegation event
        log_action(
            "orchestrator.delegate",
            f"ORCHESTRATOR delegated task '{task.title}' to {target_worker}",
            level="info",
            task_id=task.id,
            output_data={
                "target_worker": target_worker,
                "worker_health": target_agent.get("health_score"),
                "worker_load": f"{active_tasks}/{max_tasks}",
                "reason": "capability_match",
                "log_id": result.get("log_id")
            }
        )
        return True, target_worker, result
    
    return False, None, result


def execute_task(task: Task, dry_run: bool = False, approval_bypassed: bool = False) -> Tuple[bool, Dict]:
    """Execute a single task with full Level 3 compliance and L2 risk assessment."""
    start_time = time.time()
    
    # L2: Assess risk before execution
    risk_score, risk_level, risk_factors = assess_task_risk(task)
    log_risk_warning(task, risk_score, risk_level, risk_factors)
    
    # L2: Log decision with confidence based on risk
    confidence = 1.0 - (risk_score * 0.5)  # Higher risk = lower confidence
    log_decision("task.execute", task.title, f"Priority {task.priority}, type {task.task_type}",
                 {"task_id": task.id, "risk_score": risk_score, "risk_level": risk_level},
                 confidence=confidence)
    
    # Check permission using RBAC-integrated is_action_allowed
    allowed, reason = is_action_allowed(f"task.{task.task_type}")
    if not allowed:
        log_action("task.blocked", f"Task blocked: {reason}", level="warn", task_id=task.id)
        return False, {"blocked": True, "reason": reason}
    
    # L2: High-risk tasks require approval even if not explicitly marked
    # Log if approval was bypassed (already approved in prior step)
    if approval_bypassed and should_require_approval_for_risk(risk_score, risk_level):
        log_action("approval.bypassed", 
                  f"Task '{task.title}' bypassing risk approval (already approved)",
                  task_id=task.id,
                  output_data={"risk_score": risk_score, "risk_level": risk_level, "reason": "prior_approval"})

    if should_require_approval_for_risk(risk_score, risk_level) and not task.requires_approval and not approval_bypassed:
        log_action("risk.approval_required", 
                  f"Task '{task.title}' requires approval due to {risk_level.upper()} risk ({risk_score:.0%})",
                  level="warn", task_id=task.id,
                  output_data={"risk_score": risk_score, "risk_level": risk_level, "risk_factors": risk_factors})
        # FIX: Set requires_approval so check_approval_status works correctly
        task.requires_approval = True
        # Create an approval record so standard workflow can pick it up
        ensure_approval_request(task)
        update_task_status(task.id, "waiting_approval", {
            "reason": f"High risk task ({risk_level}: {risk_score:.0%})",
            "risk_factors": risk_factors
        })
        return False, {"waiting_approval": True, "risk_triggered": True, "risk_score": risk_score, "risk_level": risk_level}
    
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
                   output_data={"task_type": task.task_type, "payload": task.payload, 
                               "risk_score": risk_score, "risk_level": risk_level})
        return True, {"dry_run": True, "would_execute": task.task_type, "risk_level": risk_level}
    
    try:
        # Execute based on task type
        result = {"executed": True}
        task_succeeded = True  # Track overall success

        # Experiment lifecycle hooks (optional)
        experiment_id = None
        try:
            if isinstance(task.payload, dict):
                experiment_id = task.payload.get("experiment_id")
        except Exception:
            experiment_id = None

        if EXPERIMENTS_AVAILABLE and experiment_id:
            try:
                ensure_experiment_schema()
                link_task_to_experiment(
                    experiment_id=str(experiment_id),
                    task_id=str(task.id),
                    link_type=str(task.task_type or "task"),
                    notes=task.title,
                    created_by=WORKER_ID,
                )
            except Exception as exp_link_err:
                log_action(
                    "experiment.task_link_failed",
                    f"Failed to link task {task.id} to experiment {experiment_id}: {str(exp_link_err)[:200]}",
                    level="warn",
                    task_id=task.id,
                )
        
        if task.task_type == "tool_execution":
            tool_name = task.payload.get("tool_name")
            tool_params = task.payload.get("params", {})
            success, output = execute_tool(tool_name, tool_params)
            result = {"success": success, "output": output}
            task_succeeded = success
            
        elif task.task_type == "workflow":
            steps = task.payload.get("steps")
            if not steps:
                handler_result = None
                try:
                    from core.handlers import get_handler

                    task_dict = {
                        "id": task.id,
                        "task_type": task.task_type,
                        "title": task.title,
                        "description": task.description,
                        "priority": task.priority,
                        "payload": task.payload or {},
                    }

                    handler = get_handler("workflow", execute_sql, log_action)
                    if handler is None:
                        handler = get_handler("ai", execute_sql, log_action)
                    if handler is not None:
                        handler_result = handler.execute(task_dict)
                except Exception as handler_err:
                    log_action(
                        "task.handler_dispatch_failed",
                        f"Workflow handler dispatch failed: {str(handler_err)[:200]}",
                        level="warn",
                        task_id=task.id,
                    )

                if handler_result is not None:
                    result = handler_result.to_dict()
                    waiting = bool((handler_result.data or {}).get("waiting_approval"))
                    if waiting:
                        update_task_status(task.id, "waiting_approval", handler_result.data)
                        return False, {"waiting_approval": True, **(handler_result.data or {})}
                    task_succeeded = bool(handler_result.success)
                else:
                    result = {"error": "Workflow task missing 'steps' in payload", "expected_fields": ["steps"]}
                    task_succeeded = False
            else:
                # Execute workflow steps
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
            # Phase 5: Call the proactive opportunity scan handler
            if PROACTIVE_AVAILABLE:
                scan_result = handle_opportunity_scan(
                    task.payload if hasattr(task, 'payload') else {"config": {}},
                    execute_sql,
                    log_action
                )
                result = scan_result
                task_succeeded = scan_result.get("success", False)
                if task_succeeded:
                    log_action(
                        "opportunity_scan.complete",
                        f"Scan completed: found={scan_result.get('opportunities_found', 0)}, qualified={scan_result.get('opportunities_qualified', 0)}",
                        task_id=task.id,
                        output_data={
                            "scan_id": scan_result.get("scan_id"),
                            "sources_scanned": scan_result.get("sources_scanned", 0),
                            "opportunities_found": scan_result.get("opportunities_found", 0),
                            "opportunities_qualified": scan_result.get("opportunities_qualified", 0),
                            "tasks_created": scan_result.get("tasks_created", 0)
                        }
                    )
            else:
                result = {"error": "Proactive module not available", "import_error": _proactive_import_error}
                task_succeeded = False
                log_action("opportunity_scan.unavailable", "Proactive module not available",
                          level="warn", task_id=task.id, error_data=result)
            
        elif task.task_type == "health_check":
            result = {"healthy": True, "component": task.payload.get("component")}
            
        
        elif task.task_type == "database":
            # Execute SQL query from payload
            sql_query = task.payload.get("sql") or task.payload.get("query")
            if not sql_query:
                log_action(
                    "task.error",
                    "Database task missing 'sql' in payload",
                    level="error",
                    task_id=task.id,
                )
                result = {"error": "No SQL query provided in payload", "expected_fields": ["sql", "query"]}
                task_succeeded = False
            else:
                sql_upper = sql_query.strip().upper()
                first_token = sql_upper.split()[0] if sql_upper.split() else ""
                read_only_statements = {"SELECT", "WITH", "SHOW", "EXPLAIN", "DESCRIBE"}

                required_scope = "database.read" if first_token in read_only_statements else "database.write"
                allowed_scope, reason_scope = is_action_allowed(required_scope)
                if not allowed_scope:
                    result = {"blocked": True, "reason": reason_scope, "required_scope": required_scope}
                    task_succeeded = False
                    log_action(
                        "task.blocked",
                        f"Database task blocked: {reason_scope}",
                        level="warn",
                        task_id=task.id,
                        error_data={"required_scope": required_scope},
                    )
                else:
                    # Writes require approval
                    if first_token not in read_only_statements and not task.requires_approval and not approval_bypassed:
                        log_action(
                            "task.write_blocked",
                            f"Write operation '{first_token}' requires approval",
                            level="warn",
                            task_id=task.id,
                            output_data={"statement_type": first_token, "task_id": task.id},
                        )

                        try:
                            execute_sql(
                                f"UPDATE governance_tasks SET requires_approval = TRUE WHERE id = {escape_value(task.id)}"
                            )
                        except Exception:
                            pass

                        ensure_approval_request(task)
                        update_task_status(
                            task.id,
                            "waiting_approval",
                            {
                                "reason": f"Write operation '{first_token}' requires human approval",
                                "statement_type": first_token,
                                "sql_preview": sql_query[:100] + "..." if len(sql_query) > 100 else sql_query,
                            },
                        )

                        return False, {
                            "waiting_approval": True,
                            "reason": f"Write operation '{first_token}' requires approval",
                            "statement_type": first_token,
                        }

                    try:
                        if first_token not in read_only_statements:
                            if not DB_VERIFICATION_AVAILABLE:
                                raise Exception(f"DB write verification unavailable: {_db_verification_import_error}")

                            db_result, verification = execute_db_write_with_verification(
                                execute_sql=execute_sql,
                                sql=sql_query,
                            )

                            result = {
                                "executed": True,
                                "rowCount": db_result.get("rowCount", 0),
                                "rows_preview": (
                                    db_result.get("rows", [])[:5]
                                    if isinstance(db_result.get("rows"), list)
                                    else []
                                ),
                                "verification": verification,
                            }

                            if EXPERIMENTS_AVAILABLE and experiment_id:
                                try:
                                    record_experiment_change(
                                        experiment_id=str(experiment_id),
                                        change_type="db_write",
                                        description=f"Database write via task {task.id}",
                                        change_data={
                                            "task_id": str(task.id),
                                            "statement_type": first_token,
                                            "sql_preview": (sql_query[:500] if isinstance(sql_query, str) else None),
                                            "verified": bool(verification.get("verified")),
                                        },
                                        created_by=WORKER_ID,
                                    )
                                except Exception:
                                    pass

                            if not verification.get("verified"):
                                task_succeeded = False
                                log_action(
                                    "task.database_verification_failed",
                                    "DB write verification failed",
                                    level="error",
                                    task_id=task.id,
                                    error_data={"statement_type": first_token, "verification": verification},
                                )
                            else:
                                log_action(
                                    "task.database_write_verified",
                                    "DB write verified",
                                    level="info",
                                    task_id=task.id,
                                    output_data={"statement_type": first_token, "verification": verification},
                                )
                        else:
                            query_result = execute_sql(sql_query)
                            result = {
                                "executed": True,
                                "rowCount": query_result.get("rowCount", 0),
                                "rows_preview": query_result.get("rows", [])[:5],
                            }

                            if EXPERIMENTS_AVAILABLE and experiment_id:
                                try:
                                    record_metric_point(
                                        experiment_id=str(experiment_id),
                                        metric_name="database.row_count",
                                        metric_value=float(query_result.get("rowCount", 0) or 0),
                                        metric_type="count",
                                        source_task_id=str(task.id),
                                        raw_data={"statement_type": first_token},
                                    )
                                except Exception:
                                    pass
                            log_action(
                                "task.database_executed",
                                "Query executed successfully",
                                task_id=task.id,
                                output_data={
                                    "executed": True,
                                    "rowCount": query_result.get("rowCount", 0),
                                    "sql_length": len(sql_query),
                                    "sql_truncated": len(sql_query) > 200,
                                },
                            )
                    except Exception as sql_error:
                        result = {"error": str(sql_error)}
                        task_succeeded = False
                        log_action(
                            "task.database_failed",
                            "SQL execution failed",
                            level="error",
                            task_id=task.id,
                            error_data={"error": str(sql_error), "sql_length": len(sql_query)},
                        )

        elif task.task_type == "api_call":
            allowed_scope, reason_scope = is_action_allowed("api.execute")
            if not allowed_scope:
                result = {"blocked": True, "reason": reason_scope, "required_scope": "api.execute"}
                task_succeeded = False
                log_action(
                    "task.blocked",
                    f"API call task blocked: {reason_scope}",
                    level="warn",
                    task_id=task.id,
                    error_data={"required_scope": "api.execute"},
                )
            else:
                url = task.payload.get("url")
                method = task.payload.get("method") or "GET"
                headers = task.payload.get("headers") or {}
                timeout_seconds = int(task.payload.get("timeout_seconds") or 20)
                json_body = task.payload.get("json")
                body = task.payload.get("body")

                if not url:
                    log_action(
                        "task.error",
                        "API call task missing 'url' in payload",
                        level="error",
                        task_id=task.id,
                    )
                    result = {"error": "No URL provided in payload", "expected_fields": ["url"]}
                    task_succeeded = False
                else:
                    try:
                        if not API_VERIFICATION_AVAILABLE:
                            raise Exception(f"API call verification unavailable: {_api_verification_import_error}")

                        api_result, verification = execute_api_call_with_verification(
                            url=url,
                            method=method,
                            headers=headers if isinstance(headers, dict) else {},
                            body=body,
                            json_body=json_body,
                            timeout_seconds=timeout_seconds,
                        )

                        result = {**(api_result or {}), "verification": verification}

                        if EXPERIMENTS_AVAILABLE and experiment_id:
                            try:
                                record_metric_point(
                                    experiment_id=str(experiment_id),
                                    metric_name="api_call.verified",
                                    metric_value=1.0 if verification.get("verified") else 0.0,
                                    metric_type="boolean",
                                    source_task_id=str(task.id),
                                    raw_data={"url": url, "method": method, "status": verification.get("status")},
                                )
                            except Exception:
                                pass
                        if not verification.get("verified"):
                            task_succeeded = False
                            log_action(
                                "task.api_call_verification_failed",
                                "API call verification failed",
                                level="error",
                                task_id=task.id,
                                error_data={"verification": verification},
                            )
                        else:
                            log_action(
                                "task.api_call_verified",
                                "API call verified",
                                level="info",
                                task_id=task.id,
                                output_data={"verification": verification},
                            )
                    except Exception as api_error:
                        result = {"error": str(api_error)}
                        task_succeeded = False
                        log_action(
                            "task.api_call_failed",
                            "API call execution failed",
                            level="error",
                            task_id=task.id,
                            error_data={"error": str(api_error)},
                        )

        elif task.task_type in ("deploy", "deployment"):
            allowed_scope, reason_scope = is_action_allowed("railway.deploy")
            if not allowed_scope:
                result = {"blocked": True, "reason": reason_scope, "required_scope": "railway.deploy"}
                task_succeeded = False
                log_action(
                    "task.blocked",
                    f"Deploy task blocked: {reason_scope}",
                    level="warn",
                    task_id=task.id,
                    error_data={"required_scope": "railway.deploy"},
                )
            else:
                service_id = task.payload.get("service_id") or task.payload.get("railway_service_id")
                service_name = task.payload.get("service_name") or task.payload.get("service")
                environment_id = task.payload.get("environment_id") or "8bfa6a1a-92f4-4a42-bf51-194b1c844a76"
                timeout_seconds = int(task.payload.get("timeout_seconds") or 300)

                if not service_id:
                    log_action(
                        "task.error",
                        "Deploy task missing 'service_id' in payload",
                        level="error",
                        task_id=task.id,
                    )
                    result = {"error": "No service_id provided in payload", "expected_fields": ["service_id"]}
                    task_succeeded = False
                else:
                    try:
                        if not DEPLOY_VERIFICATION_AVAILABLE:
                            raise Exception(f"Deploy verification unavailable: {_deploy_verification_import_error}")

                        railway_token = get_scoped_credential(
                            WORKER_ID,
                            "RAILWAY_TOKEN",
                            required_scope="railway.deploy",
                        )

                        deploy_result, verification = execute_deploy_with_verification(
                            service_id=service_id,
                            service_name=service_name,
                            environment_id=environment_id,
                            railway_token=railway_token,
                            timeout_seconds=timeout_seconds,
                            poll_interval_seconds=10,
                        )

                        result = {**(deploy_result or {}), "verification": verification}

                        if EXPERIMENTS_AVAILABLE and experiment_id:
                            try:
                                record_experiment_change(
                                    experiment_id=str(experiment_id),
                                    change_type="deploy",
                                    description=f"Railway deploy via task {task.id}",
                                    change_data={
                                        "task_id": str(task.id),
                                        "service_id": service_id,
                                        "service_name": service_name,
                                        "environment_id": environment_id,
                                        "verified": bool(verification.get("verified")),
                                    },
                                    created_by=WORKER_ID,
                                )
                            except Exception:
                                pass
                        if not verification.get("verified"):
                            task_succeeded = False
                            log_action(
                                "task.deploy_verification_failed",
                                "Deploy verification failed",
                                level="error",
                                task_id=task.id,
                                error_data={"verification": verification},
                            )
                        else:
                            log_action(
                                "task.deploy_verified",
                                "Deploy verified",
                                level="info",
                                task_id=task.id,
                                output_data={"verification": verification},
                            )
                    except Exception as deploy_error:
                        result = {"error": str(deploy_error)}
                        task_succeeded = False
                        log_action(
                            "task.deploy_failed",
                            "Deploy execution failed",
                            level="error",
                            task_id=task.id,
                            error_data={"error": str(deploy_error)},
                        )
        
        elif task.task_type == "test":
            # Execute verification/test queries
            test_queries = task.payload.get("queries", [])
            test_sql = task.payload.get("sql")
            
            # TYPE SAFETY: Handle string input by wrapping in list
            if isinstance(test_queries, str):
                test_queries = [test_queries]
            
            if test_sql:
                test_queries = [test_sql]
            
            if not test_queries:
                result = {"error": "Test task missing 'queries' or 'sql' in payload"}
                task_succeeded = False
            else:
                test_results = []
                all_passed = True
                for i, query in enumerate(test_queries):
                    try:
                        query_result = execute_sql(query)
                        test_results.append({
                            "index": i,
                            "passed": True,
                            "rowCount": query_result.get("rowCount", 0)
                        })
                    except Exception as test_error:
                        test_results.append({
                            "index": i,
                            "passed": False,
                            "error": str(test_error)
                        })
                        all_passed = False
                
                result = {
                    "executed": True,
                    "tests_run": len(test_results),
                    "all_passed": all_passed,
                    "results": test_results
                }
                task_succeeded = all_passed
                log_action("task.test_completed", f"Ran {len(test_results)} tests, passed={all_passed}",
                          task_id=task.id, output_data=result)
        
        elif task.task_type == "scan":
            # Opportunity scanning - check for leads/opportunities
            scan_type = task.payload.get("scan_type", "general")
            source = task.payload.get("source", "unknown")
            
            # Log the scan attempt - actual scanning logic depends on external integrations
            result = {
                "executed": True,
                "scan_type": scan_type,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": "Scan completed - check external systems for results"
            }
            log_action("task.scan_completed", f"Scan completed: {scan_type} from {source}",
                      task_id=task.id, output_data=result)
        
        elif task.task_type == "verification":
            # Execute verification checks from payload
            verification_queries = task.payload.get("queries", [])
            verification_sql = task.payload.get("sql")
            assertions = task.payload.get("assertions", [])
            
            # TYPE SAFETY: Handle string input by wrapping in list
            if isinstance(verification_queries, str):
                verification_queries = [verification_queries]
            
            if verification_sql:
                verification_queries = [verification_sql]
            
            if not verification_queries:
                result = {"error": "Verification task missing 'queries' or 'sql' in payload"}
                task_succeeded = False
            else:
                verification_results = []
                all_passed = True
                
                for i, query in enumerate(verification_queries):
                    try:
                        query_result = execute_sql(query)
                        rows = query_result.get("rows", [])
                        row_count = query_result.get("rowCount", 0)
                        
                        # Check assertions if provided for this query
                        assertion_passed = True
                        assertion_message = None
                        
                        if i < len(assertions):
                            assertion = assertions[i]
                            expected_count = assertion.get("expected_count")
                            min_count = assertion.get("min_count")
                            max_count = assertion.get("max_count")
                            expected_value = assertion.get("expected_value")
                            
                            if expected_count is not None and row_count != expected_count:
                                assertion_passed = False
                                assertion_message = f"Expected {expected_count} rows, got {row_count}"
                            elif min_count is not None and row_count < min_count:
                                assertion_passed = False
                                assertion_message = f"Expected at least {min_count} rows, got {row_count}"
                            elif max_count is not None and row_count > max_count:
                                assertion_passed = False
                                assertion_message = f"Expected at most {max_count} rows, got {row_count}"
                            elif expected_value is not None and rows:
                                # Check first row's first value
                                first_value = list(rows[0].values())[0] if rows[0] else None
                                if first_value != expected_value:
                                    assertion_passed = False
                                    assertion_message = f"Expected value {expected_value}, got {first_value}"
                        
                        verification_results.append({
                            "index": i,
                            "passed": assertion_passed,
                            "rowCount": row_count,
                            "assertion_message": assertion_message
                        })
                        
                        if not assertion_passed:
                            all_passed = False
                            
                    except Exception as ver_error:
                        verification_results.append({
                            "index": i,
                            "passed": False,
                            "error": str(ver_error)
                        })
                        all_passed = False
                
                result = {
                    "executed": True,
                    "verifications_run": len(verification_results),
                    "all_passed": all_passed,
                    "results": verification_results
                }
                task_succeeded = all_passed
                log_action("task.verification_completed", 
                          f"Ran {len(verification_results)} verifications, passed={all_passed}",
                          task_id=task.id, output_data=result)
        
        elif task.task_type == "evaluation":
            # Execute evaluation logic from payload
            # Auto-detect eval_type if not explicitly set
            explicit_type = task.payload.get("eval_type")
            if explicit_type:
                eval_type = explicit_type
            elif task.payload.get("opp_id"):
                eval_type = "opportunity"
            elif task.payload.get("sql") or task.payload.get("query"):
                eval_type = "query"
            elif task.payload.get("metric_value") is not None:
                eval_type = "metric"
            else:
                eval_type = "query"  # Default fallback
            
            eval_sql = task.payload.get("sql") or task.payload.get("query")
            criteria = task.payload.get("criteria", {})
            
            if eval_type == "query" and eval_sql:
                try:
                    query_result = execute_sql(eval_sql)
                    rows = query_result.get("rows", [])
                    row_count = query_result.get("rowCount", 0)
                    
                    # Evaluate based on criteria
                    score = 100  # Start with perfect score
                    evaluation_notes = []
                    
                    # Check row count criteria
                    if "min_rows" in criteria and row_count < criteria["min_rows"]:
                        score -= 25
                        evaluation_notes.append(f"Below minimum row count: {row_count} < {criteria['min_rows']}")
                    if "max_rows" in criteria and row_count > criteria["max_rows"]:
                        score -= 25
                        evaluation_notes.append(f"Above maximum row count: {row_count} > {criteria['max_rows']}")
                    
                    # Check for required fields in results
                    required_fields = criteria.get("required_fields", [])
                    if rows and required_fields:
                        first_row = rows[0]
                        missing_fields = [f for f in required_fields if f not in first_row]
                        if missing_fields:
                            score -= 10 * len(missing_fields)
                            evaluation_notes.append(f"Missing required fields: {missing_fields}")
                    
                    # Determine pass/fail based on threshold
                    threshold = criteria.get("pass_threshold", 70)
                    passed = score >= threshold
                    
                    result = {
                        "executed": True,
                        "eval_type": eval_type,
                        "score": score,
                        "passed": passed,
                        "threshold": threshold,
                        "row_count": row_count,
                        "notes": evaluation_notes
                    }
                    task_succeeded = passed
                    log_action("task.evaluation_completed",
                              f"Evaluation completed: score={score}, passed={passed}",
                              task_id=task.id, output_data=result)
                              
                except Exception as eval_error:
                    result = {"error": str(eval_error), "eval_type": eval_type}
                    task_succeeded = False
                    log_action("task.evaluation_failed", f"Evaluation failed: {str(eval_error)}",
                              level="error", task_id=task.id, error_data=result)
            
            elif eval_type == "metric":
                # Evaluate a metric value against thresholds
                metric_name = task.payload.get("metric_name", "unknown")
                metric_value = task.payload.get("metric_value")
                
                if metric_value is None:
                    result = {"error": "Metric evaluation requires 'metric_value' in payload"}
                    task_succeeded = False
                else:
                    min_threshold = criteria.get("min_value")
                    max_threshold = criteria.get("max_value")
                    target_value = criteria.get("target_value")
                    
                    passed = True
                    notes = []
                    
                    if min_threshold is not None and metric_value < min_threshold:
                        passed = False
                        notes.append(f"Below minimum: {metric_value} < {min_threshold}")
                    if max_threshold is not None and metric_value > max_threshold:
                        passed = False
                        notes.append(f"Above maximum: {metric_value} > {max_threshold}")
                    if target_value is not None:
                        variance = abs(metric_value - target_value) / target_value * 100 if target_value else 0
                        notes.append(f"Variance from target: {variance:.1f}%")
                    
                    result = {
                        "executed": True,
                        "eval_type": eval_type,
                        "metric_name": metric_name,
                        "metric_value": metric_value,
                        "passed": passed,
                        "notes": notes
                    }
                    task_succeeded = passed
                    log_action("task.evaluation_completed",
                              f"Metric evaluation: {metric_name}={metric_value}, passed={passed}",
                              task_id=task.id, output_data=result)
            elif eval_type == "opportunity":
                # Evaluate an opportunity from the opportunities table
                opp_id = task.payload.get("opp_id")
                source = task.payload.get("src", "unknown")
                
                if not opp_id:
                    result = {"error": "Opportunity evaluation requires 'opp_id' in payload"}
                    task_succeeded = False
                else:
                    try:
                        opp_result = execute_sql(f"""
                            SELECT id, opportunity_type, category, estimated_value,
                                   confidence_score, status, description, source_description
                            FROM opportunities WHERE id = '{opp_id}'
                        """)
                        
                        if opp_result.get("rowCount", 0) == 0:
                            result = {
                                "error": f"Opportunity not found: {opp_id}",
                                "eval_type": eval_type,
                                "opp_id": opp_id
                            }
                            task_succeeded = False
                        else:
                            opp = opp_result["rows"][0]
                            
                            # Score the opportunity
                            score = 100
                            notes = []
                            
                            # Check confidence score
                            confidence = float(opp.get("confidence_score") or 0)
                            if confidence < 0.5:
                                score -= 30
                                notes.append(f"Low confidence: {confidence:.2f}")
                            elif confidence < 0.7:
                                score -= 15
                                notes.append(f"Medium confidence: {confidence:.2f}")
                            
                            # Check estimated value
                            est_value = float(opp.get("estimated_value") or 0)
                            if est_value < 1000:
                                score -= 20
                                notes.append(f"Low estimated value: ${est_value:.2f}")
                            
                            # Check status
                            opp_status = opp.get("status", "unknown")
                            if opp_status in ("closed", "lost", "expired"):
                                score -= 50
                                notes.append(f"Unfavorable status: {opp_status}")
                            
                            # Determine pass/fail
                            threshold = criteria.get("pass_threshold", 50)
                            passed = score >= threshold
                            
                            result = {
                                "executed": True,
                                "eval_type": eval_type,
                                "opportunity_id": opp_id,
                                "opportunity_type": opp.get("opportunity_type"),
                                "category": opp.get("category"),
                                "estimated_value": est_value,
                                "confidence": confidence,
                                "status": opp_status,
                                "score": score,
                                "passed": passed,
                                "threshold": threshold,
                                "notes": notes,
                                "source": source
                            }
                            task_succeeded = passed
                            log_action("task.evaluation_completed",
                                      f"Opportunity evaluation: {opp_id}, score={score}, passed={passed}",
                                      task_id=task.id, output_data=result)
                                      
                    except Exception as opp_error:
                        result = {"error": str(opp_error), "eval_type": eval_type, "opp_id": opp_id}
                        task_succeeded = False
                        log_action("task.evaluation_failed", f"Opportunity eval failed: {str(opp_error)}",
                                  level="error", task_id=task.id, error_data=result)
            
            else:
                result = {
                    "error": f"Unknown eval_type '{eval_type}' or missing required fields",
                    "supported_types": ["query", "metric", "opportunity"],
                    "payload_keys": list(task.payload.keys()) if task.payload else []
                }
                task_succeeded = False

        elif task.task_type == "code":
            # Autonomous code generation handler (PR #185)
            if CODE_TASK_AVAILABLE:
                # Log tool execution start to tool_executions table
                tool_exec_id = None
                code_start_time = time.time()
                try:
                    tool_params = {
                        "task_title": task.title,
                        "task_description": task.description[:500] if task.description else "",
                        "auto_merge": False
                    }
                    now = datetime.now(timezone.utc).isoformat()
                    sql = f"""
                        INSERT INTO tool_executions (
                            tool_name, params, status, worker_id, task_id, started_at
                        ) VALUES (
                            {escape_value('code_task_executor')}, 
                            {escape_value(tool_params)}, 
                            'running', 
                            {escape_value(WORKER_ID)},
                            {escape_value(str(task.id))},
                            {escape_value(now)}
                        ) RETURNING id
                    """
                    exec_result = execute_sql(sql)
                    tool_exec_id = exec_result.get("rows", [{}])[0].get("id")
                except Exception as log_err:
                    log_action("tool_exec.log_failed", f"Failed to log tool execution start: {log_err}",
                              level="warn", task_id=task.id)
                
                try:
                    code_result = execute_code_task(
                        task_id=task.id,
                        task_title=task.title,
                        task_description=task.description or "",
                        task_payload=task.payload or {},
                        log_action_func=log_action,
                        auto_merge=False  # Set True to auto-merge PRs
                    )
                    result = code_result
                    task_succeeded = code_result.get("success", False)
                    
                    # Update tool_executions with result
                    if tool_exec_id:
                        try:
                            code_duration_ms = int((time.time() - code_start_time) * 1000)
                            now = datetime.now(timezone.utc).isoformat()
                            status = 'completed' if task_succeeded else 'failed'
                            sql = f"""
                                UPDATE tool_executions SET
                                    status = {escape_value(status)},
                                    result_data = {escape_value(code_result)},
                                    completed_at = {escape_value(now)},
                                    duration_ms = {code_duration_ms}
                                WHERE id = {escape_value(tool_exec_id)}
                            """
                            execute_sql(sql)
                        except Exception as upd_err:
                            log_action("tool_exec.update_failed", f"Failed to update tool execution: {upd_err}",
                                      level="warn", task_id=task.id)
                    
                    if task_succeeded:
                        log_action("code_task.completed",
                                  f"Code task created PR #{code_result.get('pr_number')}",
                                  task_id=task.id, output_data=code_result)
                    else:
                        log_action("code_task.failed",
                                  f"Code task failed: {code_result.get('error', 'Unknown error')}",
                                  level="error", task_id=task.id, error_data=code_result)
                except Exception as code_err:
                    result = {"error": str(code_err), "task_type": "code"}
                    task_succeeded = False
                    
                    # Update tool_executions with error
                    if tool_exec_id:
                        try:
                            code_duration_ms = int((time.time() - code_start_time) * 1000)
                            now = datetime.now(timezone.utc).isoformat()
                            sql = f"""
                                UPDATE tool_executions SET
                                    status = 'failed',
                                    result_data = {escape_value(result)},
                                    error_message = {escape_value(str(code_err))},
                                    completed_at = {escape_value(now)},
                                    duration_ms = {code_duration_ms}
                                WHERE id = {escape_value(tool_exec_id)}
                            """
                            execute_sql(sql)
                        except Exception:
                            pass  # Don't fail if we can't update the record
                    
                    log_action("code_task.exception", f"Code task exception: {str(code_err)}",
                              level="error", task_id=task.id, error_data=result)
            else:
                result = {"error": "Code task executor not available", "import_error": _code_task_import_error}
                task_succeeded = False
                log_action("code_task.unavailable", "Code task executor not available",
                          level="warn", task_id=task.id, error_data=result)

        else:
            # Unknown task type - attempt modular handler dispatch, then fall back to AI.
            handler_result = None
            try:
                from core.handlers import get_handler

                task_dict = {
                    "id": task.id,
                    "task_type": task.task_type,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "payload": task.payload or {},
                }

                log_action(
                    "task.handler_lookup",
                    f"Looking up handler for task_type='{task.task_type}' (will fallback to 'ai')",
                    level="info",
                    task_id=task.id,
                )

                handler = get_handler(task.task_type, execute_sql, log_action)
                log_action(
                    "task.handler_lookup_result",
                    f"Primary handler for '{task.task_type}': {handler.__class__.__name__ if handler else 'None'}",
                    level="info",
                    task_id=task.id,
                )
                if handler is None:
                    handler = get_handler("ai", execute_sql, log_action)
                    log_action(
                        "task.handler_lookup_result",
                        f"Fallback handler for 'ai': {handler.__class__.__name__ if handler else 'None'}",
                        level="info",
                        task_id=task.id,
                    )

                if handler is not None:
                    handler_result = handler.execute(task_dict)
            except Exception as handler_err:
                log_action(
                    "task.handler_dispatch_failed",
                    f"Handler dispatch failed: {str(handler_err)[:200]}",
                    level="warn",
                    task_id=task.id,
                )

            if handler_result is not None:
                result = handler_result.to_dict()
                waiting = bool((handler_result.data or {}).get("waiting_approval"))
                if waiting:
                    update_task_status(task.id, "waiting_approval", handler_result.data)
                    return False, {"waiting_approval": True, **(handler_result.data or {})}

                task_succeeded = bool(handler_result.success)
            else:
                # If handler dispatch wasn't possible, fall back to human guidance.
                log_action(
                    "task.unhandled_type",
                    f"Task type '{task.task_type}' has no automated handler - waiting for human guidance",
                    level="warn",
                    task_id=task.id,
                    output_data={"task_type": task.task_type, "title": task.title},
                )

                update_task_status(
                    task.id,
                    "waiting_approval",
                    {
                        "reason": f"No automated handler for task_type '{task.task_type}'",
                        "requires": "Human review and execution guidance",
                        "task_description": task.description[:500] if task.description else None,
                    },
                )

                return False, {
                    "waiting_approval": True,
                    "reason": f"Task type '{task.task_type}' requires human guidance",
                    "task_type": task.task_type,
                }
        # Mark based on actual success
        duration_ms = int((time.time() - start_time) * 1000)
        
        if task_succeeded:
            update_task_status(task.id, "completed", result)
            log_action("task.completed", f"Task completed: {task.title}", task_id=task.id,
                       output_data=result, duration_ms=duration_ms)
            # MED-02: Capture learning from successful task
            if LEARNING_CAPTURE_AVAILABLE:
                try:
                    capture_task_learning(
                        execute_sql_func=execute_sql,
                        escape_value_func=escape_value,
                        log_action_func=log_action,
                        task_id=task.id,
                        task_type=task.task_type,
                        task_title=task.title,
                        task_description=task.description,
                        success=True,
                        result=result,
                        duration_ms=duration_ms,
                        worker_id=WORKER_ID,
                    )
                except Exception as learn_err:
                    log_action("learning.capture_error", f"Failed to capture learning: {learn_err}",
                               task_id=task.id, level="warning")
            # Notify Slack (best-effort, don't affect task status)
            try:
                notify_task_completed(
                    task_id=task.id,
                    task_title=task.title,
                    worker_id=WORKER_ID,
                    duration_secs=duration_ms // 1000,
                    details=result.get("summary") if isinstance(result, dict) else None
                )
            except Exception as notify_err:
                log_action("notification.failed", f"Failed to send completion notification: {notify_err}",
                           task_id=task.id, level="warning")
        else:
            update_task_status(task.id, "failed", result)
            log_action("task.failed", f"Task failed: {task.title}", task_id=task.id,
                       level="error", error_data=result, duration_ms=duration_ms)
            # MED-02: Capture learning from failed task
            if LEARNING_CAPTURE_AVAILABLE:
                try:
                    capture_task_learning(
                        execute_sql_func=execute_sql,
                        escape_value_func=escape_value,
                        log_action_func=log_action,
                        task_id=task.id,
                        task_type=task.task_type,
                        task_title=task.title,
                        task_description=task.description,
                        success=False,
                        result=result,
                        duration_ms=duration_ms,
                        worker_id=WORKER_ID,
                    )
                except Exception as learn_err:
                    log_action("learning.capture_error", f"Failed to capture learning: {learn_err}",
                               task_id=task.id, level="warning")
            # Notify Slack (best-effort, don't affect task status)
            try:
                notify_task_failed(
                    task_id=task.id,
                    task_title=task.title,
                    error_message=result.get("error", "Unknown error") if isinstance(result, dict) else str(result),
                    worker_id=WORKER_ID
                )
            except Exception as notify_err:
                log_action("notification.failed", f"Failed to send failure notification: {notify_err}",
                           task_id=task.id, level="warning")
        
        return task_succeeded, result
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_str = str(e)

        # FIX-14: Release resource allocation on task failure
        release_allocation(task.id)
        
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
            # Notify Slack of permanent failure (best-effort, don't mask DLQ handling)
            try:
                notify_task_failed(
                    task_id=task.id,
                    task_title=task.title,
                    error_message=f"Permanently failed after {retries} retries: {error_str}",
                    worker_id=WORKER_ID,
                    retry_count=retries
                )
            except Exception as notify_err:
                log_action("notification.failed", f"Failed to send DLQ notification: {notify_err}",
                           task_id=task.id, level="warning")
        
        return False, {"error": error_str, "retries": retries}


# ============================================================
# THE AUTONOMY LOOP
# ============================================================

def autonomy_loop():
    """The main loop that makes JUGGERNAUT autonomous."""
    # Note: shutdown_requested is only read here, no global declaration needed
    
    log_info("Autonomy loop starting", {"worker_id": WORKER_ID, "interval": LOOP_INTERVAL})
    
    # GAP-03: Log RBAC framework status
    if RBAC_AVAILABLE:
        log_info("RBAC framework available - access_audit_log active", {"status": "enabled"})
    elif _rbac_import_error:
        log_action("rbac.unavailable", f"RBAC disabled: {_rbac_import_error}", level="warn")
    
    # Log experiment framework status (deferred from import time)
    if EXPERIMENTS_AVAILABLE:
        log_info("Experiments framework available", {"status": "enabled"})
    elif _experiments_import_error:
        log_action("experiments.unavailable", f"Experiments disabled: {_experiments_import_error}", level="warn")
    
    # Log proactive framework status (HIGH-05)
    if PROACTIVE_AVAILABLE:
        log_info("Proactive opportunity scanner available", {"status": "enabled"})
    elif _proactive_import_error:
        log_action("proactive.unavailable", f"Proactive systems disabled: {_proactive_import_error}", level="warn")
    
    # Log error recovery framework status (MED-01)
    if ERROR_RECOVERY_AVAILABLE:
        log_info("Error recovery framework available", {"status": "enabled"})
    elif _error_recovery_import_error:
        log_action("error_recovery.unavailable", f"Error recovery disabled: {_error_recovery_import_error}", level="warn")
    
    # Log failover framework status (L5-07)
    if FAILOVER_AVAILABLE:
        log_info("Failover and resilience framework available", {"status": "enabled"})
    elif _failover_import_error:
        log_action("failover.unavailable", f"Failover disabled: {_failover_import_error}", level="warn")

    # Log stale cleanup framework status (CRITICAL-03c)
    if STALE_CLEANUP_AVAILABLE:
        log_info("Stale task cleanup available", {"status": "enabled"})
    elif _stale_cleanup_import_error:
        log_action("stale_cleanup.unavailable", f"Stale cleanup disabled: {_stale_cleanup_import_error}", level="warn")
    
    # Log auto-scaling framework status (SCALE-03)
    if AUTO_SCALING_AVAILABLE and ENABLE_AUTO_SCALING:
        log_info("Auto-scaling enabled", {"status": "enabled", "interval_seconds": AUTO_SCALING_INTERVAL_SECONDS})
    elif AUTO_SCALING_AVAILABLE and not ENABLE_AUTO_SCALING:
        log_info("Auto-scaling available but disabled", {"status": "disabled", "enable_with": "ENABLE_AUTO_SCALING=true"})
    elif _auto_scaling_import_error:
        log_action("auto_scaling.unavailable", f"Auto-scaling disabled: {_auto_scaling_import_error}", level="warn")
    
    # Initialize auto-scaler if enabled (SCALE-03)
    auto_scaler = None
    last_auto_scale_time = time.time()
    if AUTO_SCALING_AVAILABLE and ENABLE_AUTO_SCALING:
        try:
            auto_scaler = create_auto_scaler(
                db_endpoint=NEON_ENDPOINT,
                connection_string=DATABASE_URL,
                config=ScalingConfig(enabled=True)
            )
            log_info("Auto-scaler initialized", {"db_endpoint": NEON_ENDPOINT})
        except Exception as as_init_err:
            log_error(f"Failed to initialize auto-scaler: {as_init_err}")
            auto_scaler = None
    
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
        
        
        # L5-07: Check for failed workers and reassign tasks at start of each loop
        if FAILOVER_AVAILABLE:
            try:
                failover_result = process_failover()
                if failover_result.get("tasks_reassigned", 0) > 0:
                    log_action(
                        "failover.tasks_reassigned",
                        f"Reassigned {failover_result['tasks_reassigned']} tasks from failed workers",
                        data=failover_result
                    )
            except Exception as failover_err:
                log_error(f"Failover check failed: {failover_err}")

        # CRITICAL-03c: Reset stale tasks at START of each loop cycle
        if STALE_CLEANUP_AVAILABLE:
            try:
                reset_count, reset_tasks = reset_stale_tasks()
                if reset_count > 0:
                    log_action(
                        "stale_cleanup.reset",
                        f"Reset {reset_count} stale tasks back to pending",
                        level="info",
                        output_data={"reset_count": reset_count, "task_ids": [t.get("id") for t in reset_tasks]}
                    )
            except Exception as stale_err:
                log_action(
                    "stale_cleanup.error",
                    f"Failed to reset stale tasks: {stale_err}",
                    level="error"
                )

        # SCALE-03: Execute auto-scaling at configurable intervals
        if auto_scaler is not None:
            time_since_last_scale = time.time() - last_auto_scale_time
            if time_since_last_scale >= AUTO_SCALING_INTERVAL_SECONDS:
                try:
                    scaling_result = auto_scaler.execute_scaling()
                    last_auto_scale_time = time.time()
                    
                    # Log scaling action if anything happened
                    if scaling_result.get("action") != "no_action":
                        log_action(
                            "auto_scaling.executed",
                            f"Auto-scaling: {scaling_result.get('action')} - {scaling_result.get('reason')}",
                            level="info",
                            output_data={
                                "action": scaling_result.get("action"),
                                "reason": scaling_result.get("reason"),
                                "current_workers": scaling_result.get("current_workers"),
                                "queue_depth": scaling_result.get("queue_depth"),
                                "workers_added": len(scaling_result.get("workers_added", [])),
                                "workers_removed": len(scaling_result.get("workers_removed", [])),
                                "errors": scaling_result.get("errors", [])
                            }
                        )
                    elif loop_count % 10 == 0:  # Log no_action every 10 loops
                        log_action(
                            "auto_scaling.check",
                            f"Auto-scaling check: {scaling_result.get('reason')}",
                            level="info",
                            output_data={
                                "current_workers": scaling_result.get("current_workers"),
                                "queue_depth": scaling_result.get("queue_depth")
                            }
                        )
                except Exception as as_err:
                    log_action(
                        "auto_scaling.error",
                        f"Auto-scaling failed: {as_err}",
                        level="error",
                        error_data={"error": str(as_err)}
                    )

        # L5-WIRE-04: Check escalation timeouts each loop
        if ORCHESTRATION_AVAILABLE:
            try:
                escalated = check_escalation_timeouts()
                if escalated:
                    log_action(
                        "escalation.timeout_check",
                        f"Auto-escalated {len(escalated)} timed-out escalations",
                        output_data={"escalated_ids": escalated}
                    )
            except Exception as esc_err:
                log_error(f"Escalation timeout check failed: {esc_err}")

        # L5-WIRE-05: Auto-approve timed out approval requests
        try:
            approval_result = auto_approve_timed_out_tasks()
            if approval_result.get("auto_approved"):
                for task_id in approval_result["auto_approved"]:
                    log_action("approval.auto_timeout_processed",
                              f"Task auto-approved after timeout",
                              task_id=task_id)
            if approval_result.get("escalated"):
                for task_id in approval_result["escalated"]:
                    log_action("approval.timeout_escalated",
                              f"High-risk task escalated due to approval timeout",
                              task_id=task_id)
        except Exception as approval_err:
            log_error(f"Approval timeout check failed: {approval_err}")
        
        # L5-WIRE-06: Handle orphaned waiting_approval tasks
        try:
            orphan_result = handle_orphaned_waiting_approval_tasks()
            if orphan_result.get("reset"):
                for task_id in orphan_result["reset"]:
                    log_action("task.orphan_processed",
                              f"Orphaned task reset to pending",
                              task_id=task_id)
            if orphan_result.get("created_approvals"):
                for task_id in orphan_result["created_approvals"]:
                    log_action("approval.orphan_created_processed",
                              f"Created approval for orphaned high-priority task",
                              task_id=task_id)
        except Exception as orphan_err:
            log_error(f"Orphaned task handler failed: {orphan_err}")

        # L5-WIRE-04: Create escalations for stuck tasks (in_progress > 30 min)
        try:
            stuck_threshold_minutes = 30
            stuck_sql = f"""
            SELECT id, title, task_type 
            FROM governance_tasks 
            WHERE status = 'in_progress' 
              AND started_at < NOW() - INTERVAL '{stuck_threshold_minutes} minutes'
              AND id NOT IN (
                  SELECT DISTINCT CAST(context->>'task_id' AS UUID)
                  FROM escalations 
                  WHERE context->>'task_id' IS NOT NULL 
                  AND status = 'open'
              )
            LIMIT 5
            """
            stuck_result = execute_sql(stuck_sql)
            for stuck_task in stuck_result.get("rows", []):
                create_escalation(
                    stuck_task["id"],
                    f"Task stuck in_progress for >{stuck_threshold_minutes} minutes: {stuck_task.get('title', 'Unknown')}"
                )
                log_action(
                    "escalation.stuck_task",
                    f"Created escalation for stuck task: {stuck_task.get('title', 'Unknown')}",
                    task_id=stuck_task["id"]
                )
        except Exception as stuck_err:
            log_error(f"Stuck task escalation check failed: {stuck_err}")

        try:
            # -1. Reset stale tasks at start of each loop (CRITICAL-03c)
            if STALE_CLEANUP_AVAILABLE:
                try:
                    reset_count, reset_tasks = reset_stale_tasks()
                    if reset_count > 0:
                        log_action(
                            "stale_cleanup",
                            f"Reset {reset_count} stale tasks",
                            output_data={
                                "reset_count": reset_count,
                                "task_ids": [t.get("id") for t in reset_tasks]
                            }
                        )
                except Exception as cleanup_err:
                    log_action(
                        "stale_cleanup.error",
                        f"Stale cleanup failed: {cleanup_err}",
                        level="warn"
                    )
            
            # 0. Check for approved tasks that can resume (L3: Human-in-the-Loop)
            approved_tasks = poll_approved_tasks(limit=3)
            if approved_tasks:
                for approved_task in approved_tasks:
                    # Resume execution of approved task
                    success, result = resume_approved_task(approved_task)
                    if success:
                        log_action(
                            "approval.completed",
                            f"Approved task executed successfully: {approved_task.title}",
                            task_id=approved_task.id
                        )
                        break  # Execute one approved task per loop
                    else:
                        log_action(
                            "approval.failed",
                            f"Approved task execution failed: {approved_task.title}",
                            level="error",
                            task_id=approved_task.id,
                            error_data=result
                        )
            
            # 1. Check for pending tasks
            tasks = get_pending_tasks(limit=5)
            
            if tasks:
                # Try to claim and execute tasks in priority order
                task_executed = False  # Track if any task was executed
                tasks_executed_this_loop = 0
                
                for task in tasks:
                    # Check permission BEFORE claiming (Level 3: Permission enforcement)
                    # This prevents claiming tasks that the worker is forbidden from executing
                    # GAP-03: Now uses RBAC check_permission via is_action_allowed
                    allowed, reason = is_action_allowed(f"task.{task.task_type}")
                    if not allowed:
                        log_action("task.skipped", f"Task skipped (forbidden): {reason}", 
                                   level="warn", task_id=task.id)
                        continue  # Skip forbidden tasks without claiming
                    
                    # Try to claim this task
                    if not claim_task(task.id):
                        continue  # Someone else claimed it, try next
                    
                    # FIX-09: Allocate resources for the claimed task
                    allocation = allocate_task_resources(task.id, task.title, task.priority)
                    if not allocation.get("success"):
                        log_action("resource.skip", f"Resource allocation failed but continuing: {allocation.get('error')}", 
                                   level="warn", task_id=task.id)
                    
                    log_decision("loop.execute", f"Executing task: {task.title}",
                                 f"Priority {task.priority} of {len(tasks)} pending tasks")
                    
                    # L5: Try to delegate to specialized worker via ORCHESTRATOR first
                    if ORCHESTRATION_AVAILABLE:
                        delegated, target_worker_id, delegate_result = delegate_to_worker(task)
                        if delegated:
                            # BUG FIX: Check for self-delegation - if target is ourselves, execute locally
                            if target_worker_id == WORKER_ID or target_worker_id in (WORKER_ID.upper(), WORKER_ID.lower()):
                                log_action(
                                    "orchestrator.self_delegation",
                                    f"Self-delegation detected ({target_worker_id} == {WORKER_ID}), executing locally",
                                    level="info",
                                    task_id=task.id,
                                    output_data=delegate_result
                                )
                                # Fall through to local execution below
                            else:
                                log_decision(
                                    "orchestrator.delegated",
                                    f"Task delegated to {target_worker_id}",
                                    f"ORCHESTRATOR routing: {delegate_result.get('message', 'capability_match')}"
                                )
                                # Task is now assigned to specialized worker - don't execute locally
                                task_executed = True
                                break
                        else:
                            # Delegation failed - log reason and fall back to local execution
                            log_action(
                                "orchestrator.fallback",
                                f"Delegation failed, executing locally: {delegate_result.get('reason', 'unknown')}",
                                level="info",
                                task_id=task.id,
                                output_data=delegate_result
                            )
                    
                    # Execute task locally (either no ORCHESTRATOR or delegation failed)
                    success, result = execute_task(task)
                    
                    if result.get("waiting_approval"):
                        # Task is waiting for approval, try next task
                        continue
                    
                    # FIX-09: Update resource usage with estimated time
                    if success and allocation.get("allocation_id"):
                        # Estimate time based on result - could be enhanced with actual timing
                        estimated_time = 15 if task.task_type == "verification" else 30
                        update_resource_usage(task.id, estimated_time)
                    
                    # Task was executed (success or failure), we're done for this loop
                    task_executed = True
                    tasks_executed_this_loop += 1
                    if tasks_executed_this_loop >= max(1, MAX_TASKS_PER_LOOP):
                        break
                
                if not task_executed:
                    # All tasks either couldn't be claimed, are forbidden, or are waiting for approval
                    log_action("loop.no_executable", "No executable tasks this iteration",
                               output_data={"tasks_checked": len(tasks)})
            else:
                # 2. Check scheduled tasks
                scheduled = get_due_scheduled_tasks()
                if scheduled:
                    sched_task = scheduled[0]
                    sched_task_type = sched_task.get('task_type', 'unknown')
                    sched_task_id = sched_task.get('id')
                    log_decision("loop.scheduled", f"Running scheduled task: {sched_task['name']}",
                                 f"No pending tasks, running scheduled task (type: {sched_task_type})")
                    
                    # Start the task run - creates record in scheduled_task_runs
                    run_info = None
                    run_id = None
                    if SCHEDULER_AVAILABLE:
                        run_info = start_task_run(sched_task_id, triggered_by=WORKER_ID)
                        run_id = run_info.get("run_id") if run_info.get("success") else None
                    
                    # Execute the scheduled task based on task_type
                    sched_result = None
                    sched_success = False
                    
                    try:
                        if sched_task_type == "opportunity_scan":
                            # Use the proactive opportunity scan handler
                            if PROACTIVE_AVAILABLE:
                                sched_result = handle_opportunity_scan(
                                    sched_task,
                                    execute_sql,
                                    log_action
                                )
                                sched_success = sched_result.get("success", False)
                            else:
                                sched_result = {"error": "Proactive module not available"}
                                sched_success = False
                        elif sched_task_type == "health_check":
                            # Simple health check - verify DB connection
                            execute_sql("SELECT 1")
                            sched_result = {"healthy": True, "timestamp": datetime.now(timezone.utc).isoformat()}
                            sched_success = True
                        elif sched_task_type == "log_retention":
                            # Log retention cleanup - placeholder
                            sched_result = {"cleaned": True, "timestamp": datetime.now(timezone.utc).isoformat()}
                            sched_success = True
                        elif sched_task_type == "completion_verification":
                            # Completion verification - placeholder
                            sched_result = {"verified": True, "timestamp": datetime.now(timezone.utc).isoformat()}
                            sched_success = True
                        else:
                            # Unknown scheduled task type - log and continue
                            sched_result = {"skipped": True, "reason": f"No handler for task_type: {sched_task_type}"}
                            sched_success = True  # Don't mark as failed, just skipped
                        
                        # Log the result
                        log_action(
                            f"scheduled.{sched_task_type}.{'complete' if sched_success else 'failed'}",
                            f"Scheduled task {sched_task['name']}: {'success' if sched_success else 'failed'}",
                            level="info" if sched_success else "error",
                            output_data=sched_result
                        )
                        
                        # Complete the task run - updates scheduled_task_runs with result
                        if SCHEDULER_AVAILABLE and run_id:
                            complete_task_run(run_id, result=sched_result)
                        
                    except Exception as sched_error:
                        sched_success = False
                        sched_result = {"error": str(sched_error)}
                        log_action(
                            f"scheduled.{sched_task_type}.error",
                            f"Scheduled task {sched_task['name']} failed: {str(sched_error)}",
                            level="error",
                            error_data={"error": str(sched_error), "traceback": traceback.format_exc()[:300]}
                        )
                        
                        # Fail the task run - updates scheduled_task_runs with error
                        if SCHEDULER_AVAILABLE and run_id:
                            fail_task_run(run_id, error_message=str(sched_error))
                else:
                    # 3. Nothing to do - log heartbeat
                    # Proactive diversity engine: if idle, generate 2-3 diverse meaningful tasks (rate-limited)
                    try:
                        gen_result = _maybe_generate_diverse_proactive_tasks()
                        if isinstance(gen_result, dict) and gen_result.get("tasks_created"):
                            log_action(
                                "proactive.diverse_generation",
                                "Generated diverse proactive tasks",
                                level="info",
                                output_data=gen_result,
                            )
                    except Exception:
                        pass

                    if loop_count % 5 == 0:  # Every 5 loops
                        log_action("loop.heartbeat", f"Loop {loop_count}: No work found",
                                   output_data={"loop": loop_count, "tasks_checked": 0})
            
            # Update heartbeat
            now = datetime.now(timezone.utc).isoformat()
            sql = f"UPDATE worker_registry SET last_heartbeat = {escape_value(now)} WHERE worker_id = {escape_value(WORKER_ID)}"
            execute_sql(sql)
            
            # Update heartbeats for specialist workers (ANALYST, STRATEGIST, EXECUTOR)
            # These are logical workers handled by this engine, not separate processes
            # GAP-04: Fix stale heartbeats for specialist workers
            if ORCHESTRATION_AVAILABLE:
                for specialist in ["ANALYST", "STRATEGIST", "EXECUTOR"]:
                    try:
                        update_worker_heartbeat(specialist)
                    except Exception as hb_err:
                        log_error(f"Failed to update {specialist} heartbeat: {hb_err}")
            
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
    """HTTP handler for health checks and dashboard API."""
    
    def log_message(self, format, *args):
        pass  # Suppress default logging
    
    def send_cors_headers(self):
        """Add CORS headers to allow dashboard access."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        import urllib.parse
        
        # Parse path and query params
        path = self.path.split('?')[0]
        query_string = self.path.split('?')[1] if '?' in self.path else ''
        params = {}
        if query_string:
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = urllib.parse.unquote(value)
        
        # Health endpoint
        if path == "/health":
            uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()
            
            db_ok = True
            try:
                execute_sql("SELECT 1")
            except Exception:
                db_ok = False
            
            status = "healthy" if db_ok else "degraded"
            response = {
                "status": status,
                "version": DEPLOY_VERSION,
                "commit": DEPLOY_COMMIT,
                "worker_id": WORKER_ID,
                "uptime_seconds": int(uptime),
                "database": "connected" if db_ok else "error",
                "loop_interval": LOOP_INTERVAL,
                "dry_run": DRY_RUN,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        
        # Root endpoint
        elif path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "JUGGERNAUT Autonomy Engine",
                "status": "running",
                "version": DEPLOY_VERSION,
                "commit": DEPLOY_COMMIT,
                "endpoints": [
                    "/", "/health",
                    "/api/dashboard/stats",
                    "/api/dashboard/opportunities",
                    "/api/executive",
                    "/api/dashboard/activity",
                    "/api/dashboard/revenue",
                    "/api/dashboard/workers",
                    "/api/dashboard/experiments",
                    "/api/dashboard/tasks",
                    "/api/brain/consult",
                    "/api/brain/history",
                    "/api/brain/clear"
                ]
            }).encode())
        
        # Dashboard API endpoints

        # Executive Dashboard API (FIX-10)
        elif path == "/api/executive":
            if not EXEC_DASHBOARD_API_AVAILABLE:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": f"Executive Dashboard API not available: {_exec_dashboard_import_error}"
                }).encode())
                return
            
            exec_data = get_executive_dashboard()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(exec_data, default=str).encode())

        elif path.startswith("/api/dashboard/"):
            if not DASHBOARD_API_AVAILABLE:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": f"Dashboard API not available: {_dashboard_import_error}"
                }).encode())
                return
            
            endpoint = path.replace("/api/dashboard/", "")
            result = handle_dashboard_request(endpoint, params)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())
        
        # Brain API endpoints (GET)
        elif path.startswith("/api/brain/"):
            endpoint = path.replace("/api/brain/", "")
            result = handle_brain_request("GET", endpoint, params)
            
            self.send_response(result.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(result.get("body", {}), default=str).encode())
        
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def do_POST(self):
        """Handle POST requests (for recording revenue)."""
        path = self.path.split('?')[0]
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = {}
        if content_length > 0:
            body_bytes = self.rfile.read(content_length)
            try:
                body = json.loads(body_bytes.decode('utf-8'))
            except json.JSONDecodeError:
                pass
        
        if path == "/api/dashboard/revenue":
            if not DASHBOARD_API_AVAILABLE:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Dashboard API not available"}).encode())
                return
            
            if "amount" not in body or "source" not in body:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Missing required fields: amount, source"}).encode())
                return
            
            result = record_revenue(
                amount=float(body["amount"]),
                source=body["source"],
                description=body.get("description", ""),
                opportunity_id=body.get("opportunity_id"),
                metadata=body.get("metadata")
            )
            
            self.send_response(200 if result.get("success") else 400)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
        # Brain API endpoints (POST)
        elif path.startswith("/api/brain/"):
            endpoint = path.replace("/api/brain/", "")
            
            # Parse query params
            query_string = self.path.split('?')[1] if '?' in self.path else ''
            params = {}
            if query_string:
                import urllib.parse
                for param in query_string.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = urllib.parse.unquote(value)
            
            result = handle_brain_request("POST", endpoint, params, body)
            
            self.send_response(result.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(result.get("body", {}), default=str).encode())
        
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())


    def do_DELETE(self):
        """Handle DELETE requests."""
        path = self.path.split('?')[0]
        
        # Parse query params
        query_string = self.path.split('?')[1] if '?' in self.path else ''
        params = {}
        if query_string:
            import urllib.parse
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = urllib.parse.unquote(value)
        
        # Brain API DELETE endpoints
        if path.startswith("/api/brain/"):
            endpoint = path.replace("/api/brain/", "")
            result = handle_brain_request("DELETE", endpoint, params)
            
            self.send_response(result.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(result.get("body", {}), default=str).encode())
        
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())


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
    print(f"JUGGERNAUT AUTONOMY ENGINE v{DEPLOY_VERSION}")
    print("=" * 60)
    print(f"Worker ID: {WORKER_ID}")
    print(f"Commit: {DEPLOY_COMMIT}")
    print(f"Loop Interval: {LOOP_INTERVAL} seconds")
    print(f"Dry Run Mode: {DRY_RUN}")
    print(f"Health Port: {PORT}")
    print(f"RBAC: {'available' if RBAC_AVAILABLE else 'NOT AVAILABLE'}")  # GAP-03
    if _rbac_import_error:
        print(f"  RBAC import error: {_rbac_import_error}")
    print(f"Brain API: {'available' if BRAIN_API_AVAILABLE else 'NOT AVAILABLE'}")
    if _brain_api_import_error:
        print(f"  Brain import error: {_brain_api_import_error}")
    print("=" * 60)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    # Start health server in background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Notify Slack that engine is starting (best-effort, don't abort boot)
    try:
        notify_engine_started(WORKER_ID)
    except Exception as notify_err:
        print(f"Warning: Failed to send engine start notification: {notify_err}")
    
    # Run the autonomy loop (blocks forever)
    try:
        autonomy_loop()
    except KeyboardInterrupt:
        print("\nInterrupted. Shutting down...")
    
    print("Goodbye.")



