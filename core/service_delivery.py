import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.database import query_db

logger = logging.getLogger(__name__)

async def retry_failed_deliveries(max_retries: int = 3) -> Dict[str, Any]:
    """Retry failed service deliveries."""
    try:
        # Get failed deliveries
        res = await query_db(f"""
            SELECT payment_id, service_type, customer_email, service_params
            FROM service_failures
            WHERE retry_count < {max_retries}
            ORDER BY failed_at ASC
            LIMIT 100
        """)
        failures = res.get("rows", [])
        
        success_count = 0
        for failure in failures:
            payment_id = failure.get("payment_id")
            try:
                # Retry delivery
                await deliver_service(
                    payment_id,
                    {
                        "service_type": failure.get("service_type"),
                        "customer_email": failure.get("customer_email"),
                        "service_params": failure.get("service_params", {})
                    }
                )
                success_count += 1
                
                # Mark as retried
                await query_db(f"""
                    UPDATE service_failures
                    SET retry_count = retry_count + 1,
                        last_retry_at = NOW()
                    WHERE payment_id = '{payment_id}'
                """)
            except Exception:
                continue
                
        return {"success": True, "retried": len(failures), "successful": success_count}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def deliver_service(payment_id: str, metadata: Dict[str, Any]) -> None:
    """Deliver service after successful payment."""
    try:
        # Extract service details from metadata
        service_type = metadata.get("service_type")
        customer_email = metadata.get("customer_email")
        service_params = metadata.get("service_params", {})
        
        if not service_type or not customer_email:
            logger.warning(f"Missing service details in metadata for payment {payment_id}")
            return
            
        # Record service delivery
        await query_db(f"""
            INSERT INTO service_deliveries (
                payment_id, service_type, customer_email,
                service_params, delivered_at, created_at
            ) VALUES (
                '{payment_id}', '{service_type}', '{customer_email}',
                '{json.dumps(service_params)}'::jsonb, NOW(), NOW()
            )
        """)
        
        # TODO: Add actual service delivery logic based on service_type
        # This could include:
        # - Sending emails
        # - Generating files
        # - Calling external APIs
        # - Triggering workflows
        
        logger.info(f"Successfully delivered service for payment {payment_id}")
        
    except Exception as e:
        logger.error(f"Failed to deliver service for payment {payment_id}: {str(e)}")
        # Record failure
        await query_db(f"""
            INSERT INTO service_failures (
                payment_id, error_message, failed_at, created_at
            ) VALUES (
                '{payment_id}', '{str(e)[:200]}', NOW(), NOW()
            )
        """)
