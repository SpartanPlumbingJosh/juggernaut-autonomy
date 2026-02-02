# Troubleshooting Guide

## Overview

This runbook provides troubleshooting procedures for common issues with the Juggernaut autonomous AI system. It covers database issues, API connectivity problems, task execution failures, and other operational problems.

## Prerequisites

- Access to system logs
- Database access credentials
- Admin access to the system
- Basic understanding of the Juggernaut architecture

## Common Issues and Solutions

### Database Connection Issues

#### Symptoms
- Error messages containing "database connection failed"
- Tasks stuck in pending state
- System logs showing PostgreSQL connection errors

#### Diagnostic Steps

1. Check database connectivity:

```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1"
```

2. Check database credentials:

```bash
# Verify that DATABASE_URL is correctly set
echo $DATABASE_URL | grep -o "postgres.*@" | sed 's/@$//'
```

3. Check database server status:

```bash
# For Railway-hosted database
railway status
```

#### Solution

1. If credentials are incorrect, update the environment variable:

```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
```

2. If the database server is down, contact the database administrator or restart the service if you have permissions.

3. If connection pooling issues are occurring, restart the application to reset the connection pool:

```bash
# Restart the main service
kill -TERM $(pgrep -f "python main.py")
python main.py
```

### API Rate Limiting Issues

#### Symptoms
- Error messages containing "rate limit exceeded"
- Tasks failing with API-related errors
- Circuit breakers in OPEN state

#### Diagnostic Steps

1. Check circuit breaker status:

```bash
# Query circuit breaker status
psql $DATABASE_URL -c "SELECT * FROM tool_executions WHERE error_message LIKE '%circuit breaker%' ORDER BY created_at DESC LIMIT 5"
```

2. Check API cost tracking:

```bash
# Check recent API costs
psql $DATABASE_URL -c "SELECT SUM(cost_usd) FROM api_cost_tracking WHERE created_at > NOW() - INTERVAL '24 hours'"
```

#### Solution

1. If hitting rate limits, implement a backoff strategy:

```bash
# Update worker budgets to reduce limits temporarily
psql $DATABASE_URL -c "UPDATE worker_budgets SET daily_limit = daily_limit * 0.5 WHERE worker_id IN ('EXECUTOR', 'ANALYST')"
```

2. Reset circuit breakers if necessary:

```python
# In a Python console
from core.circuit_breaker import reset_all_circuit_breakers
reset_all_circuit_breakers()
```

3. Check for any stuck tasks and move them to the DLQ:

```bash
# Find stuck tasks
psql $DATABASE_URL -c "SELECT id, title FROM governance_tasks WHERE status = 'in_progress' AND updated_at < NOW() - INTERVAL '30 minutes'"

# Move to DLQ (use task IDs from previous query)
python -c "from core.dlq import move_to_dlq; import asyncio; asyncio.run(move_to_dlq('task-id', 'Rate limit exceeded'))"
```

### Dead Letter Queue Issues

#### Symptoms
- Large number of tasks in the DLQ
- Similar failure patterns across multiple tasks
- Recurring task failures

#### Diagnostic Steps

1. Check DLQ contents:

```bash
# Query DLQ items
psql $DATABASE_URL -c "SELECT id, task_id, failure_reason, created_at FROM dead_letter_queue ORDER BY created_at DESC LIMIT 10"
```

2. Analyze failure patterns:

```bash
# Group by failure reason
psql $DATABASE_URL -c "SELECT failure_reason, COUNT(*) FROM dead_letter_queue GROUP BY failure_reason ORDER BY COUNT(*) DESC"
```

#### Solution

1. For transient failures, retry tasks:

```python
# In a Python console
from core.dlq import retry_dlq_item
import asyncio

# Retry a specific DLQ item
asyncio.run(retry_dlq_item('dlq-id'))

# Retry all items with a specific failure pattern
async def retry_all_matching(pattern):
    from core.dlq import get_dlq_items
    items = await get_dlq_items(status='pending')
    for item in items:
        if pattern in item.get('failure_reason', ''):
            await retry_dlq_item(item['id'])

asyncio.run(retry_all_matching('connection reset'))
```

2. For persistent failures, resolve and fix the root cause:

```python
# After fixing the issue, resolve the DLQ items
from core.dlq import resolve_dlq_item
import asyncio

asyncio.run(resolve_dlq_item('dlq-id', 'Fixed by updating API credentials'))
```

### Memory Leaks and Performance Issues

#### Symptoms
- Increasing memory usage over time
- Slow response times
- System becoming unresponsive

#### Diagnostic Steps

1. Check memory usage:

```bash
# Monitor memory usage
ps -o pid,rss,command -p $(pgrep -f "python main.py")
```

2. Check for long-running tasks:

```bash
# Find long-running tasks
psql $DATABASE_URL -c "SELECT id, title, EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_running FROM governance_tasks WHERE status = 'in_progress' ORDER BY started_at ASC LIMIT 10"
```

#### Solution

1. For memory leaks, restart the service:

```bash
# Gracefully restart the main service
kill -TERM $(pgrep -f "python main.py")
python main.py
```

2. For long-running tasks, consider terminating them:

```bash
# Update task status to failed
psql $DATABASE_URL -c "UPDATE governance_tasks SET status = 'failed', updated_at = NOW(), error_message = 'Terminated due to excessive runtime' WHERE id = 'task-id'"
```

3. Optimize database queries if database is the bottleneck:

```bash
# Find slow queries
psql $DATABASE_URL -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10"
```

### WATCHDOG Failures

#### Symptoms
- No recent WATCHDOG heartbeats
- System not performing scheduled tasks
- Error messages related to WATCHDOG in logs

#### Diagnostic Steps

1. Check WATCHDOG process:

```bash
# Check if WATCHDOG is running
ps aux | grep watchdog_main.py
```

2. Check recent heartbeats:

```bash
# Check Redis for heartbeats
redis-cli -u $REDIS_URL GET watchdog:heartbeat:WATCHDOG

# Check database for heartbeats
psql $DATABASE_URL -c "SELECT worker_id, last_heartbeat FROM worker_registry WHERE worker_id = 'WATCHDOG'"
```

#### Solution

1. If WATCHDOG is not running, restart it:

```bash
# Start WATCHDOG
python watchdog_main.py
```

2. If WATCHDOG is running but not sending heartbeats, check for Redis connectivity issues:

```bash
# Test Redis connection
redis-cli -u $REDIS_URL PING
```

3. If Redis is working but heartbeats aren't being recorded, check for permission issues:

```bash
# Check WATCHDOG permissions
psql $DATABASE_URL -c "SELECT * FROM worker_tool_permissions WHERE worker_id = 'WATCHDOG'"
```

### Circuit Breaker Issues

#### Symptoms
- Multiple services in OPEN circuit state
- API calls failing with circuit breaker errors
- Tasks failing due to external service unavailability

#### Diagnostic Steps

1. Check circuit breaker status:

```python
# In a Python console
from core.circuit_breaker import get_circuit_breaker_status
import asyncio

asyncio.run(get_circuit_breaker_status())
```

2. Check for external service issues:

```bash
# Check recent API errors
psql $DATABASE_URL -c "SELECT error_message, COUNT(*) FROM tool_executions WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 hour' GROUP BY error_message ORDER BY COUNT(*) DESC"
```

#### Solution

1. Reset specific circuit breakers after confirming external service is available:

```python
# In a Python console
from core.circuit_breaker import reset_circuit_breaker
import asyncio

asyncio.run(reset_circuit_breaker('openrouter'))
```

2. If external service is still having issues, implement a temporary workaround:

```python
# Update circuit breaker settings to be more tolerant
from core.circuit_breaker import update_circuit_breaker_settings
import asyncio

asyncio.run(update_circuit_breaker_settings(
    'openrouter',
    failure_threshold=10,  # More failures before opening
    reset_timeout=60       # Shorter timeout before trying again
))
```

## Verification

After applying any solution, verify that the issue is resolved:

1. Check system health:

```bash
# Check health endpoint
curl http://localhost:8000/health
```

2. Monitor logs for recurring errors:

```bash
# Tail logs
tail -f logs/juggernaut.log | grep ERROR
```

3. Verify task execution:

```bash
# Create a test task
curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d '{"title": "Health check", "task_type": "evaluation", "payload": {"eval_type": "metric", "metric_value": 100}}'
```

## References

- [System Architecture Documentation](../architecture/overview.md)
- [Database Schema](../architecture/database_schema.md)
- [Circuit Breaker Documentation](../architecture/circuit_breaker.md)
- [Dead Letter Queue Documentation](../architecture/dlq.md)
- [API Integration Guide](../integration/api_integration.md)
