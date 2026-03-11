"""
Payment processing and monetization logic.
Handles:
- Payment provider integration
- Revenue tracking
- Payout calculations
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

PAYMENT_PROVIDERS = {
    "stripe": {
        "min_payout": 500,  # $5.00 minimum
        "fee_percent": 2.9,
        "fee_flat": 30,  # $0.30
    },
    "paypal": {
        "min_payout": 2000,  # $20.00 minimum 
        "fee_percent": 2.9,
        "fee_flat": 30,
    },
}

class PaymentProcessor:
    def __init__(self, provider: str = "stripe") -> None:
        """Initialize payment processor with specified provider."""
        self.provider = provider.lower()
        if self.provider not in PAYMENT_PROVIDERS:
            raise ValueError(f"Unsupported payment provider: {provider}")
        
        self.config = PAYMENT_PROVIDERS[self.provider]
        logger.info(f"Initialized payment processor with {self.provider}")

    def process_payment(self, amount_cents: int, customer_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Process a payment transaction."""
        try:
            # In production, this would integrate with actual payment provider API
            transaction_id = f"tx_{datetime.now(timezone.utc).timestamp()}"
            fee = self._calculate_fee(amount_cents)
            
            logger.info(f"Processing payment of {amount_cents} cents via {self.provider}")
            
            # Generate receipt data
            receipt = {
                "transaction_id": transaction_id,
                "amount_cents": amount_cents,
                "currency": "USD",
                "fee_cents": fee,
                "net_amount_cents": amount_cents - fee,
                "source": self.provider,
                "customer_email": customer_data.get("email"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": customer_data.get("metadata", {}),
            }
            
            logger.debug(f"Payment receipt generated: {receipt}")
            return True, receipt
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}", exc_info=True)
            return False, None

    def _calculate_fee(self, amount_cents: int) -> int:
        """Calculate payment provider fees."""
        percentage_fee = int(amount_cents * (self.config["fee_percent"] / 100))
        total_fee = percentage_fee + self.config["fee_flat"]
        return total_fee

    def can_payout(self, balance_cents: int) -> bool:
        """Check if current balance meets minimum payout threshold."""
        return balance_cents >= self.config["min_payout"]

    @staticmethod
    def record_revenue_event(
        execute_sql: Callable[[str], Dict[str, Any]], 
        event_type: str,
        amount_cents: int,
        source: str,
        metadata: Dict[str, Any],
        experiment_id: Optional[str] = None
    ) -> bool:
        """Record revenue or cost event in database."""
        try:
            metadata_json = json.dumps(metadata).replace("'", "''")
            
            execute_sql(f"""
                INSERT INTO revenue_events (
                    id, 
                    experiment_id,
                    event_type,
                    amount_cents, 
                    currency,
                    source,
                    metadata,
                    recorded_at,
                    created_at
                ) VALUES (
                    gen_random_uuid(),
                    {f"'{experiment_id}'::uuid" if experiment_id else "NULL"},
                    '{event_type}',
                    {amount_cents},
                    'USD',
                    '{source.replace("'", "''")}',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
            """)
            return True
        except Exception as e:
            logger.error(f"Failed to record revenue event: {str(e)}")
            return False
