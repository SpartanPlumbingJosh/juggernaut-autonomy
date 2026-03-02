from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
import uuid
import json
from decimal import Decimal

class RevenueEngine:
    """Core engine for autonomous revenue generation."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        
    async def create_transaction(
        self,
        amount: Decimal,
        currency: str,
        source: str,
        event_type: str = "revenue",
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a revenue transaction with idempotency check."""
        try:
            # Check for existing transaction if idempotency key provided
            if idempotency_key:
                existing = await self.execute_sql(
                    f"""
                    SELECT id FROM revenue_events
                    WHERE metadata->>'idempotency_key' = '{idempotency_key}'
                    LIMIT 1
                    """
                )
                if existing.get("rows"):
                    return {"success": True, "transaction_id": existing["rows"][0]["id"]}
            
            # Create new transaction
            transaction_id = str(uuid.uuid4())
            metadata = metadata or {}
            metadata["idempotency_key"] = idempotency_key
            
            await self.execute_sql(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    source, metadata, recorded_at, created_at
                ) VALUES (
                    '{transaction_id}',
                    '{event_type}',
                    {int(amount * 100)},
                    '{currency}',
                    '{source}',
                    '{json.dumps(metadata)}',
                    NOW(),
                    NOW()
                )
                """
            )
            
            await self.log_action(
                "revenue.transaction_created",
                f"Created {event_type} transaction",
                level="info",
                output_data={
                    "transaction_id": transaction_id,
                    "amount": float(amount),
                    "currency": currency,
                    "source": source
                }
            )
            
            return {"success": True, "transaction_id": transaction_id}
            
        except Exception as e:
            await self.log_action(
                "revenue.transaction_failed",
                f"Failed to create transaction: {str(e)}",
                level="error",
                error_data={
                    "amount": float(amount),
                    "currency": currency,
                    "source": source,
                    "error": str(e)
                }
            )
            return {"success": False, "error": str(e)}
            
    async def process_recurring_transactions(self) -> Dict[str, Any]:
        """Process scheduled recurring transactions."""
        try:
            # Get due recurring transactions
            res = await self.execute_sql(
                """
                SELECT id, amount_cents, currency, source, metadata
                FROM recurring_revenue
                WHERE next_run_at <= NOW()
                  AND status = 'active'
                ORDER BY next_run_at ASC
                LIMIT 100
                """
            )
            transactions = res.get("rows", []) or []
            
            processed = 0
            failures = []
            
            for txn in transactions:
                amount = Decimal(txn["amount_cents"]) / Decimal(100)
                currency = txn["currency"]
                source = txn["source"]
                metadata = txn.get("metadata") or {}
                
                # Create transaction
                result = await self.create_transaction(
                    amount=amount,
                    currency=currency,
                    source=source,
                    metadata=metadata,
                    idempotency_key=f"recurring_{txn['id']}_{txn['next_run_at']}"
                )
                
                if result["success"]:
                    processed += 1
                    # Update next run date
                    await self.execute_sql(
                        f"""
                        UPDATE recurring_revenue
                        SET last_run_at = NOW(),
                            next_run_at = NOW() + INTERVAL '1 {metadata.get("interval", "month")}',
                            updated_at = NOW()
                        WHERE id = '{txn['id']}'
                        """
                    )
                else:
                    failures.append({
                        "transaction_id": txn["id"],
                        "error": result.get("error", "unknown")
                    })
                    
            await self.log_action(
                "revenue.recurring_processed",
                f"Processed {processed} recurring transactions",
                level="info",
                output_data={
                    "processed": processed,
                    "failures": len(failures)
                }
            )
            
            return {
                "success": True,
                "processed": processed,
                "failures": failures
            }
            
        except Exception as e:
            await self.log_action(
                "revenue.recurring_failed",
                f"Failed to process recurring transactions: {str(e)}",
                level="error",
                error_data={"error": str(e)}
            )
            return {"success": False, "error": str(e)}
