"""
Core billing and payment processing automation.
Handles subscriptions, usage-based billing, invoicing and payment reconciliation.
"""
import datetime
from enum import Enum
from typing import Dict, List, Optional
import json
import uuid
import logging

from dataclasses import dataclass


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class InvoiceLineItem:
    description: str
    amount_cents: int
    quantity: int = 1
    tax_rate: float = 0.0
    metadata: Optional[Dict] = None


class BillingManager:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.logger = logging.getLogger("billing")
    
    def create_subscription(self, customer_id: str, plan_id: str, billing_cycle: BillingCycle) -> Dict:
        """Create a new subscription for a customer"""
        sub_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Calculate billing dates
        if billing_cycle == BillingCycle.MONTHLY:
            next_billing_date = now + datetime.timedelta(days=30)
        elif billing_cycle == BillingCycle.QUARTERLY:
            next_billing_date = now + datetime.timedelta(days=90)
        else: # annual
            next_billing_date = now + datetime.timedelta(days=365)

        try:
            self.execute_sql(
                f"""
                INSERT INTO subscriptions (
                    id, customer_id, plan_id, status, 
                    billing_cycle, next_billing_date,
                    created_at, updated_at
                ) VALUES (
                    '{sub_id}', '{customer_id}', '{plan_id}', 'active',
                    '{billing_cycle.value}', '{next_billing_date.isoformat()}',
                    NOW(), NOW()
                )
                """
            )
            return {"success": True, "subscription_id": sub_id}
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_invoice(self, subscription_id: str) -> Dict:
        """Generate an invoice for a subscription"""
        # Get subscription details
        sub = self.execute_sql(
            f"SELECT * FROM subscriptions WHERE id = '{subscription_id}'"
        )
        if not sub.get("rows"):
            return {"success": False, "error": "Subscription not found"}

        # Generate invoice number
        invoice_number = f"INV-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        
        try:
            # Create invoice
            invoice_id = str(uuid.uuid4())
            self.execute_sql(
                f"""
                INSERT INTO invoices (
                    id, subscription_id, invoice_number, 
                    status, amount_due_cents,
                    due_date, created_at
                ) VALUES (
                    '{invoice_id}', '{subscription_id}', '{invoice_number}',
                    'pending', 0, 
                    NOW() + INTERVAL '14 days', NOW()
                )
                """
            )
            return {"success": True, "invoice_id": invoice_id}
        except Exception as e:
            self.logger.error(f"Failed to generate invoice: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def process_payment(
        self, 
        invoice_id: str, 
        payment_method_id: str
    ) -> Dict:
        """Process payment for an invoice"""
        # Validate transaction
        fraud_check = self._check_fraud_risk(invoice_id)
        if not fraud_check.get("approved", True):
            return {
                "success": False,
                "error": "Payment blocked by fraud detection",
                "fraud_risk": fraud_check.get("risk_score")
            }
        
        # Process payment
        try:
            payment_id = str(uuid.uuid4())
            self.execute_sql(
                f"""
                INSERT INTO payments (
                    id, invoice_id, payment_method_id,
                    status, amount_cents, processed_at
                ) VALUES (
                    '{payment_id}', '{invoice_id}', '{payment_method_id}',
                    'pending', 0, NOW()
                )
                """
            )
            
            # Update invoice status
            self.execute_sql(
                f"""
                UPDATE invoices 
                SET status = 'paid',
                    paid_at = NOW()
                WHERE id = '{invoice_id}'
                """
            )
            
            return {"success": True, "payment_id": payment_id}
        except Exception as e:
            self.logger.error(f"Payment processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _check_fraud_risk(self, invoice_id: str) -> Dict:
        """Check transaction for fraud risk"""
        # Implement fraud detection rules:
        # - Compare to customer's usual patterns
        # - Check for suspicious metadata
        # - Verify payment method
        invoice = self.execute_sql(
            f"SELECT * FROM invoices WHERE id = '{invoice_id}'"
        ).get("rows", [{}])[0]
        
        # Basic checks - real implementation would integrate with fraud service
        risk_score = 0.0
        
        return {
            "approved": True,
            "risk_score": risk_score
        }


class UsageMeter:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
    
    def record_usage(self, customer_id: str, metric_name: str, units: float) -> Dict:
        """Record usage data for metered billing"""
        try:
            usage_id = str(uuid.uuid4())
            self.execute_sql(
                f"""
                INSERT INTO usage_records (
                    id, customer_id, metric_name,
                    units, recorded_at
                ) VALUES (
                    '{usage_id}', '{customer_id}', '{metric_name}',
                    {units}, NOW()
                )
                """
            )
            return {"success": True, "usage_id": usage_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def calculate_usage_charges(self, customer_id: str) -> List[Dict]:
        """Calculate charges for usage-based metrics"""
        # Query for unbilled usage grouped by metric
        sql = f"""
        SELECT metric_name, SUM(units) as total_units
        FROM usage_records
        WHERE customer_id = '{customer_id}'
        AND billed = FALSE
        GROUP BY metric_name
        """
        result = self.execute_sql(sql)
        
        charges = []
        for row in result.get("rows", []):
            # Get pricing from pricing tables - simplified here
            pricing = self._get_pricing(row['metric_name'])
            amount = round(row['total_units'] * pricing['price_per_unit'], 2)
            
            charges.append({
                "metric": row['metric_name'],
                "units": row['total_units'],
                "amount_cents": int(amount * 100)
            })
        
        return charges
    
    def _get_pricing(self, metric_name: str) -> Dict:
        """Get pricing for a usage metric (mock implementation)"""
        # In real system this would query pricing tables
        return {
            "metric_name": metric_name,
            "price_per_unit": 0.10,  # $0.10 per unit
            "billing_unit": "each"
        }
