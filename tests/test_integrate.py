import importlib
import os
import sys
import types


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))


def test_integrate_module_imports_successfully():
    module = importlib.import_module("integrate")
    assert isinstance(module, types.ModuleType)


def test_integrate_module_has_no_public_attributes():
    module = importlib.import_module("integrate")
    public_attrs = [
        name
        for name in dir(module)
        if not name.startswith("_")
    ]
    # If the module is intentionally empty, it should not define any public
    # attributes. Adjust this test if public API is added later.
    assert public_attrs == []
