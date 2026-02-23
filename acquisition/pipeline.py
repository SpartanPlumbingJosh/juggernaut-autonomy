from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

class AcquisitionSource(Enum):
    ORGANIC = "organic"
    PAID = "paid"
    REFERRAL = "referral"
    PARTNERSHIP = "partnership"
    CONTENT = "content"

class OnboardingStage(Enum):
    LEAD = "lead"
    MQL = "mql"
    TRIAL = "trial"
    CONVERTED = "converted"
    CHURNED = "churned"

class AcquisitionPipeline:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action

    async def track_acquisition(self, source: AcquisitionSource, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Track a new customer acquisition"""
        try:
            metadata_json = json.dumps(metadata).replace("'", "''")
            res = await self.execute_sql(f"""
                INSERT INTO acquisitions (
                    id, source, metadata, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{source.value}',
                    '{metadata_json}'::jsonb,
                    NOW(),
                    NOW()
                )
                RETURNING id
            """)
            return {"success": True, "acquisition_id": res.get("rows", [{}])[0].get("id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_onboarding_stage(self, acquisition_id: str, stage: OnboardingStage) -> Dict[str, Any]:
        """Update a customer's onboarding stage"""
        try:
            await self.execute_sql(f"""
                UPDATE acquisitions
                SET stage = '{stage.value}',
                    updated_at = NOW()
                WHERE id = '{acquisition_id}'
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_acquisition_metrics(self) -> Dict[str, Any]:
        """Get key acquisition metrics"""
        try:
            # CAC by source
            cac_res = await self.execute_sql("""
                SELECT source,
                       AVG(metadata->>'cac') as avg_cac,
                       COUNT(*) as count
                FROM acquisitions
                GROUP BY source
            """)
            
            # Conversion rates
            conversion_res = await self.execute_sql("""
                SELECT stage,
                       COUNT(*) as count,
                       AVG((metadata->>'time_to_convert')::numeric) as avg_time_to_convert
                FROM acquisitions
                GROUP BY stage
            """)
            
            # Payback period
            payback_res = await self.execute_sql("""
                SELECT AVG((metadata->>'payback_period')::numeric) as avg_payback_period
                FROM acquisitions
                WHERE stage = 'converted'
            """)
            
            return {
                "success": True,
                "cac_by_source": cac_res.get("rows", []),
                "conversion_rates": conversion_res.get("rows", []),
                "avg_payback_period": payback_res.get("rows", [{}])[0].get("avg_payback_period")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
