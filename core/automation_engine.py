"""
Core automation engine for autonomous revenue system.
Handles payment processing, self-healing, and monitoring.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List

class AutomationEngine:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.last_check = datetime.utcnow()
        self.health_checks = []
        self.payment_processors = []
        
    def add_payment_processor(self, processor: 'PaymentProcessor'):
        """Register a payment processor"""
        self.payment_processors.append(processor)
        
    def add_health_check(self, check: Callable[[], Dict[str, Any]]):
        """Register a health check"""
        self.health_checks.append(check)
        
    def process_payments(self) -> Dict[str, Any]:
        """Process pending payments through all registered processors"""
        results = []
        try:
            # Get pending payments
            res = self.execute_sql("""
                SELECT id, amount_cents, currency, metadata 
                FROM payments 
                WHERE status = 'pending'
                LIMIT 100
            """)
            payments = res.get("rows", [])
            
            for payment in payments:
                for processor in self.payment_processors:
                    try:
                        result = processor.process_payment(payment)
                        if result.get("success"):
                            # Update payment status
                            self.execute_sql(f"""
                                UPDATE payments 
                                SET status = 'processed',
                                    processed_at = NOW(),
                                    processor = '{processor.name}'
                                WHERE id = '{payment['id']}'
                            """)
                            results.append(result)
                            break
                    except Exception as e:
                        self.log_action(
                            "payment.process_failed",
                            f"Payment processing failed: {str(e)}",
                            level="error",
                            error_data={"payment_id": payment['id'], "error": str(e)}
                        )
                        
            return {"success": True, "processed": len(results)}
            
        except Exception as e:
            self.log_action(
                "payment.processing_error",
                f"Payment processing error: {str(e)}",
                level="error"
            )
            return {"success": False, "error": str(e)}
            
    def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = []
        for check in self.health_checks:
            try:
                result = check()
                results.append(result)
                if not result.get("success"):
                    self.attempt_self_healing(result)
            except Exception as e:
                self.log_action(
                    "health_check.failed",
                    f"Health check failed: {str(e)}",
                    level="error"
                )
                
        return {"success": True, "results": results}
        
    def attempt_self_healing(self, health_result: Dict[str, Any]) -> bool:
        """Attempt to automatically fix detected issues"""
        try:
            # Example self-healing logic
            if health_result.get("issue") == "database_connection":
                self.execute_sql("SELECT 1")  # Test connection
                return True
                
            return False
        except Exception as e:
            self.log_action(
                "self_healing.failed",
                f"Self-healing attempt failed: {str(e)}",
                level="error"
            )
            return False
            
    def monitor_system(self) -> Dict[str, Any]:
        """Collect system metrics and status"""
        try:
            # Get basic system stats
            res = self.execute_sql("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_payments,
                    COUNT(*) FILTER (WHERE status = 'processed') as processed_payments,
                    SUM(amount_cents) FILTER (WHERE status = 'processed') as total_revenue
                FROM payments
            """)
            stats = res.get("rows", [{}])[0]
            
            return {
                "success": True,
                "stats": stats,
                "last_check": self.last_check.isoformat(),
                "uptime": (datetime.utcnow() - self.last_check).total_seconds()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def run_cycle(self) -> Dict[str, Any]:
        """Run one automation cycle"""
        try:
            self.last_check = datetime.utcnow()
            
            # Process payments
            payment_result = self.process_payments()
            
            # Run health checks
            health_result = self.run_health_checks()
            
            # Monitor system
            monitor_result = self.monitor_system()
            
            return {
                "success": True,
                "payments": payment_result,
                "health": health_result,
                "monitoring": monitor_result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class PaymentProcessor:
    """Base class for payment processors"""
    def __init__(self, name: str):
        self.name = name
        
    def process_payment(self, payment: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single payment"""
        raise NotImplementedError

class StripeProcessor(PaymentProcessor):
    """Stripe payment processor implementation"""
    def __init__(self):
        super().__init__("stripe")
        
    def process_payment(self, payment: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through Stripe"""
        # Implement Stripe API integration here
        return {"success": True, "processor": self.name}

# Example health checks
def database_health_check(execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        execute_sql("SELECT 1")
        return {"success": True}
    except Exception as e:
        return {"success": False, "issue": "database_connection", "error": str(e)}
