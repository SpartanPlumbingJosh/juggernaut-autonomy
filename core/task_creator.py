"""
Task Creator

Creates governance tasks for error investigation based on alert rules.

Part of Milestone 3: Railway Logs Crawler
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class TaskCreator:
    """Creates governance tasks for error investigation."""
    
    def get_fingerprint_details(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """Get full details for an error fingerprint."""
        try:
            query = """
                SELECT 
                    f.id,
                    f.fingerprint,
                    f.normalized_message,
                    f.error_type,
                    f.first_seen,
                    f.last_seen,
                    f.occurrence_count,
                    f.stack_trace,
                    l.message as sample_message,
                    l.log_level,
                    l.timestamp as sample_timestamp
                FROM error_fingerprints f
                LEFT JOIN railway_logs l ON l.id = f.sample_log_id
                WHERE f.id = %s
            """
            results = fetch_all(query, (fingerprint_id,))
            return results[0] if results else None
        except Exception as e:
            logger.exception(f"Error fetching fingerprint details: {e}")
            return None
    
    def create_task_for_fingerprint(self, fingerprint_id: str, priority: str = 'high') -> Optional[str]:
        """
        Create a governance task for an error fingerprint.
        
        Args:
            fingerprint_id: Error fingerprint ID
            priority: Task priority (high, medium, low)
            
        Returns:
            Created task ID or None
        """
        try:
            # Get fingerprint details
            details = self.get_fingerprint_details(fingerprint_id)
            if not details:
                logger.error(f"Fingerprint {fingerprint_id} not found")
                return None
            
            # Build task title
            error_type = details.get('error_type', 'Unknown')
            normalized_msg = details.get('normalized_message', '')[:100]
            title = f"Investigate {error_type}: {normalized_msg}"
            
            # Build task description
            occurrence_count = int(details.get('occurrence_count', 0))
            first_seen = details.get('first_seen', '')
            last_seen = details.get('last_seen', '')
            sample_message = details.get('sample_message', '')
            stack_trace = details.get('stack_trace', '')
            
            description = f"""Error detected in Railway logs:

**Error Type:** {error_type}
**Fingerprint:** {details.get('fingerprint', '')}
**Occurrences:** {occurrence_count}
**First Seen:** {first_seen}
**Last Seen:** {last_seen}

**Sample Error Message:**
```
{sample_message[:500]}
```

**Normalized Pattern:**
```
{normalized_msg}
```
"""
            
            if stack_trace:
                description += f"""
**Stack Trace:**
```
{stack_trace[:1000]}
```
"""
            
            description += """
**Action Required:**
1. Review the error message and stack trace
2. Identify the root cause
3. Implement a fix
4. Verify the error no longer occurs
5. Mark this task as complete
"""
            
            # Create governance task
            task_query = """
                INSERT INTO governance_tasks (
                    task_type,
                    description,
                    status,
                    priority,
                    metadata,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            metadata = {
                "fingerprint_id": fingerprint_id,
                "fingerprint": details.get('fingerprint'),
                "error_type": error_type,
                "occurrence_count": occurrence_count,
                "created_by": "log_crawler",
                "source": "railway_logs"
            }
            
            params = (
                'investigate_error',
                description,
                'pending',
                priority,
                json.dumps(metadata),
                datetime.now(timezone.utc).isoformat()
            )
            
            result = fetch_all(task_query, params)
            task_id = str(result[0]['id']) if result else None
            
            if task_id:
                # Mark fingerprint as having task created
                update_query = """
                    UPDATE error_fingerprints
                    SET 
                        task_created = TRUE,
                        task_id = %s,
                        updated_at = %s
                    WHERE id = %s
                """
                execute_sql(update_query, (
                    task_id,
                    datetime.now(timezone.utc).isoformat(),
                    fingerprint_id
                ))
                
                logger.info(f"Created task {task_id} for fingerprint {fingerprint_id}")
            
            return task_id
            
        except Exception as e:
            logger.exception(f"Error creating task for fingerprint {fingerprint_id}: {e}")
            return None
    
    def create_tasks_for_fingerprints(
        self,
        fingerprint_ids: list,
        priority: str = 'high'
    ) -> Dict[str, Optional[str]]:
        """
        Create tasks for multiple fingerprints.
        
        Args:
            fingerprint_ids: List of fingerprint IDs
            priority: Task priority
            
        Returns:
            Dict mapping fingerprint IDs to task IDs
        """
        results = {}
        
        for fingerprint_id in fingerprint_ids:
            task_id = self.create_task_for_fingerprint(fingerprint_id, priority)
            results[fingerprint_id] = task_id
        
        return results
    
    def process_alert_triggers(self, triggered_rules: Dict[str, list]) -> int:
        """
        Process triggered alert rules and create tasks.
        
        Args:
            triggered_rules: Dict mapping rule IDs to fingerprint ID lists
            
        Returns:
            Number of tasks created
        """
        tasks_created = 0
        
        for rule_id, fingerprint_ids in triggered_rules.items():
            logger.info(f"Processing {len(fingerprint_ids)} fingerprints for rule {rule_id}")
            
            results = self.create_tasks_for_fingerprints(fingerprint_ids)
            
            # Count successful task creations
            tasks_created += sum(1 for task_id in results.values() if task_id is not None)
        
        return tasks_created


# Singleton instance
_task_creator = None


def get_task_creator() -> TaskCreator:
    """Get or create task creator singleton."""
    global _task_creator
    if _task_creator is None:
        _task_creator = TaskCreator()
    return _task_creator


__all__ = ["TaskCreator", "get_task_creator"]
