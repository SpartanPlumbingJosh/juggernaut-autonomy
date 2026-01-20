"""Scan handler for opportunity scanning tasks.

This module handles tasks of type 'scan' that run opportunity scans
to identify leads, market opportunities, or other business prospects.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base import BaseHandler, HandlerResult

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_SCAN_TYPE = "general"
OPPORTUNITIES_TABLE = "opportunities"
SCAN_LOG_TABLE = "opportunity_scans"


class ScanHandler(BaseHandler):
    """Handler for scan task type.
    
    Executes scanning tasks that identify opportunities, leads,
    or other business prospects from configured sources.
    """

    task_type = "scan"

    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        """Execute an opportunity scan task.
        
        Args:
            task: Task dictionary with payload containing:
                - scan_type (str, optional): Type of scan (general, domain, market, etc.)
                - source (str, optional): Source to scan
                - config (dict, optional): Scan configuration
        
        Returns:
            HandlerResult with scan results or error information.
        """
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload", {})

        scan_type = payload.get("scan_type", DEFAULT_SCAN_TYPE)
        source = payload.get("source", "unknown")
        config = payload.get("config", {})

        self._log(
            "handler.scan.starting",
            f"Starting {scan_type} scan from source: {source}",
            task_id=task_id
        )

        scan_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Log scan start
            self._record_scan_start(scan_id, scan_type, source, config, task_id)

            # Execute the scan
            scan_results = self._run_scan(scan_type, source, config, task_id)

            # Process and store any opportunities found
            opportunities_created = self._process_opportunities(
                scan_id,
                scan_results.get("opportunities", []),
                task_id
            )

            # Update scan record with results
            self._record_scan_complete(
                scan_id,
                scan_results,
                opportunities_created,
                task_id
            )

            result_data = {
                "executed": True,
                "scan_id": scan_id,
                "scan_type": scan_type,
                "source": source,
                "opportunities_found": len(scan_results.get("opportunities", [])),
                "opportunities_created": opportunities_created,
                "timestamp": now
            }

            self._log(
                "handler.scan.complete",
                f"Scan complete: found {len(scan_results.get('opportunities', []))} opportunities",
                task_id=task_id,
                output_data={
                    "scan_id": scan_id,
                    "opportunities_found": len(scan_results.get("opportunities", []))
                }
            )

            return HandlerResult(
                success=True,
                data=result_data,
                logs=self._execution_logs
            )

        except Exception as scan_error:
            error_msg = str(scan_error)
            
            # Try to mark scan as failed
            self._record_scan_failed(scan_id, error_msg)
            
            self._log(
                "handler.scan.failed",
                f"Scan failed: {error_msg[:200]}",
                level="error",
                task_id=task_id
            )
            
            return HandlerResult(
                success=False,
                data={
                    "scan_id": scan_id,
                    "scan_type": scan_type,
                    "source": source
                },
                error=error_msg,
                logs=self._execution_logs
            )

    def _run_scan(
        self,
        scan_type: str,
        source: str,
        config: Dict[str, Any],
        task_id: Optional[str]
    ) -> Dict[str, Any]:
        """Execute the actual scan logic.
        
        Args:
            scan_type: Type of scan to run.
            source: Source identifier.
            config: Scan configuration.
            task_id: Task ID for logging.
        
        Returns:
            Dictionary with scan results including opportunities found.
        """
        opportunities: List[Dict[str, Any]] = []
        
        # Different scan types may have different implementations
        if scan_type == "database_check":
            opportunities = self._scan_database_opportunities(config)
        elif scan_type == "expired_domains":
            opportunities = self._scan_expired_domains(config)
        elif scan_type == "market_trends":
            opportunities = self._scan_market_trends(config)
        else:
            # General scan - check for any pending opportunities
            opportunities = self._scan_general(config)

        self._log(
            "handler.scan.results",
            f"Scan type '{scan_type}' found {len(opportunities)} potential opportunities",
            task_id=task_id
        )

        return {
            "scan_type": scan_type,
            "source": source,
            "opportunities": opportunities,
            "scanned_at": datetime.now(timezone.utc).isoformat()
        }

    def _scan_database_opportunities(
        self,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Scan database for opportunity indicators.
        
        Args:
            config: Scan configuration.
        
        Returns:
            List of opportunity dictionaries.
        """
        opportunities = []
        
        try:
            # Check for stale leads that need follow-up
            sql = """
                SELECT COUNT(*) as stale_count 
                FROM governance_tasks 
                WHERE status = 'pending' 
                AND created_at < NOW() - INTERVAL '7 days'
            """
            result = self.execute_sql(sql)
            stale_count = result.get("rows", [{}])[0].get("stale_count", 0)
            
            if stale_count and int(stale_count) > 0:
                opportunities.append({
                    "type": "process_improvement",
                    "category": "task_management",
                    "description": f"{stale_count} stale tasks need attention",
                    "confidence": 0.8,
                    "estimated_value": int(stale_count) * 10,
                    "metadata": {"stale_count": stale_count}
                })
        except Exception as db_err:
            logger.warning("Database opportunity scan failed: %s", db_err)
        
        return opportunities

    def _scan_expired_domains(
        self,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Scan for expired domain opportunities.
        
        Args:
            config: Scan configuration.
        
        Returns:
            List of domain opportunity dictionaries.
        """
        # Placeholder for domain scanning integration
        # Would integrate with domain expiration APIs in production
        return []

    def _scan_market_trends(
        self,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Scan for market trend opportunities.
        
        Args:
            config: Scan configuration.
        
        Returns:
            List of market opportunity dictionaries.
        """
        # Placeholder for market trend integration
        # Would integrate with market data APIs in production
        return []

    def _scan_general(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run a general opportunity scan.
        
        Args:
            config: Scan configuration.
        
        Returns:
            List of opportunity dictionaries.
        """
        # Combine results from multiple scan types
        opportunities = []
        opportunities.extend(self._scan_database_opportunities(config))
        return opportunities

    def _process_opportunities(
        self,
        scan_id: str,
        opportunities: List[Dict[str, Any]],
        task_id: Optional[str]
    ) -> int:
        """Store discovered opportunities in the database.
        
        Args:
            scan_id: ID of the current scan.
            opportunities: List of opportunity dictionaries.
            task_id: Task ID for logging.
        
        Returns:
            Number of opportunities successfully created.
        """
        created_count = 0
        
        for opp in opportunities:
            try:
                opp_id = str(uuid4())
                now = datetime.now(timezone.utc).isoformat()
                
                opp_type = opp.get("type", "general")
                category = opp.get("category", "unknown")
                description = opp.get("description", "")[:500].replace("'", "''")
                confidence = opp.get("confidence", 0.5)
                value = opp.get("estimated_value", 0)
                metadata = json.dumps(opp.get("metadata", {})).replace("'", "''")
                
                # Check if opportunities table exists
                check_sql = f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{OPPORTUNITIES_TABLE}'
                    )
                """
                result = self.execute_sql(check_sql)
                if not result.get("rows", [{}])[0].get("exists", False):
                    self._log(
                        "handler.scan.table_missing",
                        f"Table {OPPORTUNITIES_TABLE} does not exist",
                        level="warn",
                        task_id=task_id
                    )
                    break
                
                insert_sql = f"""
                    INSERT INTO {OPPORTUNITIES_TABLE} 
                    (id, scan_id, opportunity_type, category, description, 
                     confidence_score, estimated_value, status, metadata, created_at)
                    VALUES (
                        '{opp_id}', '{scan_id}', '{opp_type}', '{category}',
                        '{description}', {confidence}, {value}, 'new',
                        '{metadata}'::jsonb, '{now}'
                    )
                """
                self.execute_sql(insert_sql)
                created_count += 1
                
            except Exception as insert_err:
                self._log(
                    "handler.scan.opportunity_insert_failed",
                    f"Failed to insert opportunity: {str(insert_err)[:100]}",
                    level="warn",
                    task_id=task_id
                )
        
        return created_count

    def _record_scan_start(
        self,
        scan_id: str,
        scan_type: str,
        source: str,
        config: Dict[str, Any],
        task_id: Optional[str]
    ) -> None:
        """Record scan start in the database.
        
        Args:
            scan_id: Unique scan identifier.
            scan_type: Type of scan.
            source: Scan source.
            config: Scan configuration.
            task_id: Task ID for logging.
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            config_json = json.dumps(config).replace("'", "''")
            
            sql = f"""
                INSERT INTO {SCAN_LOG_TABLE} 
                (id, scan_type, source, scan_config, status, started_at, triggered_by)
                VALUES (
                    '{scan_id}', '{scan_type}', '{source}', 
                    '{config_json}'::jsonb, 'running', '{now}', 'engine'
                )
            """
            self.execute_sql(sql)
        except Exception as record_err:
            # Log but don't fail the scan
            self._log(
                "handler.scan.record_start_failed",
                f"Failed to record scan start: {str(record_err)[:100]}",
                level="warn",
                task_id=task_id
            )

    def _record_scan_complete(
        self,
        scan_id: str,
        results: Dict[str, Any],
        opportunities_created: int,
        task_id: Optional[str]
    ) -> None:
        """Record scan completion in the database.
        
        Args:
            scan_id: Scan identifier.
            results: Scan results.
            opportunities_created: Count of opportunities created.
            task_id: Task ID for logging.
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            results_json = json.dumps(results).replace("'", "''")
            
            sql = f"""
                UPDATE {SCAN_LOG_TABLE}
                SET status = 'completed',
                    completed_at = '{now}',
                    opportunities_found = {len(results.get('opportunities', []))},
                    opportunities_qualified = {opportunities_created},
                    results_summary = '{results_json}'::jsonb
                WHERE id = '{scan_id}'
            """
            self.execute_sql(sql)
        except Exception as record_err:
            self._log(
                "handler.scan.record_complete_failed",
                f"Failed to record scan completion: {str(record_err)[:100]}",
                level="warn",
                task_id=task_id
            )

    def _record_scan_failed(self, scan_id: str, error_msg: str) -> None:
        """Record scan failure in the database.
        
        Args:
            scan_id: Scan identifier.
            error_msg: Error message.
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            escaped_error = error_msg[:500].replace("'", "''")
            
            sql = f"""
                UPDATE {SCAN_LOG_TABLE}
                SET status = 'failed',
                    completed_at = '{now}',
                    error_message = '{escaped_error}'
                WHERE id = '{scan_id}'
            """
            self.execute_sql(sql)
        except Exception:
            pass  # Best effort
