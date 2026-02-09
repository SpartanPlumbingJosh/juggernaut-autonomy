from typing import Dict
from datetime import datetime
from core.database import query_db

class Monitoring:
    async def log_event(self, event_type: str, details: Dict) -> Dict:
        """Log a system event"""
        await query_db(f"""
            INSERT INTO monitoring_events (type, details, created_at)
            VALUES (
                '{event_type}',
                '{json.dumps(details)}',
                NOW()
            )
        """)
        return {"success": True}
        
    async def get_system_status(self) -> Dict:
        """Get overall system status"""
        result = await query_db("""
            SELECT 
                COUNT(*) as total_services,
                COUNT(*) FILTER (WHERE status = 'active') as active_services,
                COUNT(*) FILTER (WHERE status = 'suspended') as suspended_services,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_services,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as recent_services
            FROM services
        """)
        stats = result.get("rows", [{}])[0]
        
        return {
            "success": True,
            "stats": stats
        }
