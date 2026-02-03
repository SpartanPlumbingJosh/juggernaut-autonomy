"""
Log Crawler Scheduler

Fetches logs from Railway, fingerprints errors, and triggers alerts.

Part of Milestone 3: Railway Logs Crawler
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from core.railway_client import get_railway_client
from core.error_fingerprinter import get_fingerprinter
from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class LogCrawler:
    """Crawls Railway logs and processes errors."""
    
    def __init__(self):
        self.railway_client = get_railway_client()
        self.fingerprinter = get_fingerprinter()
        self.project_id = None
        self.environment_id = None
    
    def get_last_run_state(self) -> Optional[Dict[str, Any]]:
        """Get the last crawler run state from database."""
        try:
            query = """
                SELECT 
                    last_run,
                    last_log_timestamp,
                    logs_processed,
                    errors_found,
                    status
                FROM log_crawler_state
                ORDER BY updated_at DESC
                LIMIT 1
            """
            results = fetch_all(query)
            return results[0] if results else None
        except Exception as e:
            logger.exception(f"Error fetching crawler state: {e}")
            return None
    
    def update_crawler_state(
        self,
        status: str,
        logs_processed: int = 0,
        errors_found: int = 0,
        tasks_created: int = 0,
        run_duration_ms: int = 0,
        error_message: Optional[str] = None,
        progress_message: Optional[str] = None
    ):
        """Update crawler state in database."""
        try:
            query = """
                INSERT INTO log_crawler_state (
                    last_run,
                    last_log_timestamp,
                    logs_processed,
                    errors_found,
                    tasks_created,
                    run_duration_ms,
                    status,
                    error_message,
                    progress_message,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                logs_processed,
                errors_found,
                tasks_created,
                run_duration_ms,
                status,
                error_message,
                progress_message,
                datetime.now(timezone.utc).isoformat()
            )
            execute_sql(query, params)
        except Exception as e:
            logger.exception(f"Error updating crawler state: {e}")
    
    def store_log(self, log_entry: Dict[str, Any]) -> Optional[str]:
        """Store a log entry in database."""
        try:
            query = """
                INSERT INTO railway_logs (
                    project_id,
                    environment_id,
                    log_level,
                    message,
                    timestamp,
                    raw_log,
                    fingerprint
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            params = (
                log_entry.get('project_id'),
                log_entry.get('environment_id'),
                log_entry.get('level', 'INFO'),
                log_entry.get('message', ''),
                log_entry.get('timestamp', datetime.now(timezone.utc).isoformat()),
                json.dumps(log_entry.get('raw', {})),
                log_entry.get('fingerprint')
            )
            
            result = fetch_all(query, params)
            return str(result[0]['id']) if result else None
        except Exception as e:
            logger.exception(f"Error storing log: {e}")
            return None
    
    def get_or_create_fingerprint(
        self,
        fingerprint: str,
        normalized_message: str,
        error_type: str,
        stack_trace: Optional[str],
        sample_log_id: str
    ) -> Optional[str]:
        """Get existing fingerprint or create new one."""
        try:
            # Check if fingerprint exists
            check_query = """
                SELECT id, occurrence_count
                FROM error_fingerprints
                WHERE fingerprint = %s
            """
            existing = fetch_all(check_query, (fingerprint,))
            
            if existing:
                # Update existing fingerprint
                fingerprint_id = str(existing[0]['id'])
                count = int(existing[0]['occurrence_count'])
                
                update_query = """
                    UPDATE error_fingerprints
                    SET 
                        last_seen = %s,
                        occurrence_count = %s,
                        updated_at = %s
                    WHERE fingerprint = %s
                """
                execute_sql(update_query, (
                    datetime.now(timezone.utc).isoformat(),
                    count + 1,
                    datetime.now(timezone.utc).isoformat(),
                    fingerprint
                ))
                
                return fingerprint_id
            else:
                # Create new fingerprint
                insert_query = """
                    INSERT INTO error_fingerprints (
                        fingerprint,
                        normalized_message,
                        error_type,
                        first_seen,
                        last_seen,
                        occurrence_count,
                        sample_log_id,
                        stack_trace,
                        status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                params = (
                    fingerprint,
                    normalized_message,
                    error_type,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    1,
                    sample_log_id,
                    stack_trace,
                    'active'
                )
                
                result = fetch_all(insert_query, params)
                return str(result[0]['id']) if result else None
        except Exception as e:
            logger.exception(f"Error managing fingerprint: {e}")
            return None
    
    def record_occurrence(self, fingerprint_id: str, log_id: str, occurred_at: str):
        """Record an error occurrence."""
        try:
            query = """
                INSERT INTO error_occurrences (
                    fingerprint_id,
                    log_id,
                    occurred_at
                ) VALUES (%s, %s, %s)
            """
            execute_sql(query, (fingerprint_id, log_id, occurred_at))
        except Exception as e:
            logger.exception(f"Error recording occurrence: {e}")
    
    def process_log_entry(self, log_entry: Dict[str, Any]) -> bool:
        """
        Process a single log entry.
        
        Returns:
            True if error was found and processed
        """
        level = log_entry.get('level', 'INFO').upper()
        message = log_entry.get('message', '')
        
        # Only process ERROR, CRITICAL, and WARN logs
        if level not in ['ERROR', 'CRITICAL', 'WARN']:
            return False
        
        # Filter out false positives
        # Skip successful HTTP responses (200, 201, 204, etc.)
        if 'http/' in message.lower() and any(code in message for code in [' 200 ', ' 201 ', ' 204 ', ' 304 ']):
            return False
        
        # Skip INFO level messages that got mislabeled
        if message.lower().startswith('info:'):
            return False
        
        # Skip health check warnings that are transient
        if 'stale_workers' in message.lower() and level == 'WARN':
            # Only flag if it's a real error, not just a warning
            return False
        
        # Fingerprint the error
        fingerprinted = self.fingerprinter.fingerprint_log(log_entry)
        
        # Store the log
        log_id = self.store_log(fingerprinted)
        if not log_id:
            return False
        
        # Get or create fingerprint
        fingerprint_id = self.get_or_create_fingerprint(
            fingerprinted['fingerprint'],
            fingerprinted['normalized_message'],
            fingerprinted.get('error_type', 'UnknownError'),
            fingerprinted.get('stack_trace'),
            log_id
        )
        
        if not fingerprint_id:
            return False
        
        # Record occurrence
        self.record_occurrence(
            fingerprint_id,
            log_id,
            fingerprinted.get('timestamp', datetime.now(timezone.utc).isoformat())
        )
        
        return True
    
    def crawl(self, project_id: str = None, environment_id: str = None) -> Dict[str, Any]:
        """
        Run a crawl cycle by reading from execution_logs database.
        
        Args:
            project_id: Railway project ID (unused, kept for compatibility)
            environment_id: Railway environment ID (unused, kept for compatibility)
            
        Returns:
            Crawl statistics
        """
        start_time = datetime.now(timezone.utc)
        logs_processed = 0
        errors_found = 0
        
        try:
            self.update_crawler_state('running')
            
            # Read logs directly from database instead of Railway API
            from core.database import fetch_all
            
            query = """
                SELECT 
                    level,
                    message,
                    error_data,
                    created_at as timestamp
                FROM execution_logs
                WHERE level IN ('error', 'warn')
                AND created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT 100
            """
            
            logs = fetch_all(query)
            
            if not logs:
                logger.info("No error/warn logs found in last hour")
                self.update_crawler_state('idle', 0, 0, 0, 0)
                return {
                    'success': True,
                    'message': 'No errors found',
                    'logs_processed': 0,
                    'errors_found': 0
                }
            
            # Process each log
            total_logs = len(logs)
            for idx, log_entry in enumerate(logs, 1):
                logs_processed += 1
                
                # Convert database log to expected format
                formatted_log = {
                    'level': log_entry.get('level', 'ERROR'),
                    'message': log_entry.get('message', ''),
                    'timestamp': log_entry.get('timestamp'),
                    'error_data': log_entry.get('error_data')
                }
                
                # Update progress
                msg_preview = formatted_log['message'][:60] + '...' if len(formatted_log['message']) > 60 else formatted_log['message']
                progress_msg = f"[{idx}/{total_logs}] Processing: {msg_preview}"
                self.update_crawler_state('running', logs_processed, errors_found, 0, 0, None, progress_msg)
                logger.info(progress_msg)
                
                # Process the log
                if self.process_log_entry(formatted_log):
                    errors_found += 1
                    result_msg = f"[{idx}/{total_logs}] Error found: {formatted_log['level']}"
                    self.update_crawler_state('running', logs_processed, errors_found, 0, 0, None, result_msg)
                    logger.info(result_msg)
                else:
                    result_msg = f"[{idx}/{total_logs}] Filtered/Clean"
                    self.update_crawler_state('running', logs_processed, errors_found, 0, 0, None, result_msg)
                    logger.info(result_msg)
            
            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update state
            self.update_crawler_state(
                'idle',
                logs_processed,
                errors_found,
                0,  # tasks_created (will be updated by alert engine)
                duration_ms
            )
            
            return {
                'success': True,
                'logs_processed': logs_processed,
                'errors_found': errors_found,
                'duration_ms': duration_ms
            }
            
        except Exception as e:
            logger.exception(f"Error during crawl: {e}")
            
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            self.update_crawler_state(
                'error',
                logs_processed,
                errors_found,
                0,
                duration_ms,
                str(e)
            )
            
            return {
                'success': False,
                'error': str(e),
                'logs_processed': logs_processed,
                'errors_found': errors_found
            }


# Singleton instance
_log_crawler = None


def get_log_crawler() -> LogCrawler:
    """Get or create log crawler singleton."""
    global _log_crawler
    if _log_crawler is None:
        _log_crawler = LogCrawler()
    return _log_crawler


__all__ = ["LogCrawler", "get_log_crawler"]
