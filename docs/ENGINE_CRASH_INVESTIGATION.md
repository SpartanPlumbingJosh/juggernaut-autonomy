# Engine Crash-Loop Investigation

## Symptom
Engine uptime: 17 seconds - crashes and restarts continuously

## Likely Causes

### 1. Unhandled Exception in Main Loop
**Check:** `main.py` lines 5769-5770
```python
except Exception as e:
    log_error(f"Loop error: {str(e)}", {"traceback": traceback.format_exc()[:500]})
```

**Issue:** Exception is caught and logged, but loop continues. If exception happens every iteration, logs will show pattern.

**Action:** Check Railway logs for `loop.error` or `Loop error:` messages

### 2. Database Connection Timeout
**Check:** `DATABASE_URL` environment variable
**Issue:** If connection pool exhausted or connection drops, queries fail
**Action:** Verify Neon connection string is valid and has connection pooling enabled

### 3. Memory Leak
**Check:** Worker memory usage in Railway metrics
**Issue:** Python process grows until OOM kill
**Action:** Look for Railway restart reason - if "OOMKilled", this is the cause

### 4. Infinite Recursion
**Check:** Task execution depth, delegation loops
**Issue:** ORCHESTRATOR delegates to EXECUTOR which delegates back
**Action:** Search logs for repeated task assignments to same task_id

### 5. Scheduled Task Failure
**Check:** Lines 5308-5319 (new scheduled task handlers)
**Issue:** If critical_monitoring, error_scanning, or stale_task_reset throw unhandled exception
**Action:** Wrap handlers in try/except to prevent crash

## Investigation Steps

### Step 1: Check Railway Logs
```bash
railway logs --filter "error" --tail 100
railway logs --filter "Loop error" --tail 50
railway logs --filter "FATAL" --tail 50
```

### Step 2: Check Restart Reason
```bash
railway logs --filter "exit" --tail 20
```

Look for:
- `exit code 1` - Exception
- `exit code 137` - OOMKilled
- `exit code 143` - SIGTERM (graceful shutdown)

### Step 3: Check Memory Usage
Railway dashboard → Service → Metrics → Memory

If memory grows linearly, it's a leak.

### Step 4: Check Database Connections
```sql
SELECT count(*) FROM pg_stat_activity 
WHERE application_name LIKE '%juggernaut%';
```

If >100 connections, connection leak.

## Quick Fixes

### Fix 1: Add Error Handling to Scheduled Tasks
```python
elif sched_task_type == "critical_monitoring":
    try:
        from core.critical_monitoring import check_critical_issues
        sched_result = check_critical_issues(execute_sql, log_action)
        sched_success = bool(isinstance(sched_result, dict) and sched_result.get("success"))
    except Exception as e:
        log_action("scheduled.critical_monitoring.error", f"Failed: {e}", level="error")
        sched_result = {"error": str(e)}
        sched_success = False
```

### Fix 2: Add Loop Iteration Limit
```python
MAX_LOOPS = int(os.getenv("MAX_LOOPS", "0"))  # 0 = infinite
if MAX_LOOPS > 0 and loop_count >= MAX_LOOPS:
    log_info(f"Reached max loops ({MAX_LOOPS}), exiting gracefully")
    break
```

### Fix 3: Add Memory Monitoring
```python
import psutil
if loop_count % 10 == 0:
    mem = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    if mem > 500:  # 500MB threshold
        log_action("memory.high", f"Memory usage: {mem:.0f}MB", level="warn")
```

## Root Cause Hypothesis

**Most likely:** New scheduled task handlers (critical_monitoring, error_scanning, stale_task_reset) are throwing exceptions that crash the scheduler, which crashes the main loop.

**Evidence:**
- Crash started after migration 016 deployed
- 17s uptime suggests it runs a few iterations then hits scheduled task
- No error handling around new handlers

**Fix:** Add try/except around all scheduled task handlers
