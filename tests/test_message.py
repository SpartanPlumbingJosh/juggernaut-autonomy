import importlib
import types
import pytest


@pytest.fixture(scope="module")
def message_module() -> types.ModuleType:
    """Fixture to import the message module once per test module."""
    return importlib.import_module("message")


def test_message_module_imports_successfully(message_module):
    """Module 'message' should be importable without raising exceptions."""
    assert message_module is not None
    assert isinstance(message_module, types.ModuleType)


def test_message_module_has_no_public_attributes(message_module):
    """
    Empty module should not expose any public attributes.

    Public attributes are those not starting with an underscore.
    """
    public_attrs = [
        name for name in dir(message_module)
        if not name.startswith("_")
    ]

    # In an empty module, there should be no public attributes
    assert public_attrs == []


def test_message_module_has_expected_builtins_only(message_module):
    """
    Verify that the module does not unexpectedly define variables.

    It should only have standard module attributes (all starting with '_').
    """
    for name in dir(message_module):
        # All attributes in an empty module should be "private"/dunder
        assert name.startswith("_")
