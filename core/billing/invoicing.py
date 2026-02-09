from datetime import datetime, timedelta
from typing import Dict, Any
from .models import Invoice
from core.database import query_db

def generate_invoices() -> Dict[str, Any]:
    """
    Generate invoices for upcoming payments.
    
    Returns:
        Dict with success status and statistics
    """
    try:
        # Get subscriptions due for invoicing
        res = query_db("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
              AND current_period_end <= NOW() + INTERVAL '7 days'
            LIMIT 100
        """)
        subscriptions = res.get('rows', [])
        
        generated = 0
        
        for sub in subscriptions:
            invoice_id = str(uuid.uuid4())
            query_db(f"""
                INSERT INTO invoices (
                    invoice_id, customer_id, amount, currency, status, due_date
                ) VALUES (
                    '{invoice_id}', '{sub['customer_id']}', {sub['amount']}, '{sub['currency']}', 'open', NOW() + INTERVAL '7 days'
                )
            """)
            generated += 1
            
        return {
            'success': True,
            'generated': generated,
            'total': len(subscriptions)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
