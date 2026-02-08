"""
Autonomous Service Manager - Handles 24/7 operation of revenue-generating services
with automated delivery, monitoring, and failover.
"""

import time
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self, execute_sql, log_action):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.services = {}
        self.last_health_check = datetime.utcnow()
        
    def register_service(self, service_id: str, config: Dict[str, Any]):
        """Register a new revenue-generating service"""
        self.services[service_id] = {
            'config': config,
            'status': 'idle',
            'last_check': datetime.utcnow(),
            'failures': 0
        }
        
    def start_service(self, service_id: str):
        """Start a registered service"""
        if service_id not in self.services:
            raise ValueError(f"Service {service_id} not registered")
            
        service = self.services[service_id]
        service['status'] = 'starting'
        
        try:
            # Start service in background
            self.executor.submit(self._run_service, service_id)
            service['status'] = 'running'
            self.log_action(
                "service.started",
                f"Service {service_id} started successfully",
                level="info"
            )
        except Exception as e:
            service['status'] = 'failed'
            service['failures'] += 1
            self.log_action(
                "service.start_failed",
                f"Failed to start service {service_id}: {str(e)}",
                level="error"
            )
            
    def _run_service(self, service_id: str):
        """Main service execution loop"""
        service = self.services[service_id]
        config = service['config']
        
        while service['status'] == 'running':
            try:
                # Execute service logic
                self._process_transactions(service_id)
                self._check_health(service_id)
                
                # Sleep based on service interval
                time.sleep(config.get('interval_seconds', 60))
                
            except Exception as e:
                service['failures'] += 1
                self.log_action(
                    "service.error",
                    f"Service {service_id} encountered error: {str(e)}",
                    level="error"
                )
                if service['failures'] > config.get('max_failures', 3):
                    service['status'] = 'failed'
                    self.log_action(
                        "service.failed",
                        f"Service {service_id} failed after {service['failures']} attempts",
                        level="critical"
                    )
                    break
                
    def _process_transactions(self, service_id: str):
        """Process pending transactions for a service"""
        try:
            # Get pending transactions
            res = self.execute_sql(
                f"""
                SELECT * FROM transactions
                WHERE service_id = '{service_id}'
                AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT 100
                """
            )
            transactions = res.get('rows', [])
            
            # Process each transaction
            for tx in transactions:
                self._handle_transaction(tx)
                
        except Exception as e:
            self.log_action(
                "transaction.processing_error",
                f"Failed to process transactions for {service_id}: {str(e)}",
                level="error"
            )
            
    def _handle_transaction(self, transaction: Dict[str, Any]):
        """Handle an individual transaction"""
        tx_id = transaction.get('id')
        try:
            # Process transaction logic
            # Update transaction status
            self.execute_sql(
                f"""
                UPDATE transactions
                SET status = 'completed',
                    processed_at = NOW()
                WHERE id = '{tx_id}'
                """
            )
            self.log_action(
                "transaction.processed",
                f"Transaction {tx_id} processed successfully",
                level="info"
            )
        except Exception as e:
            self.execute_sql(
                f"""
                UPDATE transactions
                SET status = 'failed',
                    error = '{str(e)[:200]}'
                WHERE id = '{tx_id}'
                """
            )
            self.log_action(
                "transaction.failed",
                f"Transaction {tx_id} failed: {str(e)}",
                level="error"
            )
            
    def _check_health(self, service_id: str):
        """Perform health check for a service"""
        service = self.services[service_id]
        service['last_check'] = datetime.utcnow()
        
        # Check service metrics
        try:
            res = self.execute_sql(
                f"""
                SELECT COUNT(*) as pending_count
                FROM transactions
                WHERE service_id = '{service_id}'
                AND status = 'pending'
                """
            )
            pending = res.get('rows', [{}])[0].get('pending_count', 0)
            
            if pending > service['config'].get('max_pending', 100):
                self.log_action(
                    "service.health_warning",
                    f"Service {service_id} has {pending} pending transactions",
                    level="warning"
                )
                
        except Exception as e:
            self.log_action(
                "service.health_check_failed",
                f"Health check failed for {service_id}: {str(e)}",
                level="error"
            )
            
    def monitor_services(self):
        """Monitor all registered services"""
        while True:
            try:
                for service_id, service in self.services.items():
                    # Check for stalled services
                    last_check = service.get('last_check', datetime.utcnow())
                    if datetime.utcnow() - last_check > timedelta(minutes=5):
                        self.log_action(
                            "service.stalled",
                            f"Service {service_id} appears stalled - restarting",
                            level="warning"
                        )
                        self.start_service(service_id)
                        
                time.sleep(60)
                
            except Exception as e:
                self.log_action(
                    "monitoring.error",
                    f"Service monitoring failed: {str(e)}",
                    level="error"
                )
                time.sleep(60)
