"""
Error to Task Pipeline - Autonomous Bug Detection

Monitors execution logs for recurring errors and automatically creates
code_fix tasks to trigger Aider-based self-healing.

This closes the detection loop:
error logged → pattern detected → code_fix task created → Aider fixes → PR → merge → deploy
"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ErrorToTaskPipeline:
    """Monitors errors and creates code_fix tasks automatically."""
    
    def __init__(self, execute_sql, log_action):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
        # Thresholds for task creation
        self.error_threshold = int(os.getenv("ERROR_TASK_THRESHOLD", "5"))
        self.time_window_minutes = int(os.getenv("ERROR_WINDOW_MINUTES", "60"))
    
    def scan_and_create_tasks(self) -> Dict[str, Any]:
        """Scan for error patterns and create code_fix tasks.
        
        Returns:
            Dict with scan results and tasks created.
        """
        try:
            # Find error patterns in last time window
            patterns = self._find_error_patterns()
            
            if not patterns:
                self.log_action(
                    "error_to_task.no_patterns",
                    "No recurring error patterns detected",
                    level="info"
                )
                return {
                    "success": True,
                    "patterns_found": 0,
                    "tasks_created": 0
                }
            
            # Create tasks for each pattern
            tasks_created = []
            for pattern in patterns:
                task_id = self._create_code_fix_task(pattern)
                if task_id:
                    tasks_created.append(task_id)
            
            self.log_action(
                "error_to_task.scan_complete",
                f"Created {len(tasks_created)} code_fix tasks from {len(patterns)} error patterns",
                level="info",
                output_data={
                    "patterns_found": len(patterns),
                    "tasks_created": len(tasks_created),
                    "task_ids": tasks_created
                }
            )
            
            return {
                "success": True,
                "patterns_found": len(patterns),
                "tasks_created": len(tasks_created),
                "task_ids": tasks_created
            }
            
        except Exception as e:
            logger.exception(f"Error to task scan failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_error_patterns(self) -> List[Dict[str, Any]]:
        """Find recurring error patterns in execution logs.
        
        Returns:
            List of error patterns with metadata.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.time_window_minutes)
        
        sql = f"""
            SELECT 
                message,
                metadata::text as metadata_text,
                COUNT(*) as occurrence_count,
                MAX(created_at) as last_seen,
                MIN(created_at) as first_seen
            FROM execution_logs
            WHERE level IN ('error', 'critical')
              AND created_at >= '{cutoff.isoformat()}'
            GROUP BY message, metadata::text
            HAVING COUNT(*) >= {self.error_threshold}
            ORDER BY occurrence_count DESC
            LIMIT 10
        """
        
        result = self.execute_sql(sql)
        rows = result.get("rows", [])
        
        patterns = []
        for row in rows:
            # Extract file path and line number from error message or metadata
            file_info = self._extract_file_info(row.get("message", ""), row.get("metadata_text", ""))
            
            if file_info:
                patterns.append({
                    "error_message": row.get("message", ""),
                    "file_path": file_info["file_path"],
                    "line_number": file_info.get("line_number"),
                    "occurrence_count": row.get("occurrence_count", 0),
                    "last_seen": row.get("last_seen"),
                    "first_seen": row.get("first_seen")
                })
        
        return patterns
    
    def _extract_file_info(self, message: str, metadata: str) -> Optional[Dict[str, Any]]:
        """Extract file path and line number from error message or metadata.
        
        Args:
            message: Error message
            metadata: Metadata JSON string
        
        Returns:
            Dict with file_path and optional line_number, or None if not found.
        """
        # Try to extract from message first
        # Pattern: "File: path/to/file.py, Line: 123"
        file_match = re.search(r'File:\s*([^\s,]+\.py)', message)
        line_match = re.search(r'Line:\s*(\d+)', message)
        
        if file_match:
            return {
                "file_path": file_match.group(1),
                "line_number": int(line_match.group(1)) if line_match else None
            }
        
        # Try Python traceback format
        # Pattern: "  File "/path/to/file.py", line 123"
        traceback_match = re.search(r'File\s+"([^"]+\.py)",\s+line\s+(\d+)', message)
        if traceback_match:
            return {
                "file_path": traceback_match.group(1),
                "line_number": int(traceback_match.group(2))
            }
        
        # Try to extract from metadata
        try:
            if metadata:
                meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                if isinstance(meta, dict):
                    if "file_path" in meta:
                        return {
                            "file_path": meta["file_path"],
                            "line_number": meta.get("line_number")
                        }
        except Exception:
            pass
        
        return None
    
    def _create_code_fix_task(self, pattern: Dict[str, Any]) -> Optional[str]:
        """Create a code_fix task for an error pattern.
        
        Args:
            pattern: Error pattern with file_path, error_message, etc.
        
        Returns:
            Task ID if created successfully, None otherwise.
        """
        task_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        title = f"Fix: {pattern['error_message'][:100]}"
        description = f"""Autonomous bug fix triggered by recurring error pattern.

**Error:** {pattern['error_message']}

**File:** {pattern['file_path']}
{f"**Line:** {pattern['line_number']}" if pattern.get('line_number') else ""}

**Occurrences:** {pattern['occurrence_count']} times in last {self.time_window_minutes} minutes
**First Seen:** {pattern['first_seen']}
**Last Seen:** {pattern['last_seen']}

This task will trigger Aider to analyze the code and generate a fix.
"""
        
        payload = {
            "error_message": pattern["error_message"],
            "file_path": pattern["file_path"],
            "line_number": pattern.get("line_number"),
            "occurrence_count": pattern["occurrence_count"],
            "auto_generated": True
        }
        
        tags = ["auto-fix", "aider", "self-heal", pattern["file_path"].split("/")[0]]
        
        try:
            from core.database import fetch_all
            
            fetch_all("""
                INSERT INTO governance_tasks (
                    id, title, description, task_type, status, priority,
                    payload, tags, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                task_id,
                title,
                description,
                "code_fix",
                "pending",
                "high",
                json.dumps(payload),
                json.dumps(tags),
                now,
                now
            ))
            
            self.log_action(
                "error_to_task.task_created",
                f"Created code_fix task for {pattern['file_path']}",
                level="info",
                output_data={
                    "task_id": task_id,
                    "file_path": pattern["file_path"],
                    "error_message": pattern["error_message"][:100]
                }
            )
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create code_fix task: {e}")
            return None


def scan_errors_and_create_tasks(
    execute_sql,
    log_action
) -> Dict[str, Any]:
    """Entry point for error scanning - called by orchestrator.
    
    Args:
        execute_sql: SQL execution function
        log_action: Logging function
    
    Returns:
        Dict with scan results.
    """
    pipeline = ErrorToTaskPipeline(execute_sql, log_action)
    return pipeline.scan_and_create_tasks()
