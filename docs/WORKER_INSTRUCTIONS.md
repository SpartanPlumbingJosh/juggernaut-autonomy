# Worker Task Claiming Protocol

This document describes how multiple simultaneous Claude chat sessions should claim and work on tasks from the `governance_tasks` queue.

## Overview

Multiple Claude chat instances (up to 5 simultaneously) can work on tasks in parallel. This protocol prevents race conditions and duplicate work through optimistic locking.

## Worker Identification

Each Claude session must generate a unique worker ID when starting:

```
claude-chat-XXXX
```

Where `XXXX` is a random 4-character alphanumeric string (e.g., `claude-chat-7K9X`, `claude-chat-AB3C`).

## Finding Available Tasks

Query the `governance_tasks` table for pending tasks assigned to the generic `claude-chat` worker:

```sql
SELECT id, title, description, priority, task_type 
FROM governance_tasks 
WHERE status = 'pending' 
  AND assigned_worker = 'claude-chat'
ORDER BY CASE priority 
  WHEN 'critical' THEN 1 
  WHEN 'high' THEN 2 
  WHEN 'medium' THEN 3 
  WHEN 'low' THEN 4 
  ELSE 5 END, 
created_at 
LIMIT 5;
```

## Claiming a Task

To claim a task, use an atomic UPDATE with a WHERE clause that checks the task is still pending:

```sql
UPDATE governance_tasks 
SET assigned_worker = 'claude-chat-XXXX', 
    status = 'in_progress',
    started_at = NOW()
WHERE id = 'TASK_ID_HERE' 
  AND status = 'pending';
```

### Handling Race Conditions

- **If `rowCount = 1`**: You successfully claimed the task. Proceed with the work.
- **If `rowCount = 0`**: Another worker claimed it first. Query for available tasks again and pick a different one.

## Completing a Task

When the task is finished:

```sql
UPDATE governance_tasks 
SET status = 'completed',
    completed_at = NOW()
WHERE id = 'TASK_ID_HERE';
```

## Releasing a Task (if abandoning)

If you cannot complete a task (e.g., blocked, need clarification), release it back to the pool:

```sql
UPDATE governance_tasks 
SET assigned_worker = 'claude-chat',
    status = 'pending',
    started_at = NULL
WHERE id = 'TASK_ID_HERE';
```

## Workflow Summary

1. **Generate worker ID**: `claude-chat-XXXX`
2. **Query available tasks**: Use the `SELECT` query above
3. **Claim a task**: Use the atomic `UPDATE`
4. **Check rowCount**:
   - `rowCount = 1` → Proceed with task
   - `rowCount = 0` → Go back to step 2
5. **Do the work**
6. **Mark complete** (or release if blocked)

## Best Practices

- **One task at a time**: Complete or release your current task before claiming another
- **Do not hoard**: If you cannot complete a task, release it promptly
- **Respect priority**: The query sorts by priority, so pick from the top
- **No fake data**: Never create placeholder or test values

## Task States

| Status | Description |
|--------|-------------|
| `pending` | Available to be claimed |
| `in_progress` | Currently being worked on |
| `completed` | Finished successfully |
| `failed` | Could not be completed |

## Example Session

```
1. Generate ID: claude-chat-7K9X

2. Query tasks:
   SELECT id, title, priority FROM governance_tasks 
   WHERE status = 'pending' AND assigned_worker = 'claude-chat'
   -> Returns 3 tasks

3. Pick task: abc-123-456

4. Claim it:
   UPDATE governance_tasks 
   SET assigned_worker = 'claude-chat-7K9X', status = 'in_progress', started_at = NOW()
   WHERE id = 'abc-123-456' AND status = 'pending';
   -> rowCount = 1 ✓

5. Do the work...

6. Mark complete:
   UPDATE governance_tasks SET status = 'completed', completed_at = NOW()
   WHERE id = 'abc-123-456';
```

## Related Documentation

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Code standards and workflow
- [docs/SCHEMA.md](SCHEMA.md) - Database schema reference
