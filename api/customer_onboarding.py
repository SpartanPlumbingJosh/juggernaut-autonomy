from typing import Dict, Optional
from fastapi import HTTPException
from core.payment_processor import PaymentProcessor
from core.product_delivery import ProductDeliveryService
from core.database import query_db

class CustomerOnboarding:
    def __init__(self):
        self.payment_processor = PaymentProcessor()
        self.delivery_service = ProductDeliveryService()

    async def start_checkout(
        self,
        product_id: str,
        price_id: str,
        customer_email: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Start checkout process for new customer"""
        try:
            # Create checkout session
            session = self.payment_processor.create_checkout_session(
                price_id=price_id,
                customer_email=customer_email,
                metadata={
                    'product_id': product_id,
                    **(metadata or {})
                }
            )

            # Create customer record
            await query_db(
                f"""
                INSERT INTO customers (
                    email, status, created_at
                ) VALUES (
                    '{customer_email}',
                    'pending_payment',
                    NOW()
                )
                ON CONFLICT (email) DO UPDATE SET
                    status = 'pending_payment',
                    updated_at = NOW()
                """
            )

            return {
                'success': True,
                'checkout_url': session['url']
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Checkout failed: {str(e)}"
            )

    async def complete_onboarding(self, session_id: str) -> Dict:
        """Complete onboarding after successful payment"""
        try:
            # Get payment details
            payment = self.payment_processor.get_session(session_id)
            
            # Deliver product
            product_id = payment['metadata']['product_id']
            delivery = await self.delivery_service.deliver_product(
                customer_email=payment['customer_email'],
                product_id=product_id,
                order_details={
                    'order_id': session_id
                }
            )

            if not delivery['success']:
                raise Exception("Failed to deliver product")

            # Update customer status
            await query_db(
                f"""
                UPDATE customers
                SET status = 'active',
                    activated_at = NOW()
                WHERE email = '{payment['customer_email']}'
                """
            )

            return {
                'success': True,
                'message': 'Onboarding completed'
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Onboarding failed: {str(e)}"
            )
