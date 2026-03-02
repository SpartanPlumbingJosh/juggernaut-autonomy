import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import hashlib
import hmac
import json

logger = logging.getLogger(__name__)

class TransactionProcessor:
    """Process and validate revenue transactions."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode('utf-8')
        
    def validate_signature(self, payload: str, signature: str) -> bool:
        """Validate HMAC signature of incoming webhook."""
        try:
            digest = hmac.new(
                self.secret_key,
                msg=payload.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(digest, signature)
        except Exception as e:
            logger.error(f"Signature validation failed: {str(e)}")
            return False
            
    def process_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate a transaction."""
        try:
            # Validate required fields
            required_fields = ['amount_cents', 'currency', 'source', 'event_type']
            if not all(field in transaction_data for field in required_fields):
                return {"success": False, "error": "Missing required fields"}
                
            # Validate event types
            if transaction_data['event_type'] not in ['revenue', 'cost']:
                return {"success": False, "error": "Invalid event type"}
                
            # Add metadata
            transaction_data['recorded_at'] = datetime.now(timezone.utc).isoformat()
            transaction_data['metadata'] = transaction_data.get('metadata', {})
            
            return {"success": True, "transaction": transaction_data}
            
        except Exception as e:
            logger.error(f"Transaction processing failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def save_transaction(self, execute_sql: Callable[[str], Dict[str, Any]], transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Save validated transaction to database."""
        try:
            # Escape values for SQL
            amount_cents = int(transaction['amount_cents'])
            currency = transaction['currency'].replace("'", "''")
            source = transaction['source'].replace("'", "''")
            event_type = transaction['event_type'].replace("'", "''")
            metadata = json.dumps(transaction.get('metadata', {})).replace("'", "''")
            recorded_at = transaction['recorded_at'].replace("'", "''")
            
            sql = f"""
            INSERT INTO revenue_events (
                id, amount_cents, currency, source,
                event_type, metadata, recorded_at
            ) VALUES (
                gen_random_uuid(),
                {amount_cents},
                '{currency}',
                '{source}',
                '{event_type}',
                '{metadata}'::jsonb,
                '{recorded_at}'
            )
            """
            
            execute_sql(sql)
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Transaction save failed: {str(e)}")
            return {"success": False, "error": str(e)}
