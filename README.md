# JUGGERNAUT-AUTONOMY

Autonomous revenue generation system. Target: $100M.

## What It Does

JUGGERNAUT is a self-operating business system where AI workers autonomously claim and execute tasks from a central governance database. The system:

- **Manages a task queue** where AI workers pick up pending work, claim it with unique IDs, and execute without human intervention
- **Handles its own development** - workers create branches, write code, submit PRs, and merge after automated review
- **Tracks revenue experiments** - tests different business approaches and measures results
- **Coordinates multiple agents** - scales from single-worker execution to multi-agent collaboration
- **Self-monitors** - logs all activity, tracks progress, and surfaces issues
- **Unified Brain architecture** - centralized AI reasoning with standardized tool execution

The goal is an AI system that can identify opportunities, build solutions, and generate revenue with minimal human oversight.

## Structure
```
/core        - Database operations, logging, shared utilities
/core/unified_brain.py - Centralized brain with tool execution
/agents      - L3-L5 agent implementations  
/experiments - Revenue experiment definitions and tracking
/api         - External API endpoints
/docs        - Schema documentation, architecture decisions
/orchestrator - Task coordination and worker management
/services    - Business logic and integrations
/mcp         - Model Context Protocol server for tool execution
```

## Quick Start

```bash
pip install -r requirements.txt
python -m core.database  # Verify database connection
```

## Core Functions

### Unified Brain
```python
from core.unified_brain import BrainService

brain = BrainService()
result = brain.consult_with_tools(
    question="What's the status of our revenue experiments?",
    enable_tools=True,
    auto_execute=True
)
print(result["response"])
```

### Code Execution
```python
from core.unified_brain import BrainService

brain = BrainService()
result = brain._execute_tool(
    tool_name="code_executor",
    arguments={
        "task_title": "Add new feature",
        "task_description": "Implement X functionality",
        "auto_merge": True
    }
)
print(result)
```

### Logging
```python
from core.database import log_execution

log_execution(
    worker_id="ORCHESTRATOR",
    action="experiment.start",
    message="Starting digital products experiment",
    output_data={"experiment_id": "exp_001"}
)
```

### Opportunity Tracking
```python
from core.database import create_opportunity

opp_id = create_opportunity(
    opportunity_type="digital_product",
    category="templates",
    description="AI prompt pack for business automation",
    estimated_value=500,
    confidence_score=0.7
)
```

## Current Phase: L3.5 (Advanced Agents with Partial Innovation)

**L5 Completion: ~65%** | **Revenue Generated: $0** (infrastructure complete, activation pending)

### Completed Infrastructure
- [x] Database schema deployed (21 tables)
- [x] Unified Brain architecture with streaming
- [x] Autonomous task execution loop
- [x] Self-healing with model fallback (Milestone 2A)
- [x] Multi-agent coordination (Milestone 3A)
- [x] Conflict resolution system (Milestone 3B)
- [x] Innovation engine (Milestone 4A)
- [x] Opportunity discovery framework
- [x] Experiment management system
- [x] Cost-optimized models ($111/month)
- [x] Hallucination gating

### Pending Activation
- [ ] Revenue generation (infrastructure exists, not activated)
- [ ] Scheduled opportunity scans
- [ ] Active experiments running
- [ ] Learning from results
- [ ] Autonomous financial management

## L1-L5 Autonomy Levels

| Level | Name | Capabilities | Status |
|-------|------|--------------|--------|
| L1 | Conversational | Basic Q&A, chat interface | ✅ 100% |
| L2 | Reasoners | Multi-turn memory, chain-of-thought, risk assessment | ✅ 100% |
| L3 | Agents | Goal acceptance, tool execution, error recovery | ✅ 100% |
| L4 | Innovators | Proactive scanning, experimentation, self-improvement | ⚠️ 70% |
| L5 | Organizations | Multi-agent coordination, resource allocation, revenue generation | ⚠️ 50% |

**See [docs/L5_AUTONOMY_AUDIT.md](docs/L5_AUTONOMY_AUDIT.md) for detailed assessment.**

## Database

Neon PostgreSQL via SQL over HTTP.

See [docs/SCHEMA.md](docs/SCHEMA.md) for full schema documentation.
