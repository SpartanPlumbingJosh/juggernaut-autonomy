"""
Payment Processor Integrations - Automatically ingest revenue data from payment processors.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

class PaymentProcessor:
    """Base class for payment processor integrations."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def fetch_transactions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Fetch transactions from the payment processor."""
        raise NotImplementedError
        
    async def normalize_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transaction data to our schema."""
        raise NotImplementedError


class StripeProcessor(PaymentProcessor):
    """Stripe payment processor integration."""
    
    async def fetch_transactions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        # Implement Stripe API calls here
        pass
        
    async def normalize_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": transaction.get("id"),
            "amount_cents": int(float(transaction.get("amount", 0)) * 100),
            "currency": transaction.get("currency", "usd"),
            "customer_id": transaction.get("customer"),
            "description": transaction.get("description"),
            "metadata": transaction.get("metadata", {}),
            "recorded_at": datetime.fromtimestamp(transaction.get("created", 0)),
            "is_recurring": transaction.get("object") == "subscription",
            "source": "stripe"
        }


class PayPalProcessor(PaymentProcessor):
    """PayPal payment processor integration."""
    
    async def fetch_transactions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        # Implement PayPal API calls here
        pass
        
    async def normalize_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": transaction.get("id"),
            "amount_cents": int(float(transaction.get("amount", {}).get("value", 0)) * 100),
            "currency": transaction.get("amount", {}).get("currency_code", "usd"),
            "customer_id": transaction.get("payer", {}).get("payer_id"),
            "description": transaction.get("description"),
            "metadata": transaction.get("custom", {}),
            "recorded_at": datetime.strptime(transaction.get("create_time"), "%Y-%m-%dT%H:%M:%SZ"),
            "is_recurring": transaction.get("billing_agreement_id") is not None,
            "source": "paypal"
        }


async def ingest_payment_processor_data(processor: PaymentProcessor, execute_sql: Callable[[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Ingest data from a payment processor."""
    try:
        # Get last successful sync timestamp
        last_sync_result = await execute_sql("""
            SELECT MAX(recorded_at) as last_sync 
            FROM revenue_events 
            WHERE source = %s
        """, [processor.__class__.__name__.lower()])
        
        last_sync = last_sync_result.get("rows", [{}])[0].get("last_sync")
        start_date = last_sync or datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        # Fetch transactions
        transactions = await processor.fetch_transactions(start_date, end_date)
        
        # Normalize and insert transactions
        inserted = 0
        for transaction in transactions:
            normalized = await processor.normalize_transaction(transaction)
            
            await execute_sql("""
                INSERT INTO revenue_events (
                    id, amount_cents, currency, customer_id,
                    description, metadata, recorded_at,
                    is_recurring, source
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                ) ON CONFLICT (id) DO NOTHING
            """, [
                normalized["id"],
                normalized["amount_cents"],
                normalized["currency"],
                normalized["customer_id"],
                normalized["description"],
                json.dumps(normalized["metadata"]),
                normalized["recorded_at"],
                normalized["is_recurring"],
                normalized["source"]
            ])
            
            inserted += 1
            
        return {
            "success": True,
            "inserted": inserted,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
