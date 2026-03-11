import time
import stripe
from datetime import datetime

stripe.api_key = "sk_test_..."  # TODO: Move to config

def fulfill_orders():
    """Check Stripe for new orders and fulfill them."""
    while True:
        try:
            payments = stripe.PaymentIntent.list(limit=10)
            for payment in payments.auto_paging_iter():
                if payment.status == 'succeeded' and not payment.metadata.get('fulfilled'):
                    # TODO: Add your fulfillment logic here
                    print(f"Fulfilling order {payment.id}")
                    
                    # Mark as fulfilled
                    stripe.PaymentIntent.modify(
                        payment.id,
                        metadata={'fulfilled': 'true', 'fulfilled_at': str(datetime.now())}
                    )
        except Exception as e:
            print(f"Fulfillment error: {e}")
        
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    fulfill_orders()
