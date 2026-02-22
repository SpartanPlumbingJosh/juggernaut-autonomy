"""
Revenue Strategy Configuration - Centralized settings for revenue automation.
"""

from datetime import timedelta

class RevenueConfig:
    # Idea generation settings
    IDEA_GENERATION_LIMIT = 10
    IDEA_SCORING_LIMIT = 20
    
    # Experiment settings
    MIN_SCORE = 60.0
    MAX_NEW_EXPERIMENTS = 3
    EXPERIMENT_BUDGET = 100.0
    
    # Cycle timing
    CYCLE_INTERVAL = timedelta(hours=1)
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = timedelta(minutes=5)
    
    # Logging settings
    LOG_RETENTION_DAYS = 30
    
    @classmethod
    def get_settings(cls):
        return {
            k: v for k, v in cls.__dict__.items()
            if not k.startswith('_') and not callable(v)
        }
