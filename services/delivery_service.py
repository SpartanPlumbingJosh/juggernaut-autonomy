from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
from core.database import query_db

logger = logging.getLogger(__name__)

class DeliveryService:
    """Handles automated service delivery and billing integration"""
    
    def __init__(self):
        self.service_config = {
            'base_price_cents': 9900,  # $99/month
            'trial_days': 7,
            'max_retries': 3,
            'retry_delay_seconds': 60
        }
    
    async def provision_service(self, customer_id: str, plan: str) -> Dict[str, Any]:
        """Provision service for new customer"""
        try:
            # Check if customer already has service
            existing = await query_db(
                f"SELECT id FROM services WHERE customer_id = '{customer_id}' LIMIT 1"
            )
            if existing.get('rows'):
                return {'success': False, 'error': 'Service already exists'}
            
            # Create service record
            start_date = datetime.now(timezone.utc)
            trial_end = start_date + timedelta(days=self.service_config['trial_days'])
            
            await query_db(f"""
                INSERT INTO services (
                    id, customer_id, plan, status,
                    start_date, trial_end, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    '{plan}',
                    'active',
                    '{start_date.isoformat()}',
                    '{trial_end.isoformat()}',
                    NOW()
                )
            """)
            
            # Trigger first billing
            await self._create_billing_record(customer_id, start_date)
            
            return {'success': True, 'service_start': start_date.isoformat()}
            
        except Exception as e:
            logger.error(f"Failed to provision service: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _create_billing_record(self, customer_id: str, billing_date: datetime) -> Dict[str, Any]:
        """Create billing record and trigger payment"""
        try:
            # Create billing record
            await query_db(f"""
                INSERT INTO billing (
                    id, customer_id, amount_cents,
                    billing_date, status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{customer_id}',
                    {self.service_config['base_price_cents']},
                    '{billing_date.isoformat()}',
                    'pending',
                    NOW()
                )
            """)
            
            # Process payment
            payment_result = await self._process_payment(customer_id)
            if not payment_result.get('success'):
                raise Exception(payment_result.get('error'))
                
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to create billing record: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _process_payment(self, customer_id: str) -> Dict[str, Any]:
        """Process payment through billing system"""
        try:
            # Integration with billing system would go here
            # For MVP, we'll simulate successful payment
            
            # Update billing status
            await query_db(f"""
                UPDATE billing
                SET status = 'paid',
                    paid_at = NOW()
                WHERE customer_id = '{customer_id}'
                  AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def handle_service_expiry(self) -> Dict[str, Any]:
        """Handle expired services and retries"""
        try:
            # Get expired services
            expired = await query_db("""
                SELECT id, customer_id, trial_end
                FROM services
                WHERE status = 'active'
                  AND trial_end < NOW()
                LIMIT 100
            """)
            
            processed = 0
            failures = []
            
            for service in expired.get('rows', []):
                service_id = service['id']
                customer_id = service['customer_id']
                
                # Attempt billing
                billing_result = await self._create_billing_record(customer_id, datetime.now(timezone.utc))
                
                if billing_result.get('success'):
                    processed += 1
                else:
                    failures.append({
                        'service_id': service_id,
                        'error': billing_result.get('error')
                    })
            
            return {
                'success': True,
                'processed': processed,
                'failures': failures
            }
            
        except Exception as e:
            logger.error(f"Failed to handle service expiry: {str(e)}")
            return {'success': False, 'error': str(e)}
