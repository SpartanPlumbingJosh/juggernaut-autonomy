from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TransactionEngine:
    """Core transaction processing engine for revenue operations."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    async def process_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a revenue transaction and log it to the database.
        
        Args:
            transaction_data: Dictionary containing transaction details including:
                - amount_cents: Transaction amount in cents
                - currency: Currency code (e.g. 'USD')
                - source: Transaction source identifier
                - metadata: Additional transaction metadata
                - event_type: 'revenue' or 'cost'
                
        Returns:
            Dictionary with success status and transaction details
        """
        try:
            # Validate required fields
            required_fields = ['amount_cents', 'currency', 'source', 'event_type']
            for field in required_fields:
                if field not in transaction_data:
                    return {"success": False, "error": f"Missing required field: {field}"}
                    
            # Prepare data for database insertion
            amount_cents = int(transaction_data['amount_cents'])
            currency = str(transaction_data['currency'])
            source = str(transaction_data['source'])
            event_type = str(transaction_data['event_type'])
            metadata = json.dumps(transaction_data.get('metadata', {}))
            
            # Insert transaction into database
            sql = f"""
            INSERT INTO revenue_events (
                id, amount_cents, currency, source,
                metadata, event_type, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                {amount_cents},
                '{currency}',
                '{source}',
                '{metadata}'::jsonb,
                '{event_type}',
                NOW(),
                NOW()
            )
            RETURNING id
            """
            
            result = await self.execute_sql(sql)
            transaction_id = result.get('rows', [{}])[0].get('id')
            
            if not transaction_id:
                return {"success": False, "error": "Failed to insert transaction"}
                
            logger.info(f"Successfully processed transaction {transaction_id}")
            return {
                "success": True,
                "transaction_id": transaction_id,
                "amount_cents": amount_cents,
                "currency": currency,
                "source": source,
                "event_type": event_type
            }
            
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Retrieve status of a processed transaction.
        
        Args:
            transaction_id: UUID of the transaction to check
            
        Returns:
            Dictionary with transaction details and status
        """
        try:
            sql = f"""
            SELECT id, amount_cents, currency, source, metadata,
                   event_type, recorded_at, created_at
            FROM revenue_events
            WHERE id = '{transaction_id}'
            """
            
            result = await self.execute_sql(sql)
            transaction = result.get('rows', [{}])[0]
            
            if not transaction.get('id'):
                return {"success": False, "error": "Transaction not found"}
                
            return {
                "success": True,
                "transaction": transaction
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve transaction status: {str(e)}")
            return {"success": False, "error": str(e)}
