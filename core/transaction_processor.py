"""
Transaction Processor - Handles revenue event processing and validation.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

class TransactionProcessor:
    """Process and validate revenue transactions."""
    
    def __init__(self):
        self.min_amount_cents = 1  # Minimum transaction amount
        self.max_amount_cents = 100000000  # Maximum transaction amount
        self.required_fields = ["event_type", "amount_cents", "currency", "source"]
        self.valid_event_types = ["revenue", "cost", "refund"]
        
    def validate_transaction(self, transaction: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate transaction data structure and values."""
        if not isinstance(transaction, dict):
            return False, "Transaction must be a dictionary"
            
        for field in self.required_fields:
            if field not in transaction:
                return False, f"Missing required field: {field}"
                
        if transaction["event_type"] not in self.valid_event_types:
            return False, f"Invalid event_type: {transaction['event_type']}"
            
        try:
            amount = int(transaction["amount_cents"])
            if amount < self.min_amount_cents or amount > self.max_amount_cents:
                return False, f"Amount out of range: {amount}"
        except (ValueError, TypeError):
            return False, "Invalid amount_cents value"
            
        return True, None
        
    def process_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Process and normalize transaction data."""
        valid, error = self.validate_transaction(transaction)
        if not valid:
            raise ValueError(f"Invalid transaction: {error}")
            
        # Add timestamps
        transaction["recorded_at"] = transaction.get("recorded_at") or datetime.now(timezone.utc).isoformat()
        transaction["created_at"] = datetime.now(timezone.utc).isoformat()
        
        # Normalize metadata
        if "metadata" in transaction:
            if isinstance(transaction["metadata"], str):
                try:
                    transaction["metadata"] = json.loads(transaction["metadata"])
                except json.JSONDecodeError:
                    transaction["metadata"] = {}
            elif not isinstance(transaction["metadata"], dict):
                transaction["metadata"] = {}
                
        return transaction
        
    def batch_process(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process multiple transactions with error handling."""
        processed = []
        errors = []
        
        for idx, transaction in enumerate(transactions):
            try:
                processed.append(self.process_transaction(transaction))
            except Exception as e:
                errors.append({
                    "index": idx,
                    "error": str(e),
                    "transaction": transaction
                })
                
        return {
            "success": len(errors) == 0,
            "processed": processed,
            "errors": errors,
            "total": len(transactions),
            "valid": len(processed),
            "invalid": len(errors)
        }
