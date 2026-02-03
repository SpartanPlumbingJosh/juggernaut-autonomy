import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

from core.database import query_db
from watchdog.alerting import create_fix_task
from watchdog.monitors.railway_monitor import RailwayMonitor
from watchdog.monitors.vercel_monitor import VercelMonitor


WORKER_ID = os.getenv("WORKER_ID", "WATCHDOG")
POLL_INTERVAL_SECONDS = int(os.getenv("WATCHDOG_POLL_INTERVAL", "60"))
ENABLE_EXTERNAL_POLLING = (
    os.getenv("WATCHDOG_ENABLE_EXTERNAL_POLLING", "0").strip().lower() in ("1", "true", "yes", "y", "on")
    and os.getenv("WATCHDOG_ALLOW_EXTERNAL_POLLING", "0").strip().lower() in ("1", "true", "yes", "y", "on")
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def start_health_server(port: int) -> None:
    server = HTTPServer(("0.0.0.0", int(port)), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def _send_heartbeat() -> None:
    try:
        from core.heartbeat import send_heartbeat as redis_heartbeat
        success = redis_heartbeat(WORKER_ID)
        if not success:
            print("WATCHDOG heartbeat failed", flush=True)
    except Exception as e:
        print(f"WATCHDOG heartbeat error: {e}", flush=True)
        # Fallback to direct database update if heartbeat module fails
        try:
            query_db(
                """
                INSERT INTO worker_registry (worker_id, name, worker_type, status, last_heartbeat)
                VALUES ($1, 'JUGGERNAUT Watchdog', 'watchdog', 'active', NOW())
                ON CONFLICT (worker_id) DO UPDATE SET
                    last_heartbeat = NOW(),
                    status = 'active'
                """,
                [WORKER_ID],
            )
            print("WATCHDOG heartbeat fallback succeeded", flush=True)
        except Exception as db_err:
            print(f"WATCHDOG heartbeat fallback failed: {db_err}", flush=True)


def _issue_to_task(issue: Dict[str, Any]) -> Dict[str, Any]:
    platform = issue.get("platform")
    service = issue.get("service") or "unknown"

    if platform == "railway":
        missing_module = issue.get("missing_module")
        error_type = issue.get("error_type") or "DeployFailure"
        title = (
            f"Fix: {service} build failure - missing module '{missing_module}'"
            if missing_module
            else f"Fix: {service} build/deploy failure ({error_type})"
        )
        desc = (
            f"Railway deployment failed for service '{service}'.\n"
            f"Deployment: {issue.get('deployment_id')}\n"
            f"Status: {issue.get('status')}\n"
            f"Error type: {error_type}\n\n"
            f"Log snippet:\n{issue.get('log_snippet') or ''}"
        )
        issue_key = f"railway:{service}:{issue.get('deployment_id')}"
        return create_fix_task(
            title=title,
            description=desc,
            priority="critical",
            service=service,
            issue_key=issue_key,
            metadata={
                "platform": "railway",
                "deployment_id": issue.get("deployment_id"),
                "status": issue.get("status"),
                "error_type": error_type,
                "log_snippet": issue.get("log_snippet"),
            },
        )

    if platform == "vercel":
        title = f"Fix: {service} deployment failure (Vercel)"
        desc = (
            f"Vercel deployment failed for '{service}'.\n"
            f"Deployment: {issue.get('deployment_id')}\n"
            f"Status: {issue.get('status')}\n"
        )
        issue_key = f"vercel:{service}:{issue.get('deployment_id')}"
        return create_fix_task(
            title=title,
            description=desc,
            priority="high",
            service=service,
            issue_key=issue_key,
            metadata={
                "platform": "vercel",
                "deployment_id": issue.get("deployment_id"),
                "status": issue.get("status"),
                "events": issue.get("events"),
            },
        )

    return {"success": False, "error": f"Unknown platform: {platform}"}


def main() -> None:
    os.environ.setdefault("WORKER_ID", "WATCHDOG")

    print(f"WATCHDOG starting (worker_id={WORKER_ID})", flush=True)

    port = int(os.getenv("PORT", "8000"))
    print(f"WATCHDOG starting health server on port {port}", flush=True)

    start_health_server(port)
    print("WATCHDOG health server started", flush=True)

    railway = None
    vercel = None
    if ENABLE_EXTERNAL_POLLING:
        railway = RailwayMonitor()
        vercel = VercelMonitor()
        print("WATCHDOG monitors initialized", flush=True)
    else:
        print("WATCHDOG external polling disabled", flush=True)

    while True:
        issues = []
        if ENABLE_EXTERNAL_POLLING:
            try:
                issues.extend(railway.poll())
            except Exception as e:
                print(f"WATCHDOG railway poll error: {e}", flush=True)

            try:
                issues.extend(vercel.poll())
            except Exception as e:
                print(f"WATCHDOG vercel poll error: {e}", flush=True)

        for issue in issues:
            _issue_to_task(issue)

        _send_heartbeat()

        time.sleep(max(5, POLL_INTERVAL_SECONDS))


if __name__ == "__main__":
    main()
