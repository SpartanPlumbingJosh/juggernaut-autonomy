"""
Payment Processor - Handle recurring subscriptions, usage-based billing, and one-time transactions.
Integrates with payment gateways and automates invoicing, collections, and dunning management.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.database import query_db

class PaymentProcessor:
    """Handle all payment processing operations."""
    
    def __init__(self):
        self.supported_gateways = ["stripe", "paypal", "braintree"]
    
    async def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new customer record."""
        try:
            # Insert customer record
            sql = f"""
            INSERT INTO customers (
                id, name, email, phone, 
                billing_address, shipping_address,
                tax_id, metadata, created_at
            ) VALUES (
                gen_random_uuid(),
                '{customer_data.get('name', '').replace("'", "''")}',
                '{customer_data.get('email', '').replace("'", "''")}',
                '{customer_data.get('phone', '').replace("'", "''")}',
                '{json.dumps(customer_data.get('billing_address', {})).replace("'", "''")}',
                '{json.dumps(customer_data.get('shipping_address', {})).replace("'", "''")}',
                '{customer_data.get('tax_id', '').replace("'", "''")}',
                '{json.dumps(customer_data.get('metadata', {})).replace("'", "''")}',
                NOW()
            ) RETURNING id
            """
            result = await query_db(sql)
            customer_id = result.get("rows", [{}])[0].get("id")
            
            return {"success": True, "customer_id": customer_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def create_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new subscription."""
        try:
            # Validate payment gateway
            gateway = subscription_data.get("gateway")
            if gateway not in self.supported_gateways:
                return {"success": False, "error": f"Unsupported gateway: {gateway}"}
            
            # Insert subscription record
            sql = f"""
            INSERT INTO subscriptions (
                id, customer_id, plan_id, status,
                start_date, end_date, trial_end,
                billing_cycle, gateway, gateway_id,
                metadata, created_at
            ) VALUES (
                gen_random_uuid(),
                '{subscription_data.get('customer_id')}',
                '{subscription_data.get('plan_id')}',
                'active',
                NOW(),
                NULL,
                {f"'{subscription_data.get('trial_end')}'" if subscription_data.get('trial_end') else "NULL"},
                '{subscription_data.get('billing_cycle', 'monthly')}',
                '{gateway}',
                '{subscription_data.get('gateway_id')}',
                '{json.dumps(subscription_data.get('metadata', {})).replace("'", "''")}',
                NOW()
            ) RETURNING id
            """
            result = await query_db(sql)
            subscription_id = result.get("rows", [{}])[0].get("id")
            
            return {"success": True, "subscription_id": subscription_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment transaction."""
        try:
            # Validate payment gateway
            gateway = payment_data.get("gateway")
            if gateway not in self.supported_gateways:
                return {"success": False, "error": f"Unsupported gateway: {gateway}"}
            
            # Insert payment record
            sql = f"""
            INSERT INTO payments (
                id, customer_id, subscription_id,
                amount, currency, status,
                gateway, gateway_id, metadata,
                created_at
            ) VALUES (
                gen_random_uuid(),
                {f"'{payment_data.get('customer_id')}'" if payment_data.get('customer_id') else "NULL"},
                {f"'{payment_data.get('subscription_id')}'" if payment_data.get('subscription_id') else "NULL"},
                {payment_data.get('amount')},
                '{payment_data.get('currency', 'USD')}',
                'pending',
                '{gateway}',
                '{payment_data.get('gateway_id')}',
                '{json.dumps(payment_data.get('metadata', {})).replace("'", "''")}',
                NOW()
            ) RETURNING id
            """
            result = await query_db(sql)
            payment_id = result.get("rows", [{}])[0].get("id")
            
            # TODO: Implement actual gateway integration
            # For now, mark as succeeded
            await query_db(f"""
                UPDATE payments 
                SET status = 'succeeded'
                WHERE id = '{payment_id}'
            """)
            
            return {"success": True, "payment_id": payment_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def generate_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an invoice for a customer."""
        try:
            # Insert invoice record
            sql = f"""
            INSERT INTO invoices (
                id, customer_id, subscription_id,
                amount, currency, status,
                due_date, metadata, created_at
            ) VALUES (
                gen_random_uuid(),
                '{invoice_data.get('customer_id')}',
                {f"'{invoice_data.get('subscription_id')}'" if invoice_data.get('subscription_id') else "NULL"},
                {invoice_data.get('amount')},
                '{invoice_data.get('currency', 'USD')}',
                'pending',
                {f"'{invoice_data.get('due_date')}'" if invoice_data.get('due_date') else "NOW() + INTERVAL '30 days'"},
                '{json.dumps(invoice_data.get('metadata', {})).replace("'", "''")}',
                NOW()
            ) RETURNING id
            """
            result = await query_db(sql)
            invoice_id = result.get("rows", [{}])[0].get("id")
            
            return {"success": True, "invoice_id": invoice_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def handle_dunning(self) -> Dict[str, Any]:
        """Process overdue invoices and send reminders."""
        try:
            # Get overdue invoices
            sql = """
            SELECT id, customer_id, amount, due_date
            FROM invoices
            WHERE status = 'pending'
              AND due_date < NOW()
            ORDER BY due_date ASC
            LIMIT 100
            """
            result = await query_db(sql)
            invoices = result.get("rows", [])
            
            processed = 0
            for invoice in invoices:
                invoice_id = invoice.get("id")
                
                # Update invoice status
                await query_db(f"""
                    UPDATE invoices
                    SET status = 'overdue'
                    WHERE id = '{invoice_id}'
                """)
                
                # TODO: Implement actual dunning process (email/SMS reminders)
                processed += 1
            
            return {"success": True, "processed": processed}
        except Exception as e:
            return {"success": False, "error": str(e)}
