# JUGGERNAUT Orchestrator Service

## Overview

The Orchestrator service coordinates multi-agent task execution, handles failures, 
and manages escalations for the JUGGERNAUT autonomy system.

## Deployment

### Railway Configuration

1. Create a new service in Railway
2. Connect the service to your engine repository
3. Set rootDirectory to repository root (not this folder)
4. Configure to use `Dockerfile.orchestrator` as the Dockerfile
5. Set environment variable: `WORKER_ID=ORCHESTRATOR`

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WORKER_ID` | Yes | ORCHESTRATOR | Unique identifier for this worker |
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |

### Health Check

The service exposes a health endpoint at `/health` on port 8000.

## Functionality

The orchestrator runs continuously and:

1. Discovers available agents via `discover_agents()`
2. Routes pending tasks to appropriate workers via `route_task()`
3. Handles agent failures via `handle_agent_failure()`
4. Checks and auto-escalates timed-out escalations
5. Synchronizes shared memory across agents

## Files

- `railway.toml` - Railway deployment configuration (references root Dockerfile.orchestrator)
- `../Dockerfile.orchestrator` - Docker build configuration (at repo root)
- `../orchestrator_main.py` - Main entry point (at repo root)
