import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

class PaymentProcessor:
    """Handles payment processing and transaction recording."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action

    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a payment and record the transaction."""
        try:
            # Validate required fields
            required_fields = ['amount_cents', 'currency', 'payment_method', 'customer_id']
            for field in required_fields:
                if field not in payment_data:
                    return {"success": False, "error": f"Missing required field: {field}"}

            # Process payment (mock implementation)
            payment_id = f"pay_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            status = "succeeded"
            
            # Record transaction
            transaction_data = {
                "payment_id": payment_id,
                "amount_cents": payment_data["amount_cents"],
                "currency": payment_data["currency"],
                "status": status,
                "metadata": payment_data.get("metadata", {}),
                "customer_id": payment_data["customer_id"],
                "payment_method": payment_data["payment_method"]
            }
            
            await self._record_transaction(transaction_data)
            
            return {
                "success": True,
                "payment_id": payment_id,
                "status": status,
                "amount_cents": payment_data["amount_cents"],
                "currency": payment_data["currency"]
            }
            
        except Exception as e:
            self.log_action(
                "payment.failed",
                f"Payment processing failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}

    async def _record_transaction(self, transaction_data: Dict[str, Any]) -> None:
        """Record transaction in the database."""
        try:
            metadata_json = json.dumps(transaction_data.get("metadata", {})).replace("'", "''")
            
            await self.execute_sql(f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'revenue',
                    {transaction_data["amount_cents"]},
                    '{transaction_data["currency"]}',
                    'payment',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            
            self.log_action(
                "payment.success",
                f"Payment processed successfully: {transaction_data['payment_id']}",
                level="info",
                output_data={
                    "payment_id": transaction_data["payment_id"],
                    "amount_cents": transaction_data["amount_cents"]
                }
            )
            
        except Exception as e:
            self.log_action(
                "payment.recording_failed",
                f"Failed to record payment: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            raise

    async def refund_payment(self, payment_id: str, amount_cents: Optional[int] = None) -> Dict[str, Any]:
        """Process a refund for a payment."""
        try:
            # Get original payment
            res = await self.execute_sql(f"""
                SELECT amount_cents, currency, metadata
                FROM revenue_events
                WHERE source = 'payment'
                  AND metadata->>'payment_id' = '{payment_id}'
                LIMIT 1
            """)
            
            if not res.get("rows"):
                return {"success": False, "error": "Payment not found"}
            
            original = res["rows"][0]
            refund_amount = amount_cents if amount_cents is not None else original["amount_cents"]
            
            # Record refund transaction
            await self._record_transaction({
                "payment_id": f"refund_{payment_id}",
                "amount_cents": -refund_amount,
                "currency": original["currency"],
                "status": "refunded",
                "metadata": original["metadata"],
                "customer_id": original["metadata"].get("customer_id", ""),
                "payment_method": original["metadata"].get("payment_method", "")
            })
            
            return {
                "success": True,
                "payment_id": payment_id,
                "refund_amount_cents": refund_amount,
                "currency": original["currency"]
            }
            
        except Exception as e:
            self.log_action(
                "refund.failed",
                f"Refund failed: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
