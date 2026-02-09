import logging
from typing import Dict, Any
from models.user import User
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)

class OnboardingService:
    def __init__(self, execute_sql: Callable[[str], Dict]):
        self.execute_sql = execute_sql
        self.payment_service = PaymentService()
    
    async def onboard_user(self, email: str, password: str, payment_info: Dict[str, Any]) -> Dict[str, Any]:
        """Complete full onboarding flow"""
        try:
            # Create user record
            user = User.create(email, password)
            await self._save_user(user)
            
            # Process payment
            payment_result = await self.payment_service.create_payment_intent(
                amount=payment_info['amount'],
                currency=payment_info.get('currency', 'usd'),
                metadata={'user_id': user.id}
            )
            
            if not payment_result.success:
                raise ValueError("Payment failed")
                
            await self._send_welcome_email(user)
            
            return {
                'success': True,
                'user_id': user.id,
                'transaction_id': payment_result.transaction_id
            }
        except Exception as e:
            logger.error(f"Onboarding failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _save_user(self, user: User) -> bool:
        """Save user to database"""
        # Implementation omitted for brevity
        pass
    
    async def _send_welcome_email(self, user: User) -> bool:
        """Send welcome email"""
        # Implementation omitted for brevity 
        pass
