"""
Supabase Compatibility Launcher for Juggernaut Engine.

Intercepts urllib.request.urlopen calls to the Supabase endpoint and
re-routes them through http.client.HTTPSConnection, which preserves
exact header casing. This is required because:
  - urllib.request.Request normalizes headers to Title-Case
  - CF-Access-Client-Id becomes Cf-access-client-id
  - Cloudflare Access rejects lowercased CF headers (error 1010)

Also normalizes Supabase flat-array responses [{col: val}, ...] to
Neon-compatible {rows, fields, rowCount} dicts.

Start command: python start_engine.py
"""

import os
import sys
import json
import ssl
import http.client
import io
from urllib.parse import urlparse

# --- Configuration from environment ---
SUPABASE_ENDPOINT = os.getenv(
    "SUPABASE_ENDPOINT",
    "https://kong.thejuggernaut.org/rest/v1/rpc/run_sql"
)
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
CF_ID = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

_parsed_sb = urlparse(SUPABASE_ENDPOINT)
_SB_HOST = _parsed_sb.hostname or ""
_SB_PATH = _parsed_sb.path or "/rest/v1/rpc/run_sql"

# Override NEON_ENDPOINT env var before any imports read it
os.environ["NEON_ENDPOINT"] = SUPABASE_ENDPOINT

# --- Build the exact headers Supabase needs (case-preserved) ---
_SUPABASE_HEADERS = {
    "Content-Type": "application/json",
    "Content-Profile": "spartan_ops",
}
if SUPABASE_KEY:
    _SUPABASE_HEADERS["apikey"] = SUPABASE_KEY
    _SUPABASE_HEADERS["Authorization"] = f"Bearer {SUPABASE_KEY}"
if CF_ID:
    _SUPABASE_HEADERS["CF-Access-Client-Id"] = CF_ID
if CF_SECRET:
    _SUPABASE_HEADERS["CF-Access-Client-Secret"] = CF_SECRET


class _FakeResponse:
    """Mimics urllib HTTPResponse so callers (execute_sql, Database.query) work."""

    def __init__(self, status, body_bytes, headers=None):
        self.status = status
        self.code = status
        self.reason = "OK" if 200 <= status < 300 else "Error"
        self._body = body_bytes
        self._headers = headers or {}

    def read(self):
        return self._body

    def getheader(self, name, default=None):
        return self._headers.get(name, default)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _supabase_request(body_bytes, timeout=30):
    """Make a request to Supabase via http.client (preserves header casing)."""
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(_SB_HOST, timeout=timeout, context=ctx)
    try:
        conn.request("POST", _SB_PATH, body=body_bytes, headers=_SUPABASE_HEADERS)
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status

        if 200 <= status < 300:
            # Normalize Supabase flat array to Neon-style dict
            try:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, list):
                    wrapped = {
                        "rows": parsed,
                        "fields": [],
                        "rowCount": len(parsed),
                    }
                    raw = json.dumps(wrapped).encode("utf-8")
            except Exception:
                pass
            return _FakeResponse(status, raw)
        else:
            # Raise HTTPError so callers' except blocks work
            import urllib.error
            fp = io.BytesIO(raw)
            raise urllib.error.HTTPError(
                SUPABASE_ENDPOINT, status, raw.decode("utf-8", errors="replace"), {}, fp
            )
    finally:
        conn.close()


# --- Monkey-patch urllib.request.urlopen ---
import urllib.request
import urllib.error

_orig_urlopen = urllib.request.urlopen


def _patched_urlopen(req_or_url, *args, **kwargs):
    """Intercept Supabase requests and route through http.client."""
    # Determine the URL
    url = ""
    if hasattr(req_or_url, "full_url"):
        url = req_or_url.full_url
    elif isinstance(req_or_url, str):
        url = req_or_url

    if _SB_HOST and _SB_HOST in url and "/rpc/run_sql" in url:
        # Extract body from the request
        data = None
        if hasattr(req_or_url, "data"):
            data = req_or_url.data
        elif len(args) > 0:
            data = args[0]

        if data is None:
            data = b'{"query": "SELECT 1"}'

        timeout = kwargs.get("timeout", 30)
        return _supabase_request(data, timeout=timeout)

    # All other requests pass through normally
    return _orig_urlopen(req_or_url, *args, **kwargs)


urllib.request.urlopen = _patched_urlopen

# --- Startup banner ---
print("=" * 60)
print("[SUPABASE PATCH] Compatibility layer active (http.client)")
print(f"[SUPABASE PATCH] Host: {_SB_HOST}")
print(f"[SUPABASE PATCH] Path: {_SB_PATH}")
print(f"[SUPABASE PATCH] Service key: {'set' if SUPABASE_KEY else 'MISSING'}")
print(f"[SUPABASE PATCH] CF-Access: {'set' if CF_ID else 'MISSING'}")
print("=" * 60)

# --- Run main.py in __main__ context ---
_main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
with open(_main_path, "r") as f:
    _code = compile(f.read(), "main.py", "exec")
exec(_code)
