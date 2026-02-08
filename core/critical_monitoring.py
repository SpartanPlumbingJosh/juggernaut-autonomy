"""
Critical Issue Monitoring and Alerting

Monitors for critical system issues and raises loud warnings:
- Database connection failures
- Worker crashes
- High error rates
- Stuck tasks accumulating
- Self-heal failures
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CriticalMonitor:
    """Monitors for critical system issues and raises alerts."""
    
    def __init__(self, execute_sql: Callable, log_action: Callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
        # Thresholds for critical alerts
        self.error_rate_threshold = 50  # errors per hour
        self.stuck_task_threshold = 10
        self.worker_offline_threshold = 3  # minutes
        self.task_failure_rate_threshold = 0.5  # 50%
    
    def check_all(self) -> Dict[str, Any]:
        """Run all critical checks and return results."""
        issues = []
        
        # Check database connectivity
        db_issue = self._check_database()
        if db_issue:
            issues.append(db_issue)
        
        # Check worker health
        worker_issue = self._check_workers()
        if worker_issue:
            issues.append(worker_issue)
        
        # Check error rates
        error_issue = self._check_error_rates()
        if error_issue:
            issues.append(error_issue)
        
        # Check stuck tasks
        stuck_issue = self._check_stuck_tasks()
        if stuck_issue:
            issues.append(stuck_issue)
        
        # Check task failure rates
        failure_issue = self._check_failure_rates()
        if failure_issue:
            issues.append(failure_issue)
        
        # Log critical issues
        if issues:
            for issue in issues:
                self.log_action(
                    "critical_monitor.issue_detected",
                    issue["message"],
                    level="critical",
                    output_data=issue
                )
        
        return {
            "critical_issues": len(issues),
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _check_database(self) -> Optional[Dict[str, Any]]:
        """Check if database is responsive."""
        try:
            result = self.execute_sql("SELECT 1 as test")
            if not result or not result.get("rows"):
                return {
                    "type": "database_unresponsive",
                    "severity": "critical",
                    "message": "Database query returned no results"
                }
            return None
        except Exception as e:
            return {
                "type": "database_connection_failed",
                "severity": "critical",
                "message": f"Database connection failed: {str(e)[:200]}",
                "error": str(e)
            }
    
    def _check_workers(self) -> Optional[Dict[str, Any]]:
        """Check if workers are online and healthy."""
        try:
            # Use SQL to do the datetime comparison, not Python
            result = self.execute_sql(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE last_heartbeat >= NOW() - INTERVAL '{self.worker_offline_threshold} minutes') as online
                FROM worker_registry
            """)
            
            rows = result.get("rows", [])
            if not rows:
                return {
                    "type": "no_workers_found",
                    "severity": "critical",
                    "message": "No workers found in registry"
                }
            
            total = rows[0].get("total", 0)
            online = rows[0].get("online", 0)
            try:
                total = int(total or 0)
            except (TypeError, ValueError):
                total = 0
            try:
                online = int(online or 0)
            except (TypeError, ValueError):
                online = 0
            
            if total == 0:
                return {
                    "type": "no_workers_registered",
                    "severity": "critical",
                    "message": "No workers registered in system"
                }
            
            if online == 0:
                return {
                    "type": "all_workers_offline",
                    "severity": "critical",
                    "message": f"All {total} workers are offline (no heartbeat in {self.worker_offline_threshold} min)",
                    "total_workers": total
                }
            
            offline_pct = ((total - online) / total) * 100
            if offline_pct > 50:
                return {
                    "type": "majority_workers_offline",
                    "severity": "critical",
                    "message": f"{offline_pct:.0f}% of workers offline ({total-online}/{total})",
                    "total_workers": total,
                    "online_workers": online
                }
            
            return None
            
        except Exception as e:
            logger.exception(f"Worker check failed: {e}")
            return {
                "type": "worker_check_failed",
                "severity": "critical",
                "message": f"Failed to check worker status: {str(e)[:200]}",
                "error": str(e)
            }
    
    def _check_error_rates(self) -> Optional[Dict[str, Any]]:
        """Check if error rate is critically high."""
        try:
            result = self.execute_sql("""
                SELECT COUNT(*) as error_count
                FROM execution_logs
                WHERE level IN ('error', 'critical')
                  AND created_at >= NOW() - INTERVAL '1 hour'
            """)
            
            rows = result.get("rows", [])
            if not rows:
                return None
            
            error_count = rows[0].get("error_count", 0)
            try:
                error_count = int(error_count or 0)
            except (TypeError, ValueError):
                error_count = 0
            
            if error_count >= self.error_rate_threshold:
                return {
                    "type": "high_error_rate",
                    "severity": "critical",
                    "message": f"Critical error rate: {error_count} errors in last hour (threshold: {self.error_rate_threshold})",
                    "error_count": error_count,
                    "threshold": self.error_rate_threshold
                }
            
            return None
            
        except Exception as e:
            logger.exception(f"Error rate check failed: {e}")
            return None
    
    def _check_stuck_tasks(self) -> Optional[Dict[str, Any]]:
        """Check if tasks are accumulating in stuck states."""
        try:
            result = self.execute_sql("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'blocked') as blocked,
                    COUNT(*) FILTER (WHERE status = 'in_progress' 
                                     AND updated_at < NOW() - INTERVAL '30 minutes') as stuck_in_progress
                FROM governance_tasks
            """)
            
            rows = result.get("rows", [])
            if not rows:
                return None
            
            blocked = rows[0].get("blocked", 0)
            stuck = rows[0].get("stuck_in_progress", 0)
            try:
                blocked = int(blocked or 0)
            except (TypeError, ValueError):
                blocked = 0
            try:
                stuck = int(stuck or 0)
            except (TypeError, ValueError):
                stuck = 0
            total_stuck = blocked + stuck
            
            if total_stuck >= self.stuck_task_threshold:
                return {
                    "type": "tasks_accumulating",
                    "severity": "critical",
                    "message": f"{total_stuck} tasks stuck (blocked: {blocked}, in_progress>30min: {stuck})",
                    "blocked_count": blocked,
                    "stuck_count": stuck,
                    "threshold": self.stuck_task_threshold
                }
            
            return None
            
        except Exception as e:
            logger.exception(f"Stuck task check failed: {e}")
            return None
    
    def _check_failure_rates(self) -> Optional[Dict[str, Any]]:
        """Check if task failure rate is critically high."""
        try:
            result = self.execute_sql("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM governance_tasks
                WHERE updated_at >= NOW() - INTERVAL '24 hours'
                  AND status IN ('completed', 'failed')
            """)
            
            rows = result.get("rows", [])
            if not rows:
                return None
            
            completed = rows[0].get("completed", 0)
            failed = rows[0].get("failed", 0)
            try:
                completed = int(completed or 0)
            except (TypeError, ValueError):
                completed = 0
            try:
                failed = int(failed or 0)
            except (TypeError, ValueError):
                failed = 0
            total = completed + failed
            
            if total == 0:
                return None
            
            failure_rate = failed / total
            
            if failure_rate >= self.task_failure_rate_threshold:
                return {
                    "type": "high_failure_rate",
                    "severity": "critical",
                    "message": f"Task failure rate: {failure_rate*100:.1f}% ({failed}/{total} in 24h)",
                    "completed": completed,
                    "failed": failed,
                    "failure_rate": failure_rate,
                    "threshold": self.task_failure_rate_threshold
                }
            
            return None
            
        except Exception as e:
            logger.exception(f"Failure rate check failed: {e}")
            return None


def check_critical_issues(execute_sql: Callable, log_action: Callable) -> Dict[str, Any]:
    """Entry point for critical monitoring - called by orchestrator.
    
    Args:
        execute_sql: SQL execution function
        log_action: Logging function
    
    Returns:
        Dict with critical issues found.
    """
    monitor = CriticalMonitor(execute_sql, log_action)
    return monitor.check_all()
