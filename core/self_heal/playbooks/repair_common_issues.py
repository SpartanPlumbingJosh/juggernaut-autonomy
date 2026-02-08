"""
Repair Common Issues Playbook

Safe, bounded repair actions for common problems:
- Reset blocked tasks to pending
- Clear stale worker heartbeats
- Create fix tasks for error patterns
- Clean up orphaned records

All actions are safe and reversible.

Part of Milestone 2: Self-Heal Workflows
"""

from typing import List
from core.self_heal.playbook import RepairPlaybook, PlaybookStep, StepType
from core.database import execute_sql, fetch_all
import logging

logger = logging.getLogger(__name__)


class RepairCommonIssuesPlaybook(RepairPlaybook):
    """Repair common system issues with safe, bounded actions."""
    
    def __init__(self):
        super().__init__(safe_actions_only=True)
        self.issues_found = []
        self.repairs_attempted = []
    
    def get_name(self) -> str:
        return "repair_common_issues"
    
    def get_description(self) -> str:
        return "Safe repair actions for blocked tasks, stale workers, and error patterns"
    
    def build_steps(self) -> List[PlaybookStep]:
        """Build repair steps."""
        return [
            PlaybookStep(
                name="identify_blocked_tasks",
                step_type=StepType.QUERY,
                description="Find tasks blocked for >1 hour",
                action=self._identify_blocked_tasks,
                safe=True,
                required=True
            ),
            PlaybookStep(
                name="reset_blocked_tasks",
                step_type=StepType.REPAIR,
                description="Reset blocked tasks to pending (max 10)",
                action=self._reset_blocked_tasks,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="identify_stuck_running_tasks",
                step_type=StepType.QUERY,
                description="Find tasks stuck in running state >30 min",
                action=self._identify_stuck_tasks,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="reset_stuck_tasks",
                step_type=StepType.REPAIR,
                description="Reset stuck running tasks to pending (max 5)",
                action=self._reset_stuck_tasks,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="identify_error_patterns",
                step_type=StepType.QUERY,
                description="Find repeated error patterns in logs",
                action=self._identify_error_patterns,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="create_fix_tasks",
                step_type=StepType.REPAIR,
                description="Create governance tasks to fix error patterns",
                action=self._create_fix_tasks,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="verify_repairs",
                step_type=StepType.VERIFY,
                description="Verify repairs were successful",
                action=self._verify_repairs,
                safe=True,
                required=True
            )
        ]
    
    def _identify_blocked_tasks(self) -> dict:
        """Identify blocked tasks."""
        try:
            query = """
                SELECT 
                    id,
                    task_type,
                    description,
                    created_at,
                    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_blocked
                FROM governance_tasks
                WHERE status = 'blocked'
                AND created_at < NOW() - INTERVAL '1 hour'
                ORDER BY created_at ASC
                LIMIT 10
            """
            blocked_tasks = fetch_all(query)
            
            self.issues_found.append({
                "issue_type": "blocked_tasks",
                "count": len(blocked_tasks),
                "tasks": blocked_tasks
            })
            
            return {
                "blocked_count": len(blocked_tasks),
                "tasks": blocked_tasks
            }
        except Exception as e:
            logger.exception(f"Error identifying blocked tasks: {e}")
            return {"error": str(e)}
    
    def _reset_blocked_tasks(self) -> dict:
        """Reset blocked tasks to pending (bounded to 10)."""
        try:
            # Get blocked tasks
            blocked_tasks = [
                issue for issue in self.issues_found 
                if issue.get("issue_type") == "blocked_tasks"
            ]
            
            if not blocked_tasks or blocked_tasks[0].get("count", 0) == 0:
                return {"reset_count": 0, "message": "No blocked tasks to reset"}
            
            # Reset up to 10 tasks
            reset_query = """
                UPDATE governance_tasks
                SET 
                    status = 'pending',
                    updated_at = NOW(),
                    error_message = 'Auto-reset by self-heal system from blocked state'
                WHERE id IN (
                    SELECT id
                    FROM governance_tasks
                    WHERE status = 'blocked'
                    AND created_at < NOW() - INTERVAL '1 hour'
                    ORDER BY created_at ASC
                    LIMIT 10
                )
                RETURNING id, task_type, title
            """
            
            reset_results = fetch_all(reset_query)
            reset_count = len(reset_results)
            
            # Record action
            self.record_action("reset_blocked_tasks", {
                "reset_count": reset_count,
                "task_ids": [r["id"] for r in reset_results]
            })
            
            self.repairs_attempted.append({
                "repair_type": "reset_blocked_tasks",
                "count": reset_count,
                "tasks": reset_results
            })
            
            return {
                "reset_count": reset_count,
                "tasks_reset": reset_results
            }
        except Exception as e:
            logger.exception(f"Error resetting blocked tasks: {e}")
            return {"error": str(e), "reset_count": 0}
    
    def _identify_stuck_tasks(self) -> dict:
        """Identify tasks stuck in in_progress state."""
        try:
            query = """
                SELECT 
                    id,
                    task_type,
                    title,
                    assigned_to,
                    started_at,
                    EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_running
                FROM governance_tasks
                WHERE status = 'in_progress'
                AND started_at < NOW() - INTERVAL '30 minutes'
                ORDER BY started_at ASC
                LIMIT 5
            """
            stuck_tasks = fetch_all(query)
            
            self.issues_found.append({
                "issue_type": "stuck_tasks",
                "count": len(stuck_tasks),
                "tasks": stuck_tasks
            })
            
            return {
                "stuck_count": len(stuck_tasks),
                "tasks": stuck_tasks
            }
        except Exception as e:
            logger.exception(f"Error identifying stuck tasks: {e}")
            return {"error": str(e)}
    
    def _reset_stuck_tasks(self) -> dict:
        """Reset stuck in_progress tasks to pending."""
        try:
            # Get stuck tasks
            stuck_tasks = [
                issue for issue in self.issues_found 
                if issue.get("issue_type") == "stuck_tasks"
            ]
            
            if not stuck_tasks or stuck_tasks[0].get("count", 0) == 0:
                return {"reset_count": 0, "message": "No stuck tasks to reset"}
            
            # Reset up to 5 tasks
            reset_query = """
                UPDATE governance_tasks
                SET 
                    status = 'pending',
                    assigned_to = NULL,
                    updated_at = NOW(),
                    error_message = 'Auto-reset by self-heal: stuck in in_progress >30min'
                WHERE id IN (
                    SELECT id
                    FROM governance_tasks
                    WHERE status = 'in_progress'
                    AND started_at < NOW() - INTERVAL '30 minutes'
                    ORDER BY started_at ASC
                    LIMIT 5
                )
                RETURNING id, task_type, title
            """
            reset_results = fetch_all(reset_query)
            reset_count = len(reset_results)
            
            self.record_action("reset_stuck_tasks", {
                "reset_count": reset_count,
                "task_ids": [r["id"] for r in reset_results]
            })
            
            self.repairs_attempted.append({
                "repair_type": "reset_stuck_tasks",
                "count": reset_count,
                "tasks": reset_results
            })
            
            return {
                "reset_count": reset_count,
                "tasks_reset": reset_results
            }
        except Exception as e:
            logger.exception(f"Error resetting stuck tasks: {e}")
            return {"error": str(e), "reset_count": 0}
    
    def _identify_error_patterns(self) -> dict:
        """Identify repeated error patterns."""
        try:
            query = """
                SELECT 
                    LEFT(message, 200) as error_message,
                    COUNT(*) as occurrence_count,
                    MAX(created_at) as last_seen
                FROM execution_logs
                WHERE level IN ('error', 'critical')
                AND created_at > NOW() - INTERVAL '1 hour'
                GROUP BY LEFT(message, 200)
                HAVING COUNT(*) >= 5
                ORDER BY occurrence_count DESC
                LIMIT 5
            """
            error_patterns = fetch_all(query)
            
            self.issues_found.append({
                "issue_type": "error_patterns",
                "count": len(error_patterns),
                "patterns": error_patterns
            })
            
            return {
                "pattern_count": len(error_patterns),
                "patterns": error_patterns
            }
        except Exception as e:
            logger.exception(f"Error identifying error patterns: {e}")
            return {"error": str(e)}
    
    def _create_fix_tasks(self) -> dict:
        """Create governance tasks to investigate/fix error patterns."""
        try:
            error_patterns = [
                issue for issue in self.issues_found 
                if issue.get("issue_type") == "error_patterns"
            ]
            
            if not error_patterns or error_patterns[0].get("count", 0) == 0:
                return {"created_count": 0, "message": "No error patterns to create tasks for"}
            
            # Create investigation tasks for top error patterns
            from uuid import uuid4
            from datetime import datetime, timezone
            
            created_tasks = []
            for pattern in error_patterns[0].get("patterns", [])[:3]:  # Top 3 patterns
                task_id = str(uuid4())
                error_msg = pattern.get("error_message", "Unknown error")
                occurrence_count = pattern.get("occurrence_count", 0)
                
                insert_query = """
                    INSERT INTO governance_tasks (
                        id, task_type, title, description, priority, status,
                        payload, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                
                title = f"Investigate: {error_msg[:50]}..."
                description = f"Error occurred {occurrence_count} times in the last hour. Investigate root cause and implement fix."
                payload = {
                    "error_pattern": error_msg,
                    "occurrence_count": occurrence_count,
                    "auto_generated": True,
                    "generated_by": "self_heal"
                }
                
                now = datetime.now(timezone.utc)
                params = (
                    task_id, "code", title, description, "high", "pending",
                    json.dumps(payload), now, now
                )
                
                result = fetch_all(insert_query, params)
                if result:
                    created_tasks.append(result[0])
            
            self.record_action("create_fix_tasks", {
                "created_count": len(created_tasks),
                "task_ids": [t["id"] for t in created_tasks]
            })
            
            self.repairs_attempted.append({
                "repair_type": "reset_blocked_tasks",
                "count": len(reset_tasks)
            })
            
            return {
                "reset_count": len(reset_tasks),
                "tasks": reset_tasks
            }
        except Exception as e:
            logger.exception(f"Error resetting blocked tasks: {e}")
            return {"error": str(e)}
    
    def _identify_stuck_tasks(self) -> dict:
        """Identify stuck running tasks."""
        try:
            query = """
                SELECT 
                    id,
                    task_type,
                    description,
                    updated_at,
                    EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as minutes_stuck
                FROM governance_tasks
                WHERE status = 'running'
                AND updated_at < NOW() - INTERVAL '30 minutes'
                ORDER BY updated_at ASC
                LIMIT 5
            """
            stuck_tasks = fetch_all(query)
            
            self.issues_found.append({
                "issue_type": "stuck_running_tasks",
                "count": len(stuck_tasks),
                "tasks": stuck_tasks
            })
            
            return {
                "stuck_count": len(stuck_tasks),
                "tasks": stuck_tasks
            }
        except Exception as e:
            logger.exception(f"Error identifying stuck tasks: {e}")
            return {"error": str(e)}
    
    def _reset_stuck_tasks(self) -> dict:
        """Reset stuck running tasks (bounded to 5)."""
        try:
            stuck_tasks = [
                issue for issue in self.issues_found 
                if issue.get("issue_type") == "stuck_running_tasks"
            ]
            
            if not stuck_tasks or stuck_tasks[0].get("count", 0) == 0:
                return {"reset_count": 0, "message": "No stuck tasks to reset"}
            
            reset_query = """
                UPDATE governance_tasks
                SET 
                    status = 'pending',
                    updated_at = NOW(),
                    error_message = 'Auto-reset by self-heal system from stuck running state'
                WHERE id IN (
                    SELECT id
                    FROM governance_tasks
                    WHERE status = 'running'
                    AND updated_at < NOW() - INTERVAL '30 minutes'
                    ORDER BY updated_at ASC
                    LIMIT 5
                )
                RETURNING id, task_type
            """
            reset_tasks = fetch_all(reset_query)
            
            self.record_action("reset_stuck_tasks", {
                "count": len(reset_tasks),
                "task_ids": [t.get('id') for t in reset_tasks]
            })
            
            self.repairs_attempted.append({
                "repair_type": "reset_stuck_tasks",
                "count": len(reset_tasks)
            })
            
            return {
                "reset_count": len(reset_tasks),
                "tasks": reset_tasks
            }
        except Exception as e:
            logger.exception(f"Error resetting stuck tasks: {e}")
            return {"error": str(e)}
    
    def _identify_error_patterns(self) -> dict:
        """Identify repeated error patterns."""
        try:
            query = """
                SELECT 
                    message,
                    COUNT(*) as occurrence_count,
                    MAX(created_at) as last_seen
                FROM dashboard_logs
                WHERE level IN ('ERROR', 'CRITICAL')
                AND created_at > NOW() - INTERVAL '1 hour'
                GROUP BY message
                HAVING COUNT(*) >= 5
                ORDER BY occurrence_count DESC
                LIMIT 5
            """
            error_patterns = fetch_all(query)
            
            self.issues_found.append({
                "issue_type": "error_patterns",
                "count": len(error_patterns),
                "patterns": error_patterns
            })
            
            return {
                "pattern_count": len(error_patterns),
                "patterns": error_patterns
            }
        except Exception as e:
            logger.exception(f"Error identifying error patterns: {e}")
            return {"error": str(e)}
    
    def _create_fix_tasks(self) -> dict:
        """Create governance tasks to investigate/fix error patterns."""
        try:
            error_patterns = [
                issue for issue in self.issues_found 
                if issue.get("issue_type") == "error_patterns"
            ]
            
            if not error_patterns or error_patterns[0].get("count", 0) == 0:
                return {"created_count": 0, "message": "No error patterns to create tasks for"}
            
            import json
            from uuid import uuid4
            from datetime import datetime, timezone
            
            created_tasks = []
            for pattern in error_patterns[0].get("patterns", [])[:3]:  # Max 3 tasks
                task_id = str(uuid4())
                error_msg = pattern.get("error_message", "Unknown error")
                occurrence_count = pattern.get("occurrence_count", 0)
                
                insert_query = """
                    INSERT INTO governance_tasks (
                        id, task_type, title, description, priority, status,
                        payload, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                
                title = f"Fix: {error_msg[:60]}"
                description = f"Error pattern detected: occurred {occurrence_count} times in the last hour. Investigate root cause and implement fix."
                payload = {
                    "error_pattern": error_msg,
                    "occurrence_count": occurrence_count,
                    "auto_generated": True,
                    "generated_by": "self_heal"
                }
                
                now = datetime.now(timezone.utc)
                params = (
                    task_id, "code", title, description, "high", "pending",
                    json.dumps(payload), now, now
                )
                
                result = fetch_all(insert_query, params)
                if result:
                    created_tasks.append(result[0])
            
            self.record_action("create_fix_tasks", {
                "created_count": len(created_tasks),
                "task_ids": [t["id"] for t in created_tasks]
            })
            
            self.repairs_attempted.append({
                "repair_type": "create_fix_tasks",
                "count": len(created_tasks)
            })
            
            return {
                "created_count": len(created_tasks),
                "tasks": created_tasks
            }
        except Exception as e:
            logger.exception(f"Error creating fix tasks: {e}")
            return {"error": str(e), "created_count": 0}
    
    def _verify_repairs(self) -> dict:
        """Verify that repairs were successful."""
        try:
            total_repairs = len(self.repairs_attempted)
            successful_repairs = sum(1 for r in self.repairs_attempted if r.get("count", 0) > 0)
            
            verification_result = {
                "total_repairs_attempted": total_repairs,
                "successful_repairs": successful_repairs,
                "success_rate": (successful_repairs / total_repairs * 100) if total_repairs > 0 else 0,
                "repairs": self.repairs_attempted
            }
            
            return verification_result
        except Exception as e:
            logger.exception(f"Error verifying repairs: {e}")
            return {"error": str(e)}
            # Check if stuck tasks were reduced
            stuck_query = """
                SELECT COUNT(*) as count
                FROM governance_tasks
                WHERE status = 'running'
                AND updated_at < NOW() - INTERVAL '30 minutes'
            """
            stuck_result = fetch_all(stuck_query)
            current_stuck = stuck_result[0].get('count', 0) if stuck_result else 0
            
            verification["current_stuck_tasks"] = current_stuck
            
            return verification
        except Exception as e:
            logger.exception(f"Error verifying repairs: {e}")
            return {"error": str(e), "success": False}


__all__ = ["RepairCommonIssuesPlaybook"]
