from typing import Dict, Any
import hmac
import hashlib
import os

def authenticate_request(query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Authenticate API requests using HMAC signature."""
    api_key = query_params.get("api_key", "")
    timestamp = query_params.get("timestamp", "")
    signature = query_params.get("signature", "")
    
    if not api_key or not timestamp or not signature:
        return {"authenticated": False, "error": "Missing auth parameters"}
    
    # Verify timestamp is recent
    try:
        import time
        if abs(int(time.time()) - int(timestamp)) > 300:  # 5 minute window
            return {"authenticated": False, "error": "Expired timestamp"}
    except:
        return {"authenticated": False, "error": "Invalid timestamp"}
    
    # Verify signature
    secret_key = os.getenv("API_SECRET_KEY")
    if not secret_key:
        return {"authenticated": False, "error": "Missing server configuration"}
    
    expected_signature = hmac.new(
        secret_key.encode(),
        f"{api_key}{timestamp}".encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, signature):
        return {"authenticated": False, "error": "Invalid signature"}
    
    return {"authenticated": True}
