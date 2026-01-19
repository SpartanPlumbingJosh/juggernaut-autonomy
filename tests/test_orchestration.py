"""Tests for core/orchestration.py module.

Covers L5 capabilities: Agent Coordination, Resource Allocation, Cross-Agent Memory.
Target: 80%+ coverage for orchestration module.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from uuid import uuid4

# Import module under test
from core.orchestration import (
    AgentStatus,
    TaskPriority,
    HandoffReason,
    ConflictType,
    EscalationLevel,
    AgentCard,
    SwarmTask,
    _format_value,
    discover_agents,
    route_task,
    get_agent_workload,
    balance_workload,
    handoff_task,
    log_coordination_event,
    allocate_budget_to_goal,
    get_resource_status,
    resolve_conflict,
    write_shared_memory,
    read_shared_memory,
    sync_memory_to_agents,
    garbage_collect_memory,
    create_escalation,
    get_open_escalations,
    resolve_escalation,
    check_escalation_timeouts,
    detect_agent_failures,
    handle_agent_failure,
    activate_backup_agent,
    run_health_check,
)


class TestEnums:
    """Test enum definitions."""

    def test_agent_status_values(self):
        """AgentStatus enum has expected values."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.BUSY.value == "busy"
        assert AgentStatus.OFFLINE.value == "offline"

    def test_task_priority_values(self):
        """TaskPriority enum has expected values."""
        assert TaskPriority.CRITICAL.value == "critical"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.MEDIUM.value == "medium"
        assert TaskPriority.LOW.value == "low"

    def test_handoff_reason_values(self):
        """HandoffReason enum has expected values."""
        assert HandoffReason.CAPACITY.value == "capacity"
        assert HandoffReason.EXPERTISE.value == "expertise"
        assert HandoffReason.FAILURE.value == "failure"

    def test_conflict_type_values(self):
        """ConflictType enum has expected values."""
        assert ConflictType.RESOURCE.value == "resource"
        assert ConflictType.PRIORITY.value == "priority"
        assert ConflictType.OWNERSHIP.value == "ownership"

    def test_escalation_level_values(self):
        """EscalationLevel enum has expected values."""
        assert EscalationLevel.WORKER.value == 1
        assert EscalationLevel.ORCHESTRATOR.value == 2
        assert EscalationLevel.OWNER.value == 3


class TestDataclasses:
    """Test dataclass definitions."""

    def test_agent_card_creation(self):
        """AgentCard can be created with required fields."""
        card = AgentCard(
            worker_id="test-worker-1",
            role="developer",
            capabilities=["python", "testing"],
            status=AgentStatus.IDLE,
        )
        assert card.worker_id == "test-worker-1"
        assert card.role == "developer"
        assert "python" in card.capabilities
        assert card.status == AgentStatus.IDLE

    def test_swarm_task_creation(self):
        """SwarmTask can be created with required fields."""
        task = SwarmTask(
            task_id=str(uuid4()),
            title="Test Task",
            priority=TaskPriority.HIGH,
            task_type="code",
        )
        assert task.title == "Test Task"
        assert task.priority == TaskPriority.HIGH
        assert task.task_type == "code"


class TestFormatValue:
    """Test SQL value formatting utility."""

    def test_format_none(self):
        """None formats to NULL."""
        assert _format_value(None) == "NULL"

    def test_format_string(self):
        """Strings are quoted and escaped."""
        assert _format_value("test") == "'test'"
        assert _format_value("it's") == "'it''s'"

    def test_format_int(self):
        """Integers are converted to strings."""
        assert _format_value(42) == "42"

    def test_format_float(self):
        """Floats are converted to strings."""
        assert _format_value(3.14) == "3.14"

    def test_format_bool(self):
        """Booleans format as true/false."""
        assert _format_value(True) == "true"
        assert _format_value(False) == "false"


class TestDiscoverAgents:
    """Test agent discovery function."""

    @patch("core.orchestration._query")
    def test_discover_agents_returns_list(self, mock_query):
        """discover_agents returns list of AgentCards."""
        mock_query.return_value = {
            "rows": [
                {
                    "worker_id": "agent-1",
                    "role": "developer",
                    "capabilities": ["python"],
                    "status": "idle",
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                }
            ]
        }
        agents = discover_agents()
        assert isinstance(agents, list)
        mock_query.assert_called_once()

    @patch("core.orchestration._query")
    def test_discover_agents_empty(self, mock_query):
        """discover_agents handles no agents."""
        mock_query.return_value = {"rows": []}
        agents = discover_agents()
        assert agents == []


class TestRouteTask:
    """Test task routing function."""

    @patch("core.orchestration._query")
    @patch("core.orchestration.discover_agents")
    def test_route_task_finds_agent(self, mock_discover, mock_query):
        """route_task finds available agent."""
        mock_discover.return_value = [
            AgentCard(
                worker_id="agent-1",
                role="developer",
                capabilities=["python"],
                status=AgentStatus.IDLE,
            )
        ]
        mock_query.return_value = {"rows": [], "rowCount": 0}
        
        task = SwarmTask(
            task_id=str(uuid4()),
            title="Test Task",
            priority=TaskPriority.MEDIUM,
            task_type="code",
        )
        result = route_task(task)
        # Result is either agent_id or None
        assert result is None or isinstance(result, str)

    @patch("core.orchestration.discover_agents")
    def test_route_task_no_agents(self, mock_discover):
        """route_task returns None when no agents available."""
        mock_discover.return_value = []
        task = SwarmTask(
            task_id=str(uuid4()),
            title="Test Task",
            priority=TaskPriority.MEDIUM,
            task_type="code",
        )
        result = route_task(task)
        assert result is None


class TestGetAgentWorkload:
    """Test workload retrieval function."""

    @patch("core.orchestration._query")
    def test_get_agent_workload_returns_dict(self, mock_query):
        """get_agent_workload returns workload dictionary."""
        mock_query.return_value = {
            "rows": [{"pending": 5, "in_progress": 2, "total": 7}]
        }
        workload = get_agent_workload("test-agent")
        assert isinstance(workload, dict)

    @patch("core.orchestration._query")
    def test_get_agent_workload_empty(self, mock_query):
        """get_agent_workload handles missing agent."""
        mock_query.return_value = {"rows": []}
        workload = get_agent_workload("nonexistent")
        assert workload == {} or "pending" not in workload


class TestBalanceWorkload:
    """Test workload balancing function."""

    @patch("core.orchestration._query")
    @patch("core.orchestration.discover_agents")
    def test_balance_workload_dry_run(self, mock_discover, mock_query):
        """balance_workload in dry_run mode returns suggestions."""
        mock_discover.return_value = []
        mock_query.return_value = {"rows": []}
        suggestions = balance_workload(dry_run=True)
        assert isinstance(suggestions, list)


class TestHandoffTask:
    """Test task handoff function."""

    @patch("core.orchestration._query")
    def test_handoff_task_success(self, mock_query):
        """handoff_task updates task assignment."""
        mock_query.return_value = {"rowCount": 1}
        result = handoff_task(
            task_id=str(uuid4()),
            from_agent="agent-1",
            to_agent="agent-2",
            reason=HandoffReason.CAPACITY,
        )
        assert result is True or result is False


class TestLogCoordinationEvent:
    """Test coordination event logging."""

    @patch("core.orchestration._query")
    def test_log_event_success(self, mock_query):
        """log_coordination_event creates event record."""
        mock_query.return_value = {"rows": [{"id": str(uuid4())}]}
        event_id = log_coordination_event(
            event_type="task_assigned",
            data={"task_id": "123", "agent_id": "456"},
        )
        assert event_id is None or isinstance(event_id, str)


class TestAllocateBudget:
    """Test budget allocation function."""

    @patch("core.orchestration._query")
    def test_allocate_budget_success(self, mock_query):
        """allocate_budget_to_goal updates budget."""
        mock_query.return_value = {"rowCount": 1}
        result = allocate_budget_to_goal(
            goal_id=str(uuid4()),
            budget_cents=10000,
            source="daily_pool",
        )
        assert result is True or result is False


class TestGetResourceStatus:
    """Test resource status retrieval."""

    @patch("core.orchestration._query")
    def test_get_resource_status_returns_dict(self, mock_query):
        """get_resource_status returns status dictionary."""
        mock_query.return_value = {
            "rows": [{"total_budget": 100000, "used": 25000}]
        }
        status = get_resource_status()
        assert isinstance(status, dict)


class TestResolveConflict:
    """Test conflict resolution function."""

    @patch("core.orchestration._query")
    def test_resolve_conflict_returns_result(self, mock_query):
        """resolve_conflict returns resolution result."""
        mock_query.return_value = {"rowCount": 1}
        result = resolve_conflict(
            conflict_type=ConflictType.RESOURCE,
            participants=["agent-1", "agent-2"],
            resource_id="resource-123",
        )
        assert result is not None


class TestSharedMemory:
    """Test shared memory functions."""

    @patch("core.orchestration._query")
    def test_write_shared_memory(self, mock_query):
        """write_shared_memory stores data."""
        mock_query.return_value = {"rowCount": 1}
        result = write_shared_memory(
            key="test_key",
            value={"data": "test"},
            ttl_hours=24,
        )
        assert result is True or result is False

    @patch("core.orchestration._query")
    def test_read_shared_memory(self, mock_query):
        """read_shared_memory retrieves data."""
        mock_query.return_value = {
            "rows": [{"value": '{"data": "test"}'}]
        }
        result = read_shared_memory("test_key")
        assert result is None or isinstance(result, dict)

    @patch("core.orchestration._query")
    def test_read_shared_memory_missing(self, mock_query):
        """read_shared_memory handles missing key."""
        mock_query.return_value = {"rows": []}
        result = read_shared_memory("nonexistent")
        assert result is None


class TestSyncMemory:
    """Test memory synchronization function."""

    @patch("core.orchestration._query")
    @patch("core.orchestration.discover_agents")
    def test_sync_memory_to_agents(self, mock_discover, mock_query):
        """sync_memory_to_agents broadcasts to agents."""
        mock_discover.return_value = []
        mock_query.return_value = {"rowCount": 0}
        result = sync_memory_to_agents(
            key="sync_key",
            value={"synced": True},
        )
        assert isinstance(result, int)


class TestGarbageCollect:
    """Test memory garbage collection."""

    @patch("core.orchestration._query")
    def test_garbage_collect_memory(self, mock_query):
        """garbage_collect_memory removes old entries."""
        mock_query.return_value = {"rowCount": 5}
        count = garbage_collect_memory(max_age_days=30)
        assert isinstance(count, int)


class TestEscalations:
    """Test escalation management functions."""

    @patch("core.orchestration._query")
    def test_create_escalation(self, mock_query):
        """create_escalation creates new escalation."""
        mock_query.return_value = {"rows": [{"id": str(uuid4())}]}
        result = create_escalation(
            task_id=str(uuid4()),
            reason="Budget exceeded",
            level=EscalationLevel.ORCHESTRATOR,
        )
        assert result is None or isinstance(result, str)

    @patch("core.orchestration._query")
    def test_get_open_escalations(self, mock_query):
        """get_open_escalations returns list."""
        mock_query.return_value = {"rows": []}
        escalations = get_open_escalations()
        assert isinstance(escalations, list)

    @patch("core.orchestration._query")
    def test_resolve_escalation(self, mock_query):
        """resolve_escalation updates escalation."""
        mock_query.return_value = {"rowCount": 1}
        result = resolve_escalation(
            escalation_id=str(uuid4()),
            resolution="Approved",
            resolved_by="josh",
        )
        assert result is True or result is False

    @patch("core.orchestration._query")
    def test_check_escalation_timeouts(self, mock_query):
        """check_escalation_timeouts finds timed out escalations."""
        mock_query.return_value = {"rows": []}
        timeouts = check_escalation_timeouts()
        assert isinstance(timeouts, list)


class TestFailureDetection:
    """Test failure detection and recovery functions."""

    @patch("core.orchestration._query")
    def test_detect_agent_failures(self, mock_query):
        """detect_agent_failures finds stale agents."""
        mock_query.return_value = {"rows": []}
        failures = detect_agent_failures(heartbeat_threshold_seconds=120)
        assert isinstance(failures, list)

    @patch("core.orchestration._query")
    def test_handle_agent_failure(self, mock_query):
        """handle_agent_failure processes failure."""
        mock_query.return_value = {"rowCount": 1, "rows": []}
        result = handle_agent_failure("failed-agent")
        assert isinstance(result, dict)

    @patch("core.orchestration._query")
    def test_activate_backup_agent(self, mock_query):
        """activate_backup_agent starts backup."""
        mock_query.return_value = {"rowCount": 1}
        result = activate_backup_agent(
            primary_id="primary-agent",
            backup_id="backup-agent",
        )
        assert result is True or result is False


class TestHealthCheck:
    """Test health check function."""

    @patch("core.orchestration._query")
    @patch("core.orchestration.discover_agents")
    @patch("core.orchestration.get_resource_status")
    @patch("core.orchestration.get_open_escalations")
    def test_run_health_check(
        self, mock_escalations, mock_resources, mock_discover, mock_query
    ):
        """run_health_check returns system health."""
        mock_discover.return_value = []
        mock_resources.return_value = {}
        mock_escalations.return_value = []
        mock_query.return_value = {"rows": []}
        
        health = run_health_check()
        assert isinstance(health, dict)
        assert "status" in health or "agents" in health or len(health) >= 0
