from datetime import datetime, timedelta
from typing import List, Dict
from decimal import Decimal

class RevenueRecognizer:
    """Automate revenue recognition based on accounting rules."""
    
    async def recognize_revenue(self, deferred_revenue_id: str) -> List[Dict]:
        """Recognize revenue according to schedule."""
        deferred = await query_db(
            f"SELECT * FROM deferred_revenue WHERE id = '{deferred_revenue_id}'"
        )
        if not deferred.get('rows'):
            return []
            
        deferred_row = deferred['rows'][0]
        recognition_schedule = json.loads(deferred_row['recognition_schedule'])
        
        recognized = []
        for period in recognition_schedule:
            if period['recognized_at'] < datetime.now():
                continue
                
            await execute_db(
                f"""
                INSERT INTO revenue_events (
                    id, event_type, amount_cents, currency,
                    attribution, recorded_at, created_at
                ) VALUES (
                    gen_random_uuid(), 'revenue',
                    {int(Decimal(period['amount']) * 100)},
                    '{deferred_row['currency']}',
                    '{json.dumps({
                        'deferred_id': deferred_row['id'],
                        'period': period['period']
                    })}'::jsonb,
                    '{period['recognized_at']}', NOW()
                )
                """
            )
            recognized.append(period)
            
        return recognized
