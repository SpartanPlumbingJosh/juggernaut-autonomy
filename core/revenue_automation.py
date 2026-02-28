"""
Revenue Automation System - Core logic for automated revenue generation.

Features:
- API integrations with multiple revenue sources
- Task execution with rate limiting
- Error handling and retries
- Database logging of all events
- 24-48 hour autonomous operation
"""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging
import requests
from ratelimit import limits, sleep_and_retry

from core.database import query_db, execute_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting configuration
MAX_CALLS_PER_HOUR = 100
ONE_HOUR = 3600

class RevenueAutomation:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.active_sources = config.get("active_sources", [])
        self.min_sleep = config.get("min_sleep", 60)
        self.max_sleep = config.get("max_sleep", 300)
        self.max_retries = config.get("max_retries", 3)
        self.session = requests.Session()
        
    @sleep_and_retry
    @limits(calls=MAX_CALLS_PER_HOUR, period=ONE_HOUR)
    def _call_api(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call with rate limiting."""
        try:
            response = self.session.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed: {str(e)}")
            raise

    def _log_revenue_event(self, event_data: Dict[str, Any]) -> bool:
        """Log revenue event to database."""
        try:
            sql = """
            INSERT INTO revenue_events (
                id, event_type, amount_cents, currency, source,
                metadata, recorded_at, created_at
            ) VALUES (
                gen_random_uuid(),
                %(event_type)s,
                %(amount_cents)s,
                %(currency)s,
                %(source)s,
                %(metadata)s,
                NOW(),
                NOW()
            )
            """
            execute_db(sql, event_data)
            return True
        except Exception as e:
            logger.error(f"Failed to log revenue event: {str(e)}")
            return False

    def _process_revenue_source(self, source: str) -> Tuple[int, int]:
        """Process a single revenue source."""
        successes = 0
        failures = 0
        
        # Get source configuration
        source_config = self.config.get("sources", {}).get(source, {})
        endpoint = source_config.get("endpoint")
        params = source_config.get("params", {})
        
        if not endpoint:
            logger.error(f"Missing endpoint for source: {source}")
            return 0, 0
            
        # Process with retries
        for attempt in range(self.max_retries):
            try:
                data = self._call_api(endpoint, params)
                
                # Parse and log revenue events
                events = self._parse_revenue_data(source, data)
                for event in events:
                    if self._log_revenue_event(event):
                        successes += 1
                    else:
                        failures += 1
                
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {source}: {str(e)}")
                if attempt == self.max_retries - 1:
                    failures += 1
                time.sleep(random.uniform(1, 3))
                
        return successes, failures

    def _parse_revenue_data(self, source: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse raw API data into revenue events."""
        events = []
        
        # Example parsing logic - should be customized per source
        if source == "example_source":
            for item in data.get("items", []):
                event = {
                    "event_type": "revenue",
                    "amount_cents": int(float(item.get("amount", 0)) * 100),
                    "currency": item.get("currency", "USD"),
                    "source": source,
                    "metadata": json.dumps({
                        "transaction_id": item.get("id"),
                        "details": item.get("details", {})
                    })
                }
                events.append(event)
                
        return events

    def run(self, duration_hours: int = 24) -> Dict[str, Any]:
        """Run automation system for specified duration."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        total_successes = 0
        total_failures = 0
        
        logger.info(f"Starting revenue automation for {duration_hours} hours")
        
        while datetime.now() < end_time:
            for source in self.active_sources:
                successes, failures = self._process_revenue_source(source)
                total_successes += successes
                total_failures += failures
                
                if datetime.now() >= end_time:
                    break
                    
            # Sleep before next iteration
            sleep_time = random.uniform(self.min_sleep, self.max_sleep)
            time.sleep(sleep_time)
            
        logger.info(f"Completed revenue automation run. Successes: {total_successes}, Failures: {total_failures}")
        
        return {
            "success": True,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

def start_revenue_automation(config: Dict[str, Any], duration_hours: int = 24) -> Dict[str, Any]:
    """Start the revenue automation system."""
    automation = RevenueAutomation(config)
    return automation.run(duration_hours)

__all__ = ["start_revenue_automation"]
