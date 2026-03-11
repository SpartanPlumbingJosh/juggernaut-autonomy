import json
from datetime import datetime
from typing import Dict, Optional

class ServiceDelivery:
    def __init__(self, db_executor):
        self.db_executor = db_executor
        
    def deliver_service(self, payment_intent_id: str) -> Dict:
        """Deliver service after successful payment"""
        try:
            # Get payment details
            payment = self._get_payment_details(payment_intent_id)
            if not payment:
                return {'error': 'Payment not found'}
                
            # Create service record
            service_id = self._create_service_record(payment)
            if not service_id:
                return {'error': 'Failed to create service record'}
                
            # Perform service delivery
            delivery_result = self._perform_delivery(payment)
            if not delivery_result.get('success'):
                return {'error': 'Delivery failed'}
                
            return {
                'success': True,
                'service_id': service_id,
                'delivery_result': delivery_result
            }
            
        except Exception as e:
            return {'error': str(e)}
            
    def _get_payment_details(self, payment_intent_id: str) -> Optional[Dict]:
        """Retrieve payment details from database"""
        result = self.db_executor(f"""
            SELECT * FROM payments WHERE payment_intent_id = '{payment_intent_id}'
        """)
        return result.get('rows', [{}])[0] if result.get('rows') else None
        
    def _create_service_record(self, payment: Dict) -> Optional[str]:
        """Create service record in database"""
        result = self.db_executor(f"""
            INSERT INTO services (
                id, payment_id, status, created_at, metadata
            ) VALUES (
                gen_random_uuid(),
                '{payment['id']}',
                'pending',
                NOW(),
                '{json.dumps(payment.get('metadata', {}))}'
            )
            RETURNING id
        """)
        return result.get('rows', [{}])[0].get('id') if result.get('rows') else None
        
    def _perform_delivery(self, payment: Dict) -> Dict:
        """Perform actual service delivery"""
        # Implement your specific delivery logic here
        # This could be sending emails, generating files, etc.
        return {
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'details': 'Service delivered successfully'
        }
