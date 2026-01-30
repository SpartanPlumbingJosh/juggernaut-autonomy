import logging
from typing import List, Dict, Any

import pytest
import test_hello as hello_module


@pytest.fixture
def hello_world() -> hello_module.HelloWorld:
    return hello_module.HelloWorld("TestUser")


@pytest.fixture
def mock_logging_info(monkeypatch) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    def fake_info(msg, *args, **kwargs):
        calls.append({"msg": msg, "args": args, "kwargs": kwargs})

    monkeypatch.setattr(hello_module.logging, "info", fake_info)
    return calls


def test_log_level_constant_matches_logging_info():
    assert hello_module.LOG_LEVEL == logging.INFO


def test_helloworld_init_stores_name_correctly():
    hw = hello_module.HelloWorld("Bob")
    assert hw.name == "Bob"


def test_helloworld_init_allows_empty_string():
    hw = hello_module.HelloWorld("")
    assert hw.name == ""


def test_helloworld_init_allows_non_string_types():
    # Type hints are not enforced at runtime; ensure it still behaves predictably
    hw = hello_module.HelloWorld(123)  # type: ignore[arg-type]
    assert hw.name == 123


def test_helloworld_greet_logs_expected_message(hello_world, mock_logging_info):
    hello_world.greet()
    assert len(mock_logging_info) == 1
    assert mock_logging_info[0]["msg"] == "Hello, TestUser!"


def test_helloworld_greet_with_empty_name_logs_trailing_space(mock_logging_info):
    hw = hello_module.HelloWorld("")
    hw.greet()
    assert len(mock_logging_info) == 1
    assert mock_logging_info[0]["msg"] == "Hello, !"


def test_helloworld_greet_with_special_characters_in_name(mock_logging_info):
    special_name = "Ålice-测试-🙂"
    hw = hello_module.HelloWorld(special_name)
    hw.greet()
    assert len(mock_logging_info) == 1
    assert mock_logging_info[0]["msg"] == f"Hello, {special_name}!"


def test_helloworld_greet_with_non_string_name_logs_stringified_value(mock_logging_info):
    hw = hello_module.HelloWorld(123)  # type: ignore[arg-type]
    hw.greet()
    assert len(mock_logging_info) == 1
    assert mock_logging_info[0]["msg"] == "Hello, 123!"


def test_main_configures_logging_and_greets_alice(monkeypatch):
    basic_config_calls = []

    def fake_basicConfig(*args, **kwargs):
        basic_config_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(hello_module.logging, "basicConfig", fake_basicConfig)

    created_instances = []

    class DummyHelloWorld:
        def __init__(self, name: str) -> None:
            self.name = name
            self.greet_called = False
            created_instances.append(self)

        def greet(self) -> None:
            self.greet_called = True

    monkeypatch.setattr(hello_module, "HelloWorld", DummyHelloWorld)

    hello_module.main()

    # Assert logging.basicConfig was called once with the correct log level
    assert len(basic_config_calls) == 1
    call = basic_config_calls[0]
    assert call["kwargs"].get("level") == hello_module.LOG_LEVEL

    # Assert HelloWorld was instantiated with "Alice" and greet was called
    assert len(created_instances) == 1
    instance = created_instances[0]
    assert instance.name == "Alice"
    assert instance.greet_called is True