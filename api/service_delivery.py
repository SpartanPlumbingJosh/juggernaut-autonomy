"""
Service Delivery API - Handles automated service delivery pipelines
including code generation, content creation, and data processing.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from core.pipelines import (
    CodeGenerationPipeline,
    ContentCreationPipeline,
    DataProcessingPipeline
)
from core.database import query_db

PIPELINES = {
    "code_generation": CodeGenerationPipeline,
    "content_creation": ContentCreationPipeline,
    "data_processing": DataProcessingPipeline
}

async def execute_pipeline(pipeline_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a service delivery pipeline."""
    try:
        if pipeline_type not in PIPELINES:
            return {"error": "Invalid pipeline type"}
            
        pipeline = PIPELINES[pipeline_type]()
        result = await pipeline.execute(params)
        
        # Log pipeline execution
        await query_db(
            f"""
            INSERT INTO pipeline_executions (
                id, pipeline_type, params, 
                result, created_at
            ) VALUES (
                gen_random_uuid(),
                '{pipeline_type}',
                '{json.dumps(params)}'::jsonb,
                '{json.dumps(result)}'::jsonb,
                NOW()
            )
            """
        )
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"error": f"Pipeline execution failed: {str(e)}"}

async def route_service_request(path: str, method: str, body: Optional[str] = None) -> Dict[str, Any]:
    """Route service delivery API requests."""
    if method != "POST":
        return {"error": "Method not allowed"}
    
    try:
        data = json.loads(body or "{}")
        pipeline_type = data.get("pipeline_type")
        params = data.get("params", {})
        
        if path == "/service/execute":
            return await execute_pipeline(pipeline_type, params)
            
        return {"error": "Invalid endpoint"}
        
    except Exception as e:
        return {"error": f"Request processing failed: {str(e)}"}

__all__ = ["route_service_request"]
