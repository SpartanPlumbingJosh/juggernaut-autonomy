"""
Self-Improvement System - L4 Autonomy

Closes the loop between learning and action:
1. Detects repeating failure patterns (3+ occurrences)
2. Generates fix tasks automatically
3. Tracks which learnings have been applied
4. Prevents duplicate fix tasks

This is what separates L3 (retry failures) from L4 (fix root causes).
"""

import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .database import query_db, log_execution


@dataclass
class FailurePattern:
    """Represents a detected failure pattern."""
    pattern_id: str
    category: str
    summary: str
    occurrence_count: int
    applied_count: int
    first_seen: datetime
    last_seen: datetime
    example_context: Dict
    suggested_fix: Optional[str] = None


class SelfImprovementEngine:
    """
    Autonomous self-improvement system.
    
    Detects patterns in failures and creates tasks to fix them.
    This is the difference between retrying (L3) and improving (L4).
    """
    
    def __init__(self, min_occurrences: int = 3):
        self.min_occurrences = min_occurrences
        self.pattern_matchers = self._build_pattern_matchers()
    
    def _build_pattern_matchers(self) -> List[Dict]:
        """
        Define patterns and their corresponding fix tasks.
        
        Each pattern has:
        - regex: Pattern to match in failure messages
        - task_template: Template for fix task
        - priority: Task priority
        - category: Type of fix needed
        """
        return [
            {
                "name": "missing_payload_field",
                "regex": r"missing ['\"]?(\w+)['\"]? in payload",
                "task_template": "Add payload validation for '{field}' in {handler}",
                "priority": "high",
                "category": "validation",
                "task_type": "code_task"
            },
            {
                "name": "puppeteer_fetch_failure",
                "regex": r"Failed to fetch|Puppeteer.*timeout|Navigation timeout",
                "task_template": "Debug and fix Puppeteer fetch failures for {source}",
                "priority": "high",
                "category": "infrastructure",
                "task_type": "debugging"
            },
            {
                "name": "table_not_exists",
                "regex": r"table ['\"]?(\w+)['\"]? does not exist",
                "task_template": "Create missing table '{table}' or fix query",
                "priority": "critical",
                "category": "database",
                "task_type": "code_task"
            },
            {
                "name": "api_rate_limit",
                "regex": r"rate limit|429|too many requests",
                "task_template": "Implement rate limiting and backoff for {api}",
                "priority": "medium",
                "category": "api",
                "task_type": "code_task"
            },
            {
                "name": "authentication_failure",
                "regex": r"authentication failed|unauthorized|401|403",
                "task_template": "Fix authentication for {service}",
                "priority": "high",
                "category": "auth",
                "task_type": "debugging"
            },
            {
                "name": "json_parse_error",
                "regex": r"JSON.*parse|invalid JSON|Expecting value",
                "task_template": "Add JSON validation and error handling for {source}",
                "priority": "medium",
                "category": "validation",
                "task_type": "code_task"
            },
            {
                "name": "timeout_error",
                "regex": r"timeout|timed out|deadline exceeded",
                "task_template": "Increase timeout or optimize {operation}",
                "priority": "medium",
                "category": "performance",
                "task_type": "optimization"
            },
            {
                "name": "null_reference",
                "regex": r"NoneType.*attribute|null.*undefined|cannot read property",
                "task_template": "Add null checks for {variable} in {location}",
                "priority": "high",
                "category": "validation",
                "task_type": "code_task"
            },
            {
                "name": "import_error",
                "regex": r"ImportError|ModuleNotFoundError|cannot import",
                "task_template": "Fix missing dependency or import for {module}",
                "priority": "critical",
                "category": "dependencies",
                "task_type": "code_task"
            },
            {
                "name": "database_connection",
                "regex": r"connection.*refused|database.*unavailable|could not connect",
                "task_template": "Fix database connection handling and retry logic",
                "priority": "critical",
                "category": "infrastructure",
                "task_type": "debugging"
            }
        ]
    
    def detect_patterns(self) -> List[FailurePattern]:
        """
        Detect repeating failure patterns from learnings table.
        
        Returns patterns that have occurred 3+ times and haven't been fixed.
        """
        sql = """
        SELECT 
            id,
            category,
            summary,
            context,
            applied_count,
            created_at
        FROM learnings
        WHERE category = 'failure_pattern'
        ORDER BY created_at DESC
        LIMIT 1000
        """
        
        try:
            result = query_db(sql)
            learnings = result.get("rows", [])
            
            # Group by similar summaries
            pattern_groups = self._group_similar_patterns(learnings)
            
            # Filter for patterns with 3+ occurrences and applied_count=0
            actionable_patterns = []
            for pattern_key, group in pattern_groups.items():
                if len(group) >= self.min_occurrences:
                    # Check if any in group have been applied
                    total_applied = sum(l.get("applied_count", 0) for l in group)
                    
                    if total_applied == 0:  # Not yet fixed
                        pattern = self._create_pattern_from_group(group)
                        actionable_patterns.append(pattern)
            
            return actionable_patterns
            
        except Exception as e:
            log_execution(
                worker_id="SELF_IMPROVEMENT",
                action="pattern_detection.error",
                message=f"Failed to detect patterns: {e}",
                level="error"
            )
            return []
    
    def _group_similar_patterns(self, learnings: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group learnings by similar failure patterns.
        
        Uses fuzzy matching on summaries to group related failures.
        """
        groups = {}
        
        for learning in learnings:
            summary = learning.get("summary", "")
            
            # Extract key terms for grouping
            key = self._extract_pattern_key(summary)
            
            if key not in groups:
                groups[key] = []
            groups[key].append(learning)
        
        return groups
    
    def _extract_pattern_key(self, summary: str) -> str:
        """
        Extract a key for grouping similar patterns.
        
        Examples:
        - "missing 'query' in payload" → "missing_in_payload"
        - "Failed to fetch source" → "failed_to_fetch"
        - "table users does not exist" → "table_does_not_exist"
        """
        summary_lower = summary.lower()
        
        # Try each pattern matcher
        for matcher in self.pattern_matchers:
            if re.search(matcher["regex"], summary_lower, re.IGNORECASE):
                return matcher["name"]
        
        # Fallback: use first 3 significant words
        words = re.findall(r'\b\w{4,}\b', summary_lower)
        return "_".join(words[:3]) if words else "unknown_pattern"
    
    def _create_pattern_from_group(self, group: List[Dict]) -> FailurePattern:
        """Create a FailurePattern from a group of similar learnings."""
        first = group[0]
        last = group[-1]
        
        return FailurePattern(
            pattern_id=first.get("id", ""),
            category=first.get("category", ""),
            summary=first.get("summary", ""),
            occurrence_count=len(group),
            applied_count=sum(l.get("applied_count", 0) for l in group),
            first_seen=datetime.fromisoformat(last.get("created_at", datetime.now(timezone.utc).isoformat())),
            last_seen=datetime.fromisoformat(first.get("created_at", datetime.now(timezone.utc).isoformat())),
            example_context=first.get("context", {})
        )
    
    def generate_fix_task(self, pattern: FailurePattern) -> Optional[Dict]:
        """
        Generate a fix task for a detected pattern.
        
        Returns task dict ready to insert into governance_tasks.
        """
        # Find matching pattern matcher
        matcher = None
        for m in self.pattern_matchers:
            if re.search(m["regex"], pattern.summary, re.IGNORECASE):
                matcher = m
                break
        
        if not matcher:
            # Generic fix task
            task_title = f"Fix recurring failure: {pattern.summary[:100]}"
            task_description = f"""
Recurring failure pattern detected ({pattern.occurrence_count} occurrences):

**Pattern**: {pattern.summary}

**First seen**: {pattern.first_seen}
**Last seen**: {pattern.last_seen}

**Example context**:
```json
{json.dumps(pattern.example_context, indent=2)}
```

**Action needed**:
1. Investigate root cause
2. Implement fix
3. Add tests to prevent regression
4. Update documentation if needed
"""
            task_type = "debugging"
            priority = "medium"
        else:
            # Use pattern-specific template
            task_title = self._fill_template(
                matcher["task_template"],
                pattern.summary,
                pattern.example_context
            )
            
            task_description = f"""
Recurring {matcher['category']} issue detected ({pattern.occurrence_count} occurrences):

**Pattern**: {pattern.summary}

**First seen**: {pattern.first_seen}
**Last seen**: {pattern.last_seen}

**Fix type**: {matcher['category']}

**Example context**:
```json
{json.dumps(pattern.example_context, indent=2)}
```

**Suggested fix**:
{task_title}

**Action needed**:
1. Implement the suggested fix
2. Add validation/error handling
3. Add tests to prevent regression
4. Update learnings.applied_count after fix
"""
            task_type = matcher["task_type"]
            priority = matcher["priority"]
        
        return {
            "title": task_title,
            "description": task_description,
            "task_type": task_type,
            "priority": priority,
            "metadata": {
                "pattern_id": pattern.pattern_id,
                "occurrence_count": pattern.occurrence_count,
                "auto_generated": True,
                "source": "self_improvement_engine"
            }
        }
    
    def _fill_template(self, template: str, summary: str, context: Dict) -> str:
        """
        Fill task template with extracted values.
        
        Extracts values from summary and context to fill placeholders.
        """
        # Extract field names, table names, etc. from summary
        extractions = {}
        
        # Extract field name from "missing 'field' in payload"
        field_match = re.search(r"missing ['\"]?(\w+)['\"]?", summary, re.IGNORECASE)
        if field_match:
            extractions["field"] = field_match.group(1)
        
        # Extract table name from "table 'name' does not exist"
        table_match = re.search(r"table ['\"]?(\w+)['\"]?", summary, re.IGNORECASE)
        if table_match:
            extractions["table"] = table_match.group(1)
        
        # Extract handler/source from context
        if "handler" in context:
            extractions["handler"] = context["handler"]
        elif "task_type" in context:
            extractions["handler"] = f"{context['task_type']} handler"
        else:
            extractions["handler"] = "handler"
        
        if "source" in context:
            extractions["source"] = context["source"]
        else:
            extractions["source"] = "source"
        
        if "api" in context:
            extractions["api"] = context["api"]
        else:
            extractions["api"] = "API"
        
        if "service" in context:
            extractions["service"] = context["service"]
        else:
            extractions["service"] = "service"
        
        if "operation" in context:
            extractions["operation"] = context["operation"]
        else:
            extractions["operation"] = "operation"
        
        if "variable" in context:
            extractions["variable"] = context["variable"]
        else:
            extractions["variable"] = "variable"
        
        if "location" in context:
            extractions["location"] = context["location"]
        else:
            extractions["location"] = "code"
        
        if "module" in context:
            extractions["module"] = context["module"]
        else:
            extractions["module"] = "module"
        
        # Fill template
        try:
            return template.format(**extractions)
        except KeyError:
            # If template has placeholders we didn't extract, use generic
            return template.format(**{k: k for k in extractions.keys()})
    
    def create_fix_task(self, task_data: Dict) -> Optional[str]:
        """
        Create a fix task in governance_tasks table.
        
        Returns task_id if successful.
        """
        sql = """
        INSERT INTO governance_tasks (
            title, description, task_type, priority, status, metadata, created_at
        ) VALUES (
            $1, $2, $3, $4, 'pending', $5, NOW()
        ) RETURNING id
        """
        
        try:
            result = query_db(sql, [
                task_data["title"],
                task_data["description"],
                task_data["task_type"],
                task_data["priority"],
                json.dumps(task_data["metadata"])
            ])
            
            task_id = result.get("rows", [{}])[0].get("id")
            
            log_execution(
                worker_id="SELF_IMPROVEMENT",
                action="fix_task.created",
                message=f"Created fix task: {task_data['title']}",
                output_data={
                    "task_id": task_id,
                    "pattern_id": task_data["metadata"].get("pattern_id"),
                    "occurrence_count": task_data["metadata"].get("occurrence_count")
                }
            )
            
            return task_id
            
        except Exception as e:
            log_execution(
                worker_id="SELF_IMPROVEMENT",
                action="fix_task.error",
                message=f"Failed to create fix task: {e}",
                level="error"
            )
            return None
    
    def mark_pattern_applied(self, pattern_id: str) -> bool:
        """
        Mark a pattern as applied (fix task created).
        
        Increments applied_count to prevent duplicate fix tasks.
        """
        sql = """
        UPDATE learnings
        SET applied_count = applied_count + 1
        WHERE id = $1
        """
        
        try:
            query_db(sql, [pattern_id])
            return True
        except Exception as e:
            log_execution(
                worker_id="SELF_IMPROVEMENT",
                action="mark_applied.error",
                message=f"Failed to mark pattern applied: {e}",
                level="error"
            )
            return False
    
    def run_improvement_cycle(self) -> Dict:
        """
        Run one complete self-improvement cycle.
        
        Returns:
            Dict with patterns_detected, tasks_created, errors
        """
        log_execution(
            worker_id="SELF_IMPROVEMENT",
            action="improvement_cycle.start",
            message="Starting self-improvement cycle"
        )
        
        # Detect patterns
        patterns = self.detect_patterns()
        
        if not patterns:
            log_execution(
                worker_id="SELF_IMPROVEMENT",
                action="improvement_cycle.complete",
                message="No actionable patterns detected"
            )
            return {
                "patterns_detected": 0,
                "tasks_created": 0,
                "errors": 0
            }
        
        # Create fix tasks
        tasks_created = 0
        errors = 0
        
        for pattern in patterns:
            # Generate fix task
            task_data = self.generate_fix_task(pattern)
            
            if not task_data:
                errors += 1
                continue
            
            # Create task
            task_id = self.create_fix_task(task_data)
            
            if task_id:
                # Mark pattern as applied
                self.mark_pattern_applied(pattern.pattern_id)
                tasks_created += 1
            else:
                errors += 1
        
        log_execution(
            worker_id="SELF_IMPROVEMENT",
            action="improvement_cycle.complete",
            message=f"Created {tasks_created} fix tasks from {len(patterns)} patterns",
            output_data={
                "patterns_detected": len(patterns),
                "tasks_created": tasks_created,
                "errors": errors
            }
        )
        
        return {
            "patterns_detected": len(patterns),
            "tasks_created": tasks_created,
            "errors": errors
        }


def self_improvement_check() -> Dict:
    """
    Convenience function to run self-improvement check.
    
    Call this from autonomy_loop every 10 cycles.
    """
    engine = SelfImprovementEngine(min_occurrences=3)
    return engine.run_improvement_cycle()
