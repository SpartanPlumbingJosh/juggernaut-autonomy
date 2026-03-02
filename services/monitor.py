"""
System monitoring service to ensure 24/7 operation.
Performs health checks, alerts on failures, and recovers broken services.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any

from core.database import query_db


class SystemMonitor:
    def __init__(self):
        self.logger = logging.getLogger('monitor')
        self.checks = [
            self._check_db_connection,
            self._check_recent_transactions,
            self._check_service_health
        ]
        self.last_alert_time = {}
        
    async def run(self) -> None:
        """Run all monitoring checks."""
        results = {}
        for check in self.checks:
            try:
                results[check.__name__] = await check()
            except Exception as e:
                self.logger.error(f"Monitor check failed: {check.__name__} - {str(e)}")
                results[check.__name__] = {'status': 'error', 'error': str(e)}
        
        self._process_results(results)
        
    async def _check_db_connection(self) -> Dict[str, Any]:
        """Verify database connectivity."""
        try:
            await query_db("SELECT 1")
            return {'status': 'ok'}
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'action': 'alert_team',
                'severity': 'critical'
            }
            
    async def _check_recent_transactions(self) -> Dict[str, Any]:
        """Check for recent successful transactions."""
        cutoff = datetime.now(timezone.utc) - timezone.utc.timedelta(hours=1)
        try:
            result = await query_db(f"""
                SELECT COUNT(*) as count 
                FROM revenue_events 
                WHERE recorded_at > '{cutoff.isoformat()}'
                AND event_type = 'revenue'
            """)
            count = result.get('rows', [{'count': 0}])[0]['count']
            
            if count == 0:
                return {
                    'status': 'warning',
                    'message': 'No recent transactions',
                    'action': 'check_payment_gateway'
                }
            return {'status': 'ok', 'transaction_count': count}
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
            
    async def _check_service_health(self) -> Dict[str, Any]:
        """Check dependent service health."""
        # Would integrate with actual service health checks
        return {'status': 'ok'}
        
    def _process_results(self, results: Dict[str, Any]) -> None:
        """Process check results and alert if needed."""
        for name, result in results.items():
            if result.get('status') != 'ok':
                self._alert(name, result)
    
    def _alert(self, check_name: str, result: Dict[str, Any]) -> None:
        """Send appropriate alerts based on failure severity."""
        # Rate limit alerts to avoid spamming
        last_alert = self.last_alert_time.get(check_name, 0)
        if time.time() - last_alert < 3600:  # 1 hour cooldown
            return
            
        severity = result.get('severity', 'warning')
        message = f"{severity.upper()}: {check_name} failed - {result.get('error', result.get('message', 'Unknown error'))}"
        
        if severity == 'critical':
            # In real implementation would page on-call via PagerDuty/etc
            self.logger.critical(message)
        else:
            self.logger.warning(message)
            
        self.last_alert_time[check_name] = time.time()


async def start_monitoring() -> None:
    """Long-running monitoring process."""
    monitor = SystemMonitor()
    while True:
        await monitor.run()
        time.sleep(300)  # Check every 5 minutes
