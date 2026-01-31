"""File Upload API

Lightweight upload endpoint for spartan-hq Neural Chat attachments.

Endpoints:
    POST /api/files/upload

Contract:
    Request JSON:
        {
          "filename": "...",
          "content_base64": "...",
          "content_type": "..."  // optional
        }

    Response JSON:
        {
          "success": true,
          "file": {
            "id": "uuid",
            "filename": "...",
            "content_type": "...",
            "size_bytes": 123,
            "extracted_text": "...",
            "truncated": false
          }
        }

Authentication:
    Requires MCP_AUTH_TOKEN or INTERNAL_API_SECRET in query params or Authorization header.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import tempfile
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 250_000

ALLOWED_EXTENSIONS = {"txt", "md", "csv", "json", "pdf"}


def _make_response(
    status_code: int,
    body: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    headers = {**CORS_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status_code,
        "headers": {**headers, "Content-Type": "application/json"},
        "body": body,
    }


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    return _make_response(status_code, {"success": False, "error": message})


def _validate_auth(params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> tuple[bool, Optional[str]]:
    headers = headers or {}

    token = None
    for key in ("token", "auth", "api_key", "key"):
        if params.get(key):
            token = params.get(key)
            break

    if not token:
        auth = headers.get("Authorization") or headers.get("authorization")
        if auth and isinstance(auth, str) and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()

    token = (token or "").strip()
    if not token:
        return False, "Missing authentication token"

    allowed = {(MCP_AUTH_TOKEN or "").strip(), (INTERNAL_API_SECRET or "").strip()}
    allowed = {x for x in allowed if x}

    if not allowed:
        return False, "No server auth tokens configured"

    if token not in allowed:
        return False, "Invalid authentication token"

    return True, None


def _guess_ext(filename: str) -> str:
    name = (filename or "").strip().lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _store_temp_file(file_id: str, filename: str, raw: bytes) -> Optional[str]:
    try:
        base_dir = (os.getenv("FILE_UPLOAD_DIR") or "").strip()
        if not base_dir:
            base_dir = os.path.join(tempfile.gettempdir(), "juggernaut_uploads")
        os.makedirs(base_dir, exist_ok=True)

        safe_name = filename.replace("/", "_").replace("\\", "_")
        path = os.path.join(base_dir, f"{file_id}__{safe_name}")
        with open(path, "wb") as f:
            f.write(raw)
        return path
    except Exception:
        return None


def _extract_text_from_pdf(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    parts = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt:
            parts.append(txt)
    return "\n\n".join(parts).strip()


def _extract_text(filename: str, content_type: str, raw: bytes) -> str:
    ext = _guess_ext(filename)

    if ext == "pdf" or (content_type or "").lower() == "application/pdf":
        return _extract_text_from_pdf(raw)

    if ext == "json" or (content_type or "").lower() in ("application/json", "text/json"):
        decoded = raw.decode("utf-8", "replace")
        try:
            obj = json.loads(decoded)
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            return decoded

    return raw.decode("utf-8", "replace")


def upload_file(body: Dict[str, Any], params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    ok, err = _validate_auth(params, headers)
    if not ok:
        return _error_response(401, err or "Unauthorized")

    filename = str(body.get("filename") or "").strip()
    content_base64 = str(body.get("content_base64") or "").strip()
    content_type = str(body.get("content_type") or "").strip()

    if not filename:
        return _error_response(400, "Missing filename")
    if not content_base64:
        return _error_response(400, "Missing content_base64")

    ext = _guess_ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        return _error_response(415, f"Unsupported file type: {ext or 'unknown'}")

    try:
        raw = base64.b64decode(content_base64, validate=False)
    except Exception:
        return _error_response(400, "Invalid base64 payload")

    if len(raw) > MAX_UPLOAD_BYTES:
        return _error_response(413, f"File too large (max {MAX_UPLOAD_BYTES} bytes)")

    file_id = str(uuid4())
    stored_path = _store_temp_file(file_id, filename, raw)
    if stored_path:
        logger.info("files.upload.stored id=%s path=%s", file_id, stored_path)

    try:
        extracted = _extract_text(filename, content_type, raw)
    except Exception as e:
        logger.exception("files.upload.extract_failed id=%s", file_id)
        return _error_response(422, f"Failed to extract text: {e}")

    truncated = False
    if len(extracted) > MAX_EXTRACTED_CHARS:
        extracted = extracted[:MAX_EXTRACTED_CHARS]
        truncated = True

    return _make_response(
        200,
        {
            "success": True,
            "file": {
                "id": file_id,
                "filename": filename,
                "content_type": content_type or "",
                "size_bytes": len(raw),
                "extracted_text": extracted,
                "truncated": truncated,
            },
        },
    )


def handle_files_request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    params = params or {}
    body = body or {}
    headers = headers or {}

    if method == "OPTIONS":
        return _make_response(200, {"success": True})

    path = (path or "").strip("/")
    segments = path.split("/") if path else []

    if len(segments) == 1 and segments[0] == "upload":
        if method == "POST":
            return upload_file(body, params, headers)
        return _error_response(405, f"Method {method} not allowed")

    return _error_response(404, f"Unknown endpoint: {path}")
