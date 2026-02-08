# Critical Monitoring and Alerting

System for detecting and alerting on critical issues before they cause failures.

## Overview

The critical monitoring system runs periodic checks and raises loud warnings for:
- Database connection failures
- Worker crashes/offline status
- High error rates (>50/hour)
- Stuck task accumulation (>10 tasks)
- High failure rates (>50%)

## Usage

### Automatic Monitoring

Add to orchestrator schedule (runs every 5 minutes):

```python
from core.critical_monitoring import check_critical_issues

result = check_critical_issues(execute_sql, log_action)

if result["critical_issues"] > 0:
    # Critical issues detected - logged at CRITICAL level
    # Alerts sent via execution_logs
    pass
```

### Manual Check

```python
from core.critical_monitoring import CriticalMonitor

monitor = CriticalMonitor(execute_sql, log_action)
result = monitor.check_all()

print(f"Critical issues: {result['critical_issues']}")
for issue in result['issues']:
    print(f"- {issue['type']}: {issue['message']}")
```

## Alert Types

### Database Issues
- `database_connection_failed` - Cannot connect to database
- `database_unresponsive` - Query returns no results

### Worker Issues
- `no_workers_registered` - No workers in system
- `all_workers_offline` - All workers offline (no heartbeat in 3 min)
- `majority_workers_offline` - >50% workers offline

### Error Rate Issues
- `high_error_rate` - >50 errors per hour in execution_logs

### Task Issues
- `tasks_accumulating` - >10 tasks stuck (blocked or in_progress >30min)
- `high_failure_rate` - >50% task failure rate in last 24 hours

## Thresholds

Configurable in `CriticalMonitor.__init__`:

```python
self.error_rate_threshold = 50  # errors per hour
self.stuck_task_threshold = 10  # stuck tasks
self.worker_offline_threshold = 3  # minutes
self.task_failure_rate_threshold = 0.5  # 50%
```

## Log Format

Critical issues are logged with:
- **Level:** `critical`
- **Action:** `critical_monitor.issue_detected`
- **Message:** Human-readable description
- **Output Data:** Full issue details

Example:
```json
{
  "action": "critical_monitor.issue_detected",
  "level": "critical",
  "message": "All 5 workers are offline (no heartbeat in 3 min)",
  "output_data": {
    "type": "all_workers_offline",
    "severity": "critical",
    "total_workers": 5
  }
}
```

## Integration with Self-Heal

Critical issues automatically trigger self-heal actions:
1. Monitor detects issue
2. Logs at CRITICAL level
3. Error-to-task pipeline creates code_fix task
4. Aider generates fix
5. PR created and merged
6. Railway deploys

## Monitoring Queries

### Check Recent Critical Issues

```sql
SELECT 
    action,
    message,
    output_data,
    created_at
FROM execution_logs
WHERE level = 'critical'
  AND created_at >= NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

### Critical Issue Frequency

```sql
SELECT 
    output_data->>'type' as issue_type,
    COUNT(*) as occurrences,
    MAX(created_at) as last_seen
FROM execution_logs
WHERE action = 'critical_monitor.issue_detected'
  AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY output_data->>'type'
ORDER BY occurrences DESC;
```

## Alerting

Critical issues can be routed to:
- Slack (via `slack_notifications.py`)
- Email (via notification system)
- Dashboard (red banner)
- PagerDuty (future)

### Slack Integration

```python
from core.slack_notifications import send_slack_alert

if result["critical_issues"] > 0:
    for issue in result["issues"]:
        send_slack_alert(
            message=issue["message"],
            priority="critical",
            channel="#alerts"
        )
```

## Testing

### Inject Test Critical Issue

```python
# Simulate database failure
monitor = CriticalMonitor(
    execute_sql=lambda sql: {"rows": []},  # Empty response
    log_action=log_action
)
result = monitor.check_all()
# Should detect database_unresponsive
```

### Verify Alert Routing

```bash
# Check if critical logs are being created
railway logs --filter "level=critical"

# Check if alerts reach Slack
# (requires SLACK_WEBHOOK_URL set)
```

## Best Practices

1. **Run frequently** - Every 5 minutes minimum
2. **Don't ignore** - Critical means critical, investigate immediately
3. **Track patterns** - Recurring issues need permanent fixes
4. **Test alerts** - Verify notification routing works
5. **Document fixes** - Add to self-heal playbooks

## Future Enhancements

1. **Predictive alerts** - Warn before thresholds hit
2. **Auto-remediation** - Trigger fixes automatically
3. **Escalation** - Page on-call if not resolved
4. **Historical analysis** - Track MTTR and patterns
5. **Custom thresholds** - Per-environment configuration
