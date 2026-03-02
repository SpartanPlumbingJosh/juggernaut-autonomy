from typing import Dict
from datetime import datetime, timedelta
from core.database import query_db

class FraudDetector:
    """Detects and prevents fraudulent transactions."""
    
    async def check_fraud(self, customer_id: str, payment_data: Dict) -> Dict:
        """Run fraud detection checks."""
        try:
            # Check for suspicious activity patterns
            recent_payments = await query_db(
                f"""
                SELECT COUNT(*) as payment_count
                FROM payment_events
                WHERE customer_id = '{customer_id}'
                  AND created_at >= NOW() - INTERVAL '1 hour'
                """
            )
            payment_count = recent_payments.get("rows", [{}])[0].get("payment_count", 0)
            
            if payment_count > 5:  # More than 5 payments in last hour
                return {"fraud": True, "reason": "Too many recent payments"}
                
            # Check IP address reputation
            ip_reputation = await self._check_ip_reputation(payment_data.get("ip_address"))
            if ip_reputation.get("risk_score", 0) > 0.8:
                return {"fraud": True, "reason": "High risk IP address"}
                
            return {"fraud": False}
        except Exception as e:
            return {"fraud": False, "error": str(e)}
            
    async def _check_ip_reputation(self, ip_address: str) -> Dict:
        """Check IP address reputation using external service."""
        # Placeholder for actual IP reputation check
        return {"risk_score": 0.0}
