# JUGGERNAUT AUTONOMOUS WORKER INSTRUCTIONS

## Overview

This document defines how autonomous workers (ORCHESTRATOR, EXECUTOR, WATCHDOG, ANALYST, STRATEGIST) operate within the Juggernaut system. These workers run on Railway and execute tasks from the governance queue without human intervention.

---

## Worker Registry

All workers must register and maintain heartbeats.

### Registration
```sql
INSERT INTO worker_registry (worker_id, worker_type, status, capabilities, last_heartbeat)
VALUES ('EXECUTOR', 'executor', 'active', '["code", "test", "verification"]', NOW())
ON CONFLICT (worker_id) DO UPDATE SET 
  status = 'active',
  last_heartbeat = NOW();
```

### Heartbeat (Every 60 seconds)
```sql
UPDATE worker_registry 
SET last_heartbeat = NOW(), 
    status = 'active',
    current_task_id = 'TASK_ID_OR_NULL'
WHERE worker_id = 'WORKER_ID';
```

### Status Values
- `active` - Worker is running and healthy
- `idle` - Worker is running but not processing
- `busy` - Worker is executing a task
- `stale` - No heartbeat in 5+ minutes
- `offline` - Worker has stopped

---

## Task Claiming Protocol

Workers must use atomic claiming to prevent conflicts.

### Find Available Tasks
```sql
SELECT id, title, description, task_type, priority, acceptance_criteria
FROM governance_tasks 
WHERE status = 'pending'
  AND (assigned_worker IS NULL OR assigned_worker = 'WORKER_TYPE')
  AND task_type = ANY(WORKER_CAPABILITIES)
ORDER BY 
  CASE priority 
    WHEN 'critical' THEN 1 
    WHEN 'high' THEN 2 
    WHEN 'medium' THEN 3 
    WHEN 'low' THEN 4 
  END,
  created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

### Claim Task (Atomic)
```sql
UPDATE governance_tasks 
SET status = 'in_progress',
    assigned_worker = 'WORKER_ID',
    started_at = NOW()
WHERE id = 'TASK_ID'
  AND status = 'pending'
RETURNING id;
```

If `RETURNING` is empty, another worker claimed it. Try again.

---

## Task Execution

### Before Starting
1. Read the full task description
2. Parse acceptance_criteria
3. Verify you have required capabilities
4. Log execution start

### Execution Logging
```sql
INSERT INTO execution_logs (task_id, worker_id, action, level, message, metadata)
VALUES (
  'TASK_ID',
  'WORKER_ID', 
  'task_start',
  'info',
  'Starting task: TASK_TITLE',
  '{"task_type": "code", "priority": "high"}'
);
```

### Error Handling
```sql
INSERT INTO execution_logs (task_id, worker_id, action, level, message, error_data)
VALUES (
  'TASK_ID',
  'WORKER_ID',
  'task_error',
  'error',
  'Error description',
  '{"error_type": "GitHubAuthError", "details": "..."}'
);
```

---

## Task Completion

### Requirements for Completion

A task is NOT complete until ALL of:
1. All acceptance_criteria are met
2. Evidence exists proving the work was done
3. For code tasks: PR is MERGED (not just created)

### Completion Evidence Requirements

| Task Type | Required Evidence |
|-----------|-------------------|
| code | Merged PR URL: `https://github.com/.../pull/XX` |
| test | Test results with pass/fail counts |
| verification | Verification report with specific checks |
| research | Summary with sources cited |
| documentation | Document URL or content location |

### Good vs Bad Evidence

**GOOD:**
```
Merged PR #156: https://github.com/<GITHUB_REPO>/pull/156
- Added core/memory.py with MemoryStore class
- Implemented save_memory(), recall_memories(), search_similar()
- All 12 unit tests passing
```

**BAD:**
```
Done
```
```
Completed the task
```
```
Fixed it
```

### Mark Complete
```sql
UPDATE governance_tasks 
SET status = 'completed',
    completed_at = NOW(),
    completion_evidence = 'Detailed evidence here...'
WHERE id = 'TASK_ID';
```

### Mark Failed
```sql
UPDATE governance_tasks 
SET status = 'failed',
    completed_at = NOW(),
    error_message = 'Specific error description'
WHERE id = 'TASK_ID';
```

---

## Worker Capabilities

### ORCHESTRATOR
- Goal decomposition
- Task creation and assignment
- Priority management
- Cross-team coordination

### EXECUTOR
- Code generation and modification
- GitHub operations (branch, commit, PR, merge)
- Test execution
- Verification tasks

### WATCHDOG
- Health monitoring
- Stale task detection
- Worker heartbeat monitoring
- Alert generation

### ANALYST
- Data gathering
- Pattern analysis
- Report generation
- Metric calculation

### STRATEGIST
- Long-term planning
- Resource allocation
- Priority recommendations
- Risk assessment

---

## Code Task Workflow

For tasks with `task_type = 'code'`:

### Step 1: Get main branch SHA
```
GET https://api.github.com/repos/<GITHUB_REPO>/git/ref/heads/main
```

### Step 2: Create feature branch
```
POST https://api.github.com/repos/<GITHUB_REPO>/git/refs
Body: {"ref": "refs/heads/feature/TASK_ID", "sha": "MAIN_SHA"}
```

### Step 3: Create/update files
```
PUT https://api.github.com/repos/<GITHUB_REPO>/contents/path/to/file.py
Body: {
  "message": "feat: Description of change",
  "content": "BASE64_ENCODED_CONTENT",
  "branch": "feature/TASK_ID"
}
```

### Step 4: Create PR
```
POST https://api.github.com/repos/<GITHUB_REPO>/pulls
Body: {
  "title": "TASK_ID: Task Title",
  "body": "Description\n\n## Changes\n- ...",
  "head": "feature/TASK_ID",
  "base": "main"
}
```

### Step 5: Merge PR
```
PUT https://api.github.com/repos/<GITHUB_REPO>/pulls/PR_NUMBER/merge
Body: {"merge_method": "squash"}
```

### Step 6: Mark complete with merged PR URL

---

## Code Quality Requirements

All code must have:
- Type hints on every function
- Docstrings on every function
- No bare `except:` - catch specific exceptions
- No `print()` - use `logging`
- No magic numbers - use constants
- Parameterized SQL queries
- Grouped and sorted imports

---

## Prohibited Actions

Workers must NEVER:
- Make financial transactions
- Delete production data
- Modify RBAC permissions
- Deploy without approval (for high-risk tasks)
- Access external systems not in capability set
- Mark tasks complete without evidence
- Claim tasks outside their capability set

---

## Risk Assessment

Before executing, assess task risk:

| Risk Level | Examples | Action |
|------------|----------|--------|
| low | Documentation, tests, minor fixes | Execute immediately |
| medium | New features, schema changes | Execute with logging |
| high | Production deploys, data migrations | Request approval first |
| critical | Security changes, financial operations | Always require human approval |

### Request Approval
```sql
UPDATE governance_tasks 
SET status = 'waiting_approval',
    requires_approval = true,
    approval_reason = 'High-risk operation: production deployment'
WHERE id = 'TASK_ID';
```

---

## Learning Capture

After completing tasks, capture learnings:

```sql
INSERT INTO learnings (
  task_id, worker_id, category, title, description, 
  impact_score, tags, created_at
) VALUES (
  'TASK_ID',
  'WORKER_ID',
  'technique',
  'Learning title',
  'What was learned and how it can be applied',
  0.8,
  '["github", "automation"]',
  NOW()
);
```

---

## Monitoring

Workers are monitored via:
- Heartbeat freshness (stale = `last_heartbeat > 5 minutes ago`)
- Task completion rate
- Failure rate
- Execution log patterns

WATCHDOG alerts on:
- Worker heartbeat failures
- Task stuck in `in_progress` > 2 hours
- High failure rates
- Repeated errors

---

## Environment Variables Required

```
DATABASE_URL=postgresql://...
GITHUB_TOKEN=ghp_...
OPENROUTER_API_KEY=sk-or-...
WORKER_ID=EXECUTOR
WORKER_TYPE=executor
```

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [SCHEMA.md](SCHEMA.md) - Database schema reference
- [L1_L5_CAPABILITY_MATRIX.md](L1_L5_CAPABILITY_MATRIX.md) - Capability levels
