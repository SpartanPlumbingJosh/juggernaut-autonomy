"""
Usage metering and billing infrastructure.
Tracks usage events and calculates charges.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.database import query_db
from core.config import settings

logger = logging.getLogger(__name__)

class UsageMeter:
    def __init__(self):
        self.billing_cycle_days = settings.BILLING_CYCLE_DAYS

    async def record_usage(
        self, 
        customer_id: str,
        subscription_id: str,
        feature_name: str,
        quantity: float 
    ) -> Dict[str, Any]:
        """Record a usage event"""
        try:
            sql = """
                INSERT INTO usage_events (
                    id, customer_id, subscription_id, 
                    feature_name, quantity, recorded_at
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, %s, NOW()
                )
            """
            await query_db(sql, (customer_id, subscription_id, feature_name, quantity))
            return {'success': True}
        except Exception as e:
            logger.error(f"Error recording usage: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def generate_invoice_items(
        self,
        customer_id: str,
        subscription_id: str,
        billing_date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate invoice items from usage"""
        try:
            # Get usage since last billing
            start_date = billing_date - timedelta(days=self.billing_cycle_days)
            sql = """
                SELECT feature_name, SUM(quantity) as total_quantity
                FROM usage_events
                WHERE customer_id = %s 
                AND subscription_id = %s
                AND recorded_at > %s
                GROUP BY feature_name
            """
            result = await query_db(sql, (customer_id, subscription_id, start_date))
            
            invoice_items = []
            for row in result.get('rows', []):
                # Lookup pricing for each feature
                pricing = await self._get_feature_pricing(row['feature_name'])
                if pricing:
                    amount = row['total_quantity'] * pricing['unit_price']
                    invoice_items.append({
                        'feature': row['feature_name'],
                        'quantity': row['total_quantity'],
                        'amount': amount,
                        'currency': pricing['currency']
                    })
            
            return invoice_items
        except Exception as e:
            logger.error(f"Error generating invoice items: {str(e)}")
            raise e

    async def _get_feature_pricing(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get pricing info for a feature"""
        sql = "SELECT unit_price, currency FROM feature_pricing WHERE name = %s"
        result = await query_db(sql, (feature_name,))
        row = result.get('rows', [{}])[0]
        return row if row.get('unit_price') else None
