"""
JUGGERNAUT Core Module
Database operations, logging, and shared utilities.
"""

from .database import Database, log_execution, create_opportunity, query_db

__all__ = ["Database", "log_execution", "create_opportunity", "query_db"]
