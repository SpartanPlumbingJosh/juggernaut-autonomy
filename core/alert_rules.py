"""
Alert Rules Engine

Evaluates error patterns and triggers task creation when rules match.

Part of Milestone 3: Railway Logs Crawler
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from core.database import fetch_all, execute_sql

logger = logging.getLogger(__name__)


class AlertRulesEngine:
    """Evaluates alert rules and triggers actions."""
    
    def get_active_rules(self) -> List[Dict[str, Any]]:
        """Get all enabled alert rules."""
        try:
            query = """
                SELECT 
                    id,
                    name,
                    rule_type,
                    condition,
                    action,
                    cooldown_minutes,
                    last_triggered
                FROM log_alert_rules
                WHERE enabled = TRUE
                ORDER BY rule_type
            """
            return fetch_all(query)
        except Exception as e:
            logger.exception(f"Error fetching alert rules: {e}")
            return []
    
    def is_in_cooldown(self, rule: Dict[str, Any]) -> bool:
        """Check if rule is in cooldown period."""
        last_triggered = rule.get('last_triggered')
        if not last_triggered:
            return False
        
        cooldown_minutes = int(rule.get('cooldown_minutes', 30))
        
        # Parse last_triggered timestamp
        if isinstance(last_triggered, str):
            last_triggered = datetime.fromisoformat(last_triggered.replace('Z', '+00:00'))
        
        # Ensure timezone-aware (handle naive datetimes from database)
        if last_triggered.tzinfo is None:
            last_triggered = last_triggered.replace(tzinfo=timezone.utc)
        
        cooldown_until = last_triggered + timedelta(minutes=cooldown_minutes)
        return datetime.now(timezone.utc) < cooldown_until
    
    def update_rule_triggered(self, rule_id: str):
        """Update rule's last triggered timestamp."""
        try:
            query = """
                UPDATE log_alert_rules
                SET 
                    last_triggered = %s,
                    trigger_count = trigger_count + 1,
                    updated_at = %s
                WHERE id = %s
            """
            execute_sql(query, (
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                rule_id
            ))
        except Exception as e:
            logger.exception(f"Error updating rule trigger: {e}")
    
    def check_new_fingerprint_rule(self, rule: Dict[str, Any]) -> List[str]:
        """
        Check for new error fingerprints.
        
        Returns:
            List of fingerprint IDs that triggered the rule
        """
        try:
            # Get fingerprints created in last 5 minutes that don't have tasks
            query = """
                SELECT id, fingerprint, normalized_message, error_type
                FROM error_fingerprints
                WHERE 
                    task_created = FALSE
                    AND status = 'active'
                    AND first_seen > %s
                ORDER BY first_seen DESC
            """
            
            five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            results = fetch_all(query, (five_min_ago.isoformat(),))
            
            return [str(r['id']) for r in results]
        except Exception as e:
            logger.exception(f"Error checking new fingerprint rule: {e}")
            return []
    
    def check_spike_rule(self, rule: Dict[str, Any]) -> List[str]:
        """
        Check for error rate spikes.
        
        Returns:
            List of fingerprint IDs that triggered the rule
        """
        try:
            condition = rule.get('condition', {})
            if isinstance(condition, str):
                import json
                condition = json.loads(condition)
            
            rate_threshold = int(condition.get('rate_per_minute', 10))
            window_minutes = int(condition.get('window_minutes', 5))
            
            # Get fingerprints with high occurrence rate
            query = """
                SELECT 
                    f.id,
                    f.fingerprint,
                    COUNT(o.id) as recent_count
                FROM error_fingerprints f
                JOIN error_occurrences o ON o.fingerprint_id = f.id
                WHERE 
                    o.occurred_at > %s
                    AND f.task_created = FALSE
                    AND f.status = 'active'
                GROUP BY f.id, f.fingerprint
                HAVING COUNT(o.id) >= %s
            """
            
            since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            results = fetch_all(query, (since.isoformat(), rate_threshold * window_minutes))
            
            return [str(r['id']) for r in results]
        except Exception as e:
            logger.exception(f"Error checking spike rule: {e}")
            return []
    
    def check_sustained_rule(self, rule: Dict[str, Any]) -> List[str]:
        """
        Check for sustained errors.
        
        Returns:
            List of fingerprint IDs that triggered the rule
        """
        try:
            condition = rule.get('condition', {})
            if isinstance(condition, str):
                import json
                condition = json.loads(condition)
            
            duration_minutes = int(condition.get('duration_minutes', 5))
            min_occurrences = int(condition.get('min_occurrences', 3))
            
            # Get fingerprints with sustained occurrences
            query = """
                SELECT 
                    f.id,
                    f.fingerprint,
                    MIN(o.occurred_at) as first_occurrence,
                    MAX(o.occurred_at) as last_occurrence,
                    COUNT(o.id) as occurrence_count
                FROM error_fingerprints f
                JOIN error_occurrences o ON o.fingerprint_id = f.id
                WHERE 
                    o.occurred_at > %s
                    AND f.task_created = FALSE
                    AND f.status = 'active'
                GROUP BY f.id, f.fingerprint
                HAVING COUNT(o.id) >= %s
            """
            
            since = datetime.now(timezone.utc) - timedelta(minutes=duration_minutes)
            results = fetch_all(query, (since.isoformat(), min_occurrences))
            
            return [str(r['id']) for r in results]
        except Exception as e:
            logger.exception(f"Error checking sustained rule: {e}")
            return []
    
    def check_critical_rule(self, rule: Dict[str, Any]) -> List[str]:
        """
        Check for critical level errors.
        
        Returns:
            List of fingerprint IDs that triggered the rule
        """
        try:
            # Get fingerprints from CRITICAL logs without tasks
            query = """
                SELECT DISTINCT f.id
                FROM error_fingerprints f
                JOIN railway_logs l ON l.fingerprint = f.fingerprint
                WHERE 
                    l.log_level = 'CRITICAL'
                    AND f.task_created = FALSE
                    AND f.status = 'active'
                    AND l.timestamp > %s
            """
            
            five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            results = fetch_all(query, (five_min_ago,))
            
            return [str(r['id']) for r in results]
        except Exception as e:
            logger.exception(f"Error checking critical rule: {e}")
            return []
    
    def evaluate_rule(self, rule: Dict[str, Any]) -> List[str]:
        """
        Evaluate a single rule.
        
        Returns:
            List of fingerprint IDs that triggered the rule
        """
        rule_type = rule.get('rule_type')
        
        if rule_type == 'new_fingerprint':
            return self.check_new_fingerprint_rule(rule)
        elif rule_type == 'spike':
            return self.check_spike_rule(rule)
        elif rule_type == 'sustained':
            return self.check_sustained_rule(rule)
        elif rule_type == 'critical':
            return self.check_critical_rule(rule)
        else:
            logger.warning(f"Unknown rule type: {rule_type}")
            return []
    
    def evaluate_all_rules(self) -> Dict[str, List[str]]:
        """
        Evaluate all active rules.
        
        Returns:
            Dict mapping rule IDs to lists of triggered fingerprint IDs
        """
        triggered = {}
        rules = self.get_active_rules()
        
        for rule in rules:
            rule_id = str(rule['id'])
            
            # Check cooldown
            if self.is_in_cooldown(rule):
                logger.debug(f"Rule {rule['name']} is in cooldown")
                continue
            
            # Evaluate rule
            fingerprint_ids = self.evaluate_rule(rule)
            
            if fingerprint_ids:
                triggered[rule_id] = fingerprint_ids
                logger.info(f"Rule {rule['name']} triggered for {len(fingerprint_ids)} fingerprints")
                
                # Update rule trigger timestamp
                self.update_rule_triggered(rule_id)
        
        return triggered


# Singleton instance
_alert_engine = None


def get_alert_engine() -> AlertRulesEngine:
    """Get or create alert engine singleton."""
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = AlertRulesEngine()
    return _alert_engine


__all__ = ["AlertRulesEngine", "get_alert_engine"]
