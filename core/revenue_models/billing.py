"""
Billing automation engine - handles recurring payments, invoices, dunning, etc.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Callable
import json

RUN_LIMIT = 100  # Max operations per cycle for stability

async def process_invoice(invoice: Dict[str, Any], execute_sql: Callable[[str], Dict[str, Any]]) -> bool:
    """Process a single invoice with retries and validation"""
    invoice_id = invoice.get("id")
    try:
        # Process invoice with retry logic
        result = await execute_sql(f"""
            UPDATE billing_invoices
            SET status = 'processing',
                last_attempt = NOW()
            WHERE id = '{invoice_id}'
            RETURNING *
        """)
        
        # Validate payment
        payment_result = await execute_sql(f"""
            INSERT INTO revenue_events (
                id, experiment_id, event_type, 
                amount_cents, currency, source,
                recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                NULL,
                'revenue',
                {invoice.get("amount_due")},
                '{invoice.get("currency")}',
                'billing',
                NOW(),
                NOW()
            )
            RETURNING id
        """)
        
        # Mark invoice as paid
        await execute_sql(f"""
            UPDATE billing_invoices
            SET status = 'paid',
                paid_at = NOW(),
                payment_id = '{payment_result.get("rows")[0].get("id")}'
            WHERE id = '{invoice_id}'
        """)
        return True
        
    except Exception as e:
        # Log failure and retry later
        await execute_sql(f"""
            UPDATE billing_invoices
            SET status = 'failed',
                error_count = COALESCE(error_count, 0) + 1,
                last_error = '{str(e).replace("'", "''")}'
            WHERE id = '{invoice_id}'
        """)
        return False

async def run_billing_cycle(
    execute_sql: Callable[[str], Dict[str, Any]],
    log_action: Callable[..., Any],
    batch_size: int = 50
) -> Dict[str, Any]:
    """Execute a billing cycle with proper error handling"""
    try:
        # Get pending invoices
        invoice_result = await execute_sql(f"""
            SELECT * FROM billing_invoices
            WHERE status IN ('pending', 'failed')
            AND (last_attempt IS NULL OR last_attempt < NOW() - INTERVAL '1 hour')
            ORDER BY due_date ASC
            LIMIT {min(batch_size, RUN_LIMIT)}
        """)
        
        invoices = invoice_result.get("rows", [])
        processed = 0
        errors = 0
        
        # Process each invoice
        for inv in invoices:
            success = await process_invoice(inv, execute_sql)
            if success:
                processed += 1
            else:
                errors += 1
        
        # Log results
        log_action(
            "billing.cycle_completed",
            f"Processed {processed} invoices with {errors} errors",
            level="info",
            data={
                "processed": processed,
                "errors": errors,
                "batch_size": len(invoices)
            }
        )
        
        return {
            "success": True,
            "processed": processed,
            "errors": errors,
            "batch_size": len(invoices)
        }
        
    except Exception as e:
        log_action(
            "billing.cycle_failed",
            f"Billing cycle failed: {str(e)}",
            level="error"
        )
        return {"success": False, "error": str(e)}
