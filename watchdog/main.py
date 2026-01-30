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
        query_db(
            """
            INSERT INTO worker_registry (worker_id, worker_type, status, last_heartbeat)
            VALUES ($1, 'watchdog', 'active', NOW())
            ON CONFLICT (worker_id) DO UPDATE SET
                last_heartbeat = NOW(),
                status = 'active'
            """,
            [WORKER_ID],
        )
    except Exception:
        pass


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

    start_health_server(int(os.getenv("PORT", "8000")))

    railway = RailwayMonitor()
    vercel = VercelMonitor()

    while True:
        _send_heartbeat()
        issues = []
        try:
            issues.extend(railway.poll())
        except Exception:
            pass

        try:
            issues.extend(vercel.poll())
        except Exception:
            pass

        for issue in issues:
            _issue_to_task(issue)

        time.sleep(max(5, POLL_INTERVAL_SECONDS))


if __name__ == "__main__":
    main()
