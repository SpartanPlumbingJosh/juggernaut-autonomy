"""
Payment Processor - Handles billing, payments, and financial integrations.
Includes circuit breakers, audit logging, and transaction validation.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from functools import wraps

# Circuit breaker state
CIRCUIT_OPEN = False
LAST_FAILURE = None
FAILURE_THRESHOLD = 3  # Number of failures before opening circuit
FAILURE_WINDOW = 60  # Seconds to track failures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment_processor")

class PaymentError(Exception):
    """Base class for payment processing errors"""
    pass

class CircuitBreakerError(PaymentError):
    """Raised when circuit breaker is open"""
    pass

class ValidationError(PaymentError):
    """Raised when transaction validation fails"""
    pass

def circuit_breaker(func):
    """Decorator to implement circuit breaker pattern"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        global CIRCUIT_OPEN, LAST_FAILURE
        
        if CIRCUIT_OPEN:
            if LAST_FAILURE and (datetime.now(timezone.utc) - LAST_FAILURE).total_seconds() > 300:
                CIRCUIT_OPEN = False  # Try resetting after 5 minutes
            else:
                raise CircuitBreakerError("Payment processing is temporarily unavailable")
                
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            LAST_FAILURE = datetime.now(timezone.utc)
            raise

    return wrapper

async def validate_transaction(transaction: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate transaction data"""
    required_fields = ["amount_cents", "currency", "source", "customer_id"]
    for field in required_fields:
        if field not in transaction:
            return False, f"Missing required field: {field}"
            
    if transaction["amount_cents"] <= 0:
        return False, "Amount must be positive"
        
    if len(transaction["currency"]) != 3:
        return False, "Invalid currency code"
        
    return True, None

@circuit_breaker        
async def process_payment(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a payment transaction through financial gateway.
    Returns processed transaction details.
    """
    try:
        # Validate transaction
        is_valid, error = await validate_transaction(transaction)
        if not is_valid:
            raise ValidationError(error)
            
        # Simulate payment gateway integration
        # In production, this would call actual financial APIs
        payment_result = {
            "transaction_id": "simulated_txn_123",
            "status": "success",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "amount_cents": transaction["amount_cents"],
            "currency": transaction["currency"],
            "source": transaction["source"],
            "customer_id": transaction["customer_id"],
            "metadata": transaction.get("metadata", {})
        }
        
        # Audit log the transaction
        logger.info(f"Processed payment: {json.dumps(payment_result)}")
        
        return payment_result
        
    except Exception as e:
        logger.error(f"Payment processing failed: {str(e)}")
        raise PaymentError(f"Payment processing failed: {str(e)}")

async def refund_payment(transaction_id: str, amount_cents: int) -> Dict[str, Any]:
    """
    Process a refund for a given transaction.
    Returns refund details.
    """
    try:
        # Simulate refund processing
        refund_result = {
            "refund_id": "simulated_refund_123",
            "transaction_id": transaction_id,
            "status": "success",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "amount_cents": amount_cents,
            "original_transaction_id": transaction_id
        }
        
        # Audit log the refund
        logger.info(f"Processed refund: {json.dumps(refund_result)}")
        
        return refund_result
        
    except Exception as e:
        logger.error(f"Refund processing failed: {str(e)}")
        raise PaymentError(f"Refund processing failed: {str(e)}")
