import logging
import importlib
import runpy
from pathlib import Path

import pytest


@pytest.fixture
def simple_module():
    """
    Fixture to import and return the module under test.
    """
    return importlib.import_module("simple")


def test_greeting_message_constant_has_expected_value(simple_module):
    """
    GREETING_MESSAGE should equal the expected greeting string.
    """
    assert simple_module.GREETING_MESSAGE == "Hello World"
    assert isinstance(simple_module.GREETING_MESSAGE, str)


def test_logger_is_configured_for_module_name(simple_module):
    """
    LOGGER should be a logging.Logger instance named after the module.
    """
    logger = simple_module.LOGGER
    assert isinstance(logger, logging.Logger)
    assert logger.name == simple_module.__name__


def test_get_greeting_returns_constant(simple_module):
    """
    get_greeting should return the GREETING_MESSAGE constant.
    """
    result = simple_module.get_greeting()
    assert result == simple_module.GREETING_MESSAGE
    assert result == "Hello World"


def test_get_greeting_logs_debug_message(monkeypatch, simple_module):
    """
    get_greeting should emit a debug log with the expected message.
    """
    logged_messages = []

    def fake_debug(msg, *args, **kwargs):
        logged_messages.append(msg)

    monkeypatch.setattr(simple_module.LOGGER, "debug", fake_debug)

    result = simple_module.get_greeting()

    assert result == simple_module.GREETING_MESSAGE
    assert logged_messages == ["Generating greeting message."]


def test_get_greeting_emits_debug_log_record(simple_module, caplog):
    """
    get_greeting should produce a DEBUG level log record with the correct message.
    """
    caplog.set_level(logging.DEBUG, logger=simple_module.LOGGER.name)

    _ = simple_module.get_greeting()

    debug_records = [
        r
        for r in caplog.records
        if r.levelno == logging.DEBUG and r.name == simple_module.LOGGER.name
    ]
    assert any(
        "Generating greeting message." in r.getMessage() for r in debug_records
    ), "Expected debug log message not found in log records"


def test_main_block_logs_greeting_when_run_as_script(simple_module, caplog):
    """
    Executing the module as a script (__main__) should log the greeting at INFO level.
    """
    module_path = Path(simple_module.__file__)

    with caplog.at_level(logging.INFO):
        runpy.run_path(str(module_path), run_name="__main__")

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]

    assert any(
        "Hello World" in r.getMessage() for r in info_records
    ), "Expected 'Hello World' INFO log message when running module as __main__"