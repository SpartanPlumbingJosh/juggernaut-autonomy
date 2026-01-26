import re
import json
import os
import socket
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_table_from_sql(sql: str) -> Optional[str]:
    s = sql.strip()

    m = re.search(r"\binsert\s+into\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\b", s, re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r"\bupdate\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\b", s, re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r"\bdelete\s+from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\b", s, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _parse_operation_from_sql(sql: str) -> Optional[str]:
    s = sql.strip().lower()
    if s.startswith("insert"):
        return "insert"
    if s.startswith("update"):
        return "update"
    if s.startswith("delete"):
        return "delete"
    return None


def _extract_uuid_after_id(sql: str) -> Optional[str]:
    # Matches: id = 'uuid'
    m = re.search(
        r"\bid\s*=\s*'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})'",
        sql,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    # Matches common Postgres cast: id = 'uuid'::uuid
    m = re.search(
        r"\bid\s*=\s*'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})'::uuid",
        sql,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)

    return None


def _extract_inserted_uuid(sql: str) -> Optional[str]:
    # Best-effort: if INSERT specifies id in column list, capture the corresponding UUID literal.
    # Example: INSERT INTO t (id, name) VALUES ('uuid', 'x')
    m = re.search(
        r"\binsert\s+into\s+[a-zA-Z_][a-zA-Z0-9_\.]*(?:\s*\((?P<cols>[^\)]*)\))?\s*values\s*\((?P<vals>[^\)]*)\)",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None

    cols_raw = m.group("cols")
    vals_raw = m.group("vals")
    if not cols_raw or not vals_raw:
        return None

    cols = [c.strip().strip('"') for c in cols_raw.split(",")]
    vals = [v.strip() for v in vals_raw.split(",")]

    try:
        idx = cols.index("id")
    except ValueError:
        return None

    if idx >= len(vals):
        return None

    v = vals[idx]
    m2 = re.search(
        r"'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})'",
        v,
    )
    return m2.group(1) if m2 else None


def execute_db_write_with_verification(
    *,
    execute_sql: Callable[[str], Dict[str, Any]],
    sql: str,
    table: Optional[str] = None,
    operation: Optional[str] = None,
    verify_select_sql: Optional[str] = None,
    attempt_returning_id: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute a DB write and return structured verification evidence.

    This is a best-effort verifier designed for Postgres-style SQL.

    Verification strategies (in order):
    1) If query result returns rows with an `id` column, use that id.
    2) If we can extract an id from the SQL (UPDATE ... WHERE id='..' OR INSERT (id,...) VALUES ('..',...)),
       run a follow-up SELECT to confirm the row exists.
    3) If verify_select_sql is provided, run it and require rowCount > 0.

    Returns:
        (db_result, verification)
    """

    verified_at = _iso_now()
    op = operation or _parse_operation_from_sql(sql) or "write"
    tbl = table or _parse_table_from_sql(sql)

    db_result: Dict[str, Any]
    try_sql = sql
    attempted_returning = False

    # Prefer RETURNING id when possible (gives strong evidence).
    # Best-effort: only attempt for INSERT/UPDATE when query has no RETURNING clause.
    if attempt_returning_id and op in ("insert", "update"):
        lowered = sql.lower()
        if "returning" not in lowered:
            try_sql = sql.rstrip().rstrip(";") + " RETURNING id"
            attempted_returning = True

    try:
        db_result = execute_sql(try_sql)
    except Exception as e:
        if attempted_returning:
            # Fall back to original SQL if RETURNING is unsupported for this statement
            try:
                db_result = execute_sql(sql)
            except Exception as e2:
                return (
                    {"status": "error", "error": str(e2)},
                    {
                        "type": "db_write",
                        "verified": False,
                        "table": tbl,
                        "row_id": None,
                        "operation": op,
                        "verified_at": verified_at,
                        "error": str(e2),
                    },
                )
        else:
            return (
                {"status": "error", "error": str(e)},
                {
                    "type": "db_write",
                    "verified": False,
                    "table": tbl,
                    "row_id": None,
                    "operation": op,
                    "verified_at": verified_at,
                    "error": str(e),
                },
            )

    row_id = None
    try:
        rows = db_result.get("rows") or []
        if rows and isinstance(rows[0], dict) and rows[0].get("id") is not None:
            row_id = str(rows[0].get("id"))
    except Exception:
        row_id = None

    # Attempt follow-up verification
    followup_ok = None
    followup_error = None

    if row_id is None:
        row_id = _extract_uuid_after_id(sql) or _extract_inserted_uuid(sql)

    if row_id is not None and tbl:
        try:
            check_sql = f"SELECT id FROM {tbl} WHERE id = '{row_id}'::uuid LIMIT 1"
            check = execute_sql(check_sql)
            followup_ok = bool(check.get("rowCount", 0) > 0)
            if not followup_ok:
                followup_error = "Follow-up SELECT returned 0 rows"
        except Exception as e:
            followup_ok = False
            followup_error = str(e)
    elif verify_select_sql:
        try:
            check = execute_sql(verify_select_sql)
            followup_ok = bool(check.get("rowCount", 0) > 0)
            if not followup_ok:
                followup_error = "verify_select_sql returned 0 rows"
        except Exception as e:
            followup_ok = False
            followup_error = str(e)

    # If we got an id directly from RETURNING, consider verified.
    if row_id is not None and followup_ok is None:
        followup_ok = True

    verified = bool(followup_ok)

    verification: Dict[str, Any] = {
        "type": "db_write",
        "verified": verified,
        "table": tbl,
        "row_id": row_id,
        "operation": op,
        "verified_at": verified_at,
    }

    if not verified:
        verification["error"] = followup_error or "Unable to verify DB write"

    return db_result, verification


def execute_api_call_with_verification(
    *,
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    json_body: Any = None,
    timeout_seconds: int = 20,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    verified_at = _iso_now()
    m = (method or "GET").upper()
    hdrs: Dict[str, str] = dict(headers or {})

    request_body: Optional[bytes] = None
    if json_body is not None:
        request_body = json.dumps(json_body).encode("utf-8")
        if not any(k.lower() == "content-type" for k in hdrs.keys()):
            hdrs["Content-Type"] = "application/json"
    elif body is not None:
        if isinstance(body, (bytes, bytearray)):
            request_body = bytes(body)
        elif isinstance(body, str):
            request_body = body.encode("utf-8")
        else:
            request_body = json.dumps(body).encode("utf-8")
            if not any(k.lower() == "content-type" for k in hdrs.keys()):
                hdrs["Content-Type"] = "application/json"

    try:
        req = urllib.request.Request(url=url, data=request_body, headers=hdrs, method=m)
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status_code = int(getattr(resp, "status", None) or resp.getcode())
            resp_body = resp.read()
            resp_text: str
            try:
                resp_text = resp_body.decode("utf-8", errors="replace")
            except Exception:
                resp_text = str(resp_body)[:500]

            response_ok = 200 <= status_code < 300
            verification: Dict[str, Any] = {
                "type": "api_call",
                "verified": bool(response_ok),
                "url": url,
                "method": m,
                "status_code": status_code,
                "response_ok": bool(response_ok),
                "verified_at": verified_at,
            }

            result: Dict[str, Any] = {
                "url": url,
                "method": m,
                "status_code": status_code,
                "response_ok": bool(response_ok),
                "response_body_preview": resp_text[:500],
            }

            if not response_ok:
                verification["error"] = f"Non-2xx response: {status_code}"

            return result, verification

    except urllib.error.HTTPError as e:
        status_code = int(getattr(e, "code", 0) or 0)
        body_preview = ""
        try:
            raw = e.read()
            body_preview = raw.decode("utf-8", errors="replace")[:500]
        except Exception:
            body_preview = ""

        return (
            {
                "url": url,
                "method": m,
                "status_code": status_code,
                "response_ok": False,
                "error": str(e),
                "response_body_preview": body_preview,
            },
            {
                "type": "api_call",
                "verified": False,
                "url": url,
                "method": m,
                "status_code": status_code,
                "response_ok": False,
                "verified_at": verified_at,
                "error": str(e),
            },
        )
    except (socket.timeout, TimeoutError) as e:
        return (
            {"url": url, "method": m, "status_code": None, "response_ok": False, "error": "timeout"},
            {
                "type": "api_call",
                "verified": False,
                "url": url,
                "method": m,
                "status_code": None,
                "response_ok": False,
                "verified_at": verified_at,
                "error": "timeout",
            },
        )
    except urllib.error.URLError as e:
        return (
            {
                "url": url,
                "method": m,
                "status_code": None,
                "response_ok": False,
                "error": str(getattr(e, "reason", e)),
            },
            {
                "type": "api_call",
                "verified": False,
                "url": url,
                "method": m,
                "status_code": None,
                "response_ok": False,
                "verified_at": verified_at,
                "error": str(getattr(e, "reason", e)),
            },
        )
    except Exception as e:
        return (
            {"url": url, "method": m, "status_code": None, "response_ok": False, "error": str(e)},
            {
                "type": "api_call",
                "verified": False,
                "url": url,
                "method": m,
                "status_code": None,
                "response_ok": False,
                "verified_at": verified_at,
                "error": str(e),
            },
        )


def execute_deploy_with_verification(
    *,
    service_id: str,
    service_name: Optional[str] = None,
    environment_id: str = "8bfa6a1a-92f4-4a42-bf51-194b1c844a76",
    railway_token: Optional[str] = None,
    poll_interval_seconds: int = 10,
    timeout_seconds: int = 300,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    verified_at = _iso_now()
    token = railway_token or os.environ.get("RAILWAY_TOKEN")
    if not token:
        return (
            {"status": "error", "error": "Missing RAILWAY_TOKEN"},
            {
                "type": "railway_deploy",
                "verified": False,
                "service_id": service_id,
                "service_name": service_name,
                "deployment_id": None,
                "status": "ERROR",
                "verified_at": verified_at,
                "error": "Missing RAILWAY_TOKEN",
            },
        )

    api_url = "https://backboard.railway.com/graphql/v2"

    def _graphql(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    mutation = """
mutation Redeploy($serviceId: String!, $environmentId: String!) {
  serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
}
"""

    try:
        m_resp = _graphql({
            "query": mutation,
            "variables": {"serviceId": service_id, "environmentId": environment_id},
        })
    except Exception as e:
        return (
            {"status": "error", "error": str(e)},
            {
                "type": "railway_deploy",
                "verified": False,
                "service_id": service_id,
                "service_name": service_name,
                "deployment_id": None,
                "status": "ERROR",
                "verified_at": verified_at,
                "error": str(e),
            },
        )

    if isinstance(m_resp, dict) and m_resp.get("errors"):
        return (
            {"status": "error", "error": str(m_resp.get("errors"))},
            {
                "type": "railway_deploy",
                "verified": False,
                "service_id": service_id,
                "service_name": service_name,
                "deployment_id": None,
                "status": "ERROR",
                "verified_at": verified_at,
                "error": str(m_resp.get("errors")),
            },
        )

    query = """
query LatestDeployment($serviceId: String!) {
  deployments(first: 1, input: {serviceId: $serviceId}) {
    edges {
      node {
        id
        status
      }
    }
  }
}
"""

    start = time.time()
    last_status: Optional[str] = None
    last_deployment_id: Optional[str] = None
    last_error: Optional[str] = None

    while (time.time() - start) < timeout_seconds:
        try:
            q_resp = _graphql({"query": query, "variables": {"serviceId": service_id}})
            if q_resp.get("errors"):
                last_error = str(q_resp.get("errors"))
                time.sleep(poll_interval_seconds)
                continue

            edges = (
                q_resp.get("data", {})
                .get("deployments", {})
                .get("edges", [])
            )
            node = (edges[0] or {}).get("node", {}) if edges else {}
            last_deployment_id = node.get("id")
            last_status = node.get("status")

            if last_status in ("SUCCESS", "FAILED"):
                break

        except Exception as e:
            last_error = str(e)

        time.sleep(poll_interval_seconds)

    if last_status != "SUCCESS" and last_status != "FAILED":
        last_status = last_status or "TIMEOUT"
        last_error = last_error or "timeout"

    verified = bool(last_status == "SUCCESS")
    verification: Dict[str, Any] = {
        "type": "railway_deploy",
        "verified": verified,
        "service_id": service_id,
        "service_name": service_name,
        "deployment_id": last_deployment_id,
        "status": last_status,
        "verified_at": verified_at,
    }
    if not verified:
        verification["error"] = last_error or "Deployment did not succeed"

    result: Dict[str, Any] = {
        "service_id": service_id,
        "service_name": service_name,
        "deployment_id": last_deployment_id,
        "status": last_status,
    }
    if last_error:
        result["error"] = last_error

    return result, verification
