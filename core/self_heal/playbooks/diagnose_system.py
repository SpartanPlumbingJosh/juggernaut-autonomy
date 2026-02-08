"""
Diagnose System Playbook

Comprehensive system health diagnosis:
- Worker status and availability
- Task queue health
- Recent error patterns
- Database connectivity
- API responsiveness

Part of Milestone 2: Self-Heal Workflows
"""

from typing import List
from core.self_heal.playbook import DiagnosisPlaybook, PlaybookStep, StepType
from core.database import execute_sql, fetch_all
import logging

logger = logging.getLogger(__name__)


class DiagnoseSystemPlaybook(DiagnosisPlaybook):
    """Diagnose overall system health."""
    
    def get_name(self) -> str:
        return "diagnose_system"
    
    def get_description(self) -> str:
        return "Comprehensive system health diagnosis checking workers, queues, errors, and connectivity"
    
    def build_steps(self) -> List[PlaybookStep]:
        """Build diagnosis steps."""
        return [
            PlaybookStep(
                name="check_database_connectivity",
                step_type=StepType.CHECK,
                description="Verify database is accessible and responsive",
                action=self._check_database,
                safe=True,
                required=True
            ),
            PlaybookStep(
                name="check_worker_status",
                step_type=StepType.QUERY,
                description="Check worker online status and last heartbeat",
                action=self._check_workers,
                safe=True,
                required=True
            ),
            PlaybookStep(
                name="check_task_queue",
                step_type=StepType.QUERY,
                description="Analyze task queue for blocked or stuck tasks",
                action=self._check_task_queue,
                safe=True,
                required=True
            ),
            PlaybookStep(
                name="check_recent_errors",
                step_type=StepType.QUERY,
                description="Identify error patterns in recent logs",
                action=self._check_recent_errors,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="check_task_completion_rate",
                step_type=StepType.QUERY,
                description="Calculate task success/failure rates",
                action=self._check_completion_rate,
                safe=True,
                required=False
            ),
            PlaybookStep(
                name="check_system_resources",
                step_type=StepType.CHECK,
                description="Check for resource constraints or bottlenecks",
                action=self._check_resources,
                safe=True,
                required=False
            )
        ]
    
    def _check_database(self) -> dict:
        """Check database connectivity."""
        try:
            result = fetch_all("SELECT 1 as test")
            self.add_finding("database_status", "healthy", "info")
            return {"status": "healthy", "responsive": True}
        except Exception as e:
            self.add_finding("database_status", f"error: {str(e)}", "critical")
            return {"status": "error", "error": str(e)}
    
    def _check_workers(self) -> dict:
        """Check worker status."""
        try:
            query = """
                SELECT 
                    worker_id,
                    status,
                    last_heartbeat,
                    EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
                FROM workers
                ORDER BY last_heartbeat DESC
            """
            workers = fetch_all(query)
            
            if not workers:
                self.add_finding("workers_status", "No workers table or no workers found", "warning")
                return {"total": 0, "online": 0, "offline": 0, "stale": 0, "workers": []}
            
            online_workers = [w for w in workers if w.get('status') == 'online']
            offline_workers = [w for w in workers if w.get('status') != 'online']
            stale_workers = [w for w in workers if float(w.get('seconds_since_heartbeat') or 0) > 300]
            
            self.add_finding("workers_online", len(online_workers), "info")
            self.add_finding("workers_offline", len(offline_workers), 
                           "warning" if offline_workers else "info")
            self.add_finding("workers_stale", len(stale_workers),
                           "warning" if stale_workers else "info")
            
            return {
                "total": len(workers),
                "online": len(online_workers),
                "offline": len(offline_workers),
                "stale": len(stale_workers),
                "workers": workers
            }
        except Exception as e:
            logger.exception(f"Error checking workers: {e}")
            self.add_finding("workers_check_error", str(e), "critical")
            return {"error": str(e)}
    
    def _check_task_queue(self) -> dict:
        """Check task queue health."""
        try:
            query = """
                SELECT 
                    status,
                    COUNT(*) as count,
                    MIN(created_at) as oldest_task
                FROM governance_tasks
                WHERE status IN ('pending', 'running', 'blocked', 'waiting_approval')
                GROUP BY status
            """
            queue_stats = fetch_all(query)
            
            # Check for blocked tasks
            blocked_query = """
                SELECT COUNT(*) as count
                FROM governance_tasks
                WHERE status = 'blocked'
                AND created_at < NOW() - INTERVAL '1 hour'
            """
            blocked_result = fetch_all(blocked_query)
            blocked_count = int(blocked_result[0].get('count', 0)) if blocked_result else 0
            
            # Check for stuck running tasks
            stuck_query = """
                SELECT COUNT(*) as count
                FROM governance_tasks
                WHERE status = 'running'
                AND updated_at < NOW() - INTERVAL '30 minutes'
            """
            stuck_result = fetch_all(stuck_query)
            stuck_count = int(stuck_result[0].get('count', 0)) if stuck_result else 0
            
            self.add_finding("blocked_tasks", blocked_count,
                           "critical" if blocked_count > 10 else "warning" if blocked_count > 0 else "info")
            self.add_finding("stuck_tasks", stuck_count,
                           "warning" if stuck_count > 0 else "info")
            
            return {
                "queue_stats": queue_stats,
                "blocked_count": blocked_count,
                "stuck_count": stuck_count
            }
        except Exception as e:
            logger.exception(f"Error checking task queue: {e}")
            self.add_finding("queue_check_error", str(e), "critical")
            return {"error": str(e)}
    
    def _check_recent_errors(self) -> dict:
        """Check recent error patterns."""
        try:
            query = """
                SELECT 
                    level,
                    message,
                    COUNT(*) as count
                FROM dashboard_logs
                WHERE level IN ('ERROR', 'CRITICAL')
                AND created_at > NOW() - INTERVAL '1 hour'
                GROUP BY level, message
                ORDER BY count DESC
                LIMIT 10
            """
            errors = fetch_all(query)
        except Exception as e:
            if "does not exist" in str(e):
                self.add_finding("recent_errors_check", "dashboard_logs table not found", "info")
                return {"total_errors": 0, "error_patterns": []}
            raise
        
        try:
            
            total_errors = sum(int(e.get('count', 0)) for e in errors)
            
            self.add_finding("recent_errors_1h", total_errors,
                           "critical" if total_errors > 50 else "warning" if total_errors > 10 else "info")
            
            return {
                "total_errors": total_errors,
                "error_patterns": errors
            }
        except Exception as e:
            logger.exception(f"Error checking recent errors: {e}")
            return {"error": str(e)}
    
    def _check_completion_rate(self) -> dict:
        """Check task completion rates."""
        try:
            query = """
                SELECT 
                    status,
                    COUNT(*) as count
                FROM governance_tasks
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY status
            """
            stats = fetch_all(query)
            
            completed = sum(int(s.get('count', 0)) for s in stats if s.get('status') == 'completed')
            failed = sum(int(s.get('count', 0)) for s in stats if s.get('status') == 'failed')
            total = sum(int(s.get('count', 0)) for s in stats)
            
            success_rate = (completed / total * 100) if total > 0 else 0
            
            self.add_finding("task_success_rate_24h", f"{success_rate:.1f}%",
                           "info" if success_rate > 80 else "warning" if success_rate > 50 else "critical")
            
            return {
                "completed": completed,
                "failed": failed,
                "total": total,
                "success_rate": success_rate
            }
        except Exception as e:
            logger.exception(f"Error checking completion rate: {e}")
            return {"error": str(e)}
    
    def _check_resources(self) -> dict:
        """Check for resource constraints."""
        try:
            # Check database connection pool
            pool_query = """
                SELECT 
                    count(*) as active_connections
                FROM pg_stat_activity
                WHERE datname = current_database()
            """
            pool_result = fetch_all(pool_query)
            active_connections = int(pool_result[0].get('active_connections', 0)) if pool_result else 0
            
            # Check table sizes (handle missing tables gracefully)
            table_sizes = {}
            try:
                size_query = """
                    SELECT 
                        pg_size_pretty(pg_total_relation_size('governance_tasks')) as tasks_size
                """
                size_result = fetch_all(size_query)
                if size_result:
                    table_sizes = size_result[0]
            except Exception as e:
                logger.warning(f"Could not get table sizes: {e}")
            
            self.add_finding("active_db_connections", active_connections,
                           "warning" if active_connections > 50 else "info")
            
            return {
                "active_connections": active_connections,
                "table_sizes": table_sizes
            }
        except Exception as e:
            logger.exception(f"Error checking resources: {e}")
            return {"error": str(e)}


__all__ = ["DiagnoseSystemPlaybook"]
