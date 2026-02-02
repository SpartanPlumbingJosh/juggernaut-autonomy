# System Startup

## Overview

This runbook provides step-by-step instructions for starting the Juggernaut autonomous AI system. It covers starting the main service, WATCHDOG, and verifying that all components are running correctly.

## Prerequisites

- Access to the production environment
- SSH access to the server or Railway CLI configured
- Environment variables properly configured
- Database credentials
- Redis credentials

## Procedure

### Step 1: Verify Environment Configuration

Before starting the system, verify that all required environment variables are set:

```bash
# Check if required environment variables are set
echo $DATABASE_URL
echo $REDIS_URL
echo $OPENROUTER_API_KEY
```

Ensure that none of these return empty values. If any are missing, set them before proceeding:

```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
export REDIS_URL="redis://user:password@host:port"
export OPENROUTER_API_KEY="your-api-key"
```

### Step 2: Start the Main Service

Start the main Juggernaut service:

```bash
# Navigate to the project directory
cd /path/to/juggernaut-autonomy

# Start the main service
python main.py
```

Expected output:

```
[INFO] Starting JUGGERNAUT Autonomy Engine...
[INFO] Worker ID: ORCHESTRATOR
[INFO] Database connection established
[INFO] Redis connection established
[INFO] HTTP server listening on port 8000
[INFO] Autonomy loop starting
```

### Step 3: Start the WATCHDOG Service

In a separate terminal, start the WATCHDOG service:

```bash
# Navigate to the project directory
cd /path/to/juggernaut-autonomy

# Start the WATCHDOG service
python watchdog_main.py
```

Expected output:

```
[INFO] Starting JUGGERNAUT WATCHDOG...
[INFO] Worker ID: WATCHDOG
[INFO] Database connection established
[INFO] Redis connection established
[INFO] WATCHDOG heartbeat sent
[INFO] WATCHDOG monitoring active
```

### Step 4: Verify Service Health

Check that all services are healthy:

```bash
# Check main service health
curl http://localhost:8000/health

# Check WATCHDOG heartbeat in Redis
redis-cli -u $REDIS_URL GET watchdog:heartbeat:WATCHDOG
```

Expected output from health check:

```json
{
  "status": "healthy",
  "service": "juggernaut-main",
  "uptime_seconds": 123,
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection healthy"
    },
    "workers": {
      "status": "healthy",
      "message": "2 of 2 workers active and healthy"
    }
  }
}
```

### Step 5: Verify Worker Registration

Check that workers are properly registered in the database:

```bash
# Using psql
psql $DATABASE_URL -c "SELECT worker_id, status, last_heartbeat FROM worker_registry WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'"
```

Expected output:

```
    worker_id    |  status  |         last_heartbeat         
-----------------+----------+-------------------------------
 ORCHESTRATOR    | active   | 2023-01-01 12:00:00.000000+00
 WATCHDOG        | active   | 2023-01-01 12:00:00.000000+00
```

## Verification

To verify that the system is fully operational:

1. Check the logs for any errors or warnings
2. Verify that both services are running with `ps aux | grep python`
3. Verify that the health endpoint returns "healthy" status
4. Create a test task and verify that it executes successfully:

```bash
# Create a test task
curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d '{"title": "Health check", "task_type": "evaluation", "payload": {"eval_type": "metric", "metric_value": 100}}'
```

## Troubleshooting

### Issue: Service fails to start due to database connection error

**Solution:**

1. Verify that the DATABASE_URL environment variable is set correctly
2. Check that the database is running and accessible
3. Check for network connectivity issues
4. Verify that the database user has the necessary permissions

```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1"
```

### Issue: Redis connection error

**Solution:**

1. Verify that the REDIS_URL environment variable is set correctly
2. Check that Redis is running and accessible
3. Check for network connectivity issues

```bash
# Test Redis connection
redis-cli -u $REDIS_URL PING
```

### Issue: Workers not registering

**Solution:**

1. Check the logs for any errors related to worker registration
2. Verify that the worker_registry table exists in the database
3. Restart the services

```bash
# Check worker_registry table
psql $DATABASE_URL -c "SELECT COUNT(*) FROM worker_registry"
```

## References

- [Main Service Documentation](../architecture/main_service.md)
- [WATCHDOG Documentation](../architecture/watchdog.md)
- [Environment Configuration](../deployment/environment_variables.md)
- [Troubleshooting Guide](./troubleshooting.md)
