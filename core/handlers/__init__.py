"""
Task Handlers for JUGGERNAUT Autonomy Engine
============================================
Each handler is responsible for executing a specific task type
and logging what actions it actually performed.
"""

from .database_handler import handle_database_task
from .research_handler import handle_research_task
from .scan_handler import handle_scan_task
from .test_handler import handle_test_task

__all__ = [
    'handle_database_task',
    'handle_research_task',
    'handle_scan_task',
    'handle_test_task'
]
