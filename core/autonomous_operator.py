"""
Autonomous Revenue Operator - Core scheduling and coordination for 24/7 operation.
"""
import time
from typing import Dict, Any, Callable

class AutonomousOperator:
    def __init__(self):
        self.cycle_count = 0
        self.health_status = "OK"
        self.last_cycle_time = 0
        self.performance_metrics = {}
        
    def run_cycle(
        self,
        execute_sql: Callable[[str], Dict[str, Any]],
        log_action: Callable[..., Any],
    ) -> Dict[str, Any]:
        """Execute one full cycle of autonomous operation"""
        try:
            # Phase 1: Generate revenue ideas
            from core.portfolio_manager import generate_revenue_ideas
            idea_results = generate_revenue_ideas(
                execute_sql,
                log_action,
                autonomous_mode=True
            )
            
            # Phase 2: Score and prioritize ideas
            from core.portfolio_manager import score_pending_ideas
            scoring_results = score_pending_ideas(execute_sql, log_action)
            
            # Phase 3: Launch new experiments
            from core.portfolio_manager import start_experiments_from_top_ideas
            experiment_results = start_experiments_from_top_ideas(
                execute_sql,
                log_action
            )
            
            # Phase 4: Monitor running experiments
            from core.portfolio_manager import autonomously_monitor_experiments
            monitoring_results = autonomously_monitor_experiments(
                execute_sql,
                log_action
            )
            
            # Update performance metrics
            self.cycle_count += 1
            self.last_cycle_time = time.time()
            
            return {
                "status": "completed",
                "cycle_count": self.cycle_count,
                "idea_generation": idea_results,
                "idea_scoring": scoring_results, 
                "experiment_launch": experiment_results,
                "experiment_monitoring": monitoring_results
            }
            
        except Exception as e:
            self.health_status = "ERROR"
            return {
                "status": "error",
                "error": str(e),
                "cycle_count": self.cycle_count
            }
