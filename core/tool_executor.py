"""
JUGGERNAUT Tool Executor
========================
Provides real execution capabilities for AI-driven tasks.

Tools are defined as OpenAI-compatible function schemas and executed safely
with sandboxing, timeouts, and audit logging.

Tools available:
  - read_file: Read file contents
  - write_file: Write/create files
  - patch_file: Apply find-and-replace edits to files
  - list_directory: List directory contents
  - search_files: Grep/search across files
  - run_command: Execute shell commands (sandboxed)
  - execute_sql_readonly: Run read-only SQL queries
  - http_get: Fetch a URL
"""

import ipaddress
import json
import logging
import os
import socket
import subprocess
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Sandbox root — all file operations are restricted to this directory tree.
# Defaults to /app (Railway container) or current working directory.
SANDBOX_ROOT = os.getenv("TOOL_SANDBOX_ROOT", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/app"))

# Shell command limits
COMMAND_TIMEOUT_SECONDS = int(os.getenv("TOOL_COMMAND_TIMEOUT", "30"))
COMMAND_MAX_OUTPUT_BYTES = int(os.getenv("TOOL_COMMAND_MAX_OUTPUT", "32768"))

# Max file size for reads (256 KB default)
MAX_FILE_READ_BYTES = int(os.getenv("TOOL_MAX_FILE_READ", "262144"))

# Max file size for writes (128 KB default)
MAX_FILE_WRITE_BYTES = int(os.getenv("TOOL_MAX_FILE_WRITE", "131072"))

# Blocked commands (shell injection prevention)
_BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-rf\s+/",       # rm -rf /
    r"\bmkfs\b",             # filesystem format
    r"\bdd\s+if=",           # raw disk write
    r"\b:\(\)\s*\{",         # fork bomb
    r"\bcurl\b.*\|\s*bash",  # pipe to bash
    r"\bwget\b.*\|\s*bash",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bsystemctl\b",
    r"\bkill\s+-9\s+1\b",
]

# Allowed file extensions for write operations
_BLOCKED_WRITE_PATHS = [
    ".env",
    ".ssh",
    "id_rsa",
    "id_ed25519",
    ".git/config",
    ".git/hooks",
]


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _resolve_safe_path(file_path: str) -> Tuple[bool, str, str]:
    """
    Resolve a file path and verify it's within the sandbox.

    Returns:
        (is_safe, resolved_absolute_path, error_message)
    """
    try:
        sandbox = Path(SANDBOX_ROOT).resolve()
        target = (sandbox / file_path).resolve() if not os.path.isabs(file_path) else Path(file_path).resolve()

        # Use proper Path containment check (not string prefix which can be tricked)
        try:
            target.relative_to(sandbox)
        except ValueError:
            return False, "", f"Path escapes sandbox: {file_path} resolves outside {SANDBOX_ROOT}"

        for blocked in _BLOCKED_WRITE_PATHS:
            if blocked in str(target):
                return False, "", f"Path contains blocked segment: {blocked}"

        return True, str(target), ""
    except Exception as e:
        return False, "", f"Path resolution failed: {e}"


def _is_command_safe(command: str) -> Tuple[bool, str]:
    """Check if a shell command is safe to execute."""
    for pattern in _BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Command matches blocked pattern: {pattern}"
    return True, ""


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_read_file(file_path: str, offset: int = 0, limit: int = 0) -> Dict[str, Any]:
    """Read a file's contents."""
    safe, resolved, err = _resolve_safe_path(file_path)
    if not safe:
        return {"success": False, "error": err}

    if not os.path.isfile(resolved):
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        size = os.path.getsize(resolved)
        if size > MAX_FILE_READ_BYTES:
            return {"success": False, "error": f"File too large ({size} bytes, max {MAX_FILE_READ_BYTES})"}

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if offset > 0 or limit > 0:
            start = max(0, offset - 1)  # 1-indexed to 0-indexed
            end = start + limit if limit > 0 else len(lines)
            lines = lines[start:end]

        content = "".join(lines)
        return {"success": True, "content": content, "total_lines": len(lines), "file_path": resolved}
    except Exception as e:
        return {"success": False, "error": f"Read failed: {e}"}


def tool_write_file(file_path: str, content: str, create_dirs: bool = True) -> Dict[str, Any]:
    """Write content to a file (create or overwrite)."""
    safe, resolved, err = _resolve_safe_path(file_path)
    if not safe:
        return {"success": False, "error": err}

    if len(content.encode("utf-8")) > MAX_FILE_WRITE_BYTES:
        return {"success": False, "error": f"Content too large (max {MAX_FILE_WRITE_BYTES} bytes)"}

    try:
        if create_dirs:
            os.makedirs(os.path.dirname(resolved), exist_ok=True)

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("tool_write_file: wrote %d bytes to %s", len(content), resolved)
        return {"success": True, "file_path": resolved, "bytes_written": len(content)}
    except Exception as e:
        return {"success": False, "error": f"Write failed: {e}"}


def tool_patch_file(file_path: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """Apply a find-and-replace edit to a file."""
    safe, resolved, err = _resolve_safe_path(file_path)
    if not safe:
        return {"success": False, "error": err}

    if not os.path.isfile(resolved):
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()

        if len(original.encode("utf-8")) > MAX_FILE_READ_BYTES:
            return {"success": False, "error": f"File too large to patch (max {MAX_FILE_READ_BYTES} bytes)"}

        count = original.count(old_string)
        if count == 0:
            return {"success": False, "error": "old_string not found in file"}
        if count > 1:
            return {"success": False, "error": f"old_string found {count} times — must be unique. Provide more context."}

        updated = original.replace(old_string, new_string, 1)

        if len(updated.encode("utf-8")) > MAX_FILE_WRITE_BYTES:
            return {"success": False, "error": f"Patched file exceeds write limit ({MAX_FILE_WRITE_BYTES} bytes)"}

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(updated)

        logger.info("tool_patch_file: patched %s", resolved)
        return {"success": True, "file_path": resolved}
    except Exception as e:
        return {"success": False, "error": f"Patch failed: {e}"}


def tool_list_directory(directory: str = ".", max_depth: int = 2) -> Dict[str, Any]:
    """List directory contents."""
    safe, resolved, err = _resolve_safe_path(directory)
    if not safe:
        return {"success": False, "error": err}

    if not os.path.isdir(resolved):
        return {"success": False, "error": f"Not a directory: {directory}"}

    entries = []
    try:
        base = Path(resolved)
        for item in sorted(base.rglob("*")):
            rel = item.relative_to(base)
            depth = len(rel.parts)
            if depth > max_depth:
                continue
            # Skip hidden dirs / __pycache__ / node_modules
            if any(p.startswith(".") or p in ("__pycache__", "node_modules", ".git") for p in rel.parts):
                continue

            entry = {
                "path": str(rel),
                "type": "dir" if item.is_dir() else "file",
            }
            if item.is_file():
                entry["size"] = item.stat().st_size
            entries.append(entry)

            if len(entries) >= 200:
                break

        return {"success": True, "directory": resolved, "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"success": False, "error": f"List failed: {e}"}


def tool_search_files(
    pattern: str,
    directory: str = ".",
    file_glob: str = "",
    max_results: int = 30,
) -> Dict[str, Any]:
    """Search for a pattern across files using grep."""
    safe, resolved, err = _resolve_safe_path(directory)
    if not safe:
        return {"success": False, "error": err}

    try:
        cmd = ["grep", "-rn", "--include", file_glob or "*", "-m", str(max_results), pattern, resolved]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=resolved,
        )
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        # Strip sandbox root from output for readability
        cleaned = [line.replace(str(resolved), ".") for line in lines[:max_results]]
        return {"success": True, "matches": cleaned, "count": len(cleaned)}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Search timed out"}
    except FileNotFoundError:
        # grep not available, fall back to Python
        return _python_search(pattern, resolved, max_results)
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}


def _python_search(pattern: str, directory: str, max_results: int) -> Dict[str, Any]:
    """Fallback file search using Python when grep is unavailable."""
    matches = []
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
        for root, _dirs, files in os.walk(directory):
            # Skip hidden/cache dirs
            parts = Path(root).relative_to(directory).parts
            if any(p.startswith(".") or p in ("__pycache__", "node_modules") for p in parts):
                continue
            for fname in files:
                if len(matches) >= max_results:
                    break
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if compiled.search(line):
                                rel = os.path.relpath(fpath, directory)
                                matches.append(f"./{rel}:{i}:{line.rstrip()[:200]}")
                                if len(matches) >= max_results:
                                    break
                except (OSError, UnicodeDecodeError):
                    continue
        return {"success": True, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"success": False, "error": f"Python search failed: {e}"}


def tool_run_command(command: str, working_dir: str = "") -> Dict[str, Any]:
    """Execute a shell command within the sandbox."""
    safe_cmd, cmd_err = _is_command_safe(command)
    if not safe_cmd:
        return {"success": False, "error": cmd_err}

    cwd = SANDBOX_ROOT
    if working_dir:
        safe, resolved, err = _resolve_safe_path(working_dir)
        if not safe:
            return {"success": False, "error": err}
        cwd = resolved

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            cwd=cwd,
            env={**os.environ, "PAGER": "cat"},
        )

        stdout = result.stdout[:COMMAND_MAX_OUTPUT_BYTES] if result.stdout else ""
        stderr = result.stderr[:COMMAND_MAX_OUTPUT_BYTES] if result.stderr else ""

        logger.info("tool_run_command: exit=%d cmd='%s'", result.returncode, command[:100])

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {COMMAND_TIMEOUT_SECONDS}s"}
    except Exception as e:
        return {"success": False, "error": f"Command failed: {e}"}


def tool_execute_sql_readonly(query: str) -> Dict[str, Any]:
    """Execute a read-only SQL query."""
    stripped = query.strip()

    # Block stacked statements (semicolons)
    if ";" in stripped:
        return {"success": False, "error": "Multiple statements not allowed (no semicolons)"}

    # Allowlist of safe statement starters
    first_token = stripped.upper().split(None, 1)[0] if stripped else ""
    if first_token not in ("SELECT", "WITH", "EXPLAIN"):
        return {"success": False, "error": f"Only SELECT/WITH/EXPLAIN queries are allowed, got: {first_token}"}

    try:
        from core.database import query_db
        result = query_db(stripped)
        rows = result.get("rows", [])
        return {"success": True, "rows": rows[:100], "row_count": len(rows)}
    except Exception as e:
        return {"success": False, "error": f"SQL error: {e}"}


def _is_private_ip(host: str) -> Tuple[bool, str]:
    """Check if a hostname resolves to a private/loopback/link-local address (SSRF protection)."""
    try:
        addr_infos = socket.getaddrinfo(host, None)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                return True, f"Blocked request to private/loopback address: {ip_str}"
        return False, ""
    except socket.gaierror as e:
        return True, f"DNS resolution failed for {host}: {e}"


def tool_http_get(url: str) -> Dict[str, Any]:
    """Fetch content from a URL."""
    if not url.startswith(("http://", "https://")):
        return {"success": False, "error": "URL must start with http:// or https://"}

    # SSRF protection: resolve host and block private/loopback addresses
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host:
            is_private, reason = _is_private_ip(host)
            if is_private:
                return {"success": False, "error": reason}
    except Exception as e:
        return {"success": False, "error": f"URL validation failed: {e}"}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Juggernaut-Engine/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(MAX_FILE_READ_BYTES).decode("utf-8", errors="replace")
            return {
                "success": True,
                "status": resp.status,
                "content": body[:32768],
                "content_type": resp.headers.get("Content-Type", ""),
            }
    except Exception as e:
        return {"success": False, "error": f"HTTP request failed: {e}"}


# ---------------------------------------------------------------------------
# Tool registry — maps names to (function, OpenAI schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Returns the file content as a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file (relative to project root or absolute within sandbox)"},
                    "offset": {"type": "integer", "description": "1-indexed line number to start reading from (0 = start)", "default": 0},
                    "limit": {"type": "integer", "description": "Number of lines to read (0 = all)", "default": 0},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, creating it if it doesn't exist or overwriting if it does.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to write to"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Apply a find-and-replace edit to a file. The old_string must appear exactly once in the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file to edit"},
                    "old_string": {"type": "string", "description": "Exact text to find (must be unique in the file)"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                },
                "required": ["file_path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and subdirectories in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path (default: project root)", "default": "."},
                    "max_depth": {"type": "integer", "description": "Max depth to recurse (default: 2)", "default": 2},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for a regex pattern across files in a directory. Returns matching lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "directory": {"type": "string", "description": "Directory to search in (default: project root)", "default": "."},
                    "file_glob": {"type": "string", "description": "File glob filter, e.g. '*.py'", "default": ""},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command. Use for git, npm, pip, python, etc. Commands are sandboxed to the project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "working_dir": {"type": "string", "description": "Working directory (default: project root)", "default": ""},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql_readonly",
            "description": "Execute a read-only SQL query against the database. Only SELECT queries are allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL SELECT query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using AI-powered search. Returns search results with citations. Use this for research tasks, finding current information, or gathering data about businesses, markets, or technologies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to execute"},
                    "detailed": {"type": "boolean", "description": "If true, returns more detailed results (uses more tokens)", "default": False},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient. Use this for outreach, notifications, or communication tasks. The email will be sent from the system's configured email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body content (can be plain text or HTML)"},
                    "from_address": {"type": "string", "description": "Optional: override the from address (must be configured in system)"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


def tool_web_search(query: str, detailed: bool = False) -> Dict[str, Any]:
    """Execute web search via MCP server's Perplexity integration."""
    import json
    import urllib.request
    import urllib.error
    
    # Get MCP server URL from environment
    mcp_url = os.getenv("MCP_SERVER_URL", "")
    if not mcp_url:
        # Fallback: construct from Railway internal URL pattern
        mcp_url = "http://juggernaut-mcp.railway.internal:8080"
    
    try:
        req = urllib.request.Request(
            f"{mcp_url.rstrip('/')}/tools/web_search",
            data=json.dumps({"query": query, "detailed": detailed}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"success": True, "result": result}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"MCP server error: {e.code}"}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}


def tool_send_email(to: str, subject: str, body: str, from_address: str = None) -> Dict[str, Any]:
    """Send email via MCP server's email integration."""
    import json
    import urllib.request
    
    mcp_url = os.getenv("MCP_SERVER_URL", "http://juggernaut-mcp.railway.internal:8080")
    
    payload = {
        "to": to,
        "subject": subject,
        "body": body
    }
    if from_address:
        payload["from"] = from_address
    
    try:
        req = urllib.request.Request(
            f"{mcp_url.rstrip('/')}/tools/send_email",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": f"Email send failed: {e}"}


# Map tool names to their implementation functions
_TOOL_FUNCTIONS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "patch_file": tool_patch_file,
    "list_directory": tool_list_directory,
    "search_files": tool_search_files,
    "run_command": tool_run_command,
    "execute_sql_readonly": tool_execute_sql_readonly,
    "http_get": tool_http_get,
    "web_search": tool_web_search,
    "send_email": tool_send_email,
}


def execute_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single tool call by name with the given arguments.

    Args:
        name: Tool function name
        arguments: Dict of keyword arguments for the tool

    Returns:
        Tool result dict (always has 'success' key)
    """
    func = _TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"success": False, "error": f"Unknown tool: {name}"}

    try:
        return func(**arguments)
    except TypeError as e:
        return {"success": False, "error": f"Invalid arguments for {name}: {e}"}
    except Exception as e:
        logger.exception("Tool %s raised unexpected error", name)
        return {"success": False, "error": f"Tool execution error: {e}"}
