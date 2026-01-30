import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db
from src.github_automation import GitHubClient


RAILWAY_API_URL = "https://backboard.railway.com/graphql/v2"


@dataclass
class RailwayDeployment:
    deployment_id: str
    service_name: str
    status: str
    commit_sha: Optional[str] = None


class RailwayMonitor:
    def __init__(
        self,
        *,
        token: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        self.token = token or os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_TOKEN", "")
        self.project_id = project_id or os.getenv("RAILWAY_PROJECT_ID", "")
        self._last_seen_deployments: Dict[str, str] = {}
        self._processed_failures: set[str] = set()

        try:
            self._ensure_seen_failures_schema()
            self._processed_failures = self._load_seen_failures()
        except Exception:
            self._processed_failures = set()

        self._github: Optional[GitHubClient] = None
        self._main_sha_cache: Optional[str] = None
        self._main_sha_cache_ts: float = 0.0

    def is_configured(self) -> bool:
        return bool(self.token and self.project_id)

    def _graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        req = urllib.request.Request(
            RAILWAY_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_github(self) -> Optional[GitHubClient]:
        if self._github is not None:
            return self._github
        if not os.getenv("GITHUB_TOKEN"):
            self._github = None
            return None
        self._github = GitHubClient()
        return self._github

    def _get_main_sha(self) -> Optional[str]:
        github = self._get_github()
        if github is None:
            return None
        now = __import__("time").time()
        if self._main_sha_cache and (now - self._main_sha_cache_ts) < 300:
            return self._main_sha_cache
        try:
            sha = github.get_main_sha()
            if sha:
                self._main_sha_cache = sha
                self._main_sha_cache_ts = now
            return sha
        except Exception:
            return None

    def list_services(self) -> List[Dict[str, Any]]:
        query = """
        query($id: String!) {
          project(id: $id) {
            services {
              edges { node { id name } }
            }
          }
        }
        """
        res = self._graphql(query, {"id": self.project_id})
        edges = (((res.get("data") or {}).get("project") or {}).get("services") or {}).get("edges") or []
        services = []
        for e in edges:
            n = (e or {}).get("node") or {}
            if n.get("id") and n.get("name"):
                services.append({"id": n["id"], "name": n["name"]})
        return services

    def list_recent_deployments(self, *, limit: int = 5, service_id: Optional[str] = None) -> List[RailwayDeployment]:
        service_filter = ", serviceId: $serviceId" if service_id else ""
        vars_: Dict[str, Any] = {"projectId": self.project_id, "first": int(limit)}
        if service_id:
            vars_["serviceId"] = service_id

        query_with_commit = f"""
        query($projectId: String!, $first: Int!{', $serviceId: String!' if service_id else ''}) {{
          deployments(first: $first, input: {{ projectId: $projectId{service_filter} }}) {{
            edges {{ node {{ id status service {{ name }} commitSha }} }}
          }}
        }}
        """

        query_without_commit = f"""
        query($projectId: String!, $first: Int!{', $serviceId: String!' if service_id else ''}) {{
          deployments(first: $first, input: {{ projectId: $projectId{service_filter} }}) {{
            edges {{ node {{ id status service {{ name }} }} }}
          }}
        }}
        """

        res = self._graphql(query_with_commit, vars_)
        if res.get("errors"):
            res = self._graphql(query_without_commit, vars_)
        edges = (((res.get("data") or {}).get("deployments") or {}).get("edges") or [])
        out: List[RailwayDeployment] = []
        for e in edges:
            n = (e or {}).get("node") or {}
            sid = n.get("id")
            st = (n.get("status") or "").upper()
            sname = ((n.get("service") or {}).get("name") or "")
            if sid and sname:
                out.append(
                    RailwayDeployment(
                        deployment_id=sid,
                        service_name=sname,
                        status=st,
                        commit_sha=n.get("commitSha"),
                    )
                )
        return out

    def _ensure_seen_failures_schema(self) -> None:
        query_db(
            """
            CREATE TABLE IF NOT EXISTS watchdog_seen_failures (
                deployment_id text PRIMARY KEY,
                first_seen_at timestamptz NOT NULL DEFAULT NOW()
            );
            """
        )

    def _load_seen_failures(self) -> set[str]:
        res = query_db("SELECT deployment_id FROM watchdog_seen_failures")
        rows = res.get("rows") or []
        return {str(r.get("deployment_id")) for r in rows if r.get("deployment_id")}

    def _mark_failure_seen(self, deployment_id: str) -> None:
        query_db(
            """
            INSERT INTO watchdog_seen_failures (deployment_id)
            VALUES ($1)
            ON CONFLICT (deployment_id) DO NOTHING
            """,
            [deployment_id],
        )

    def get_deployment_logs(self, deployment_id: str, *, limit: int = 200) -> List[Dict[str, Any]]:
        query = """
        query($deploymentId: String!, $limit: Int!) {
          deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
            message
            timestamp
          }
        }
        """
        res = self._graphql(query, {"deploymentId": deployment_id, "limit": int(limit)})
        return ((res.get("data") or {}).get("deploymentLogs") or [])

    def _extract_error(self, log_text: str) -> Tuple[Optional[str], Optional[str]]:
        m = re.search(r"ModuleNotFoundError: No module named '([^']+)'", log_text)
        if m:
            return "ModuleNotFoundError", m.group(1)
        if "Traceback (most recent call last):" in log_text:
            return "PythonException", None
        if "ERROR" in log_text.upper():
            return "BuildError", None
        return None, None

    def poll(self) -> List[Dict[str, Any]]:
        """Return detected issues (does not create tasks)."""
        issues: List[Dict[str, Any]] = []
        if not self.is_configured():
            return issues

        main_sha = self._get_main_sha()

        services = self.list_services()
        for svc in services:
            deployments = self.list_recent_deployments(limit=5, service_id=svc["id"])
            if not deployments:
                continue

            latest = deployments[0]
            last_seen = self._last_seen_deployments.get(latest.service_name)
            if last_seen != latest.deployment_id:
                self._last_seen_deployments[latest.service_name] = latest.deployment_id

            for dep in deployments:
                if main_sha and dep.commit_sha and dep.commit_sha != main_sha:
                    issues.append(
                        {
                            "platform": "railway",
                            "issue_type": "commit_drift",
                            "service": dep.service_name,
                            "deployment_id": dep.deployment_id,
                            "status": dep.status,
                            "deployed_commit": dep.commit_sha,
                            "expected_commit": main_sha,
                            "message": f"Service {dep.service_name} running old code: {dep.commit_sha[:8]} vs main {main_sha[:8]}",
                        }
                    )

                if dep.status not in ("FAILED", "CRASHED", "ERROR", "REMOVED"):
                    continue
                if dep.deployment_id in self._processed_failures:
                    continue

                logs = self.get_deployment_logs(dep.deployment_id, limit=200)
                log_text = "\n".join([str(x.get("message") or "") for x in logs])
                error_type, missing_module = self._extract_error(log_text)
                snippet = log_text[-1200:] if log_text else ""

                issues.append(
                    {
                        "platform": "railway",
                        "service": dep.service_name,
                        "deployment_id": dep.deployment_id,
                        "status": dep.status,
                        "error_type": error_type,
                        "missing_module": missing_module,
                        "log_snippet": snippet,
                        "commit_sha": dep.commit_sha,
                    }
                )

                self._processed_failures.add(dep.deployment_id)
                try:
                    self._mark_failure_seen(dep.deployment_id)
                except Exception:
                    pass

        return issues
