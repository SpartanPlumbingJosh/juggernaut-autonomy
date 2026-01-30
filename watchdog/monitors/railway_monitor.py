import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


RAILWAY_API_URL = "https://backboard.railway.com/graphql/v2"


@dataclass
class RailwayDeployment:
    deployment_id: str
    service_name: str
    status: str


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

        query = f"""
        query($projectId: String!, $first: Int!{', $serviceId: String!' if service_id else ''}) {{
          deployments(first: $first, input: {{ projectId: $projectId{service_filter} }}) {{
            edges {{ node {{ id status service {{ name }} }} }}
          }}
        }}
        """

        res = self._graphql(query, vars_)
        edges = (((res.get("data") or {}).get("deployments") or {}).get("edges") or [])
        out: List[RailwayDeployment] = []
        for e in edges:
            n = (e or {}).get("node") or {}
            sid = n.get("id")
            st = (n.get("status") or "").upper()
            sname = ((n.get("service") or {}).get("name") or "")
            if sid and sname:
                out.append(RailwayDeployment(deployment_id=sid, service_name=sname, status=st))
        return out

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

        services = self.list_services()
        for svc in services:
            deployments = self.list_recent_deployments(limit=5, service_id=svc["id"])
            if not deployments:
                continue

            latest = deployments[0]
            last_seen = self._last_seen_deployments.get(latest.service_name)
            if last_seen == latest.deployment_id:
                continue

            self._last_seen_deployments[latest.service_name] = latest.deployment_id

            if latest.status in ("FAILED", "CRASHED", "ERROR"):
                logs = self.get_deployment_logs(latest.deployment_id, limit=200)
                log_text = "\n".join([str(x.get("message") or "") for x in logs])
                error_type, missing_module = self._extract_error(log_text)
                snippet = log_text[-1200:] if log_text else ""

                issues.append(
                    {
                        "platform": "railway",
                        "service": latest.service_name,
                        "deployment_id": latest.deployment_id,
                        "status": latest.status,
                        "error_type": error_type,
                        "missing_module": missing_module,
                        "log_snippet": snippet,
                    }
                )

        return issues
