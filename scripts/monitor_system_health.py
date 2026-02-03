#!/usr/bin/env python3
"""
System Health Monitor

Real-time monitoring of L5 autonomy system health:
- Worker status and heartbeats
- Task queue health
- Revenue generation pipeline
- Database connectivity
- Stuck tasks detection
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import execute_sql
from core.health_monitor import run_full_health_check


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def format_health_status(status: str) -> str:
    """Format health status with color."""
    if status == "healthy":
        return f"✅ {status.upper()}"
    elif status == "degraded":
        return f"⚠️  {status.upper()}"
    else:
        return f"❌ {status.upper()}"


def display_health_check(results: dict):
    """Display health check results in a readable format."""
    
    print_section(f"System Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    overall = results.get("overall_health", "unknown")
    print(f"Overall Status: {format_health_status(overall)}\n")
    
    # Critical Issues
    critical = results.get("critical_issues", [])
    if critical:
        print("🚨 CRITICAL ISSUES:")
        for issue in critical:
            print(f"  • {issue}")
        print()
    
    # Warnings
    warnings = results.get("warnings", [])
    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  • {warning}")
        print()
    
    if not critical and not warnings:
        print("✅ No issues detected\n")
    
    # Database Check
    print("📊 Database:")
    db_check = results.get("checks", {}).get("database", {})
    if db_check.get("healthy"):
        response_time = db_check.get("response_time_ms", 0)
        print(f"  Status: ✅ Connected ({response_time:.1f}ms)")
        print(f"  Version: {db_check.get('postgres_version', 'unknown')[:50]}")
    else:
        print(f"  Status: ❌ {db_check.get('error', 'Unknown error')}")
    
    # Workers Check
    print("\n👷 Workers:")
    worker_check = results.get("checks", {}).get("workers", {})
    if worker_check.get("success"):
        health = worker_check.get("health", {})
        active = health.get("active_workers", 0)
        stale = health.get("stale_workers", 0)
        print(f"  Active: {active}")
        print(f"  Stale: {stale}")
        
        if health.get("workers"):
            print("\n  Active Workers:")
            for worker in health["workers"][:5]:
                mins = worker.get("minutes_since_heartbeat", 0)
                print(f"    • {worker.get('worker_id')}: {mins:.1f}m ago ({worker.get('status')})")
    else:
        print(f"  Error: {worker_check.get('error', 'Unknown')}")
    
    # Stuck Tasks Check
    print("\n⏱️  Task Queue:")
    stuck_check = results.get("checks", {}).get("stuck_tasks", {})
    if stuck_check.get("success"):
        stuck_count = stuck_check.get("stuck_tasks", 0)
        if stuck_count > 0:
            print(f"  Stuck Tasks: ⚠️  {stuck_count}")
            for task in stuck_check.get("tasks", [])[:3]:
                mins = task.get("minutes_running", 0)
                print(f"    • {task.get('title')[:50]}: {mins:.0f}m")
        else:
            print(f"  Stuck Tasks: ✅ None")
    else:
        print(f"  Error: {stuck_check.get('error', 'Unknown')}")
    
    # Revenue Generation Check
    print("\n💰 Revenue Generation:")
    rev_check = results.get("checks", {}).get("revenue_generation", {})
    if rev_check.get("success"):
        health = rev_check.get("health", {})
        
        ideas = health.get("ideas", {})
        print(f"  Ideas: {ideas.get('total', 0)} total, {ideas.get('pending', 0)} pending, {ideas.get('last_24h', 0)} in last 24h")
        
        experiments = health.get("experiments", {})
        print(f"  Experiments: {experiments.get('total', 0)} total, {experiments.get('running', 0)} running, {experiments.get('completed', 0)} completed")
        
        revenue = health.get("revenue", {})
        total_cents = revenue.get("total_cents", 0)
        total_dollars = total_cents / 100
        print(f"  Revenue: ${total_dollars:.2f} ({revenue.get('event_count', 0)} events)")
        
        tasks = health.get("tasks", {})
        print(f"  Tasks: {tasks.get('total', 0)} total, {tasks.get('pending', 0)} pending, {tasks.get('running', 0)} running, {tasks.get('failed', 0)} failed")
    else:
        print(f"  Error: {rev_check.get('error', 'Unknown')}")


def log_action(action: str, message: str, level: str = "info", **kwargs):
    """Dummy log action for health monitor."""
    pass


def monitor_once():
    """Run one monitoring cycle."""
    try:
        results = run_full_health_check(execute_sql, log_action)
        display_health_check(results)
        return results
    except Exception as e:
        print(f"\n❌ Error running health check: {str(e)}\n")
        return None


def monitor_continuous(interval: int = 30):
    """Monitor continuously with updates every interval seconds."""
    print("Starting continuous health monitoring (Ctrl+C to stop)...")
    print(f"Update interval: {interval} seconds\n")
    
    try:
        while True:
            results = monitor_once()
            
            if results:
                overall = results.get("overall_health", "unknown")
                critical = len(results.get("critical_issues", []))
                warnings = len(results.get("warnings", []))
                
                status_msg = f"Status: {overall}"
                if critical > 0:
                    status_msg += f" | {critical} critical issues"
                if warnings > 0:
                    status_msg += f" | {warnings} warnings"
                
                print(f"\n⏳ Next update in {interval} seconds... ({status_msg})")
            else:
                print(f"\n⏳ Next update in {interval} seconds... (check failed)")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor system health")
    parser.add_argument("--continuous", "-c", action="store_true", help="Run continuously")
    parser.add_argument("--interval", "-i", type=int, default=30, help="Update interval in seconds (default: 30)")
    
    args = parser.parse_args()
    
    if args.continuous:
        monitor_continuous(args.interval)
    else:
        monitor_once()
