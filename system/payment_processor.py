"""
Payment processing abstraction for multiple gateways.
Includes automatic retry logic and error handling.
"""

from dataclasses import dataclass
from enum import Enum

class PaymentMethod(Enum):
    CARD = "card"
    BANK = "bank"
    CRYPTO = "crypto"

@dataclass
class PaymentResult:
    success: bool
    transaction_id: str
    message: str

class PaymentGateway:
    def __init__(self):
        # Initialize payment processors
        pass
        
    async def charge(self, amount: float, currency: str, 
                    payment_method: PaymentMethod,
                    customer_id: Optional[str] = None,
                    retries: int = 3) -> PaymentResult:
        """Process payment with automatic retries."""
        for attempt in range(retries):
            try:
                # Implementation would call actual payment processor API
                return PaymentResult(
                    success=True,
                    transaction_id="txn_" + str(uuid.uuid4()),
                    message="Payment processed successfully"
                )
            except Exception as e:
                if attempt == retries - 1:
                    return PaymentResult(
                        success=False,
                        transaction_id="",
                        message=str(e)
                    )
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
