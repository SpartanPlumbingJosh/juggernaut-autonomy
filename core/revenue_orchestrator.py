"""
Revenue Strategy Orchestrator - Automates execution of revenue generation strategies.

Features:
- Automated idea generation and scoring
- Experiment portfolio management
- Revenue tracking and optimization
- Comprehensive logging and error handling
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.portfolio_manager import (
    generate_revenue_ideas,
    score_pending_ideas,
    start_experiments_from_top_ideas,
    review_experiments_stub
)
from core.database import query_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RevenueOrchestrator:
    def __init__(self, execute_sql: callable):
        self.execute_sql = execute_sql
        self.min_score = 60.0
        self.max_new_experiments = 3
        self.experiment_budget = 100.0
        
    def log_action(self, action: str, message: str, level: str = "info", **kwargs):
        """Standardized logging for all actions."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "message": message,
            **kwargs
        }
        
        log_msg = f"{action}: {message}"
        if level == "error":
            logger.error(log_msg, extra=log_data)
        elif level == "warning":
            logger.warning(log_msg, extra=log_data)
        else:
            logger.info(log_msg, extra=log_data)
            
        # Persist log to database
        try:
            self.execute_sql(
                f"""
                INSERT INTO system_logs (action, message, level, metadata)
                VALUES (
                    '{action.replace("'", "''")}',
                    '{message.replace("'", "''")}',
                    '{level}',
                    '{json.dumps(kwargs).replace("'", "''")}'::jsonb
                )
                """
            )
        except Exception as e:
            logger.error(f"Failed to persist log: {str(e)}")

    def run_full_cycle(self) -> Dict[str, Any]:
        """Execute complete revenue strategy cycle."""
        results = {}
        
        try:
            # Step 1: Generate new revenue ideas
            results['idea_generation'] = generate_revenue_ideas(
                execute_sql=self.execute_sql,
                log_action=self.log_action
            )
            
            # Step 2: Score pending ideas
            results['idea_scoring'] = score_pending_ideas(
                execute_sql=self.execute_sql,
                log_action=self.log_action
            )
            
            # Step 3: Start new experiments
            results['experiment_start'] = start_experiments_from_top_ideas(
                execute_sql=self.execute_sql,
                log_action=self.log_action,
                max_new=self.max_new_experiments,
                min_score=self.min_score,
                budget=self.experiment_budget
            )
            
            # Step 4: Review running experiments
            results['experiment_review'] = review_experiments_stub(
                execute_sql=self.execute_sql,
                log_action=self.log_action
            )
            
            self.log_action(
                "cycle_completed",
                "Revenue strategy cycle completed successfully",
                results=results
            )
            
        except Exception as e:
            self.log_action(
                "cycle_failed",
                f"Revenue strategy cycle failed: {str(e)}",
                level="error",
                error=str(e)
            )
            results['error'] = str(e)
            
        return results

def create_orchestrator() -> RevenueOrchestrator:
    """Factory function to create orchestrator instance."""
    return RevenueOrchestrator(execute_sql=query_db)
