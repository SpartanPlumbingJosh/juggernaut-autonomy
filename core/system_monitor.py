from typing import Dict, Any
import psutil
import time

class SystemMonitor:
    """Monitors system health and performs self-healing."""
    
    def check_system_health(self) -> Dict[str, Any]:
        """Check critical system metrics."""
        status = {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent,
            "timestamp": time.time()
        }
        
        if status["memory"] > 90:
            self._free_up_memory()
            
        return status
    
    def _free_up_memory(self) -> bool:
        """Attempt to free up system memory."""
        try:
            import gc
            gc.collect()
            return True
        except Exception:
            return False
