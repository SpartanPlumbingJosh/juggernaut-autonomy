"""
Automated Service Delivery Pipeline with Human Review.

Features:
- Code generation from templates
- Human-in-the-loop review
- Rate limiting
- Error handling
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.database import query_db

class DeliveryPipeline:
    """Manage automated service delivery with human review."""
    
    def __init__(self, execute_sql: callable, log_action: callable):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.rate_limit = 5  # Max requests per minute
        self.last_request_time = 0
        
    def _check_rate_limit(self) -> bool:
        """Enforce rate limiting."""
        now = time.time()
        if now - self.last_request_time < 60/self.rate_limit:
            return False
        self.last_request_time = now
        return True
        
    def generate_service_code(self, template_name: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Generate service code from template."""
        try:
            if not self._check_rate_limit():
                return False, "Rate limit exceeded"
                
            # Get template from database
            res = self.execute_sql(
                f"SELECT content FROM service_templates WHERE name = '{template_name}'"
            )
            if not res.get('rows'):
                return False, "Template not found"
                
            template = res['rows'][0]['content']
            
            # Simple template substitution (could be enhanced with Jinja2)
            for key, value in params.items():
                template = template.replace(f'{{{{{key}}}}}', str(value))
                
            return True, template
            
        except Exception as e:
            self.log_action(
                "service.code_generation_failed",
                f"Failed to generate code: {str(e)}",
                level="error"
            )
            return False, f"Generation error: {str(e)}"
            
    def submit_for_review(self, service_name: str, generated_code: str, requester: str) -> Tuple[bool, str]:
        """Submit generated service for human review."""
        try:
            res = self.execute_sql(
                f"""
                INSERT INTO service_reviews (
                    id, service_name, generated_code, 
                    requester, status, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{service_name}',
                    '{generated_code.replace("'", "''")}',
                    '{requester}',
                    'pending',
                    NOW()
                )
                RETURNING id
                """
            )
            review_id = res['rows'][0]['id']
            return True, review_id
            
        except Exception as e:
            self.log_action(
                "service.submission_failed",
                f"Failed to submit for review: {str(e)}",
                level="error"
            )
            return False, f"Submission error: {str(e)}"
            
    def get_review_status(self, review_id: str) -> Dict[str, Any]:
        """Check status of a review."""
        try:
            res = self.execute_sql(
                f"""
                SELECT status, feedback, approved_code, reviewer, reviewed_at
                FROM service_reviews
                WHERE id = '{review_id}'
                """
            )
            if not res.get('rows'):
                return {"success": False, "error": "Review not found"}
                
            row = res['rows'][0]
            return {
                "success": True,
                "status": row['status'],
                "feedback": row['feedback'],
                "approved_code": row['approved_code'],
                "reviewer": row['reviewer'],
                "reviewed_at": row['reviewed_at']
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def process_approved_services(self) -> Dict[str, Any]:
        """Process all approved services that haven't been deployed."""
        try:
            # Get approved services
            res = self.execute_sql(
                """
                SELECT id, service_name, approved_code
                FROM service_reviews
                WHERE status = 'approved'
                AND deployed_at IS NULL
                LIMIT 10
                """
            )
            services = res.get('rows', [])
            
            deployed = 0
            errors = []
            
            for service in services:
                try:
                    # Here you would add actual deployment logic
                    # For now we'll just mark as deployed
                    self.execute_sql(
                        f"""
                        UPDATE service_reviews
                        SET deployed_at = NOW()
                        WHERE id = '{service['id']}'
                        """
                    )
                    deployed += 1
                    
                    self.log_action(
                        "service.deployed",
                        f"Deployed service: {service['service_name']}",
                        level="info"
                    )
                    
                except Exception as e:
                    errors.append({
                        "service_id": service['id'],
                        "error": str(e)
                    })
                    
            return {
                "success": True,
                "deployed": deployed,
                "errors": errors
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
