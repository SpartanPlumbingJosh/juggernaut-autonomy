import importlib
import types


def test_integrate_module_imports_successfully():
    module = importlib.import_module("integrate")
    assert isinstance(module, types.ModuleType)


def test_integrate_module_has_no_public_callables():
    module = importlib.import_module("integrate")
    public_attrs = [
        name
        for name in dir(module)
        if not name.startswith("_")
    ]
    # If the module is intentionally empty, it should not define any public
    # functions or classes. Adjust this test if public API is added later.
    assert public_attrs == []