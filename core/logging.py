import logging
import sys
from typing import Any, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def log_action(
    action_type: str,
    message: str,
    level: str = "info",
    **kwargs: Any
) -> None:
    """Standardized action logging."""
    log_data = {
        "action": action_type,
        "message": message,
        **kwargs
    }
    
    if level == "error":
        logger.error(log_data)
    elif level == "warning":
        logger.warning(log_data)
    else:
        logger.info(log_data)
