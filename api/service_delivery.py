"""
Service Delivery Automation - Handles automated service delivery after payment.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Optional

async def deliver_service(execute_sql: Callable[[str], Dict], transaction_id: str) -> Dict:
    """
    Handle service delivery after successful payment.
    Returns: {
        "success": bool,
        "delivery_id": str,
        "transaction_id": str,
        "metadata": Dict
    }
    """
    try:
        # Get transaction details
        transaction_sql = f"""
        SELECT * FROM revenue_transactions
        WHERE transaction_id = '{transaction_id}'
        LIMIT 1
        """
        transaction_result = await execute_sql(transaction_sql)
        transaction = transaction_result.get("rows", [{}])[0]

        if not transaction:
            return {"success": False, "error": "Transaction not found"}

        # Generate delivery metadata
        metadata = {
            "transaction_id": transaction_id,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
            "service_type": "digital_product"  # Could be configurable
        }

        # Log delivery
        delivery_sql = f"""
        INSERT INTO service_deliveries (
            id, transaction_id, metadata, delivered_at
        ) VALUES (
            gen_random_uuid(),
            '{transaction_id}',
            '{json.dumps(metadata)}',
            NOW()
        )
        RETURNING id
        """
        delivery_result = await execute_sql(delivery_sql)
        delivery_id = delivery_result.get("rows", [{}])[0].get("id")

        if not delivery_id:
            return {"success": False, "error": "Failed to log delivery"}

        # Update transaction status
        update_sql = f"""
        UPDATE revenue_transactions
        SET status = 'completed',
            updated_at = NOW()
        WHERE transaction_id = '{transaction_id}'
        """
        await execute_sql(update_sql)

        return {
            "success": True,
            "delivery_id": delivery_id,
            "transaction_id": transaction_id,
            "metadata": metadata
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
