import logging
from typing import Dict

logger = logging.getLogger(__name__)

async def process_payment(amount_cents: int, currency: str, metadata: Dict) -> Dict:
    """Process a payment through the payment gateway."""
    try:
        # TODO: Integrate with actual payment gateway API
        # For MVP, we'll simulate successful payments
        
        # Validate amount
        if amount_cents <= 0:
            raise ValueError("Amount must be positive")
            
        # Simulate payment processing
        payment_id = f"pmt_{int(time.time())}"
        
        logger.info(
            f"Processed payment {payment_id}",
            extra={
                "payment_id": payment_id,
                "amount_cents": amount_cents,
                "currency": currency
            }
        )
        
        return {
            "success": True,
            "payment_id": payment_id,
            "amount_cents": amount_cents,
            "currency": currency
        }
        
    except Exception as e:
        logger.error(
            f"Payment failed: {str(e)}",
            extra={
                "error": str(e),
                "amount_cents": amount_cents,
                "currency": currency
            }
        )
        return {
            "success": False,
            "error": str(e),
            "amount_cents": amount_cents,
            "currency": currency
        }
