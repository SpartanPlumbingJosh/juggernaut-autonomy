# System Shutdown

## Overview

This runbook provides step-by-step instructions for safely shutting down the Juggernaut autonomous AI system. Following these procedures ensures that all tasks are properly completed or paused, and no data is lost during shutdown.

## Prerequisites

- Access to the production environment
- SSH access to the server or Railway CLI configured
- Admin permissions to access and modify system processes

## Procedure

### Step 1: Check for Active Tasks

Before shutting down, check if there are any active tasks that should be completed or paused:

```bash
# Check for in-progress tasks
psql $DATABASE_URL -c "SELECT id, title, status FROM governance_tasks WHERE status = 'in_progress'"
```

If critical tasks are in progress, consider waiting for them to complete or follow the task pausing procedure in Step 2.

### Step 2: Pause Active Tasks (Optional)

If you need to shut down immediately but want to resume tasks later:

```bash
# Update tasks to paused status
psql $DATABASE_URL -c "UPDATE governance_tasks SET status = 'paused', updated_at = NOW() WHERE status = 'in_progress'"
```

Expected output:

```
UPDATE 3
```

This indicates that 3 tasks were paused.

### Step 3: Send Graceful Shutdown Signal to Main Service

Send a SIGTERM signal to allow the main service to shut down gracefully:

```bash
# Find the process ID
PID=$(pgrep -f "python main.py")

# Send SIGTERM signal
kill -TERM $PID
```

Wait for the process to shut down gracefully (usually 30 seconds):

```bash
# Monitor the process
watch -n 1 "ps -p $PID -o pid,cmd,etime"
```

If the process doesn't terminate after 30 seconds, you can force it to shut down:

```bash
# Force shutdown
kill -9 $PID
```

### Step 4: Shut Down WATCHDOG Service

Similarly, shut down the WATCHDOG service:

```bash
# Find the process ID
WATCHDOG_PID=$(pgrep -f "python watchdog_main.py")

# Send SIGTERM signal
kill -TERM $WATCHDOG_PID
```

Wait for the WATCHDOG to shut down gracefully.

### Step 5: Verify All Services Are Stopped

Verify that all Juggernaut processes have been terminated:

```bash
# Check for any remaining Python processes
ps aux | grep python | grep -v grep
```

There should be no output if all processes have been terminated.

### Step 6: Update Worker Registry Status

Update the worker registry to reflect that workers are offline:

```bash
# Update worker status to offline
psql $DATABASE_URL -c "UPDATE worker_registry SET status = 'offline', updated_at = NOW() WHERE status = 'active'"
```

### Step 7: Log Shutdown Event

Log the shutdown event for auditing purposes:

```bash
# Log shutdown event
psql $DATABASE_URL -c "INSERT INTO system_events (event_type, description, created_by) VALUES ('system_shutdown', 'Planned system shutdown', 'admin')"
```

## Verification

To verify that the system has been properly shut down:

1. Check that no Juggernaut processes are running:

```bash
ps aux | grep python | grep -v grep
```

2. Verify that the health endpoint is not accessible:

```bash
curl -I http://localhost:8000/health
```

This should return a connection refused error.

3. Verify that worker statuses are updated in the database:

```bash
psql $DATABASE_URL -c "SELECT worker_id, status FROM worker_registry"
```

All workers should show 'offline' status.

## Troubleshooting

### Issue: Process won't terminate with SIGTERM

**Solution:**

If a process doesn't respond to SIGTERM after 30 seconds, use SIGKILL as a last resort:

```bash
# Force kill the process
kill -9 $PID
```

Note that this may lead to incomplete task state and should be avoided if possible.

### Issue: Database connection issues during shutdown

**Solution:**

If you encounter database connection issues during shutdown:

1. Check that the DATABASE_URL environment variable is still set
2. Verify that the database is still accessible
3. If needed, manually update the database after connectivity is restored:

```bash
psql $DATABASE_URL -c "UPDATE worker_registry SET status = 'offline' WHERE status = 'active'"
```

### Issue: Zombie processes remain after shutdown

**Solution:**

If zombie processes remain:

1. Identify the parent process:

```bash
ps -ef | grep defunct
```

2. Kill the parent process:

```bash
kill -9 [PARENT_PID]
```

## References

- [System Startup Runbook](./system_startup.md)
- [Task Management Documentation](../architecture/task_management.md)
- [Worker Registry Documentation](../architecture/worker_registry.md)
- [Emergency Shutdown Procedure](./emergency_response.md#emergency-shutdown)
