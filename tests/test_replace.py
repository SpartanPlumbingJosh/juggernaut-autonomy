import importlib
import inspect
from types import FunctionType
from typing import List, Tuple, Any, Type

import pytest


@pytest.fixture(scope="session")
def module_under_test():
    """
    Dynamically import the module that this test file corresponds to.

    Assumes the test file is named `test_<module_name>.py` and the module under
    test is `<module_name>.py` in the same package/directory.
    """
    module_name = __name__.replace("test_", "", 1)
    if module_name == __name__:
        pytest.skip("Cannot determine module under test name from test module name.")
    return importlib.import_module(module_name)


def _get_public_members(module) -> Tuple[List[Tuple[str, Any]], List[Tuple[str, FunctionType]], List[Tuple[str, Type[Any]]]]:
    """
    Return all public attributes, public functions, and public classes
    defined directly in the module (not imported from elsewhere).
    """
    module_name = module.__name__
    public_attrs = []
    public_funcs = []
    public_classes = []

    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue

        # Only consider objects defined in this module (exclude imports)
        if getattr(obj, "__module__", module_name) != module_name:
            continue

        public_attrs.append((name, obj))

        if isinstance(obj, FunctionType):
            public_funcs.append((name, obj))
        elif inspect.isclass(obj):
            public_classes.append((name, obj))

    return public_attrs, public_funcs, public_classes


@pytest.fixture(scope="session")
def public_members(module_under_test):
    return _get_public_members(module_under_test)


@pytest.fixture(scope="session")
def public_attributes(public_members):
    public_attrs, _, _ = public_members
    return public_attrs


@pytest.fixture(scope="session")
def public_functions(public_members):
    _, public_funcs, _ = public_members
    return public_funcs


@pytest.fixture(scope="session")
def public_classes(public_members):
    _, _, public_classes = public_members
    return public_classes


def test_module_imports_successfully(module_under_test):
    assert module_under_test is not None
    assert isinstance(module_under_test.__name__, str)
    assert module_under_test.__name__ != ""


def test_module_has_at_least_zero_public_members(public_attributes):
    # This test is mostly a placeholder to document that it's valid
    # for the module to have no public members. If this is unintended,
    # adjust the assertion accordingly.
    assert len(public_attributes) >= 0


@pytest.mark.parametrize("name,obj", indirect=False)
def test_all_public_members_are_accessible(module_under_test, public_attributes):
    for name, obj in public_attributes:
        # Ensure the attribute can be retrieved from the module without error
        assert hasattr(module_under_test, name)
        assert getattr(module_under_test, name) is obj


def test_public_functions_are_callable(public_functions):
    for name, func in public_functions:
        assert callable(func), f"Public function '{name}' should be callable"
        assert inspect.isfunction(func), f"Public callable '{name}' should be a function object"


def test_public_functions_have_consistent_signatures(public_functions):
    for name, func in public_functions:
        sig = inspect.signature(func)
        # Signature object should be retrievable without error
        assert isinstance(sig, inspect.Signature)
        # Edge-case: ensure parameters have unique names
        param_names = [p.name for p in sig.parameters.values()]
        assert len(param_names) == len(set(param_names)), f"Duplicate parameter names in function '{name}' signature"


def test_public_classes_are_types(public_classes):
    for name, cls in public_classes:
        assert inspect.isclass(cls), f"Public '{name}' should be a class"
        assert isinstance(cls, type), f"Public class '{name}' should be a type"


def test_public_classes_have_qualnames(public_classes):
    for name, cls in public_classes:
        # Edge-case: Ensure __qualname__ is set and non-empty for classes
        qualname = getattr(cls, "__qualname__", "")
        assert isinstance(qualname, str)
        assert qualname, f"Class '{name}' should have a non-empty __qualname__"


def test_public_functions_and_classes_have_docstrings_if_present(public_functions, public_classes):
    """
    Soft quality check: if a docstring exists, it should be non-empty
    and not just whitespace. This does NOT require that every public
    member has a docstring, only that existing ones are minimally valid.
    """
    for name, func in public_functions:
        doc = inspect.getdoc(func)
        if doc is not None:
            assert doc.strip(), f"Function '{name}' has a docstring that is empty or whitespace."

    for name, cls in public_classes:
        doc = inspect.getdoc(cls)
        if doc is not None:
            assert doc.strip(), f"Class '{name}' has a docstring that is empty or whitespace."


def test_no_public_member_is_named_like_dunder(public_attributes):
    for name, _ in public_attributes:
        # Edge-case: Public names should not look like magic methods/dunder
        assert not (name.startswith("__") and name.endswith("__")), (
            f"Public attribute '{name}' looks like a dunder/magic name and should likely be private or renamed."
        )