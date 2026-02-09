"""
Autonomous Revenue Capture System

Handles automated transaction processing, reconciliation, and reporting.
Integrates with payment processors and exchange APIs.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class RevenueCaptureSystem:
    """Autonomous revenue capture and processing system."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], config: Dict[str, Any]):
        """
        Initialize revenue capture system.
        
        Args:
            execute_sql: Function to execute SQL queries
            config: System configuration including API keys, thresholds, etc.
        """
        self.execute_sql = execute_sql
        self.config = config
        self.payment_processors = self._initialize_payment_processors()
        
    def _initialize_payment_processors(self) -> Dict[str, Any]:
        """Initialize configured payment processors."""
        processors = {}
        for processor_config in self.config.get("payment_processors", []):
            try:
                if processor_config["type"] == "stripe":
                    import stripe
                    stripe.api_key = processor_config["api_key"]
                    processors["stripe"] = stripe
                elif processor_config["type"] == "paypal":
                    from paypalrestsdk import configure
                    configure({
                        "mode": processor_config["mode"],
                        "client_id": processor_config["client_id"],
                        "client_secret": processor_config["client_secret"]
                    })
                    processors["paypal"] = True
                # Add other processors as needed
            except Exception as e:
                logger.error(f"Failed to initialize {processor_config['type']}: {str(e)}")
        return processors
    
    async def capture_pending_transactions(self) -> Dict[str, Any]:
        """Capture pending transactions from payment processors."""
        captured = 0
        errors = []
        
        # Process Stripe payments
        if "stripe" in self.payment_processors:
            try:
                stripe = self.payment_processors["stripe"]
                payments = stripe.PaymentIntent.list(limit=100)
                for payment in payments.auto_paging_iter():
                    if payment.status == "succeeded":
                        result = self._process_stripe_payment(payment)
                        if result["success"]:
                            captured += 1
                        else:
                            errors.append(result["error"])
            except Exception as e:
                logger.error(f"Stripe capture failed: {str(e)}")
                errors.append(f"Stripe error: {str(e)}")
        
        # Process PayPal payments
        if "paypal" in self.payment_processors:
            try:
                from paypalrestsdk import Payment
                payments = Payment.all({"count": 100})
                for payment in payments.payments:
                    if payment.state == "approved":
                        result = self._process_paypal_payment(payment)
                        if result["success"]:
                            captured += 1
                        else:
                            errors.append(result["error"])
            except Exception as e:
                logger.error(f"PayPal capture failed: {str(e)}")
                errors.append(f"PayPal error: {str(e)}")
        
        return {
            "success": True,
            "captured": captured,
            "errors": errors
        }
    
    def _process_stripe_payment(self, payment: Any) -> Dict[str, Any]:
        """Process a Stripe payment and record it in the database."""
        try:
            # Convert amount from cents to dollars
            amount_cents = payment.amount
            currency = payment.currency.upper()
            
            # Record transaction
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency}',
                    'stripe',
                    '{json.dumps(payment)}',
                    NOW(),
                    NOW()
                )
            """)
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to process Stripe payment: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _process_paypal_payment(self, payment: Any) -> Dict[str, Any]:
        """Process a PayPal payment and record it in the database."""
        try:
            # Convert amount to cents
            amount_cents = int(float(payment.transactions[0].amount.total) * 100)
            currency = payment.transactions[0].amount.currency.upper()
            
            # Record transaction
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {amount_cents},
                    '{currency}',
                    'paypal',
                    '{json.dumps(payment)}',
                    NOW(),
                    NOW()
                )
            """)
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to process PayPal payment: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def reconcile_transactions(self) -> Dict[str, Any]:
        """Reconcile recorded transactions with payment processors."""
        reconciled = 0
        errors = []
        
        # Get recent transactions from database
        try:
            result = self.execute_sql("""
                SELECT id, source, metadata
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '7 days'
                ORDER BY recorded_at DESC
                LIMIT 1000
            """)
            transactions = result.get("rows", [])
        except Exception as e:
            logger.error(f"Failed to fetch transactions: {str(e)}")
            return {"success": False, "error": str(e)}
        
        # Reconcile each transaction
        for transaction in transactions:
            try:
                source = transaction["source"]
                metadata = json.loads(transaction["metadata"])
                
                if source == "stripe":
                    payment = self.payment_processors["stripe"].PaymentIntent.retrieve(metadata["id"])
                    if payment.status != "succeeded":
                        self._mark_transaction_failed(transaction["id"])
                elif source == "paypal":
                    from paypalrestsdk import Payment
                    payment = Payment.find(metadata["id"])
                    if payment.state != "approved":
                        self._mark_transaction_failed(transaction["id"])
                
                reconciled += 1
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Reconciliation failed for transaction {transaction['id']}: {str(e)}")
        
        return {
            "success": True,
            "reconciled": reconciled,
            "errors": errors
        }
    
    def _mark_transaction_failed(self, transaction_id: str) -> None:
        """Mark a transaction as failed in the database."""
        try:
            self.execute_sql(f"""
                UPDATE revenue_events
                SET status = 'failed',
                    updated_at = NOW()
                WHERE id = '{transaction_id}'
            """)
        except Exception as e:
            logger.error(f"Failed to mark transaction {transaction_id} as failed: {str(e)}")
    
    async def generate_revenue_report(self) -> Dict[str, Any]:
        """Generate daily revenue report."""
        try:
            result = self.execute_sql("""
                SELECT 
                    DATE(recorded_at) as date,
                    SUM(amount_cents) FILTER (WHERE event_type = 'revenue') as revenue_cents,
                    SUM(amount_cents) FILTER (WHERE event_type = 'cost') as cost_cents,
                    COUNT(*) FILTER (WHERE event_type = 'revenue') as transaction_count
                FROM revenue_events
                WHERE recorded_at >= NOW() - INTERVAL '1 day'
                GROUP BY DATE(recorded_at)
            """)
            
            report = result.get("rows", [{}])[0]
            return {
                "success": True,
                "report": {
                    "date": report.get("date"),
                    "revenue_cents": report.get("revenue_cents", 0),
                    "cost_cents": report.get("cost_cents", 0),
                    "transaction_count": report.get("transaction_count", 0)
                }
            }
        except Exception as e:
            logger.error(f"Failed to generate revenue report: {str(e)}")
            return {"success": False, "error": str(e)}
