"""Task batching module for intelligent grouping of related work items.

This module provides functionality to group related tasks together for
combined PR submissions, reducing CodeRabbit API calls and merge overhead.
"""

import logging
import re
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

logger = logging.getLogger(__name__)

# Configuration constants
MAX_BATCH_SIZE = 5
MIN_SIMILARITY_THRESHOLD = 0.6
TASK_PREFIX_PATTERN = re.compile(r'^([A-Z]+-\d+)')


class BatchingStrategy(Enum):
    """Strategies for batching tasks together."""
    
    PREFIX = "prefix"  # Group by task ID prefix (e.g., TEST-01, TEST-02)
    TYPE = "type"  # Group by task_type field
    DEPENDENCY = "dependency"  # Group tasks with shared dependencies
    COMPONENT = "component"  # Group by affected component/module
    COMBINED = "combined"  # Use all strategies with weighted scoring


@dataclass
class TaskInfo:
    """Lightweight task representation for batching analysis."""
    
    task_id: str
    title: str
    description: str
    task_type: str
    priority: str
    dependencies: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    
    def get_prefix(self) -> Optional[str]:
        """Extract task prefix from title (e.g., TEST from TEST-01).
        
        Returns:
            The prefix portion of the task ID, or None if no match.
        """
        match = TASK_PREFIX_PATTERN.match(self.title)
        if match:
            full_id = match.group(1)
            return full_id.rsplit('-', 1)[0]
        return None
    
    def get_numeric_id(self) -> Optional[int]:
        """Extract numeric portion from task title.
        
        Returns:
            The numeric portion of the task ID, or None if no match.
        """
        match = TASK_PREFIX_PATTERN.match(self.title)
        if match:
            full_id = match.group(1)
            parts = full_id.rsplit('-', 1)
            if len(parts) == 2 and parts[1].isdigit():
                return int(parts[1])
        return None


@dataclass
class TaskBatch:
    """A batch of related tasks that can be completed in a single PR."""
    
    batch_id: str
    tasks: List[TaskInfo]
    strategy: BatchingStrategy
    similarity_score: float
    shared_component: Optional[str] = None
    combined_description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def task_ids(self) -> List[str]:
        """Get list of task IDs in this batch."""
        return [t.task_id for t in self.tasks]
    
    @property
    def size(self) -> int:
        """Get the number of tasks in this batch."""
        return len(self.tasks)
    
    def generate_pr_title(self) -> str:
        """Generate a combined PR title for this batch.
        
        Returns:
            A descriptive PR title covering all batched tasks.
        """
        if len(self.tasks) == 1:
            return self.tasks[0].title
        
        prefixes = [t.get_prefix() for t in self.tasks if t.get_prefix()]
        if prefixes and len(set(prefixes)) == 1:
            task_ids = [TASK_PREFIX_PATTERN.match(t.title).group(1) 
                       for t in self.tasks 
                       if TASK_PREFIX_PATTERN.match(t.title)]
            return f"{prefixes[0]}: Batch implementation ({', '.join(task_ids)})"
        
        return f"Batch: {len(self.tasks)} related tasks - {self.shared_component or 'mixed'}"
    
    def generate_pr_description(self) -> str:
        """Generate a combined PR description for this batch.
        
        Returns:
            A markdown-formatted description covering all tasks.
        """
        lines = [
            "## Batched Task Implementation",
            "",
            f"**Strategy:** {self.strategy.value}",
            f"**Similarity Score:** {self.similarity_score:.2f}",
            f"**Tasks in batch:** {self.size}",
            "",
            "### Tasks Included",
            "",
        ]
        
        for task in self.tasks:
            lines.append(f"- **{task.title}**: {task.description[:100]}...")
        
        lines.extend([
            "",
            "### Combined Scope",
            "",
            self.combined_description or "Multiple related tasks completed together.",
        ])
        
        return "\n".join(lines)


class TaskBatcher:
    """Intelligent task batching engine.
    
    Analyzes tasks and groups related ones together for combined
    PR submissions to reduce CodeRabbit API usage and merge overhead.
    """
    
    def __init__(
        self,
        max_batch_size: int = MAX_BATCH_SIZE,
        min_similarity: float = MIN_SIMILARITY_THRESHOLD
    ) -> None:
        """Initialize the task batcher.
        
        Args:
            max_batch_size: Maximum number of tasks in a single batch.
            min_similarity: Minimum similarity score for batching.
        """
        self._max_batch_size = max_batch_size
        self._min_similarity = min_similarity
        self._batches: Dict[str, TaskBatch] = {}
        self._task_to_batch: Dict[str, str] = {}
        logger.info(
            "TaskBatcher initialized with max_size=%d, min_similarity=%.2f",
            max_batch_size,
            min_similarity
        )
    
    def analyze_tasks(
        self,
        tasks: List[TaskInfo],
        strategy: BatchingStrategy = BatchingStrategy.COMBINED
    ) -> List[TaskBatch]:
        """Analyze tasks and create optimal batches.
        
        Args:
            tasks: List of tasks to analyze and batch.
            strategy: Batching strategy to use.
            
        Returns:
            List of task batches.
        """
        if not tasks:
            return []
        
        logger.info("Analyzing %d tasks with strategy %s", len(tasks), strategy.value)
        
        if strategy == BatchingStrategy.PREFIX:
            return self._batch_by_prefix(tasks)
        elif strategy == BatchingStrategy.TYPE:
            return self._batch_by_type(tasks)
        elif strategy == BatchingStrategy.DEPENDENCY:
            return self._batch_by_dependency(tasks)
        elif strategy == BatchingStrategy.COMPONENT:
            return self._batch_by_component(tasks)
        else:
            return self._batch_combined(tasks)
    
    def _batch_by_prefix(self, tasks: List[TaskInfo]) -> List[TaskBatch]:
        """Group tasks by their ID prefix.
        
        Args:
            tasks: Tasks to group.
            
        Returns:
            List of batches grouped by prefix.
        """
        prefix_groups: Dict[str, List[TaskInfo]] = {}
        ungrouped: List[TaskInfo] = []
        
        for task in tasks:
            prefix = task.get_prefix()
            if prefix:
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(task)
            else:
                ungrouped.append(task)
        
        batches = []
        batch_counter = 0
        
        for prefix, group_tasks in prefix_groups.items():
            # Sort by numeric ID for sequential ordering
            group_tasks.sort(key=lambda t: t.get_numeric_id() or 0)
            
            # Split into chunks if exceeding max size
            for i in range(0, len(group_tasks), self._max_batch_size):
                chunk = group_tasks[i:i + self._max_batch_size]
                batch_counter += 1
                batch = TaskBatch(
                    batch_id=f"batch-prefix-{batch_counter}",
                    tasks=chunk,
                    strategy=BatchingStrategy.PREFIX,
                    similarity_score=1.0,
                    shared_component=prefix,
                    combined_description=f"Sequential {prefix} tasks implementation."
                )
                batches.append(batch)
                self._register_batch(batch)
        
        # Each ungrouped task becomes its own batch
        for task in ungrouped:
            batch_counter += 1
            batch = TaskBatch(
                batch_id=f"batch-single-{batch_counter}",
                tasks=[task],
                strategy=BatchingStrategy.PREFIX,
                similarity_score=0.0,
                combined_description=task.description
            )
            batches.append(batch)
            self._register_batch(batch)
        
        logger.info("Created %d batches by prefix from %d tasks", len(batches), len(tasks))
        return batches
    
    def _batch_by_type(self, tasks: List[TaskInfo]) -> List[TaskBatch]:
        """Group tasks by their task_type.
        
        Args:
            tasks: Tasks to group.
            
        Returns:
            List of batches grouped by type.
        """
        type_groups: Dict[str, List[TaskInfo]] = {}
        
        for task in tasks:
            task_type = task.task_type or "unknown"
            if task_type not in type_groups:
                type_groups[task_type] = []
            type_groups[task_type].append(task)
        
        batches = []
        batch_counter = 0
        
        for task_type, group_tasks in type_groups.items():
            for i in range(0, len(group_tasks), self._max_batch_size):
                chunk = group_tasks[i:i + self._max_batch_size]
                batch_counter += 1
                batch = TaskBatch(
                    batch_id=f"batch-type-{batch_counter}",
                    tasks=chunk,
                    strategy=BatchingStrategy.TYPE,
                    similarity_score=0.8,
                    shared_component=task_type,
                    combined_description=f"Related {task_type} tasks."
                )
                batches.append(batch)
                self._register_batch(batch)
        
        logger.info("Created %d batches by type from %d tasks", len(batches), len(tasks))
        return batches
    
    def _batch_by_dependency(self, tasks: List[TaskInfo]) -> List[TaskBatch]:
        """Group tasks that share dependencies.
        
        Args:
            tasks: Tasks to group.
            
        Returns:
            List of batches grouped by shared dependencies.
        """
        # Build dependency graph
        dep_to_tasks: Dict[str, Set[str]] = {}
        task_map: Dict[str, TaskInfo] = {t.task_id: t for t in tasks}
        
        for task in tasks:
            for dep in task.dependencies:
                if dep not in dep_to_tasks:
                    dep_to_tasks[dep] = set()
                dep_to_tasks[dep].add(task.task_id)
        
        # Union-find to group tasks with shared deps
        parent: Dict[str, str] = {t.task_id: t.task_id for t in tasks}
        
        def find(x: str) -> str:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        for dep, task_ids in dep_to_tasks.items():
            task_list = list(task_ids)
            for i in range(1, len(task_list)):
                union(task_list[0], task_list[i])
        
        # Group by root
        groups: Dict[str, List[TaskInfo]] = {}
        for task in tasks:
            root = find(task.task_id)
            if root not in groups:
                groups[root] = []
            groups[root].append(task)
        
        batches = []
        batch_counter = 0
        
        for root, group_tasks in groups.items():
            for i in range(0, len(group_tasks), self._max_batch_size):
                chunk = group_tasks[i:i + self._max_batch_size]
                batch_counter += 1
                shared_deps = set()
                for t in chunk:
                    shared_deps.update(t.dependencies)
                
                batch = TaskBatch(
                    batch_id=f"batch-dep-{batch_counter}",
                    tasks=chunk,
                    strategy=BatchingStrategy.DEPENDENCY,
                    similarity_score=0.9 if len(shared_deps) > 1 else 0.5,
                    shared_component=", ".join(list(shared_deps)[:3]) if shared_deps else None,
                    combined_description="Tasks with shared dependencies."
                )
                batches.append(batch)
                self._register_batch(batch)
        
        logger.info("Created %d batches by dependency from %d tasks", len(batches), len(tasks))
        return batches
    
    def _batch_by_component(self, tasks: List[TaskInfo]) -> List[TaskBatch]:
        """Group tasks by affected component/module.
        
        Args:
            tasks: Tasks to group.
            
        Returns:
            List of batches grouped by component.
        """
        component_groups: Dict[str, List[TaskInfo]] = {}
        
        for task in tasks:
            # Extract component from affected files or description
            components = self._extract_components(task)
            primary_component = components[0] if components else "general"
            
            if primary_component not in component_groups:
                component_groups[primary_component] = []
            component_groups[primary_component].append(task)
        
        batches = []
        batch_counter = 0
        
        for component, group_tasks in component_groups.items():
            for i in range(0, len(group_tasks), self._max_batch_size):
                chunk = group_tasks[i:i + self._max_batch_size]
                batch_counter += 1
                batch = TaskBatch(
                    batch_id=f"batch-comp-{batch_counter}",
                    tasks=chunk,
                    strategy=BatchingStrategy.COMPONENT,
                    similarity_score=0.85,
                    shared_component=component,
                    combined_description=f"Tasks affecting {component} component."
                )
                batches.append(batch)
                self._register_batch(batch)
        
        logger.info("Created %d batches by component from %d tasks", len(batches), len(tasks))
        return batches
    
    def _batch_combined(self, tasks: List[TaskInfo]) -> List[TaskBatch]:
        """Use combined scoring from all strategies.
        
        Args:
            tasks: Tasks to batch.
            
        Returns:
            Optimally batched tasks using weighted combination.
        """
        # Get batches from prefix strategy (highest priority for sequential work)
        prefix_batches = self._batch_by_prefix(tasks)
        
        # If prefix batching worked well, use those results
        multi_task_batches = [b for b in prefix_batches if b.size > 1]
        if multi_task_batches:
            logger.info("Combined strategy: using prefix results with %d multi-task batches",
                       len(multi_task_batches))
            return prefix_batches
        
        # Fall back to type batching
        type_batches = self._batch_by_type(tasks)
        multi_task_batches = [b for b in type_batches if b.size > 1]
        if multi_task_batches:
            logger.info("Combined strategy: using type results with %d multi-task batches",
                       len(multi_task_batches))
            return type_batches
        
        # If nothing groups well, return individual tasks as batches
        logger.info("Combined strategy: no good groupings found, returning single-task batches")
        return prefix_batches
    
    def _extract_components(self, task: TaskInfo) -> List[str]:
        """Extract component names from task metadata.
        
        Args:
            task: Task to analyze.
            
        Returns:
            List of component names found.
        """
        components = []
        
        # Check affected files for module paths
        for file_path in task.affected_files:
            parts = file_path.split('/')
            if len(parts) > 1:
                components.append(parts[0])
        
        # Check description for known component keywords
        desc_lower = task.description.lower()
        known_components = ['database', 'api', 'core', 'agents', 'testing', 'auth']
        for comp in known_components:
            if comp in desc_lower:
                components.append(comp)
        
        return list(dict.fromkeys(components))  # Dedupe while preserving order
    
    def _register_batch(self, batch: TaskBatch) -> None:
        """Register a batch in the internal tracking structures.
        
        Args:
            batch: Batch to register.
        """
        self._batches[batch.batch_id] = batch
        for task_id in batch.task_ids:
            self._task_to_batch[task_id] = batch.batch_id
    
    def get_batch_for_task(self, task_id: str) -> Optional[TaskBatch]:
        """Get the batch containing a specific task.
        
        Args:
            task_id: Task ID to look up.
            
        Returns:
            The batch containing this task, or None.
        """
        batch_id = self._task_to_batch.get(task_id)
        if batch_id:
            return self._batches.get(batch_id)
        return None
    
    def get_all_batches(self) -> List[TaskBatch]:
        """Get all registered batches.
        
        Returns:
            List of all batches.
        """
        return list(self._batches.values())


def generate_batch_claim_sql(
    batch: TaskBatch,
    worker_id: str
) -> str:
    """Generate SQL for atomically claiming a batch of tasks.
    
    Args:
        batch: The batch to claim.
        worker_id: Worker ID to assign.
        
    Returns:
        SQL statement for atomic batch claim.
    """
    task_ids = batch.task_ids
    task_ids_str = ", ".join(f"'{tid}'" for tid in task_ids)
    
    sql = f"""
    UPDATE governance_tasks 
    SET assigned_worker = '{worker_id}',
        status = 'in_progress',
        started_at = NOW(),
        metadata = COALESCE(metadata, '{{}}'::jsonb) || 
            '{{"batch_id": "{batch.batch_id}", "batch_size": {batch.size}}}'::jsonb
    WHERE id IN ({task_ids_str})
      AND status = 'pending'
    RETURNING id;
    """
    
    return sql.strip()


def generate_batch_complete_sql(
    batch: TaskBatch,
    pr_url: str
) -> str:
    """Generate SQL for marking a batch complete with PR evidence.
    
    Args:
        batch: The batch to mark complete.
        pr_url: URL of the merged PR.
        
    Returns:
        SQL statement for batch completion.
    """
    task_ids = batch.task_ids
    task_ids_str = ", ".join(f"'{tid}'" for tid in task_ids)
    
    sql = f"""
    UPDATE governance_tasks 
    SET status = 'completed',
        completed_at = NOW(),
        completion_evidence = 'Merged batched PR: {pr_url}'
    WHERE id IN ({task_ids_str})
      AND status = 'in_progress';
    """
    
    return sql.strip()
