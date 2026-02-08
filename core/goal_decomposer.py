"""
Goal Decomposition Engine - The Missing Autonomous Task Generator

This is the critical piece that transforms JUGGERNAUT from "a system that executes work"
into "a system that figures out what work to do and then does it."

Scans active goals, uses LLM to break them into concrete executable subtasks,
and populates the governance_tasks queue with work linked back to parent goals.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .ai_executor import AIExecutor, select_model_for_task

logger = logging.getLogger(__name__)


class GoalDecomposer:
    """Decomposes high-level goals into executable subtasks."""
    
    def __init__(self, execute_sql: Callable, log_action: Callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
        # Configuration
        self.min_tasks_per_goal = 3
        self.max_tasks_per_goal = 7
        self.max_goals_per_cycle = 3
        
    def decompose_goals(self) -> Dict[str, Any]:
        """Main entry point - find goals and decompose them into tasks.
        
        Returns:
            Dict with decomposition results.
        """
        try:
            # Find active goals that need task decomposition
            goals_needing_work = self._find_goals_needing_decomposition()
            
            if not goals_needing_work:
                logger.debug("No goals need decomposition - all have active tasks")
                return {
                    "success": True,
                    "goals_processed": 0,
                    "tasks_created": 0,
                    "message": "No goals need decomposition"
                }
            
            total_tasks_created = 0
            goals_processed = 0
            
            for goal in goals_needing_work[:self.max_goals_per_cycle]:
                try:
                    tasks_created = self._decompose_single_goal(goal)
                    total_tasks_created += tasks_created
                    goals_processed += 1
                    
                    self.log_action(
                        "goal_decomposer.decomposed",
                        f"Decomposed goal '{goal['title'][:50]}' into {tasks_created} tasks",
                        level="info",
                        output_data={
                            "goal_id": goal["id"],
                            "tasks_created": tasks_created
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to decompose goal {goal.get('id')}: {e}")
                    self.log_action(
                        "goal_decomposer.error",
                        f"Failed to decompose goal: {str(e)[:100]}",
                        level="error",
                        output_data={"goal_id": goal.get("id"), "error": str(e)}
                    )
            
            return {
                "success": True,
                "goals_processed": goals_processed,
                "tasks_created": total_tasks_created,
                "message": f"Decomposed {goals_processed} goals into {total_tasks_created} tasks"
            }
            
        except Exception as e:
            logger.exception("Goal decomposition cycle failed")
            return {
                "success": False,
                "error": str(e),
                "goals_processed": 0,
                "tasks_created": 0
            }
    
    def _find_goals_needing_decomposition(self) -> List[Dict[str, Any]]:
        """Find active goals that have no pending/in_progress tasks.
        
        Returns:
            List of goal records needing decomposition.
        """
        sql = """
            SELECT 
                g.id,
                g.title,
                g.description,
                g.success_criteria,
                g.deadline,
                g.progress,
                g.max_cost_cents,
                COALESCE(
                    (SELECT COUNT(*) 
                     FROM governance_tasks t 
                     WHERE t.goal_id = g.id 
                       AND t.status IN ('pending', 'in_progress', 'assigned')
                    ), 
                    0
                ) as active_task_count
            FROM goals g
            WHERE g.status IN ('pending', 'in_progress', 'assigned')
              AND g.progress < 100
            ORDER BY 
                g.deadline ASC NULLS LAST,
                g.created_at ASC
            LIMIT 10
        """
        
        result = self.execute_sql(sql)
        goals = result.get("rows", [])
        
        # Filter to only goals with no active tasks
        needs_work = [g for g in goals if g.get("active_task_count", 0) == 0]
        
        return needs_work
    
    def _decompose_single_goal(self, goal: Dict[str, Any]) -> int:
        """Decompose a single goal into executable subtasks using LLM.
        
        Args:
            goal: Goal record from database
            
        Returns:
            Number of tasks created
        """
        goal_id = goal["id"]
        title = goal["title"]
        description = goal.get("description", "")
        success_criteria = goal.get("success_criteria", {})
        deadline = goal.get("deadline")
        max_cost_cents = goal.get("max_cost_cents", 50000)
        
        # Use strategy model for planning
        model = select_model_for_task("strategy")
        executor = AIExecutor(model=model, max_tokens=4096)
        
        # Build decomposition prompt
        prompt = self._build_decomposition_prompt(
            title=title,
            description=description,
            success_criteria=success_criteria,
            deadline=deadline
        )
        
        # Get LLM to break down the goal
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = executor.chat(messages=messages, temperature=0.7)
            content = response.get("content", "")
            
            # Parse task breakdown from response
            tasks = self._parse_task_breakdown(content)
            
            if not tasks:
                logger.warning(f"LLM returned no valid tasks for goal {goal_id}")
                # Create a fallback research task
                tasks = [{
                    "title": f"Research how to achieve: {title[:80]}",
                    "task_type": "research",
                    "description": f"Research strategies and approaches to achieve the goal: {title}",
                    "priority": "high"
                }]
            
            # Insert tasks into database
            tasks_created = 0
            for task_def in tasks[:self.max_tasks_per_goal]:
                task_id = self._create_task(
                    goal_id=goal_id,
                    task_def=task_def,
                    max_cost_cents=max_cost_cents
                )
                if task_id:
                    tasks_created += 1
            
            return tasks_created
            
        except Exception as e:
            logger.error(f"LLM decomposition failed for goal {goal_id}: {e}")
            # Create fallback task on error
            fallback_id = self._create_task(
                goal_id=goal_id,
                task_def={
                    "title": f"Plan approach for: {title[:80]}",
                    "task_type": "strategy",
                    "description": f"Create a detailed plan to achieve: {title}\n\n{description}",
                    "priority": "high"
                },
                max_cost_cents=max_cost_cents
            )
            return 1 if fallback_id else 0
    
    def _build_decomposition_prompt(
        self,
        title: str,
        description: str,
        success_criteria: Any,
        deadline: Optional[str]
    ) -> str:
        """Build LLM prompt for goal decomposition."""
        
        criteria_str = ""
        if success_criteria:
            if isinstance(success_criteria, dict):
                criteria_str = json.dumps(success_criteria, indent=2)
            else:
                criteria_str = str(success_criteria)
        
        deadline_str = f"\n**Deadline:** {deadline}" if deadline else ""
        
        return f"""You are JUGGERNAUT's autonomous task planning system. Break down this goal into 3-7 concrete, executable tasks.

**Goal:** {title}
**Description:** {description}
**Success Criteria:** {criteria_str}{deadline_str}

Generate a task breakdown following these rules:

1. **Be concrete and actionable** - each task should be something the system can actually execute (research, code, analysis, etc)
2. **Use proper task types** - research, code, code_fix, strategy, analysis, evaluation, outreach, database, verification
3. **Start with research/analysis** if the goal is vague or complex
4. **Include evaluation tasks** to measure progress
5. **Order tasks logically** - research before implementation, analysis before decisions
6. **Keep tasks focused** - each should be completable in one work session

Output ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "tasks": [
    {{
      "title": "Task title (60 chars max)",
      "task_type": "research|code|strategy|analysis|evaluation|outreach|database|verification",
      "description": "Detailed description of what to do and why",
      "priority": "critical|high|medium|low",
      "payload": {{}}
    }}
  ]
}}

Generate the task breakdown now:"""
    
    def _parse_task_breakdown(self, content: str) -> List[Dict[str, Any]]:
        """Parse LLM response into task definitions.
        
        Args:
            content: LLM response content
            
        Returns:
            List of task definitions
        """
        try:
            # Try to extract JSON from response
            content = content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
                content = content.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            parsed = json.loads(content)
            tasks = parsed.get("tasks", [])
            
            # Validate tasks
            valid_tasks = []
            valid_types = {
                "research", "code", "code_fix", "strategy", "analysis", 
                "evaluation", "outreach", "database", "verification", "test"
            }
            valid_priorities = {"critical", "high", "medium", "low"}
            
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                    
                # Ensure required fields
                if not task.get("title") or not task.get("task_type"):
                    continue
                
                # Validate and normalize
                task_type = str(task.get("task_type", "strategy")).lower()
                if task_type not in valid_types:
                    task_type = "strategy"  # fallback
                
                priority = str(task.get("priority", "medium")).lower()
                if priority not in valid_priorities:
                    priority = "medium"
                
                valid_tasks.append({
                    "title": str(task["title"])[:100],
                    "task_type": task_type,
                    "description": str(task.get("description", task["title"]))[:2000],
                    "priority": priority,
                    "payload": task.get("payload", {})
                })
            
            return valid_tasks
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM task breakdown: {e}")
            logger.debug(f"Content was: {content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing task breakdown: {e}")
            return []
    
    def _create_task(
        self,
        goal_id: str,
        task_def: Dict[str, Any],
        max_cost_cents: int
    ) -> Optional[str]:
        """Create a single task in the database.
        
        Args:
            goal_id: Parent goal ID
            task_def: Task definition dict
            max_cost_cents: Max cost for this task
            
        Returns:
            Task ID if created, None on failure
        """
        task_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        title = task_def["title"]
        task_type = task_def["task_type"]
        description = task_def["description"]
        priority = task_def["priority"]
        payload = task_def.get("payload", {})
        
        # Add goal linkage to payload
        payload["goal_id"] = goal_id
        payload["auto_generated"] = True
        payload["generated_by"] = "goal_decomposer"
        
        # Tags for filtering and tracking
        tags = ["auto-generated", "goal-task", f"goal:{goal_id[:8]}", task_type]
        
        try:
            from core.database import fetch_all
            
            fetch_all("""
                INSERT INTO governance_tasks (
                    id, goal_id, title, description, task_type, 
                    status, priority, payload, tags, 
                    created_at, updated_at, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                task_id,
                goal_id,
                title,
                description,
                task_type,
                'pending',
                priority,
                json.dumps(payload),
                json.dumps(tags),
                now,
                now,
                'goal_decomposer'
            ))
            
            logger.info(f"Created task {task_id} for goal {goal_id}: {title}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return None


def decompose_goals_cycle(
    execute_sql: Callable,
    log_action: Callable
) -> Dict[str, Any]:
    """Entry point for goal decomposition - called by orchestrator.
    
    Args:
        execute_sql: SQL execution function
        log_action: Logging function
    
    Returns:
        Dict with decomposition results.
    """
    decomposer = GoalDecomposer(execute_sql, log_action)
    return decomposer.decompose_goals()
