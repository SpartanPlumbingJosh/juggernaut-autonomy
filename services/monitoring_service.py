"""
Revenue-critical monitoring and alerting service.
"""
import logging
from typing import Dict

from core.database import query_db

class MonitoringService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.critical_thresholds = {
            'failed_payments': 5,
            'onboarding_failures': 3,
            'revenue_drop': 0.3  # 30% drop
        }

    async def check_revenue_health(self) -> Dict:
        """Check all revenue-critical metrics"""
        try:
            results = {}
            
            # Check failed payments
            payment_result = await query_db(
                "SELECT COUNT(*) as count FROM payments WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 hour'"
            )
            failed_payments = payment_result.get("rows", [{}])[0].get("count", 0)
            results['failed_payments'] = failed_payments

            # Check onboarding failures
            onboarding_result = await query_db(
                "SELECT COUNT(*) as count FROM onboarding_attempts WHERE success = false AND created_at > NOW() - INTERVAL '1 hour'"
            )
            failed_onboardings = onboarding_result.get("rows", [{}])[0].get("count", 0)
            results['failed_onboardings'] = failed_onboardings

            # Check revenue drop
            revenue_result = await query_db(
                """
                SELECT 
                    (SELECT SUM(amount_cents) FROM revenue_events 
                     WHERE recorded_at > NOW() - INTERVAL '1 hour' AND event_type = 'revenue') as current,
                    (SELECT SUM(amount_cents) FROM revenue_events 
                     WHERE recorded_at > NOW() - INTERVAL '2 hour' AND recorded_at < NOW() - INTERVAL '1 hour' 
                     AND event_type = 'revenue') as previous
                """
            )
            current = revenue_result.get("rows", [{}])[0].get("current", 0) or 1
            previous = revenue_result.get("rows", [{}])[0].get("previous", 1) or 1
            drop_pct = (previous - current) / previous
            results['revenue_drop_pct'] = drop_pct

            # Trigger alerts if thresholds breached
            alerts = []
            if failed_payments > self.critical_thresholds['failed_payments']:
                alerts.append("High failed payment rate")
            if failed_onboardings > self.critical_thresholds['onboarding_failures']:
                alerts.append("High onboarding failure rate")
            if drop_pct > self.critical_thresholds['revenue_drop']:
                alerts.append(f"Revenue dropped by {drop_pct*100:.1f}%")

            if alerts:
                # TODO: Send actual alerts (Slack, PagerDuty, etc.)
                self.logger.error("CRITICAL ALERTS: " + ", ".join(alerts))

            return {
                "success": True,
                "metrics": results,
                "alerts": alerts
            }

        except Exception as e:
            self.logger.error(f"Monitoring failed: {str(e)}")
            return {"success": False, "error": str(e)}
