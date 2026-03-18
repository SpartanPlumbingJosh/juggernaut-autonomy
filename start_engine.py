"""
Supabase Compatibility Launcher for Juggernaut Engine.

This wrapper patches urllib.request so all HTTP SQL API calls
(main.py execute_sql + core/database.py Database.query) automatically
use Supabase PostgREST headers instead of Neon-Connection-String,
and normalizes responses from Supabase flat arrays to Neon-style
{rows, fields} dicts.

Start command: python start_engine.py
"""

import os
import sys
import json

# --- Configuration from environment ---
SUPABASE_ENDPOINT = os.getenv(
    "SUPABASE_ENDPOINT",
    "https://kong.thejuggernaut.org/rest/v1/rpc/run_sql"
)
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
CF_ID = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

# Override NEON_ENDPOINT env var before any imports read it
os.environ["NEON_ENDPOINT"] = SUPABASE_ENDPOINT

# --- Monkey-patch urllib.request ---
import urllib.request
import urllib.error

_OrigRequest = urllib.request.Request


class _SupabaseRequest(_OrigRequest):
    """Intercepts requests to Supabase endpoint and injects proper headers."""

    def __init__(self, url, data=None, headers={}, *args, **kwargs):
        if isinstance(url, str) and SUPABASE_ENDPOINT and SUPABASE_ENDPOINT in url:
            headers = dict(headers)
            # Remove Neon-specific header
            headers.pop("Neon-Connection-String", None)
            # Add Supabase PostgREST headers
            if SUPABASE_KEY:
                headers["apikey"] = SUPABASE_KEY
                headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
            headers["Content-Profile"] = "spartan_ops"
            # Add Cloudflare Access headers
            if CF_ID:
                headers["CF-Access-Client-Id"] = CF_ID
            if CF_SECRET:
                headers["CF-Access-Client-Secret"] = CF_SECRET
        super().__init__(url, data, headers, *args, **kwargs)


urllib.request.Request = _SupabaseRequest

# Patch urlopen to normalize Supabase response format
_orig_urlopen = urllib.request.urlopen


def _patched_urlopen(req_or_url, *args, **kwargs):
    """Wraps Supabase flat-array responses into Neon-style {rows, fields} dicts."""
    resp = _orig_urlopen(req_or_url, *args, **kwargs)

    # Determine if this is a Supabase request
    url = ""
    if hasattr(req_or_url, "full_url"):
        url = req_or_url.full_url
    elif isinstance(req_or_url, str):
        url = req_or_url

    if SUPABASE_ENDPOINT and SUPABASE_ENDPOINT in url:
        _orig_read = resp.read
        _cache = [None]

        def _wrapped_read():
            if _cache[0] is not None:
                return _cache[0]
            raw = _orig_read()
            try:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, list):
                    # Supabase returns [{col: val}, ...] — wrap for Neon compat
                    wrapped = {
                        "rows": parsed,
                        "fields": [],
                        "rowCount": len(parsed),
                    }
                    _cache[0] = json.dumps(wrapped).encode("utf-8")
                    return _cache[0]
            except Exception:
                pass
            _cache[0] = raw
            return raw

        resp.read = _wrapped_read

    return resp


urllib.request.urlopen = _patched_urlopen

# --- Startup banner ---
print("=" * 60)
print("[SUPABASE PATCH] Compatibility layer active")
print(f"[SUPABASE PATCH] Endpoint: {SUPABASE_ENDPOINT}")
print(f"[SUPABASE PATCH] Service key: {'set' if SUPABASE_KEY else 'MISSING'}")
print(f"[SUPABASE PATCH] CF-Access: {'set' if CF_ID else 'MISSING'}")
print("=" * 60)

# --- Run main.py in __main__ context ---
# Using exec so the if __name__ == "__main__" block in main.py executes
_main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
with open(_main_path, "r") as f:
    _code = compile(f.read(), "main.py", "exec")
exec(_code)
