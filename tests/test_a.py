import importlib
import types
import pytest

MODULE_NAME = "a"


@pytest.fixture(scope="module")
def module_a():
    return importlib.import_module(MODULE_NAME)


def test_module_a_imports_successfully(module_a):
    assert isinstance(module_a, types.ModuleType)


def test_module_a_has_no_public_callables(module_a):
    public_names = [name for name in dir(module_a) if not name.startswith("_")]
    public_callables = [name for name in public_names if callable(getattr(module_a, name))]
    assert public_callables == []