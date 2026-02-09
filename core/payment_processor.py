import json
import stripe
import datetime
from typing import Dict, Any, Optional, List
from core.database import query_db, execute_sql

STRIPE_API_KEY = "sk_test_"  # Should be configured via environment variables
PADDLE_VENDOR_ID = ""  # Should be configured via environment variables
PADDLE_API_KEY = ""    # Should be configured via environment variables

class PaymentProcessor:
    def __init__(self):
        stripe.api_key = STRIPE_API_KEY
        self.stripe = stripe
    
    async def record_transaction(
        self,
        amount_cents: int,
        currency: str,
        source: str,
        transaction_id: str,
        attributes: Dict[str, Any],
        event_type: str = "revenue"
    ) -> Dict[str, Any]:
        """Record a financial transaction in the database."""
        try:
            metadata_json = json.dumps(attributes.get("metadata", {}))
            attribution_json = json.dumps(attributes.get("attribution", {}))
            
            await execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id,
                    event_type,
                    amount_cents,
                    currency,
                    source,
                    transaction_id,
                    metadata,
                    attribution,
                    recorded_at,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    {amount_cents},
                    '{currency}',
                    '{source}',
                    '{transaction_id}',
                    '{metadata_json}'::jsonb,
                    '{attribution_json}'::jsonb,
                    NOW(),
                    NOW()
                )
                """
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_stripe_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe webhook events."""
        event = payload
        transaction_id = event.get("id", "")
        source = "stripe"
        
        try:
            if event["type"] == "payment_intent.succeeded":
                intent = event["data"]["object"]
                amount = intent["amount"]
                currency = intent["currency"]
                metadata = intent.get("metadata", {})
                
                return await self.record_transaction(
                    amount_cents=amount,
                    currency=currency,
                    source=source,
                    transaction_id=transaction_id,
                    attributes={
                        "metadata": metadata,
                        "attribution": {
                            "payment_method": intent.get("payment_method"),
                            "customer": intent.get("customer")
                        }
                    }
                )
                
            elif event["type"] == "charge.refunded":
                charge = event["data"]["object"]
                amount = abs(charge["amount_refunded"])
                currency = charge["currency"]
                
                return await self.record_transaction(
                    amount_cents=-amount,
                    currency=currency,
                    source=source,
                    transaction_id=transaction_id,
                    attributes={
                        "metadata": charge.get("metadata", {}),
                        "attribution": {
                            "original_charge": charge.get("payment_intent"),
                            "reason": charge.get("refund_reason")
                        }
                    },
                    event_type="refund"
                )
                
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        return {"success": True, "message": "Webhook received but no action taken"}

    async def handle_paddle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process Paddle webhook events."""
        try:
            event = payload
            transaction_id = event.get("order_id", "")
            source = "paddle"
            
            if "payment_succeeded" in event.get("alert_name", ""):
                amount = float(event.get("sale_gross", 0)) * 100
                currency = event.get("currency", "USD")
                
                return await self.record_transaction(
                    amount_cents=int(amount),
                    currency=currency,
                    source=source,
                    transaction_id=transaction_id,
                    attributes={
                        "metadata": {
                            "product_id": event.get("product_id"),
                            "receipt_url": event.get("receipt_url")
                        },
                        "attribution": {
                            "customer_email": event.get("email"),
                            "payment_method": "paddle"
                        }
                    }
                )
            
            elif "refund" in event.get("alert_name", ""):
                amount = float(event.get("gross_refund", 0)) * 100
                
                return await self.record_transaction(
                    amount_cents=-int(amount),
                    currency=event.get("currency", "USD"),
                    source=source,
                    transaction_id=transaction_id,
                    attributes={
                        "metadata": {
                            "refund_reason": event.get("refund_reason"),
                            "original_order": event.get("order_id")
                        },
                        "attribution": {
                            "customer_email": event.get("email")
                        }
                    },
                    event_type="refund"
                )
                
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        return {"success": True, "message": "Webhook received but no action taken"}

    async def generate_invoice(self, transaction_id: str) -> Dict[str, Any]:
        """Generate invoice for a recorded transaction."""
        try:
            result = await query_db(
                f"""
                SELECT 
                    id, amount_cents, currency, source, 
                    recorded_at, metadata, attribution
                FROM revenue_events 
                WHERE transaction_id = '{transaction_id}'
                LIMIT 1
                """
            )
            
            if not result.get("rows"):
                return {"success": False, "error": "Transaction not found"}
            
            transaction = result["rows"][0]
            
            # Here you would implement actual invoice generation logic
            # This could create PDFs, send emails, etc.
            # For now we'll just return the transaction data
            
            return {
                "success": True,
                "invoice_data": {
                    "transaction_id": transaction_id,
                    "amount": transaction["amount_cents"] / 100,
                    "currency": transaction["currency"],
                    "date": transaction["recorded_at"].strftime("%Y-%m-%d"),
                    "metadata": transaction["metadata"]
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def revenue_recognition(self, transaction_id: str) -> Dict[str, Any]:
        """Apply revenue recognition rules to a transaction."""
        try:
            result = await query_db(
                f"""
                SELECT 
                    id, amount_cents, currency, recorded_at, 
                    attribution, metadata
                FROM revenue_events 
                WHERE transaction_id = '{transaction_id}'
                LIMIT 1
                """
            )
            
            if not result.get("rows"):
                return {"success": False, "error": "Transaction not found"}
            
            transaction = result["rows"][0]
            amount = transaction["amount_cents"]
            
            # Simple revenue recognition - recognize immediately
            # More sophisticated logic could recognize over time based on service period
            
            recognition_data = {
                "transaction_id": transaction_id,
                "recognized_amount": amount,
                "recognition_date": transaction["recorded_at"].strftime("%Y-%m-%d"),
                "recognition_status": "complete"
            }
            
            return {"success": True, "recognition_data": recognition_data}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
