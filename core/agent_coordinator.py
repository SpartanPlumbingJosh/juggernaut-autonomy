"""
Multi-Agent Coordination System for Juggernaut.

This module implements agent coordination, task distribution, and load balancing:
- Agent registry with capability matching
- Intelligent task routing based on agent capabilities and load
- Load balancing across multiple agents
- Agent health monitoring and failover
- Coordination protocols for multi-agent workflows
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from .database import query_db, escape_sql_value
from .orchestration import AgentCard, AgentStatus, SwarmTask, TaskPriority

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Task routing strategies for agent selection."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    COST_OPTIMIZED = "cost_optimized"
    FASTEST_RESPONSE = "fastest_response"


@dataclass
class AgentLoad:
    """Current load metrics for an agent."""
    agent_id: str
    current_tasks: int
    max_concurrent: int
    avg_duration_seconds: float
    success_rate: float
    daily_cost_cents: float
    last_heartbeat: datetime
    
    @property
    def load_percentage(self) -> float:
        """Calculate load as percentage of capacity."""
        if self.max_concurrent == 0:
            return 100.0
        return (self.current_tasks / self.max_concurrent) * 100.0
    
    @property
    def is_available(self) -> bool:
        """Check if agent can accept more tasks."""
        return self.current_tasks < self.max_concurrent
    
    @property
    def is_healthy(self) -> bool:
        """Check if agent is responding (heartbeat within 60s)."""
        age = datetime.now(timezone.utc) - self.last_heartbeat
        return age < timedelta(seconds=60)


@dataclass
class CoordinationMetrics:
    """Metrics for multi-agent coordination."""
    total_agents: int = 0
    active_agents: int = 0
    idle_agents: int = 0
    busy_agents: int = 0
    total_tasks_routed: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    average_routing_time_ms: float = 0.0
    load_balance_score: float = 100.0  # 100 = perfectly balanced


class AgentCoordinator:
    """
    Coordinates multiple agents for distributed task execution.
    
    Responsibilities:
    - Maintain agent registry with capabilities
    - Route tasks to appropriate agents
    - Balance load across agents
    - Monitor agent health and handle failover
    - Track coordination metrics
    """
    
    def __init__(self, routing_strategy: RoutingStrategy = RoutingStrategy.LEAST_LOADED):
        """
        Initialize agent coordinator.
        
        Args:
            routing_strategy: Default strategy for task routing
        """
        self.routing_strategy = routing_strategy
        self.agents: Dict[str, AgentCard] = {}
        self.agent_loads: Dict[str, AgentLoad] = {}
        self.metrics = CoordinationMetrics()
        self.round_robin_index = 0
        
        logger.info(f"Agent coordinator initialized with {routing_strategy.value} routing")
    
    def register_agent(self, agent: AgentCard) -> bool:
        """
        Register an agent in the coordination system.
        
        Args:
            agent: AgentCard with agent details
            
        Returns:
            True if successfully registered
        """
        try:
            self.agents[agent.agent_id] = agent
            
            # Initialize load tracking
            self.agent_loads[agent.agent_id] = AgentLoad(
                agent_id=agent.agent_id,
                current_tasks=0,
                max_concurrent=agent.max_concurrent_tasks,
                avg_duration_seconds=agent.avg_task_duration_seconds,
                success_rate=agent.success_rate_threshold,
                daily_cost_cents=0.0,
                last_heartbeat=datetime.now(timezone.utc),
            )
            
            self.metrics.total_agents += 1
            self.metrics.idle_agents += 1
            
            logger.info(f"Registered agent {agent.agent_id} ({agent.role})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent {agent.agent_id}: {e}")
            return False
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        Remove an agent from the coordination system.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successfully unregistered
        """
        if agent_id in self.agents:
            del self.agents[agent_id]
            if agent_id in self.agent_loads:
                del self.agent_loads[agent_id]
            self.metrics.total_agents -= 1
            logger.info(f"Unregistered agent {agent_id}")
            return True
        return False
    
    def update_agent_heartbeat(self, agent_id: str) -> bool:
        """
        Update agent heartbeat timestamp.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if updated
        """
        if agent_id in self.agent_loads:
            self.agent_loads[agent_id].last_heartbeat = datetime.now(timezone.utc)
            return True
        return False
    
    def get_agents_by_capability(self, required_capabilities: List[str]) -> List[AgentCard]:
        """
        Find agents that have all required capabilities.
        
        Args:
            required_capabilities: List of required capability strings
            
        Returns:
            List of matching agents
        """
        matching_agents = []
        
        for agent in self.agents.values():
            agent_caps = set(agent.capabilities)
            required_caps = set(required_capabilities)
            
            if required_caps.issubset(agent_caps):
                matching_agents.append(agent)
        
        return matching_agents
    
    def select_agent_for_task(
        self,
        task: SwarmTask,
        strategy: Optional[RoutingStrategy] = None
    ) -> Optional[str]:
        """
        Select best agent for a task based on routing strategy.
        
        Args:
            task: Task to route
            strategy: Routing strategy (uses default if None)
            
        Returns:
            Selected agent_id or None if no suitable agent
        """
        strategy = strategy or self.routing_strategy
        
        # Filter to healthy, available agents
        available_agents = [
            agent_id for agent_id, load in self.agent_loads.items()
            if load.is_healthy and load.is_available
        ]
        
        if not available_agents:
            logger.warning("No available agents for task routing")
            return None
        
        # Apply routing strategy
        if strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_agents)
        
        elif strategy == RoutingStrategy.LEAST_LOADED:
            return self._select_least_loaded(available_agents)
        
        elif strategy == RoutingStrategy.CAPABILITY_MATCH:
            return self._select_by_capability(task, available_agents)
        
        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            return self._select_cost_optimized(available_agents)
        
        elif strategy == RoutingStrategy.FASTEST_RESPONSE:
            return self._select_fastest(available_agents)
        
        else:
            # Default to least loaded
            return self._select_least_loaded(available_agents)
    
    def _select_round_robin(self, available_agents: List[str]) -> Optional[str]:
        """Round-robin selection across available agents."""
        if not available_agents:
            return None
        
        agent_id = available_agents[self.round_robin_index % len(available_agents)]
        self.round_robin_index += 1
        return agent_id
    
    def _select_least_loaded(self, available_agents: List[str]) -> Optional[str]:
        """Select agent with lowest current load."""
        if not available_agents:
            return None
        
        return min(
            available_agents,
            key=lambda aid: self.agent_loads[aid].load_percentage
        )
    
    def _select_by_capability(self, task: SwarmTask, available_agents: List[str]) -> Optional[str]:
        """Select agent based on capability match with task requirements."""
        # Extract required capabilities from task metadata
        required_caps = task.payload.get("required_capabilities", [])
        
        if not required_caps:
            # No specific requirements, fall back to least loaded
            return self._select_least_loaded(available_agents)
        
        # Filter agents with required capabilities
        capable_agents = []
        for agent_id in available_agents:
            agent = self.agents.get(agent_id)
            if agent:
                agent_caps = set(agent.capabilities)
                if set(required_caps).issubset(agent_caps):
                    capable_agents.append(agent_id)
        
        if not capable_agents:
            logger.warning(f"No agents with required capabilities: {required_caps}")
            return None
        
        # Among capable agents, select least loaded
        return self._select_least_loaded(capable_agents)
    
    def _select_cost_optimized(self, available_agents: List[str]) -> Optional[str]:
        """Select agent with lowest daily cost."""
        if not available_agents:
            return None
        
        return min(
            available_agents,
            key=lambda aid: self.agent_loads[aid].daily_cost_cents
        )
    
    def _select_fastest(self, available_agents: List[str]) -> Optional[str]:
        """Select agent with fastest average response time."""
        if not available_agents:
            return None
        
        return min(
            available_agents,
            key=lambda aid: self.agent_loads[aid].avg_duration_seconds
        )
    
    def route_task(self, task: SwarmTask) -> Dict[str, Any]:
        """
        Route a task to an appropriate agent.
        
        Args:
            task: Task to route
            
        Returns:
            Dict with routing result
        """
        start_time = datetime.now(timezone.utc)
        
        # Check if task has target agent specified
        if task.target_agent:
            agent_id = task.target_agent
            if agent_id not in self.agents:
                return {
                    "success": False,
                    "error": f"Target agent {agent_id} not found",
                }
            
            if not self.agent_loads[agent_id].is_available:
                return {
                    "success": False,
                    "error": f"Target agent {agent_id} not available",
                }
        else:
            # Select agent using routing strategy
            agent_id = self.select_agent_for_task(task)
            
            if not agent_id:
                self.metrics.failed_routes += 1
                return {
                    "success": False,
                    "error": "No suitable agent available",
                }
        
        # Assign task to agent
        task.target_agent = agent_id
        task.started_at = datetime.now(timezone.utc)
        task.status = "assigned"
        
        # Update agent load
        self.agent_loads[agent_id].current_tasks += 1
        
        # Update agent status
        agent = self.agents[agent_id]
        if self.agent_loads[agent_id].current_tasks >= agent.max_concurrent_tasks:
            agent.status = AgentStatus.BUSY
            self.metrics.busy_agents += 1
            self.metrics.idle_agents = max(0, self.metrics.idle_agents - 1)
        
        # Update metrics
        self.metrics.total_tasks_routed += 1
        self.metrics.successful_routes += 1
        
        routing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        self.metrics.average_routing_time_ms = (
            (self.metrics.average_routing_time_ms * (self.metrics.total_tasks_routed - 1) + routing_time)
            / self.metrics.total_tasks_routed
        )
        
        logger.info(f"Routed task {task.task_id} to agent {agent_id}")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_role": agent.role,
            "routing_time_ms": routing_time,
        }
    
    def complete_task(self, task_id: str, agent_id: str, success: bool, cost_cents: float = 0.0) -> None:
        """
        Mark task as completed and update agent load.
        
        Args:
            task_id: Task identifier
            agent_id: Agent that completed the task
            success: Whether task succeeded
            cost_cents: Cost of task execution
        """
        if agent_id in self.agent_loads:
            load = self.agent_loads[agent_id]
            load.current_tasks = max(0, load.current_tasks - 1)
            load.daily_cost_cents += cost_cents
            
            # Update agent status
            if load.current_tasks == 0:
                agent = self.agents.get(agent_id)
                if agent:
                    agent.status = AgentStatus.IDLE
                    self.metrics.idle_agents += 1
                    self.metrics.busy_agents = max(0, self.metrics.busy_agents - 1)
            
            logger.info(f"Task {task_id} completed by agent {agent_id} (success={success})")
    
    def get_load_balance_score(self) -> float:
        """
        Calculate load balance score (100 = perfectly balanced).
        
        Returns:
            Score from 0-100
        """
        if not self.agent_loads:
            return 100.0
        
        loads = [load.load_percentage for load in self.agent_loads.values()]
        
        if not loads:
            return 100.0
        
        avg_load = sum(loads) / len(loads)
        variance = sum((load - avg_load) ** 2 for load in loads) / len(loads)
        std_dev = variance ** 0.5
        
        # Score: 100 - (std_dev normalized to 0-100)
        # Lower std_dev = better balance
        score = max(0, 100 - (std_dev / 2))
        
        return round(score, 2)
    
    def get_coordination_metrics(self) -> Dict[str, Any]:
        """Get current coordination metrics."""
        self.metrics.load_balance_score = self.get_load_balance_score()
        
        # Count active agents (healthy with recent heartbeat)
        active_count = sum(
            1 for load in self.agent_loads.values()
            if load.is_healthy
        )
        self.metrics.active_agents = active_count
        
        return {
            "total_agents": self.metrics.total_agents,
            "active_agents": self.metrics.active_agents,
            "idle_agents": self.metrics.idle_agents,
            "busy_agents": self.metrics.busy_agents,
            "total_tasks_routed": self.metrics.total_tasks_routed,
            "successful_routes": self.metrics.successful_routes,
            "failed_routes": self.metrics.failed_routes,
            "success_rate": (
                self.metrics.successful_routes / self.metrics.total_tasks_routed * 100
                if self.metrics.total_tasks_routed > 0 else 0.0
            ),
            "average_routing_time_ms": round(self.metrics.average_routing_time_ms, 2),
            "load_balance_score": self.metrics.load_balance_score,
            "routing_strategy": self.routing_strategy.value,
        }
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific agent."""
        if agent_id not in self.agents:
            return None
        
        agent = self.agents[agent_id]
        load = self.agent_loads.get(agent_id)
        
        if not load:
            return None
        
        return {
            "agent_id": agent_id,
            "role": agent.role,
            "status": agent.status.value,
            "capabilities": agent.capabilities,
            "current_tasks": load.current_tasks,
            "max_concurrent": load.max_concurrent,
            "load_percentage": round(load.load_percentage, 2),
            "is_available": load.is_available,
            "is_healthy": load.is_healthy,
            "daily_cost_cents": load.daily_cost_cents,
            "success_rate": load.success_rate,
            "avg_duration_seconds": load.avg_duration_seconds,
            "last_heartbeat": load.last_heartbeat.isoformat(),
        }


# Global coordinator instance
_coordinator: Optional[AgentCoordinator] = None


def get_coordinator(routing_strategy: RoutingStrategy = RoutingStrategy.LEAST_LOADED) -> AgentCoordinator:
    """Get or create global agent coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator(routing_strategy=routing_strategy)
    return _coordinator
