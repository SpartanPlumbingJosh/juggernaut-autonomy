import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from core.database import query_db

class FulfillmentService:
    async def process_pending_orders(self) -> None:
        """Process orders that have been paid but not fulfilled."""
        while True:
            try:
                # Get paid but unfulfilled orders
                result = await query_db("""
                    SELECT r.id, r.metadata, r.amount_cents, r.currency
                    FROM revenue_events r
                    LEFT JOIN fulfillment_events f ON f.revenue_event_id = r.id
                    WHERE r.event_type = 'revenue'
                    AND f.id IS NULL
                    LIMIT 100
                """)
                
                for order in result.get("rows", []):
                    try:
                        await self._fulfill_order(order)
                    except Exception as e:
                        print(f"Failed to fulfill order {order['id']}: {str(e)}")
                
                # Sleep for 1 minute between checks
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"Fulfillment service error: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes after error

    async def _fulfill_order(self, order: Dict[str, Any]) -> None:
        """Fulfill a single order."""
        order_id = order["id"]
        metadata = order.get("metadata", {})
        
        # TODO: Implement actual fulfillment logic
        # For MVP we'll just log the fulfillment
        
        await query_db(f"""
            INSERT INTO fulfillment_events (
                id, revenue_event_id, status,
                metadata, created_at, updated_at
            ) VALUES (
                gen_random_uuid(),
                '{order_id}',
                'fulfilled',
                '{json.dumps(metadata)}'::jsonb,
                NOW(),
                NOW()
            )
        """)

async def start_fulfillment_service() -> None:
    """Start the fulfillment service."""
    service = FulfillmentService()
    await service.process_pending_orders()
