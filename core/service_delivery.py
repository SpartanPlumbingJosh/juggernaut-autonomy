from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from uuid import uuid4

class ServiceDelivery:
    """Manage service-based revenue operations."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action

    def onboard_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new client record and initial service agreement."""
        try:
            client_id = str(uuid4())
            service_id = str(uuid4())
            
            # Insert client
            self.execute_sql(f"""
                INSERT INTO clients (
                    id, name, email, company, 
                    billing_address, created_at, status
                ) VALUES (
                    '{client_id}',
                    '{client_data['name'].replace("'", "''")}',
                    '{client_data['email'].replace("'", "''")}',
                    '{client_data.get('company', '').replace("'", "''")}',
                    '{json.dumps(client_data.get('billing', {})).replace("'", "''")}',
                    NOW(),
                    'active'
                )
            """)
            
            # Create service agreement
            self.execute_sql(f"""
                INSERT INTO service_agreements (
                    id, client_id, service_type, 
                    terms, billing_frequency, 
                    rate_cents, created_at
                ) VALUES (
                    '{service_id}',
                    '{client_id}',
                    '{client_data['service_type'].replace("'", "''")}',
                    '{json.dumps(client_data.get('terms', {})).replace("'", "''")}',
                    '{client_data.get('billing_frequency', 'monthly').replace("'", "''")}',
                    {int(client_data.get('rate_cents', 0))},
                    NOW()
                )
            """)
            
            self.log_action(
                "client.onboarded",
                f"New client onboarded: {client_data['name']}",
                level="info",
                output_data={"client_id": client_id, "service_id": service_id}
            )
            
            return {"success": True, "client_id": client_id, "service_id": service_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def deliver_service(self, service_id: str) -> Dict[str, Any]:
        """Execute service delivery and create invoice."""
        try:
            # Get service details
            res = self.execute_sql(f"""
                SELECT sa.id, sa.client_id, sa.rate_cents, 
                       c.email, c.name as client_name
                FROM service_agreements sa
                JOIN clients c ON sa.client_id = c.id
                WHERE sa.id = '{service_id}'
            """)
            
            if not res.get("rows"):
                return {"success": False, "error": "Service not found"}
                
            service = res["rows"][0]
            invoice_id = str(uuid4())
            
            # Create invoice
            self.execute_sql(f"""
                INSERT INTO invoices (
                    id, service_id, client_id,
                    amount_cents, due_date, 
                    status, created_at
                ) VALUES (
                    '{invoice_id}',
                    '{service_id}',
                    '{service['client_id']}',
                    {service['rate_cents']},
                    (NOW() + INTERVAL '30 days')::date,
                    'pending',
                    NOW()
                )
            """)
            
            # Record revenue event
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents,
                    source, recorded_at, 
                    attribution
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {service['rate_cents']},
                    'service',
                    NOW(),
                    jsonb_build_object(
                        'service_id', '{service_id}',
                        'client_id', '{service['client_id']}',
                        'invoice_id', '{invoice_id}'
                    )
                )
            """)
            
            self.log_action(
                "service.delivered",
                f"Service delivered for client {service['client_name']}",
                level="info",
                output_data={
                    "service_id": service_id,
                    "invoice_id": invoice_id,
                    "amount_cents": service['rate_cents']
                }
            )
            
            return {"success": True, "invoice_id": invoice_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_payment(self, invoice_id: str, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record payment and update revenue tracking."""
        try:
            # Get invoice details
            res = self.execute_sql(f"""
                SELECT i.id, i.amount_cents, i.client_id,
                       i.service_id, i.status
                FROM invoices i
                WHERE i.id = '{invoice_id}'
            """)
            
            if not res.get("rows"):
                return {"success": False, "error": "Invoice not found"}
                
            invoice = res["rows"][0]
            
            if invoice["status"] == "paid":
                return {"success": False, "error": "Invoice already paid"}
                
            # Record payment
            self.execute_sql(f"""
                UPDATE invoices
                SET status = 'paid',
                    paid_at = NOW(),
                    payment_method = '{payment_data['method'].replace("'", "''")}',
                    transaction_id = '{payment_data.get('transaction_id', '').replace("'", "''")}'
                WHERE id = '{invoice_id}'
            """)
            
            # Record payment event
            self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents,
                    source, recorded_at, 
                    attribution
                ) VALUES (
                    gen_random_uuid(),
                    'payment',
                    {invoice['amount_cents']},
                    'payment_processing',
                    NOW(),
                    jsonb_build_object(
                        'invoice_id', '{invoice_id}',
                        'client_id', '{invoice['client_id']}',
                        'service_id', '{invoice['service_id']}'
                    )
                )
            """)
            
            self.log_action(
                "payment.processed",
                f"Payment processed for invoice {invoice_id}",
                level="info",
                output_data={
                    "invoice_id": invoice_id,
                    "amount_cents": invoice['amount_cents'],
                    "method": payment_data['method']
                }
            )
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
