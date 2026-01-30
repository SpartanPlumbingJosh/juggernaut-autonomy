import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import a


# ---------------------------------------------------------------------------
# Logging configuration tests
# ---------------------------------------------------------------------------

def test_configure_logging_adds_handler_when_none():
    logger = logging.getLogger(a.LOGGER_NAME)
    original_handlers = logger.handlers[:]
    original_level = logger.level
    try:
        logger.handlers = []
        new_logger = a.configure_logging(level=logging.DEBUG)

        assert new_logger is logger
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert logger.level == logging.DEBUG
    finally:
        logger.handlers = original_handlers
        logger.setLevel(original_level)


def test_configure_logging_does_not_add_duplicate_handlers():
    logger = logging.getLogger(a.LOGGER_NAME)
    original_handlers = logger.handlers[:]
    original_level = logger.level
    try:
        if not logger.handlers:
            logger.addHandler(logging.StreamHandler())
        existing_count = len(logger.handlers)

        a.configure_logging(level=logging.WARNING)

        assert len(logger.handlers) == existing_count
        assert logger.level == logging.WARNING
    finally:
        logger.handlers = original_handlers
        logger.setLevel(original_level)


# ---------------------------------------------------------------------------
# Dataclass and enum behavior tests
# ---------------------------------------------------------------------------

def test_pr_info_defaults_and_fields():
    pr = a.PRInfo(pr_id="123", exists=True, merged=False)
    assert