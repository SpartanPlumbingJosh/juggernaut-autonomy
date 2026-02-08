# Aider Self-Fix System

Complete autonomous bug fixing system using Aider CLI.

## Overview

JUGGERNAUT can now fix its own bugs automatically:

1. **Error Detection** → Monitors execution logs for recurring errors
2. **Task Creation** → Creates `code_fix` task with error details
3. **Aider Execution** → Calls Aider CLI to generate fix
4. **PR Creation** → Creates PR via GitHub API
5. **Review** → CodeRabbit reviews the fix
6. **Auto-Merge** → Merges if approved
7. **Deploy** → Railway auto-deploys

## Components

### 1. Aider Service (`services/aider/`)
- Dedicated Railway container
- Runs Aider CLI with repo clone
- Isolated from engine (bad fixes can't crash system)

### 2. CodeFixHandler (`core/handlers/code_fix_handler.py`)
- Handles `code_fix` task type
- Clones repo, creates branch
- Calls Aider with error details
- Creates PR via GitHub API

### 3. Error to Task Pipeline (`core/error_to_task.py`)
- Scans execution logs for recurring errors
- Extracts file path and line number
- Creates `code_fix` tasks automatically
- Threshold: 5+ occurrences in 60 minutes

### 4. Auto-Merge (`core/pr_tracker_auto_merge.py`)
- Extends PR tracker
- Auto-merges approved `code_fix` PRs
- Only for auto-generated fixes
- Uses squash merge for clean history

## Deployment

### Step 1: Deploy Aider Service

```bash
# From repo root
railway up --service aider

# Set environment variables
railway variables set GITHUB_TOKEN=ghp_xxx
railway variables set OPENROUTER_API_KEY=sk-xxx
railway variables set AIDER_MODEL=anthropic/claude-sonnet-4-20250514
```

### Step 2: Enable Error Scanning

Add to orchestrator schedule:

```python
# Run every 15 minutes
from core.error_to_task import scan_errors_and_create_tasks

result = scan_errors_and_create_tasks(execute_sql, log_action)
```

### Step 3: Verify Handler Registration

```python
from core.handlers import has_handler

assert has_handler("code_fix")  # Should be True
```

## Testing

### Test Case: Bug #14 (Type Coercion)

**Error:**
```
'<' not supported between instances of 'str' and 'int'
File: core/experiment_executor.py, Line: 554
```

**Create Test Task:**

```python
from uuid import uuid4
from datetime import datetime, timezone
import json

task_id = str(uuid4())
now = datetime.now(timezone.utc).isoformat()

payload = {
    "error_message": "'<' not supported between instances of 'str' and 'int'",
    "file_path": "core/experiment_executor.py",
    "line_number": 554,
    "traceback": "...",
    "repo": "SpartanPlumbingJosh/juggernaut-autonomy"
}

execute_sql(f"""
    INSERT INTO governance_tasks (
        id, title, description, task_type, status, priority,
        payload, tags, created_at, updated_at
    ) VALUES (
        '{task_id}',
        'Fix: Type comparison error in retry logic',
        'Auto-generated fix for type coercion bug',
        'code_fix',
        'pending',
        'high',
        '{json.dumps(payload)}'::jsonb,
        '["auto-fix", "aider", "test"]'::jsonb,
        '{now}',
        '{now}'
    )
""")
```

**Expected Result:**
1. Task picked up by worker
2. CodeFixHandler clones repo
3. Aider generates fix: `retry_count = int(retry_count) if retry_count else 0`
4. PR created with fix
5. CodeRabbit reviews
6. Auto-merged if approved
7. Railway deploys

## Monitoring

### Success Metrics

```sql
-- Fix accuracy (approved / total)
SELECT 
    COUNT(*) FILTER (WHERE current_state = 'approved') * 100.0 / COUNT(*) as approval_rate
FROM pr_tracking
WHERE metadata->>'auto_merged' = 'true';

-- Time to fix (error → PR created)
SELECT 
    AVG(EXTRACT(EPOCH FROM (pr_tracking.created_at - governance_tasks.created_at))/60) as avg_minutes
FROM governance_tasks
JOIN pr_tracking ON pr_tracking.task_id = governance_tasks.id
WHERE governance_tasks.task_type = 'code_fix';

-- Auto-merge rate
SELECT 
    COUNT(*) FILTER (WHERE metadata->>'auto_merged' = 'true') * 100.0 / COUNT(*) as auto_merge_rate
FROM pr_tracking
WHERE task_id IN (
    SELECT id FROM governance_tasks WHERE task_type = 'code_fix'
);
```

### Logs to Watch

- `error_to_task.scan_complete` - Error patterns detected
- `handler.code_fix.calling_aider` - Aider execution started
- `handler.code_fix.complete` - PR created
- `pr_tracker.auto_merge_success` - Fix merged

## Configuration

### Environment Variables

**Aider Service:**
- `GITHUB_TOKEN` - GitHub PAT with repo access (required)
- `OPENROUTER_API_KEY` - For Aider's LLM calls (required)
- `AIDER_MODEL` - Model to use (default: claude-sonnet-4)
- `AIDER_TIMEOUT_SECONDS` - Max execution time (default: 300)
- `AIDER_WORKSPACE` - Workspace directory (default: /tmp/juggernaut-fixes)

**Error Detection:**
- `ERROR_TASK_THRESHOLD` - Min occurrences to trigger (default: 5)
- `ERROR_WINDOW_MINUTES` - Time window for counting (default: 60)

## Limitations

### Current Scope
- Single-file fixes only
- Python syntax errors and type issues
- Simple logic bugs

### Not Yet Supported
- Multi-file refactors
- Schema migrations
- Breaking API changes
- Complex architectural changes

## Future Enhancements

1. **Test Generation** - Aider generates regression tests
2. **Multi-File Fixes** - Handle bugs spanning multiple files
3. **Rollback Detection** - Auto-revert if fix causes new errors
4. **Learning Loop** - Track which patterns Aider handles best
5. **Confidence Scoring** - Only auto-merge high-confidence fixes

## Troubleshooting

### Aider Not Running

```bash
# Check if service is up
railway status --service aider

# Check logs
railway logs --service aider

# Verify aider-chat installed
railway run --service aider aider --version
```

### Tasks Not Created

```bash
# Check error scanning
railway logs --filter "error_to_task"

# Verify threshold met
SELECT message, COUNT(*) 
FROM execution_logs 
WHERE level = 'error' 
  AND created_at >= NOW() - INTERVAL '60 minutes'
GROUP BY message
HAVING COUNT(*) >= 5;
```

### PRs Not Auto-Merging

```bash
# Check PR tracker logs
railway logs --filter "auto_merge"

# Verify task type
SELECT task_type FROM governance_tasks WHERE id = '<task_id>';

# Check PR approval status
SELECT current_state, review_status, mergeable 
FROM pr_tracking 
WHERE pr_number = <pr_number>;
```

## Success Story: Session 2026-02-08

**14 bugs fixed in one session** - all manually by Windsurf + human.

**With Aider active, expected flow:**
- Bug #14 (type coercion) would have been detected automatically
- code_fix task created within 15 minutes
- Aider generates fix in ~2 minutes
- PR created, CodeRabbit reviews in ~5 minutes
- Auto-merged if approved
- Railway deploys in ~3 minutes

**Total time: ~25 minutes from error → deployed fix, zero human intervention.**
