"""
Billing service - Handles payments and revenue recording.

Key flows:
- Process payments
- Record revenue events
- Handle refunds
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from core.database import query_db

async def record_revenue_event(
    amount_cents: int,
    event_type: str,
    source: str,
    metadata: Optional[Dict] = None,
    attribution: Optional[Dict] = None
) -> dict:
    """Record a revenue or cost event in the system."""
    try:
        event_id = str(uuid.uuid4())
        
        # Format the metadata and attribution
        metadata_json = {} if metadata is None else metadata
        attribution_json = {} if attribution is None else attribution
        
        # Insert into database
        sql = f"""
        INSERT INTO revenue_events (
            id,
            experiment_id,
            event_type,
            amount_cents,
            currency,
            source,
            metadata,
            attribution,
            recorded_at,
            created_at
        ) VALUES (
            '{event_id}',
            NULL,
            '{event_type}',
            {amount_cents},
            'USD',
            '{source}',
            '{json.dumps(metadata_json)}'::jsonb,
            '{json.dumps(attribution_json)}'::jsonb,
            NOW(),
            NOW()
        )
        """
        
        await query_db(sql)
        
        return {"success": True, "event_id": event_id}
    
    except Exception as e:
        return {"success": False, "error": str(e)}
