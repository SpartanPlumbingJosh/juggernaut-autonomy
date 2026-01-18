# JUGGERNAUT-AUTONOMY

Autonomous revenue generation system. Target: $100M.

## Structure
```
/core        - Database operations, logging, shared utilities
/agents      - L3-L5 agent implementations  
/experiments - Revenue experiment definitions and tracking
/api         - External API endpoints
/docs        - Schema documentation, architecture decisions
```

## Quick Start

```bash
pip install -r requirements.txt
python -m core.database  # Verify database connection
```

## Core Functions

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

## Current Phase: 0 (Foundation)

- [x] Database schema deployed (21 tables)
- [x] Core logging functions
- [x] Opportunity tracking
- [x] Schema documentation
- [ ] First revenue experiment

## L1-L5 Autonomy Levels

| Level | Name | Capabilities |
|-------|------|--------------|
| L1 | Conversational | Basic Q&A, chat interface |
| L2 | Reasoners | Multi-turn memory, chain-of-thought |
| L3 | Agents | Goal acceptance, tool execution, error recovery |
| L4 | Innovators | Proactive scanning, experimentation, self-improvement |
| L5 | Organizations | Multi-agent coordination, resource allocation |

## Database

Neon PostgreSQL via SQL over HTTP.

See [docs/SCHEMA.md](docs/SCHEMA.md) for full schema documentation.
