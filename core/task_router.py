"""
Task Router

Intelligently routes tasks to appropriate workers based on capabilities and availability.

Part of Milestone 5: Engine Autonomy Restoration
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class TaskRouter:
    """Routes tasks to appropriate workers."""
    
    def get_task_requirements(self, task: Dict[str, Any]) -> List[str]:
        """
        Determine required capabilities for a task.
        
        Args:
            task: Task data
            
        Returns:
            List of required capabilities
        """
        task_type = task.get('task_type', 'generic')
        
        # Map task types to required capabilities
        capability_map = {
            'investigate_error': ['code_analysis', 'debugging'],
            'deploy_code': ['deployment', 'devops'],
            'analyze_logs': ['log_analysis', 'debugging'],
            'fix_bug': ['code_analysis', 'debugging', 'testing'],
            'update_dependency': ['dependency_management', 'testing'],
            'create_pr': ['code_analysis', 'git'],
            'generic': []  # Any worker can handle
        }
        
        return capability_map.get(task_type, [])
    
    def find_capable_workers(self, required_capabilities: List[str]) -> List[Dict[str, Any]]:
        """
        Find workers with required capabilities.
        
        Args:
            required_capabilities: List of required capabilities
            
        Returns:
            List of capable workers
        """
        try:
            if not required_capabilities:
                # Any worker can handle tasks with no requirements
                query = """
                    SELECT DISTINCT w.*
                    FROM workers w
                    WHERE w.status = 'online'
                    ORDER BY w.last_heartbeat DESC
                """
                return fetch_all(query)
            
            # Find workers with ALL required capabilities
            placeholders = ','.join(['%s'] * len(required_capabilities))
            query = f"""
                SELECT w.*, COUNT(DISTINCT wc.capability) as capability_count
                FROM workers w
                JOIN worker_capabilities wc ON wc.worker_id = w.id
                WHERE 
                    w.status = 'online'
                    AND wc.capability IN ({placeholders})
                GROUP BY w.id
                HAVING COUNT(DISTINCT wc.capability) = %s
                ORDER BY w.last_heartbeat DESC
            """
            
            params = tuple(required_capabilities) + (len(required_capabilities),)
            return fetch_all(query, params)
        except Exception as e:
            logger.exception(f"Error finding capable workers: {e}")
            return []
    
    def get_worker_load(self, worker_id: str) -> int:
        """
        Get current task load for a worker.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            Number of active tasks
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM task_assignments
                WHERE 
                    worker_id = %s
                    AND status IN ('assigned', 'running')
            """
            results = fetch_all(query, (worker_id,))
            return int(results[0]['count']) if results else 0
        except Exception as e:
            logger.exception(f"Error getting worker load: {e}")
            return 999  # High number to avoid assignment
    
    def get_worker_success_rate(self, worker_id: str) -> float:
        """
        Get worker's recent success rate.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            Success rate (0-1)
        """
        try:
            query = """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM task_assignments
                WHERE 
                    worker_id = %s
                    AND created_at > NOW() - INTERVAL '24 hours'
            """
            results = fetch_all(query, (worker_id,))
            
            if not results or not results[0]['total']:
                return 0.5  # Neutral for new workers
            
            total = int(results[0]['total'])
            completed = int(results[0]['completed'])
            
            return completed / total if total > 0 else 0.5
        except Exception as e:
            logger.exception(f"Error getting worker success rate: {e}")
            return 0.0
    
    def find_best_worker(self, task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find the best worker for a task.
        
        Args:
            task: Task data
            
        Returns:
            Best worker or None
        """
        # Get required capabilities
        required_capabilities = self.get_task_requirements(task)
        
        # Find capable workers
        capable_workers = self.find_capable_workers(required_capabilities)
        
        if not capable_workers:
            logger.warning(f"No capable workers found for task {task.get('id')}")
            return None
        
        # Score each worker
        best_worker = None
        best_score = -1
        
        for worker in capable_workers:
            worker_id = str(worker['id'])
            
            # Calculate score based on multiple factors
            load = self.get_worker_load(worker_id)
            success_rate = self.get_worker_success_rate(worker_id)
            
            # Score formula: success_rate * 100 - load * 10
            # Prefer workers with high success rate and low load
            score = (success_rate * 100) - (load * 10)
            
            if score > best_score:
                best_score = score
                best_worker = worker
        
        return best_worker
    
    def assign_task(self, task_id: str, worker_id: str) -> bool:
        """
        Assign a task to a worker.
        
        Args:
            task_id: Task ID
            worker_id: Worker ID
            
        Returns:
            True if successful
        """
        try:
            # Create assignment
            assignment_query = """
                INSERT INTO task_assignments (
                    task_id,
                    worker_id,
                    assigned_at,
                    status
                ) VALUES (%s, %s, %s, %s)
            """
            execute_sql(assignment_query, (
                task_id,
                worker_id,
                datetime.now(timezone.utc).isoformat(),
                'assigned'
            ))
            
            # Update task status
            task_query = """
                UPDATE governance_tasks
                SET 
                    status = 'assigned',
                    updated_at = %s
                WHERE id = %s
            """
            execute_sql(task_query, (
                datetime.now(timezone.utc).isoformat(),
                task_id
            ))
            
            # Update worker status
            worker_query = """
                UPDATE workers
                SET 
                    status = 'busy',
                    current_task_id = %s,
                    updated_at = %s
                WHERE id = %s
            """
            execute_sql(worker_query, (
                task_id,
                datetime.now(timezone.utc).isoformat(),
                worker_id
            ))
            
            logger.info(f"Assigned task {task_id} to worker {worker_id}")
            return True
        except Exception as e:
            logger.exception(f"Error assigning task: {e}")
            return False
    
    def route_task(self, task: Dict[str, Any]) -> bool:
        """
        Route a task to the best available worker.
        
        Args:
            task: Task data
            
        Returns:
            True if routed successfully
        """
        worker = self.find_best_worker(task)
        
        if not worker:
            return False
        
        return self.assign_task(str(task['id']), str(worker['id']))


# Singleton instance
_task_router = None


def get_task_router() -> TaskRouter:
    """Get or create task router singleton."""
    global _task_router
    if _task_router is None:
        _task_router = TaskRouter()
    return _task_router


__all__ = ["TaskRouter", "get_task_router"]
