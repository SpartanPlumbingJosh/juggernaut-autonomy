#!/usr/bin/env python3
"""
JUGGERNAUT WATCHDOG SERVICE
===========================
Continuous health monitoring and automatic recovery for the JUGGERNAUT system.

This service runs continuously and:
1. Periodically runs health checks on all components
2. Detects agent failures (dead workers, missed heartbeats)
3. Triggers automatic recovery when issues are found
4. Creates alerts for critical failures

Environment Variables:
- WORKER_ID: Identifier for this watchdog instance (default: WATCHDOG)
- HEALTH_CHECK_INTERVAL: Seconds between health checks (default: 60)
- RECOVERY_INTERVAL: Seconds between auto-recovery runs (default: 300)
- DATABASE_URL: PostgreSQL connection string
"""

import os
import sys
import time
import signal
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Core module imports
from core.monitoring import (
    run_health_check,
    record_metric,
    record_counter,
)
from core.orchestration import (
    detect_agent_failures,
    handle_agent_failure,
    auto_recover,
    run_daily_budget_allocation,
)
from core.alerting import (
    create_alert,
    AlertType,
    AlertSeverity,
    check_stale_tasks,
)
from core.database import execute_query

SLACK_NOTIFICATIONS_AVAILABLE = False
_slack_notifications_import_error = None

try:
    from core.slack_notifications import send_system_alert
    SLACK_NOTIFICATIONS_AVAILABLE = True
except ImportError as e:
    _slack_notifications_import_error = str(e)

    def send_system_alert(
        alert_type: str,
        component: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> bool:
        return False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('watchdog')

# Constants
WORKER_ID = os.environ.get('WORKER_ID', 'WATCHDOG')
HEALTH_CHECK_INTERVAL_SECONDS = int(os.environ.get('HEALTH_CHECK_INTERVAL', '60'))
RECOVERY_INTERVAL_SECONDS = int(os.environ.get('RECOVERY_INTERVAL', '300'))
HEARTBEAT_THRESHOLD_SECONDS = int(os.environ.get('HEARTBEAT_THRESHOLD', '120'))

# Components to monitor
MONITORED_COMPONENTS = ['database', 'workers', 'api']

# Global state
running = True
last_health_check: Optional[datetime] = None
last_recovery_run: Optional[datetime] = None
health_status: Dict[str, str] = {}


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health endpoint."""
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass
    
    def do_GET(self) -> None:
        """Handle GET requests for health checks."""
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'worker_id': WORKER_ID,
                'last_health_check': last_health_check.isoformat() if last_health_check else None,
                'last_recovery_run': last_recovery_run.isoformat() if last_recovery_run else None,
                'component_status': health_status,
                'uptime_seconds': int(time.time() - start_time),
            }
            import json
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def register_watchdog() -> bool:
    """Register this watchdog in the worker registry."""
    try:
        update_res = execute_query(
            """
            UPDATE worker_registry
            SET status = 'active', last_heartbeat = NOW(), capabilities = $2
            WHERE worker_id = $1
            """,
            [WORKER_ID, '["health_check", "failure_detection", "auto_recovery"]']
        )

        updated = int(update_res.get("rowCount", 0) or 0) if isinstance(update_res, dict) else 0
        if updated <= 0:
            execute_query(
                """
                INSERT INTO worker_registry (worker_id, name, status, capabilities, last_heartbeat)
                VALUES ($1, $2, 'active', $3, NOW())
                """,
                [WORKER_ID, 'JUGGERNAUT Watchdog', '["health_check", "failure_detection", "auto_recovery"]']
            )
        logger.info(f"Watchdog registered with ID: {WORKER_ID}")
        return True
    except Exception as e:
        logger.error(f"Failed to register watchdog: {e}")
        return False


def send_heartbeat() -> None:
    """Update heartbeat timestamp using Redis SETEX pattern."""
    from core.heartbeat import send_heartbeat as redis_heartbeat
    
    success = redis_heartbeat(WORKER_ID)
    if not success:
        logger.warning("Failed to send heartbeat via Redis, check Redis connection")
        
    # Also try to claim leadership if we're a WATCHDOG
    if WORKER_ID.startswith("WATCHDOG"):
        from core.heartbeat import claim_watchdog_leadership, renew_leadership
        
        if renew_leadership():
            logger.debug("Renewed WATCHDOG leadership")
        elif claim_watchdog_leadership():
            logger.info("Claimed WATCHDOG leadership")
        else:
            logger.debug("Not the leader WATCHDOG instance")


def run_all_health_checks() -> Dict[str, Any]:
    """Run health checks on all monitored components."""
    global last_health_check, health_status
    
    results = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'checks': [],
        'overall_status': 'healthy',
    }
    
    unhealthy_count = 0
    
    for component in MONITORED_COMPONENTS:
        try:
            check_result = run_health_check(
                component=component,
                check_type='connectivity'
            )
            status = check_result.get('status', 'unknown')
            health_status[component] = status
            
            results['checks'].append({
                'component': component,
                'status': status,
                'response_time_ms': check_result.get('response_time_ms'),
                'error': check_result.get('error_message'),
            })
            
            # Record metric
            record_metric(
                metric_name=f'health_check_{component}',
                value=1 if status == 'healthy' else 0,
                metric_type='gauge',
                component='watchdog',
            )
            
            if status not in ['healthy', 'degraded']:
                unhealthy_count += 1
                # Create alert for unhealthy component
                create_alert(
                    alert_type=AlertType.HEALTH_CHECK_FAILURE,
                    severity=AlertSeverity.ERROR,
                    title=f"Health check failed: {component}",
                    message=f"Component {component} is {status}. Error: {check_result.get('error_message', 'Unknown')}",
                    component=component,
                    metadata={'check_result': check_result}
                )
                
        except Exception as e:
            logger.error(f"Health check failed for {component}: {e}")
            health_status[component] = 'error'
            results['checks'].append({
                'component': component,
                'status': 'error',
                'error': str(e),
            })
            unhealthy_count += 1
    
    # Determine overall status
    if unhealthy_count == 0:
        results['overall_status'] = 'healthy'
    elif unhealthy_count < len(MONITORED_COMPONENTS):
        results['overall_status'] = 'degraded'
    else:
        results['overall_status'] = 'unhealthy'
    
    last_health_check = datetime.now(timezone.utc)
    logger.info(f"Health check complete: {results['overall_status']} ({len(MONITORED_COMPONENTS) - unhealthy_count}/{len(MONITORED_COMPONENTS)} healthy)")
    
    return results


def detect_and_handle_failures() -> Dict[str, Any]:
    """Detect agent failures and handle them."""
    results = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'failures_detected': 0,
        'failures_handled': [],
    }
    
    try:
        # Detect failed agents
        failed_agents = detect_agent_failures(
            heartbeat_threshold_seconds=HEARTBEAT_THRESHOLD_SECONDS
        )
        results['failures_detected'] = len(failed_agents)
        
        if failed_agents:
            logger.warning(f"Detected {len(failed_agents)} failed agents")
            
            for agent in failed_agents:
                worker_id = agent.get('worker_id')
                logger.info(f"Handling failure for agent: {worker_id}")

                # Slack warning if heartbeat is stale > 5 minutes (avoid spam for shorter thresholds)
                if SLACK_NOTIFICATIONS_AVAILABLE:
                    try:
                        last_hb_raw = agent.get('last_heartbeat')
                        last_hb_dt: Optional[datetime] = None

                        if isinstance(last_hb_raw, datetime):
                            last_hb_dt = last_hb_raw
                        elif isinstance(last_hb_raw, str) and last_hb_raw:
                            try:
                                last_hb_dt = datetime.fromisoformat(
                                    last_hb_raw.replace('Z', '+00:00')
                                )
                            except Exception:
                                last_hb_dt = None

                        if last_hb_dt is not None:
                            now_dt = datetime.now(timezone.utc)
                            if last_hb_dt.tzinfo is None:
                                last_hb_dt = last_hb_dt.replace(tzinfo=timezone.utc)

                            if now_dt - last_hb_dt > timedelta(minutes=5):
                                send_system_alert(
                                    alert_type="warning",
                                    component="Watchdog",
                                    message=f"Worker {worker_id} heartbeat stale",
                                    details={"worker_id": worker_id, "last_heartbeat": str(last_hb_raw)},
                                )
                    except Exception as slack_err:
                        logger.warning(
                            "Failed to send Slack stale-heartbeat alert for worker %s: %s",
                            worker_id,
                            str(slack_err),
                        )
                
                # Create alert
                create_alert(
                    alert_type=AlertType.WORKER_UNRESPONSIVE,
                    severity=AlertSeverity.WARNING,
                    title=f"Agent unresponsive: {worker_id}",
                    message=f"Agent {worker_id} ({agent.get('name', 'Unknown')}) has stopped responding. Last heartbeat: {agent.get('last_heartbeat')}",
                    component='workers',
                    metadata={'agent': agent}
                )
                
                # Handle the failure
                handle_result = handle_agent_failure(worker_id)
                results['failures_handled'].append({
                    'worker_id': worker_id,
                    'result': handle_result,
                })
        
        # Record metric
        record_counter(
            metric_name='agent_failures_detected',
            increment=len(failed_agents),
            component='watchdog',
        )
        
    except Exception as e:
        logger.error(f"Error detecting/handling failures: {e}")
        results['error'] = str(e)
    
    return results


def run_recovery_cycle() -> Dict[str, Any]:
    """Run automatic recovery procedures."""
    global last_recovery_run
    
    results = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'recovery_actions': None,
        'stale_tasks': [],
    }
    
    try:
        # Run auto recovery
        recovery_result = auto_recover()
        results['recovery_actions'] = recovery_result
        
        # Check for stale tasks
        stale_tasks = check_stale_tasks()
        results['stale_tasks'] = stale_tasks
        
        if stale_tasks:
            logger.warning(f"Found {len(stale_tasks)} stale tasks")
        
        # Log summary
        failures_handled = len(recovery_result.get('failures_handled', []))
        escalations = len(recovery_result.get('escalations_checked', []))
        memory_cleaned = recovery_result.get('memory_cleaned', 0)
        
        logger.info(
            f"Recovery cycle complete: "
            f"{failures_handled} failures handled, "
            f"{escalations} escalations checked, "
            f"{memory_cleaned} memory entries cleaned"
        )
        
    except Exception as e:
        logger.error(f"Error in recovery cycle: {e}")
        results['error'] = str(e)
        
        # Create critical alert for recovery failure
        create_alert(
            alert_type=AlertType.HEALTH_CHECK_FAILURE,
            severity=AlertSeverity.CRITICAL,
            title="Auto-recovery cycle failed",
            message=f"The automatic recovery process encountered an error: {str(e)}",
            component='watchdog',
            metadata={'traceback': traceback.format_exc()}
        )
    
    last_recovery_run = datetime.now(timezone.utc)
    return results


def watchdog_loop() -> None:
    """Main watchdog loop."""
    global running
    
    last_health_time = 0.0
    last_recovery_time = 0.0
    last_budget_allocation_date: Optional[str] = None
    
    # Daily budget allocation constants
    DAILY_BUDGET_ALLOCATION_HOUR = 6  # Run at 6 AM UTC
    DAILY_BUDGET_POOL_CENTS = 10000   # $100 daily pool
    
    while running:
        current_time = time.time()
        current_dt = datetime.now(timezone.utc)
        
        try:
            # Send heartbeat every iteration
            send_heartbeat()
            
            # Run health checks at configured interval
            if current_time - last_health_time >= HEALTH_CHECK_INTERVAL_SECONDS:
                logger.debug("Running health checks...")
                run_all_health_checks()
                detect_and_handle_failures()
                last_health_time = current_time
            
            # Run recovery at configured interval
            if current_time - last_recovery_time >= RECOVERY_INTERVAL_SECONDS:
                logger.debug("Running recovery cycle...")
                run_recovery_cycle()
                last_recovery_time = current_time
            
            # Run daily budget allocation once per day
            today_str = current_dt.strftime("%Y-%m-%d")
            if (last_budget_allocation_date != today_str and 
                current_dt.hour >= DAILY_BUDGET_ALLOCATION_HOUR):
                logger.info("Running daily budget allocation...")
                try:
                    results = run_daily_budget_allocation(
                        daily_pool_cents=DAILY_BUDGET_POOL_CENTS
                    )
                    if not results.get("skipped"):
                        logger.info(
                            "Daily budget allocation: %d/%d goals, %d cents",
                            results.get("allocated_count", 0),
                            results.get("goals_count", 0),
                            results.get("total_allocated_cents", 0)
                        )
                    last_budget_allocation_date = today_str
                except Exception as e:
                    logger.error("Daily budget allocation failed: %s", str(e))
            
        except Exception as e:
            logger.error(f"Error in watchdog loop: {e}")
            traceback.print_exc()
            
            # Increment failure counter but don't crash
            record_counter(
                metric_name='watchdog_loop_errors',
                increment=1,
                component='watchdog',
            )
        
        # Sleep for a short interval
        time.sleep(10)


def main() -> None:
    """Main entry point for the watchdog service."""
    global start_time
    start_time = time.time()
    
    logger.info(f"Starting JUGGERNAUT Watchdog (ID: {WORKER_ID})")
    logger.info(f"Health check interval: {HEALTH_CHECK_INTERVAL_SECONDS}s")
    logger.info(f"Recovery interval: {RECOVERY_INTERVAL_SECONDS}s")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register watchdog in worker registry
    if not register_watchdog():
        logger.error("Failed to register watchdog, exiting")
        sys.exit(1)
    
    # Start health endpoint server in background
    port = int(os.environ.get('PORT', '8080'))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    logger.info(f"Health endpoint listening on port {port}")
    
    # Run initial health check
    logger.info("Running initial health check...")
    run_all_health_checks()
    
    # Start main loop
    logger.info("Starting watchdog loop...")
    watchdog_loop()
    
    # Cleanup
    logger.info("Watchdog shutting down...")
    server.shutdown()


if __name__ == '__main__':
    main()
