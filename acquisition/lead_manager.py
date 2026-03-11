import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

class LeadManager:
    """Manage lead generation and qualification."""
    
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        
    def create_lead(self, source: str, contact_info: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new lead from a specific source."""
        try:
            lead_id = str(uuid.uuid4())
            metadata_json = json.dumps(metadata or {})
            
            self.execute_sql(f"""
                INSERT INTO leads (
                    id, source, contact_info, status, metadata, created_at
                ) VALUES (
                    '{lead_id}',
                    '{source.replace("'", "''")}',
                    '{json.dumps(contact_info).replace("'", "''")}',
                    'new',
                    '{metadata_json.replace("'", "''")}',
                    NOW()
                )
            """)
            
            return {"success": True, "lead_id": lead_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def qualify_lead(self, lead_id: str, score: float, notes: str = "") -> Dict[str, Any]:
        """Qualify a lead based on scoring."""
        try:
            self.execute_sql(f"""
                UPDATE leads
                SET status = 'qualified',
                    score = {score},
                    qualification_notes = '{notes.replace("'", "''")}',
                    qualified_at = NOW()
                WHERE id = '{lead_id}'
            """)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_leads(self, status: str = "new", limit: int = 100) -> List[Dict[str, Any]]:
        """Get leads by status."""
        try:
            result = self.execute_sql(f"""
                SELECT * FROM leads
                WHERE status = '{status}'
                ORDER BY created_at DESC
                LIMIT {limit}
            """)
            return result.get("rows", [])
        except Exception as e:
            return []
