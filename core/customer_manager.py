"""
Customer management system with lifecycle tracking and segmentation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.database import query_db, execute_db

class CustomerManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new customer record."""
        try:
            # Validate customer data
            if not self._validate_customer_data(customer_data):
                return {"success": False, "error": "Invalid customer data"}
                
            # Check for existing customer
            existing = await self._find_existing_customer(customer_data)
            if existing:
                return {"success": False, "error": "Customer already exists"}
                
            # Create customer record
            customer_id = await self._create_customer_record(customer_data)
            
            return {"success": True, "customer_id": customer_id}
            
        except Exception as e:
            self.logger.error(f"Customer creation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def _validate_customer_data(self, customer_data: Dict[str, Any]) -> bool:
        """Validate required customer fields."""
        required_fields = ["email", "first_name", "last_name"]
        return all(field in customer_data for field in required_fields)
        
    async def _find_existing_customer(self, customer_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for existing customer by email."""
        sql = """
        SELECT id FROM customers 
        WHERE email = %(email)s
        LIMIT 1
        """
        result = await query_db(sql, {"email": customer_data["email"]})
        return result["rows"][0] if result["rows"] else None
        
    async def _create_customer_record(self, customer_data: Dict[str, Any]) -> str:
        """Create customer record in database."""
        sql = """
        INSERT INTO customers (
            id, email, first_name, last_name,
            created_at, updated_at, status
        ) VALUES (
            gen_random_uuid(),
            %(email)s,
            %(first_name)s,
            %(last_name)s,
            NOW(),
            NOW(),
            'active'
        ) RETURNING id
        """
        result = await execute_db(sql, customer_data)
        return result["rows"][0]["id"]
        
    async def update_customer(self, customer_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update customer record."""
        try:
            # Validate update data
            if not update_data:
                return {"success": False, "error": "No update data provided"}
                
            # Update customer record
            await self._update_customer_record(customer_id, update_data)
            
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Customer update failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _update_customer_record(self, customer_id: str, update_data: Dict[str, Any]) -> None:
        """Update customer record in database."""
        sql = """
        UPDATE customers
        SET updated_at = NOW(),
            first_name = %(first_name)s,
            last_name = %(last_name)s
        WHERE id = %(customer_id)s
        """
        await execute_db(sql, {
            "customer_id": customer_id,
            **update_data
        })
        
    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Get customer details."""
        try:
            sql = """
            SELECT * FROM customers
            WHERE id = %(customer_id)s
            LIMIT 1
            """
            result = await query_db(sql, {"customer_id": customer_id})
            return {"success": True, "customer": result["rows"][0]}
        except Exception as e:
            self.logger.error(f"Failed to get customer: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def segment_customers(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Segment customers based on criteria."""
        try:
            sql = """
            SELECT * FROM customers
            WHERE status = 'active'
            AND created_at >= %(created_after)s
            """
            result = await query_db(sql, criteria)
            return {"success": True, "customers": result["rows"]}
        except Exception as e:
            self.logger.error(f"Customer segmentation failed: {str(e)}")
            return {"success": False, "error": str(e)}
