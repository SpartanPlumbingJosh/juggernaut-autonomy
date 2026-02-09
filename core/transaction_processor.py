import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from core.payment_gateway import process_payment

logger = logging.getLogger(__name__)

class TransactionProcessor:
    """Handles revenue transaction processing and automation."""
    
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        
    async def create_transaction(self, transaction_data: Dict) -> Dict:
        """Process a new revenue transaction."""
        try:
            # Validate required fields
            required_fields = ['amount_cents', 'currency', 'source', 'event_type']
            for field in required_fields:
                if not transaction_data.get(field):
                    raise ValueError(f"Missing required field: {field}")
                    
            # Process payment if this is a revenue event
            payment_id = None
            if transaction_data['event_type'] == 'revenue':
                payment_result = await process_payment(
                    amount_cents=transaction_data['amount_cents'],
                    currency=transaction_data['currency'],
                    metadata=transaction_data.get('metadata', {})
                )
                if not payment_result.get('success'):
                    raise ValueError(f"Payment failed: {payment_result.get('error')}")
                payment_id = payment_result['payment_id']
                
            # Insert transaction record
            sql = f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, amount_cents,
                currency, source, metadata, recorded_at,
                payment_id, created_at
            ) VALUES (
                gen_random_uuid(),
                {f"'{transaction_data['experiment_id']}'" if transaction_data.get('experiment_id') else "NULL"},
                '{transaction_data['event_type']}',
                {transaction_data['amount_cents']},
                '{transaction_data['currency']}',
                '{transaction_data['source']}',
                '{json.dumps(transaction_data.get('metadata', {}))}',
                NOW(),
                {f"'{payment_id}'" if payment_id else "NULL"},
                NOW()
            )
            RETURNING id
            """
            
            result = await self.execute_sql(sql)
            transaction_id = result['rows'][0]['id']
            
            logger.info(
                f"Created transaction {transaction_id}",
                extra={
                    "transaction_id": transaction_id,
                    "amount_cents": transaction_data['amount_cents'],
                    "event_type": transaction_data['event_type']
                }
            )
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "payment_id": payment_id
            }
            
        except Exception as e:
            logger.error(
                f"Transaction failed: {str(e)}",
                extra={
                    "error": str(e),
                    "transaction_data": transaction_data
                }
            )
            return {
                "success": False,
                "error": str(e),
                "transaction_data": transaction_data
            }

    async def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Retrieve a transaction by ID."""
        try:
            sql = f"""
            SELECT * FROM revenue_events
            WHERE id = '{transaction_id}'
            """
            result = await self.execute_sql(sql)
            return result['rows'][0] if result['rows'] else None
        except Exception as e:
            logger.error(
                f"Failed to retrieve transaction {transaction_id}: {str(e)}",
                extra={"transaction_id": transaction_id}
            )
            return None
