"""
Autonomous Revenue Engine - Controls automated revenue generation strategies.
Features:
- Strategy execution with circuit breakers
- Rate limiting
- Transaction logging
- 24/7 operation monitoring
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

class RevenueEngine:
    """Main autonomous revenue engine controller"""

    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]], log_action: Callable[..., Any]):
        self.execute_sql = execute_sql
        self.log_action = log_action
        self.circuit_breaker = False
        self.last_run_at = None
        self.error_count = 0
        self.success_count = 0
    
    async def run_cycle(self, strategy_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute one full revenue generation cycle"""
        try:
            if self.circuit_breaker:
                return {"status": "circuit_breaker_tripped", "message": "Engine paused due to errors"}

            # Rate limit to 1 cycle per minute max
            if self.last_run_at and (datetime.utcnow() - self.last_run_at) < timedelta(minutes=1):
                return {"status": "rate_limited", "message": "Waiting for rate limit window"}

            self.last_run_at = datetime.utcnow()

            # Execute strategy pipeline
            results = {
                "ideas_generated": await self._generate_ideas(),
                "ideas_scored": await self._score_ideas(),
                "experiments_started": await self._start_experiments(),
                "experiments_reviewed": await self._review_experiments()
            }

            self.success_count += 1
            self.error_count = max(0, self.error_count - 1)  # Decay error count
            return {"status": "success", "results": results}

        except Exception as e:
            self.error_count += 1
            if self.error_count > 5:  # Trip circuit breaker
                self.circuit_breaker = True
            return {"status": "error", "error": str(e)}

    async def _generate_ideas(self) -> Dict[str, Any]:
        """Generate new revenue ideas"""
        try:
            result = generate_revenue_ideas(
                execute_sql=self.execute_sql,
                log_action=self.log_action,
                limit=10
            )
            await self._log_monitoring_event("idea_generation", result)
            return result
        except Exception as e:
            await self._log_error("idea_generation_failed", str(e))
            raise

    async def _score_ideas(self) -> Dict[str, Any]:
        """Score pending revenue ideas"""
        try:
            result = score_pending_ideas(
                execute_sql=self.execute_sql, 
                log_action=self.log_action,
                limit=20
            )
            await self._log_monitoring_event("idea_scoring", result)
            return result
        except Exception as e:
            await self._log_error("idea_scoring_failed", str(e))
            raise

    async def _start_experiments(self) -> Dict[str, Any]:
        """Start experiments from top ideas"""
        try:
            result = start_experiments_from_top_ideas(
                execute_sql=self.execute_sql,
                log_action=self.log_action,
                max_new=3,
                min_score=70.0
            )
            await self._log_monitoring_event("experiment_start", result)
            return result
        except Exception as e:
            await self._log_error("experiment_start_failed", str(e))
            raise

    async def _review_experiments(self) -> Dict[str, Any]:
        """Review running experiments"""
        try:
            result = review_experiments_stub(
                execute_sql=self.execute_sql,
                log_action=self.log_action
            )
            await self._log_monitoring_event("experiment_review", result)
            return result
        except Exception as e:
            await self._log_error("experiment_review_failed", str(e))
            raise

    async def _log_monitoring_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log monitoring event to database"""
        try:
            event_data = json.dumps({
                "type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "engine_status": {
                    "circuit_breaker": self.circuit_breaker,
                    "error_count": self.error_count,
                    "success_count": self.success_count
                }
            })
            await self.execute_sql(
                f"""
                INSERT INTO revenue_engine_logs (
                    id, event_type, event_data, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{event_type}',
                    '{event_data}'::jsonb,
                    NOW()
                )
                """
            )
        except Exception as e:
            await self.log_action(
                "logging_failed",
                f"Failed to log monitoring event: {str(e)}",
                level="error"
            )

    async def _log_error(self, error_type: str, message: str) -> None:
        """Log error with full context"""
        try:
            error_data = json.dumps({
                "type": error_type,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "engine_stack": {
                    "circuit_breaker": self.circuit_breaker,
                    "last_run": self.last_run_at.isoformat() if self.last_run_at else None,
                    "error_count": self.error_count,
                    "success_count": self.success_count
                }
            })
            await self.execute_sql(
                f"""
                INSERT INTO revenue_engine_errors (
                    id, error_type, error_data, created_at
                ) VALUES (
                    gen_random_uuid(),
                    '{error_type}',
                    '{error_data}'::jsonb,
                    NOW()
                )
                """
            )
            
            # Also log to global action logs
            await self.log_action(
                f"engine.error.{error_type}", 
                message,
                level="error",
                error_data=json.loads(error_data)
            )
        except Exception as e:
            print(f"CRITICAL: Failed to log error: {str(e)}")


async def run_engine_continuously(engine: RevenueEngine, interval_minutes: int = 5):
    """Run engine in continuous mode with health monitoring"""
    while True:
        start_time = datetime.utcnow()
        
        try:
            result = await engine.run_cycle()
            status = result.get("status", "unknown")
            
            if status == "success":
                await engine.log_action(
                    "engine.cycle_completed",
                    "Revenue engine cycle completed successfully",
                    level="info",
                    output_data=result
                )
            elif status == "circuit_breaker_tripped":
                # Attempt auto-reset after 1 hour
                if (datetime.utcnow() - start_time) > timedelta(hours=1):
                    engine.circuit_breaker = False
                    engine.error_count = 0

        except Exception as e:
            await engine.log_action(
                "engine.cycle_failed",
                f"Revenue engine cycle failed: {str(e)}",
                level="critical",
                error_data={"error": str(e)}
            )

        # Calculate sleep time accounting for execution duration
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        sleep_time = max(0, (interval_minutes * 60) - elapsed)
        await asyncio.sleep(sleep_time)
