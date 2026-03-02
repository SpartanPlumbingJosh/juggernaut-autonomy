import logging
from datetime import datetime
from typing import Dict, Any
from core.database import query_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def log_event(event_type: str, data: Dict[str, Any]) -> None:
    """Log system event"""
    try:
        await query_db(
            f"""
            INSERT INTO system_logs (event_type, data, created_at)
            VALUES ('{event_type}', '{json.dumps(data)}', NOW())
            """
        )
        logger.info(f"Logged {event_type} event")
    except Exception as e:
        logger.error(f"Failed to log event: {str(e)}")

async def monitor_system() -> Dict[str, Any]:
    """Check system health"""
    try:
        # Check database connection
        await query_db("SELECT 1")
        
        # Check recent errors
        res = await query_db(
            "SELECT COUNT(*) as error_count FROM system_logs WHERE event_type = 'error' AND created_at > NOW() - INTERVAL '1 hour'"
        )
        
        return {
            "success": True,
            "status": "healthy",
            "recent_errors": res["rows"][0]["error_count"]
        }
    except Exception as e:
        logger.error(f"System monitoring failed: {str(e)}")
        return {"success": False, "error": str(e)}
