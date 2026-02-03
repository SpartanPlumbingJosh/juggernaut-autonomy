"""
Autonomy Loop

Continuously executes tasks without human intervention.

Part of Milestone 5: Engine Autonomy Restoration
"""

import logging
import time
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from threading import Thread, Event

from core.task_router import get_task_router
from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class AutonomyLoop:
    """Autonomous task execution loop."""
    
    def __init__(self):
        self.router = get_task_router()
        self.is_running = False
        self.stop_event = Event()
        self.thread = None
        self.loop_interval = 30  # seconds
    
    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending tasks ready for assignment."""
        try:
            query = """
                SELECT *
                FROM governance_tasks
                WHERE 
                    status = 'pending'
                    AND (
                        id NOT IN (
                            SELECT task_id 
                            FROM task_dependencies 
                            WHERE depends_on_task_id IN (
                                SELECT id FROM governance_tasks WHERE status != 'completed'
                            )
                        )
                    )
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
            """
            return fetch_all(query, (limit,))
        except Exception as e:
            logger.exception(f"Error getting pending tasks: {e}")
            return []
    
    def get_stuck_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks that appear stuck."""
        try:
            # Tasks assigned but not started in 10 minutes
            # Or tasks running but no update in 30 minutes
            query = """
                SELECT t.*, ta.assigned_at, ta.started_at, ta.worker_id
                FROM governance_tasks t
                JOIN task_assignments ta ON ta.task_id = t.id
                WHERE 
                    (
                        ta.status = 'assigned' 
                        AND ta.assigned_at < %s
                    )
                    OR
                    (
                        ta.status = 'running'
                        AND ta.started_at < %s
                    )
            """
            
            ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            thirty_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            
            return fetch_all(query, (ten_min_ago, thirty_min_ago))
        except Exception as e:
            logger.exception(f"Error getting stuck tasks: {e}")
            return []
    
    def handle_stuck_task(self, task: Dict[str, Any]):
        """Handle a stuck task by reassigning it."""
        try:
            task_id = str(task['id'])
            worker_id = task.get('worker_id')
            
            logger.warning(f"Handling stuck task {task_id} from worker {worker_id}")
            
            # Mark current assignment as failed
            fail_query = """
                UPDATE task_assignments
                SET 
                    status = 'failed',
                    completed_at = %s,
                    last_error = 'Task stuck - no progress'
                WHERE task_id = %s AND status IN ('assigned', 'running')
            """
            execute_sql(fail_query, (
                datetime.now(timezone.utc).isoformat(),
                task_id
            ))
            
            # Reset task to pending
            reset_query = """
                UPDATE governance_tasks
                SET 
                    status = 'pending',
                    updated_at = %s
                WHERE id = %s
            """
            execute_sql(reset_query, (
                datetime.now(timezone.utc).isoformat(),
                task_id
            ))
            
            # Mark worker as potentially unhealthy
            if worker_id:
                worker_query = """
                    UPDATE workers
                    SET 
                        status = 'idle',
                        current_task_id = NULL,
                        updated_at = %s
                    WHERE id = %s
                """
                execute_sql(worker_query, (
                    datetime.now(timezone.utc).isoformat(),
                    worker_id
                ))
            
            logger.info(f"Reset stuck task {task_id} to pending")
        except Exception as e:
            logger.exception(f"Error handling stuck task: {e}")
    
    def update_worker_heartbeats(self):
        """Mark workers as offline if no recent heartbeat."""
        try:
            # Workers with no heartbeat in 5 minutes → offline
            query = """
                UPDATE workers
                SET 
                    status = 'offline',
                    updated_at = %s
                WHERE 
                    status != 'offline'
                    AND last_heartbeat < %s
            """
            
            five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            execute_sql(query, (
                datetime.now(timezone.utc).isoformat(),
                five_min_ago
            ))
        except Exception as e:
            logger.exception(f"Error updating worker heartbeats: {e}")
    
    def update_loop_state(
        self,
        tasks_processed: int,
        tasks_assigned: int,
        duration_ms: int,
        error_message: str = None
    ):
        """Update autonomy loop state."""
        try:
            query = """
                UPDATE autonomy_state
                SET 
                    last_loop_at = %s,
                    tasks_processed = tasks_processed + %s,
                    tasks_assigned = tasks_assigned + %s,
                    loop_duration_ms = %s,
                    error_message = %s,
                    updated_at = %s
                WHERE id = (SELECT id FROM autonomy_state LIMIT 1)
            """
            execute_sql(query, (
                datetime.now(timezone.utc).isoformat(),
                tasks_processed,
                tasks_assigned,
                duration_ms,
                error_message,
                datetime.now(timezone.utc).isoformat()
            ))
        except Exception as e:
            logger.exception(f"Error updating loop state: {e}")
    
    def run_loop_iteration(self):
        """Run one iteration of the autonomy loop."""
        start_time = time.time()
        tasks_processed = 0
        tasks_assigned = 0
        error_message = None
        
        try:
            # 1. Get pending tasks
            pending_tasks = self.get_pending_tasks(limit=10)
            tasks_processed = len(pending_tasks)
            
            # 2. Route each task
            for task in pending_tasks:
                if self.stop_event.is_set():
                    break
                
                if self.router.route_task(task):
                    tasks_assigned += 1
            
            # 3. Handle stuck tasks
            stuck_tasks = self.get_stuck_tasks()
            for task in stuck_tasks:
                if self.stop_event.is_set():
                    break
                
                self.handle_stuck_task(task)
            
            # 4. Update worker heartbeats
            self.update_worker_heartbeats()
            
        except Exception as e:
            logger.exception(f"Error in loop iteration: {e}")
            error_message = str(e)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Update state
        self.update_loop_state(tasks_processed, tasks_assigned, duration_ms, error_message)
        
        logger.info(f"Loop iteration: {tasks_processed} tasks processed, {tasks_assigned} assigned, {duration_ms}ms")
    
    def run(self):
        """Run the autonomy loop continuously."""
        logger.info("Starting autonomy loop")
        
        while not self.stop_event.is_set():
            try:
                self.run_loop_iteration()
            except Exception as e:
                logger.exception(f"Fatal error in autonomy loop: {e}")
            
            # Sleep for interval
            self.stop_event.wait(self.loop_interval)
        
        logger.info("Autonomy loop stopped")
    
    def start(self):
        """Start the autonomy loop in a background thread."""
        if self.is_running:
            logger.warning("Autonomy loop already running")
            return False
        
        try:
            # Update state
            query = """
                UPDATE autonomy_state
                SET 
                    is_running = TRUE,
                    updated_at = %s
                WHERE id = (SELECT id FROM autonomy_state LIMIT 1)
            """
            execute_sql(query, (datetime.now(timezone.utc).isoformat(),))
            
            # Start thread
            self.is_running = True
            self.stop_event.clear()
            self.thread = Thread(target=self.run, daemon=True)
            self.thread.start()
            
            logger.info("Autonomy loop started")
            return True
        except Exception as e:
            logger.exception(f"Error starting autonomy loop: {e}")
            return False
    
    def stop(self):
        """Stop the autonomy loop."""
        if not self.is_running:
            logger.warning("Autonomy loop not running")
            return False
        
        try:
            # Signal stop
            self.stop_event.set()
            
            # Wait for thread to finish
            if self.thread:
                self.thread.join(timeout=10)
            
            self.is_running = False
            
            # Update state
            query = """
                UPDATE autonomy_state
                SET 
                    is_running = FALSE,
                    updated_at = %s
                WHERE id = (SELECT id FROM autonomy_state LIMIT 1)
            """
            execute_sql(query, (datetime.now(timezone.utc).isoformat(),))
            
            logger.info("Autonomy loop stopped")
            return True
        except Exception as e:
            logger.exception(f"Error stopping autonomy loop: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current loop status."""
        try:
            query = """
                SELECT *
                FROM autonomy_state
                ORDER BY updated_at DESC
                LIMIT 1
            """
            results = fetch_all(query)
            
            if results:
                return results[0]
            
            return {
                'is_running': False,
                'message': 'No state found'
            }
        except Exception as e:
            logger.exception(f"Error getting status: {e}")
            return {
                'is_running': False,
                'error': str(e)
            }


# Singleton instance
_autonomy_loop = None


def get_autonomy_loop() -> AutonomyLoop:
    """Get or create autonomy loop singleton."""
    global _autonomy_loop
    if _autonomy_loop is None:
        _autonomy_loop = AutonomyLoop()
    return _autonomy_loop


__all__ = ["AutonomyLoop", "get_autonomy_loop"]
