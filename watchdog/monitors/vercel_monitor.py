import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


VERCEL_API_URL = "https://api.vercel.com"


@dataclass
class VercelDeployment:
    deployment_id: str
    name: str
    state: str


class VercelMonitor:
    def __init__(self, *, token: Optional[str] = None):
        self.token = token or os.getenv("VERCEL_TOKEN", "")
        self._last_seen: Dict[str, str] = {}

    def is_configured(self) -> bool:
        return bool(self.token)

    def _api_get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(f"{VERCEL_API_URL}{path}")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", "Juggernaut-Watchdog/1.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def list_recent_deployments(self, *, limit: int = 10) -> List[VercelDeployment]:
        res = self._api_get(f"/v6/deployments?limit={int(limit)}")
        deps = res.get("deployments") or []
        out: List[VercelDeployment] = []
        for d in deps:
            did = d.get("uid")
            name = d.get("name") or ""
            state = (d.get("state") or "").upper()
            if did and name:
                out.append(VercelDeployment(deployment_id=did, name=name, state=state))
        return out

    def get_deployment_events(self, deployment_id: str) -> Dict[str, Any]:
        return self._api_get(f"/v6/deployments/{deployment_id}/events")

    def poll(self) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        if not self.is_configured():
            return issues

        for dep in self.list_recent_deployments(limit=10):
            last_seen = self._last_seen.get(dep.name)
            if last_seen == dep.deployment_id:
                continue
            self._last_seen[dep.name] = dep.deployment_id

            if dep.state in ("ERROR", "FAILED"):
                events = self.get_deployment_events(dep.deployment_id)
                issues.append(
                    {
                        "platform": "vercel",
                        "service": dep.name,
                        "deployment_id": dep.deployment_id,
                        "status": dep.state,
                        "events": events,
                    }
                )

        return issues
