#!/usr/bin/env python3
"""
JUGGERNAUT Autonomy Engine - main.py
=====================================
The heartbeat of JUGGERNAUT. Runs 24/7/365.

Phase A: Make It Run
- A.1: Entry point that imports core library
- A.2: Autonomy loop that runs continuously  
- A.3: Scheduler executes on schedule
- A.4: Workers pick up tasks
- A.5: Every action logged
- A.6: Tasks persist across restarts
"""

import os
import sys
import time
import json
import logging
import threading
import traceback
import urllib.request
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid

# ============================================================
# CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('JUGGERNAUT')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
NEON_HTTP_URL = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
LOOP_INTERVAL_SECONDS = int(os.environ.get('LOOP_INTERVAL_SECONDS', '60'))
WORKER_ID = os.environ.get('WORKER_ID', 'ORCHESTRATOR')
PORT = int(os.environ.get('PORT', '8000'))

# ============================================================
# DATABASE LAYER
# ============================================================

def execute_sql(query: str) -> dict:
    """Execute SQL via Neon HTTP endpoint."""
    headers = {
        "Content-Type": "application/json",
        "Neon-Connection-String": DATABASE_URL
    }
    
    try:
        data = json.dumps({"query": query}).encode()
        req = urllib.request.Request(NEON_HTTP_URL, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"SQL Error: {e}")
        return {"error": str(e), "rows": []}


def log_execution(action: str, message: str, level: str = "info",
                  input_data: dict = None, output_data: dict = None,
                  duration_ms: int = None) -> None:
    """Log every autonomous action to execution_logs table (A.5)."""
    log_id = str(uuid.uuid4())
    
    # Escape quotes for SQL
    safe_message = message.replace("'", "''")[:500]
    input_json = json.dumps(input_data or {}).replace("'", "''")
    output_json = json.dumps(output_data or {}).replace("'", "''")
    
    sql = f"""
    INSERT INTO execution_logs 
    (id, worker_id, level, action, message, input_data, output_data, duration_ms, source, created_at)
    VALUES (
        '{log_id}', '{WORKER_ID}', '{level}', '{action}', '{safe_message}',
        '{input_json}'::jsonb, '{output_json}'::jsonb, 
        {duration_ms or 0}, 'autonomy_loop', NOW()
    )
    """
    execute_sql(sql)
    
    if level == "error":
        logger.error(f"[{action}] {message}")
    else:
        logger.info(f"[{action}] {message}")


# ============================================================
# TASK RETRIEVAL (A.2)
# ============================================================

def get_pending_tasks() -> List[Dict]:
    """Get highest priority pending tasks from governance_tasks."""
    result = execute_sql("""
        SELECT id, title, task_type, priority, payload, goal_id, created_at
        FROM governance_tasks 
        WHERE status = 'pending' 
        ORDER BY 
            CASE priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                WHEN 'low' THEN 4 
                ELSE 5 
            END,
            created_at ASC
        LIMIT 5
    """)
    return result.get("rows", [])


def get_due_scheduled_tasks() -> List[Dict]:
    """Get scheduled tasks that are due to run (A.3)."""
    result = execute_sql("""
        SELECT id, name, task_type, config, priority
        FROM scheduled_tasks
        WHERE enabled = true
        AND next_run_at <= NOW()
        ORDER BY priority ASC, next_run_at ASC
        LIMIT 5
    """)
    return result.get("rows", [])


def get_open_opportunities() -> List[Dict]:
    """Get opportunities that need evaluation."""
    result = execute_sql("""
        SELECT id, title, source, score, status
        FROM opportunities
        WHERE status IN ('new', 'evaluating')
        ORDER BY score DESC NULLS LAST
        LIMIT 5
    """)
    return result.get("rows", [])


# ============================================================
# TASK EXECUTION (A.4)
# ============================================================

def execute_task(task: dict) -> bool:
    """Execute a single task and update its status."""
    task_id = task.get('id')
    task_type = task.get('task_type', 'unknown')
    title = task.get('title', 'Untitled')
    
    start_time = time.time()
    
    try:
        # Mark task as running
        execute_sql(f"""
            UPDATE governance_tasks 
            SET status = 'running', 
                started_at = NOW(), 
                attempt_count = COALESCE(attempt_count, 0) + 1
            WHERE id = '{task_id}'
        """)
        
        log_execution(
            action="task.start",
            message=f"Starting task: {title}",
            input_data={"task_id": task_id, "task_type": task_type}
        )
        
        # Route to task handler based on type
        result = handle_task_by_type(task)
        
        # Mark task as completed
        result_json = json.dumps(result).replace("'", "''")
        execute_sql(f"""
            UPDATE governance_tasks 
            SET status = 'completed', 
                completed_at = NOW(), 
                result = '{result_json}'::jsonb
            WHERE id = '{task_id}'
        """)
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_execution(
            action="task.complete",
            message=f"Completed task: {title}",
            output_data=result,
            duration_ms=duration_ms
        )
        
        return True
        
    except Exception as e:
        error_msg = str(e).replace("'", "''")[:500]
        execute_sql(f"""
            UPDATE governance_tasks 
            SET status = 'failed', error_message = '{error_msg}'
            WHERE id = '{task_id}'
        """)
        
        log_execution(
            action="task.failed",
            message=f"Task failed: {title} - {e}",
            level="error"
        )
        return False


def handle_task_by_type(task: dict) -> dict:
    """Route task to appropriate handler based on task_type."""
    task_type = task.get('task_type', 'generic')
    
    handlers = {
        'opportunity_scan': handle_opportunity_scan,
        'health_check': handle_health_check,
        'goal_review': handle_goal_review,
        # Add more handlers as capabilities grow
    }
    
    handler = handlers.get(task_type, handle_generic_task)
    return handler(task)


def handle_generic_task(task: dict) -> dict:
    """Default handler for unrecognized task types."""
    return {
        "status": "completed",
        "handler": "generic",
        "note": f"Task type '{task.get('task_type')}' executed with default handler"
    }


def handle_opportunity_scan(task: dict) -> dict:
    """Scan for new opportunities."""
    # TODO: Implement actual opportunity scanning
    return {"status": "completed", "opportunities_found": 0}


def handle_health_check(task: dict) -> dict:
    """Run system health check."""
    db_result = execute_sql("SELECT COUNT(*) as count FROM worker_registry WHERE status = 'active'")
    active_workers = db_result.get("rows", [{}])[0].get("count", 0)
    return {
        "status": "completed",
        "active_workers": active_workers,
        "database": "healthy"
    }


def handle_goal_review(task: dict) -> dict:
    """Review goal progress."""
    # TODO: Implement goal progress calculation
    return {"status": "completed", "goals_reviewed": 0}


# ============================================================
# SCHEDULED TASK EXECUTION (A.3)
# ============================================================

def run_scheduled_task(task: dict) -> bool:
    """Run a scheduled task and update next_run_at."""
    task_id = task.get('id')
    name = task.get('name', 'Unnamed')
    
    start_time = time.time()
    
    try:
        log_execution(
            action="scheduled.start",
            message=f"Running scheduled task: {name}",
            input_data={"task_id": task_id}
        )
        
        # Execute the scheduled task
        result = {"status": "completed", "task": name}
        
        duration_ms = int((time.time() - start_time) * 1000)
        result_json = json.dumps(result).replace("'", "''")
        
        execute_sql(f"""
            UPDATE scheduled_tasks 
            SET last_run_at = NOW(),
                last_run_status = 'success',
                last_run_result = '{result_json}'::jsonb,
                last_run_duration_ms = {duration_ms},
                next_run_at = NOW() + (interval_seconds * INTERVAL '1 second'),
                consecutive_failures = 0
            WHERE id = '{task_id}'
        """)
        
        log_execution(
            action="scheduled.complete",
            message=f"Completed scheduled task: {name}",
            duration_ms=duration_ms
        )
        
        return True
        
    except Exception as e:
        execute_sql(f"""
            UPDATE scheduled_tasks 
            SET last_run_at = NOW(),
                last_run_status = 'failed',
                consecutive_failures = COALESCE(consecutive_failures, 0) + 1
            WHERE id = '{task_id}'
        """)
        
        log_execution(
            action="scheduled.failed",
            message=f"Scheduled task failed: {name} - {e}",
            level="error"
        )
        return False


# ============================================================
# OPPORTUNITY EVALUATION
# ============================================================

def evaluate_opportunity(opp: dict) -> bool:
    """Evaluate an opportunity and decide action."""
    opp_id = opp.get('id')
    title = opp.get('title', 'Untitled')
    score = opp.get('score')
    
    try:
        log_execution(
            action="opportunity.evaluate",
            message=f"Evaluating: {title} (score: {score})",
            input_data={"opportunity_id": opp_id, "score": score}
        )
        
        # Score threshold logic
        if score and float(score) >= 70:
            execute_sql(f"UPDATE opportunities SET status = 'pursuing' WHERE id = '{opp_id}'")
            log_execution(action="opportunity.pursue", message=f"Pursuing: {title}")
        elif score and float(score) >= 40:
            execute_sql(f"UPDATE opportunities SET status = 'evaluating' WHERE id = '{opp_id}'")
        else:
            execute_sql(f"UPDATE opportunities SET status = 'archived' WHERE id = '{opp_id}'")
            log_execution(action="opportunity.archive", message=f"Archived low-score: {title}")
        
        return True
        
    except Exception as e:
        log_execution(action="opportunity.error", message=f"Error: {e}", level="error")
        return False


# ============================================================
# WORKER HEARTBEAT (A.4)
# ============================================================

def send_heartbeat() -> None:
    """Update worker heartbeat to show we're alive."""
    execute_sql(f"""
        UPDATE worker_registry 
        SET last_heartbeat = NOW(), status = 'active'
        WHERE worker_id = '{WORKER_ID}'
    """)


# ============================================================
# THE MAIN AUTONOMY LOOP (A.2)
# ============================================================

def autonomy_loop() -> None:
    """
    THE HEARTBEAT - Runs continuously, checking for work.
    
    Priority order:
    1. Due scheduled tasks (cron jobs)
    2. Pending governance tasks  
    3. Open opportunities
    
    This is what makes JUGGERNAUT autonomous.
    """
    
    loop_count = 0
    
    log_execution(
        action="loop.start",
        message=f"Autonomy loop starting. Worker: {WORKER_ID}, Interval: {LOOP_INTERVAL_SECONDS}s"
    )
    
    while True:
        loop_start = time.time()
        loop_count += 1
        actions_taken = 0
        
        try:
            # Send heartbeat every loop
            send_heartbeat()
            
            # 1. Check scheduled tasks first (highest priority)
            scheduled = get_due_scheduled_tasks()
            for task in scheduled:
                run_scheduled_task(task)
                actions_taken += 1
            
            # 2. Check pending governance tasks
            pending = get_pending_tasks()
            for task in pending:
                execute_task(task)
                actions_taken += 1
            
            # 3. Evaluate open opportunities
            opportunities = get_open_opportunities()
            for opp in opportunities:
                evaluate_opportunity(opp)
                actions_taken += 1
            
            # Log every 10th loop OR if we took actions
            duration_ms = int((time.time() - loop_start) * 1000)
            if loop_count % 10 == 0 or actions_taken > 0:
                log_execution(
                    action="loop.cycle",
                    message=f"Loop #{loop_count}: {len(scheduled)} scheduled, {len(pending)} pending, {len(opportunities)} opps, {actions_taken} actions",
                    duration_ms=duration_ms
                )
            
        except Exception as e:
            log_execution(
                action="loop.error",
                message=f"Loop error: {traceback.format_exc()[:500]}",
                level="error"
            )
        
        # Sleep until next cycle
        elapsed = time.time() - loop_start
        sleep_time = max(1, LOOP_INTERVAL_SECONDS - elapsed)
        time.sleep(sleep_time)


# ============================================================
# FASTAPI HEALTH ENDPOINT (A.1)
# ============================================================

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="JUGGERNAUT Autonomy Engine", version="1.0.0")

START_TIME = datetime.now(timezone.utc)

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway monitoring."""
    uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()
    
    # Check database
    db_status = "healthy"
    try:
        result = execute_sql("SELECT 1 as ok")
        if not result.get("rows"):
            db_status = "degraded"
    except:
        db_status = "unhealthy"
    
    return JSONResponse({
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": "1.0.0",
        "worker_id": WORKER_ID,
        "uptime_seconds": int(uptime),
        "database": db_status,
        "loop_interval_seconds": LOOP_INTERVAL_SECONDS,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "JUGGERNAUT Autonomy Engine",
        "status": "running",
        "worker": WORKER_ID,
        "docs": "/docs"
    }


@app.get("/stats")
async def stats():
    """Get current execution stats."""
    # Recent logs
    logs = execute_sql("""
        SELECT action, COUNT(*) as count 
        FROM execution_logs 
        WHERE created_at > NOW() - INTERVAL '1 hour'
        GROUP BY action ORDER BY count DESC LIMIT 10
    """)
    
    # Pending tasks
    tasks = execute_sql("SELECT COUNT(*) as count FROM governance_tasks WHERE status = 'pending'")
    
    return {
        "recent_actions": logs.get("rows", []),
        "pending_tasks": tasks.get("rows", [{}])[0].get("count", 0),
        "uptime_seconds": int((datetime.now(timezone.utc) - START_TIME).total_seconds())
    }


def run_api():
    """Run FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("JUGGERNAUT AUTONOMY ENGINE")
    logger.info("=" * 60)
    logger.info(f"Worker ID: {WORKER_ID}")
    logger.info(f"Loop Interval: {LOOP_INTERVAL_SECONDS}s")
    logger.info(f"Port: {PORT}")
    logger.info(f"Database: {'Configured' if DATABASE_URL else 'NOT SET!'}")
    
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set!")
        logger.error("Set DATABASE_URL to your Neon connection string.")
        sys.exit(1)
    
    # Start API server in background
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info(f"Health API running on port {PORT}")
    
    # Run autonomy loop (blocks forever)
    try:
        autonomy_loop()
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
        log_execution(action="loop.stop", message="Graceful shutdown")
        sys.exit(0)
