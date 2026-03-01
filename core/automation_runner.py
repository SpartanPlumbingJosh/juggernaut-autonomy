"""
Continuous automation runner for the revenue system.
"""

import time
from core.portfolio_manager import initialize_automation_engine
from core.database import query_db
from core.logging import log_action

def run_automation():
    engine = initialize_automation_engine(query_db, log_action)
    
    while True:
        try:
            # Run automation cycle
            result = engine.run_cycle()
            
            if not result.get("success"):
                log_action(
                    "automation.error",
                    f"Automation cycle failed: {result.get('error')}",
                    level="error"
                )
                
            # Wait before next cycle
            time.sleep(60)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_action(
                "automation.critical_error",
                f"Critical automation error: {str(e)}",
                level="critical"
            )
            time.sleep(300)  # Wait longer after critical errors

if __name__ == "__main__":
    run_automation()
