from typing import Dict, Any
import os
import requests
import json
from datetime import datetime

def track_event(event_name: str, properties: Dict[str, Any]):
    """Track analytics events."""
    try:
        # Send to internal analytics
        event_data = {
            "event": event_name,
            "properties": properties,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Optionally send to external analytics provider
        if os.getenv("ANALYTICS_ENABLED", "false").lower() == "true":
            requests.post(
                os.getenv("ANALYTICS_ENDPOINT"),
                json=event_data,
                timeout=2
            )
    except:
        pass
