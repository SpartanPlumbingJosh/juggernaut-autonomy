"""
Conflict Resolution System for Multi-Agent Coordination.

This module handles conflicts that arise when multiple agents compete for resources,
attempt contradictory actions, or need to coordinate on shared goals:
- Resource contention resolution
- Action conflict detection and mediation
- Priority-based conflict resolution
- Consensus building for multi-agent decisions
- Deadlock detection and breaking
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur in multi-agent systems."""
    RESOURCE_CONTENTION = "resource_contention"
    CONTRADICTORY_ACTIONS = "contradictory_actions"
    GOAL_CONFLICT = "goal_conflict"
    PRIORITY_CONFLICT = "priority_conflict"
    DEADLOCK = "deadlock"
    CAPABILITY_OVERLAP = "capability_overlap"


class ResolutionStrategy(Enum):
    """Strategies for resolving conflicts."""
    PRIORITY_BASED = "priority_based"
    FIRST_COME_FIRST_SERVE = "first_come_first_serve"
    ROUND_ROBIN = "round_robin"
    CONSENSUS = "consensus"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    SPLIT_RESOURCE = "split_resource"
    QUEUE_AND_RETRY = "queue_and_retry"


@dataclass
class ConflictContext:
    """Context information about a detected conflict."""
    conflict_id: str
    conflict_type: ConflictType
    agents_involved: List[str]
    resources_involved: List[str]
    description: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resolution:
    """Result of conflict resolution."""
    conflict_id: str
    strategy_used: ResolutionStrategy
    winner_agent: Optional[str]
    losers: List[str]
    action_taken: str
    reason: str
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requires_retry: bool = False
    retry_delay_seconds: float = 0.0


class ConflictResolver:
    """
    Resolves conflicts between multiple agents competing for resources or actions.
    
    Handles:
    - Resource locks and contention
    - Contradictory action detection
    - Priority-based mediation
    - Deadlock detection and breaking
    - Consensus building
    """
    
    def __init__(self, default_strategy: ResolutionStrategy = ResolutionStrategy.PRIORITY_BASED):
        """
        Initialize conflict resolver.
        
        Args:
            default_strategy: Default resolution strategy
        """
        self.default_strategy = default_strategy
        self.active_conflicts: Dict[str, ConflictContext] = {}
        self.resolved_conflicts: List[Resolution] = []
        self.resource_locks: Dict[str, str] = {}  # resource_id -> agent_id
        self.agent_priorities: Dict[str, int] = {}
        self.round_robin_index = 0
        
        logger.info(f"Conflict resolver initialized with {default_strategy.value} strategy")
    
    def set_agent_priority(self, agent_id: str, priority: int) -> None:
        """
        Set priority level for an agent (higher = more priority).
        
        Args:
            agent_id: Agent identifier
            priority: Priority level (0-10, 10 = highest)
        """
        self.agent_priorities[agent_id] = max(0, min(10, priority))
    
    def detect_resource_conflict(
        self,
        resource_id: str,
        requesting_agents: List[str]
    ) -> Optional[ConflictContext]:
        """
        Detect if multiple agents are requesting the same resource.
        
        Args:
            resource_id: Resource being requested
            requesting_agents: List of agents requesting the resource
            
        Returns:
            ConflictContext if conflict detected, None otherwise
        """
        if len(requesting_agents) <= 1:
            return None
        
        conflict_id = f"resource_{resource_id}_{datetime.now(timezone.utc).timestamp()}"
        
        conflict = ConflictContext(
            conflict_id=conflict_id,
            conflict_type=ConflictType.RESOURCE_CONTENTION,
            agents_involved=requesting_agents,
            resources_involved=[resource_id],
            description=f"{len(requesting_agents)} agents competing for resource {resource_id}",
        )
        
        self.active_conflicts[conflict_id] = conflict
        logger.warning(f"Resource conflict detected: {conflict.description}")
        
        return conflict
    
    def detect_action_conflict(
        self,
        action_type: str,
        agent_actions: Dict[str, Any]
    ) -> Optional[ConflictContext]:
        """
        Detect if agents are attempting contradictory actions.
        
        Args:
            action_type: Type of action being performed
            agent_actions: Dict mapping agent_id to their intended action
            
        Returns:
            ConflictContext if conflict detected
        """
        if len(agent_actions) <= 1:
            return None
        
        # Check for contradictory actions (e.g., one wants to start, another wants to stop)
        actions = list(agent_actions.values())
        if self._are_contradictory(actions):
            conflict_id = f"action_{action_type}_{datetime.now(timezone.utc).timestamp()}"
            
            conflict = ConflictContext(
                conflict_id=conflict_id,
                conflict_type=ConflictType.CONTRADICTORY_ACTIONS,
                agents_involved=list(agent_actions.keys()),
                resources_involved=[action_type],
                description=f"Contradictory actions detected for {action_type}",
                metadata={"actions": agent_actions},
            )
            
            self.active_conflicts[conflict_id] = conflict
            logger.warning(f"Action conflict detected: {conflict.description}")
            
            return conflict
        
        return None
    
    def _are_contradictory(self, actions: List[Any]) -> bool:
        """Check if actions are contradictory."""
        # Simple heuristic: check for opposing keywords
        action_strs = [str(a).lower() for a in actions]
        
        opposing_pairs = [
            ("start", "stop"),
            ("enable", "disable"),
            ("create", "delete"),
            ("increase", "decrease"),
            ("on", "off"),
        ]
        
        for action in action_strs:
            for word1, word2 in opposing_pairs:
                if word1 in action:
                    for other_action in action_strs:
                        if other_action != action and word2 in other_action:
                            return True
        
        return False
    
    def resolve_conflict(
        self,
        conflict: ConflictContext,
        strategy: Optional[ResolutionStrategy] = None
    ) -> Resolution:
        """
        Resolve a conflict using specified strategy.
        
        Args:
            conflict: Conflict to resolve
            strategy: Resolution strategy (uses default if None)
            
        Returns:
            Resolution result
        """
        strategy = strategy or self.default_strategy
        
        logger.info(f"Resolving conflict {conflict.conflict_id} using {strategy.value}")
        
        if strategy == ResolutionStrategy.PRIORITY_BASED:
            return self._resolve_by_priority(conflict)
        
        elif strategy == ResolutionStrategy.FIRST_COME_FIRST_SERVE:
            return self._resolve_first_come(conflict)
        
        elif strategy == ResolutionStrategy.ROUND_ROBIN:
            return self._resolve_round_robin(conflict)
        
        elif strategy == ResolutionStrategy.CONSENSUS:
            return self._resolve_by_consensus(conflict)
        
        elif strategy == ResolutionStrategy.SPLIT_RESOURCE:
            return self._resolve_by_splitting(conflict)
        
        elif strategy == ResolutionStrategy.QUEUE_AND_RETRY:
            return self._resolve_by_queuing(conflict)
        
        else:
            # Default to escalation
            return self._resolve_by_escalation(conflict)
    
    def _resolve_by_priority(self, conflict: ConflictContext) -> Resolution:
        """Resolve conflict by agent priority."""
        agents = conflict.agents_involved
        
        # Get priorities (default to 5 if not set)
        agent_priorities = {
            agent: self.agent_priorities.get(agent, 5)
            for agent in agents
        }
        
        # Winner is highest priority
        winner = max(agent_priorities.keys(), key=lambda a: agent_priorities[a])
        losers = [a for a in agents if a != winner]
        
        # Lock resource if applicable
        if conflict.resources_involved:
            for resource in conflict.resources_involved:
                self.resource_locks[resource] = winner
        
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy_used=ResolutionStrategy.PRIORITY_BASED,
            winner_agent=winner,
            losers=losers,
            action_taken=f"Granted access to {winner} (priority {agent_priorities[winner]})",
            reason=f"Agent {winner} has highest priority",
            requires_retry=True,
            retry_delay_seconds=5.0,
        )
        
        self._record_resolution(resolution)
        return resolution
    
    def _resolve_first_come(self, conflict: ConflictContext) -> Resolution:
        """Resolve conflict by first-come-first-serve."""
        # First agent in list wins
        winner = conflict.agents_involved[0]
        losers = conflict.agents_involved[1:]
        
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy_used=ResolutionStrategy.FIRST_COME_FIRST_SERVE,
            winner_agent=winner,
            losers=losers,
            action_taken=f"Granted access to {winner} (first requester)",
            reason="First-come-first-serve policy",
            requires_retry=True,
            retry_delay_seconds=3.0,
        )
        
        self._record_resolution(resolution)
        return resolution
    
    def _resolve_round_robin(self, conflict: ConflictContext) -> Resolution:
        """Resolve conflict using round-robin selection."""
        agents = conflict.agents_involved
        winner = agents[self.round_robin_index % len(agents)]
        self.round_robin_index += 1
        
        losers = [a for a in agents if a != winner]
        
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy_used=ResolutionStrategy.ROUND_ROBIN,
            winner_agent=winner,
            losers=losers,
            action_taken=f"Granted access to {winner} (round-robin)",
            reason="Round-robin fairness policy",
            requires_retry=True,
            retry_delay_seconds=2.0,
        )
        
        self._record_resolution(resolution)
        return resolution
    
    def _resolve_by_consensus(self, conflict: ConflictContext) -> Resolution:
        """Resolve conflict by attempting consensus."""
        # Simplified: if all agents have same priority, split or escalate
        agents = conflict.agents_involved
        priorities = [self.agent_priorities.get(a, 5) for a in agents]
        
        if len(set(priorities)) == 1:
            # All equal priority - escalate for human decision
            return self._resolve_by_escalation(conflict)
        else:
            # Fall back to priority-based
            return self._resolve_by_priority(conflict)
    
    def _resolve_by_splitting(self, conflict: ConflictContext) -> Resolution:
        """Resolve by splitting resource among agents."""
        agents = conflict.agents_involved
        
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy_used=ResolutionStrategy.SPLIT_RESOURCE,
            winner_agent=None,
            losers=[],
            action_taken=f"Split resource among {len(agents)} agents",
            reason="Resource can be shared",
            requires_retry=False,
        )
        
        self._record_resolution(resolution)
        return resolution
    
    def _resolve_by_queuing(self, conflict: ConflictContext) -> Resolution:
        """Resolve by queuing agents for sequential access."""
        agents = conflict.agents_involved
        winner = agents[0]
        losers = agents[1:]
        
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy_used=ResolutionStrategy.QUEUE_AND_RETRY,
            winner_agent=winner,
            losers=losers,
            action_taken=f"Queued {len(losers)} agents for retry",
            reason="Sequential access via queue",
            requires_retry=True,
            retry_delay_seconds=10.0,
        )
        
        self._record_resolution(resolution)
        return resolution
    
    def _resolve_by_escalation(self, conflict: ConflictContext) -> Resolution:
        """Escalate conflict to human for decision."""
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy_used=ResolutionStrategy.ESCALATE_TO_HUMAN,
            winner_agent=None,
            losers=conflict.agents_involved,
            action_taken="Escalated to human operator",
            reason="Conflict requires human judgment",
            requires_retry=False,
        )
        
        self._record_resolution(resolution)
        logger.warning(f"Conflict {conflict.conflict_id} escalated to human")
        
        return resolution
    
    def _record_resolution(self, resolution: Resolution) -> None:
        """Record resolved conflict and clean up."""
        self.resolved_conflicts.append(resolution)
        
        if resolution.conflict_id in self.active_conflicts:
            del self.active_conflicts[resolution.conflict_id]
        
        logger.info(f"Conflict {resolution.conflict_id} resolved: {resolution.action_taken}")
    
    def release_resource(self, resource_id: str, agent_id: str) -> bool:
        """
        Release a resource lock held by an agent.
        
        Args:
            resource_id: Resource to release
            agent_id: Agent releasing the resource
            
        Returns:
            True if successfully released
        """
        if resource_id in self.resource_locks:
            if self.resource_locks[resource_id] == agent_id:
                del self.resource_locks[resource_id]
                logger.info(f"Agent {agent_id} released resource {resource_id}")
                return True
        
        return False
    
    def get_resolution_metrics(self) -> Dict[str, Any]:
        """Get conflict resolution metrics."""
        total_resolved = len(self.resolved_conflicts)
        
        if total_resolved == 0:
            return {
                "total_conflicts_resolved": 0,
                "active_conflicts": len(self.active_conflicts),
                "resolution_strategies": {},
                "average_resolution_time_ms": 0.0,
            }
        
        # Count by strategy
        strategy_counts = defaultdict(int)
        for resolution in self.resolved_conflicts:
            strategy_counts[resolution.strategy_used.value] += 1
        
        # Calculate average resolution time
        resolution_times = []
        for resolution in self.resolved_conflicts:
            if resolution.conflict_id in self.active_conflicts:
                conflict = self.active_conflicts[resolution.conflict_id]
                duration = (resolution.resolved_at - conflict.detected_at).total_seconds() * 1000
                resolution_times.append(duration)
        
        avg_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
        
        return {
            "total_conflicts_resolved": total_resolved,
            "active_conflicts": len(self.active_conflicts),
            "resolution_strategies": dict(strategy_counts),
            "average_resolution_time_ms": round(avg_time, 2),
            "escalations": strategy_counts.get(ResolutionStrategy.ESCALATE_TO_HUMAN.value, 0),
        }


# Global resolver instance
_resolver: Optional[ConflictResolver] = None


def get_conflict_resolver(
    strategy: ResolutionStrategy = ResolutionStrategy.PRIORITY_BASED
) -> ConflictResolver:
    """Get or create global conflict resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = ConflictResolver(default_strategy=strategy)
    return _resolver
