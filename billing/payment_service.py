import os
import stripe
import paddle
from datetime import datetime, timezone
from typing import Any, Dict, Optional

class PaymentService:
    """Handle payments through Stripe and Paddle with failover support."""
    
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        paddle.vendor_id = os.getenv("PADDLE_VENDOR_ID")
        paddle.api_key = os.getenv("PADDLE_API_KEY")
        
    async def create_payment_intent(
        self, 
        amount_cents: int, 
        currency: str, 
        customer_email: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create payment intent using primary processor with failover."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                receipt_email=customer_email,
                metadata=metadata or {},
                payment_method_types=["card"],
            )
            return {
                "processor": "stripe",
                "intent_id": intent.id,
                "client_secret": intent.client_secret
            }
        except Exception:
            # Fallback to Paddle
            try:
                product_id = os.getenv("PADDLE_DEFAULT_PRODUCT_ID")
                response = paddle.Order.create(
                    customer_email=customer_email,
                    price_data=[{
                        "price": amount_cents / 100,
                        "quantity": 1,
                        "product_id": product_id
                    }],
                    metadata=metadata or {}
                )
                return {
                    "processor": "paddle", 
                    "checkout_url": response.checkout_url,
                    "order_id": response.id
                }
            except Exception as e:
                raise ValueError(f"Payment processing failed: {str(e)}")

    async def record_successful_payment(
        self,
        payment_intent: str,
        amount_cents: int,
        currency: str,
        customer_id: str,
        invoice_items: list
    ) -> None:
        """Record revenue event with proper accounting treatment."""
        event_data = {
            "event_type": "revenue",
            "amount_cents": amount_cents,
            "currency": currency,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "payment_intent": payment_intent,
                "customer_id": customer_id,
                "invoice_items": invoice_items
            }
        }
        await query_db(f"""
            INSERT INTO revenue_events 
            (event_type, amount_cents, currency, metadata, recorded_at)
            VALUES (
                'revenue',
                {amount_cents},
                '{currency}',
                '{json.dumps(event_data)}'::jsonb,
                NOW()
            )
        """)


async def handle_webhook(event_data: Dict[str, Any]) -> bool:
    """Process payment processor webhook events."""
    event_type = event_data.get("type")
    data = event_data.get("data", {})
    
    if event_type in ["payment_intent.succeeded", "checkout.completed"]:
        payment = data.get("object", {})
        amount = payment.get("amount", payment.get("total", 0))
        currency = payment.get("currency", "usd").lower()
        customer_id = payment.get("customer") or payment.get("email")
        
        await record_successful_payment(
            payment_intent=payment.get("id"),
            amount_cents=amount,
            currency=currency,
            customer_id=customer_id,
            invoice_items=payment.get("invoice_items", [])
        )
        return True
        
    return False


async def adjust_revenue_recognition(
    event_id: str, 
    adjustments: Dict[str, Any]
) -> None:
    """Adjust revenue recognition schedule if needed."""
    await query_db(f"""
        UPDATE revenue_events
        SET metadata = metadata || '{json.dumps(adjustments)}'::jsonb
        WHERE id = '{event_id}'
    """)


async def get_revenue_schedule(
    start_date: str,
    end_date: str,
    recognition_window: int = 30
) -> Dict[str, Any]:
    """Get recognized vs deferred revenue by period."""
    result = await query_db(f"""
        SELECT
            DATE_TRUNC('day', recorded_at) as day,
            SUM(CASE WHEN event_type = 'revenue' 
                     THEN amount_cents ELSE 0 END) as gross_amount,
            SUM(
                CASE WHEN (metadata->>'recognized')::boolean = true
                THEN amount_cents ELSE 0 END
            ) as recognized_amount,
            COUNT(*) as transaction_count
        FROM revenue_events
        WHERE recorded_at BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY DATE_TRUNC('day', recorded_at)
        ORDER BY day ASC
    """)
    return result.get("rows", [])
