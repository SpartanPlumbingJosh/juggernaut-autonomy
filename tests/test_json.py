import json as stdlib_json
import logging
import sys
import importlib.util
from pathlib import Path

import pytest


def _load_target_module():
    """
    Robustly locate and import the module under test without relying on its import name.
    Searches for a .py file that defines MCPTools and get_mcp_tools_json.
    """
    tests_dir = Path(__file__).resolve().parent
    repo_root = tests_dir
    for _ in range(8):
        if (repo_root / "pyproject.toml").exists() or (repo_root / "setup.cfg").exists() or (repo_root / ".git").exists():
            break
        if repo_root.parent == repo_root:
            break
        repo_root = repo_root.parent

    candidates = []
    for path in repo_root.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        if any(part in {"tests", ".venv", "venv", "__pycache__", ".git", ".tox"} for part in path.parts):
            continue
        try:
            txt = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "class MCPTools" in txt and "def get_mcp_tools_json" in txt:
            candidates.append(path)

    if not candidates:
        raise RuntimeError("Could not locate module defining MCPTools and get_mcp_tools_json")

    module_path = sorted(candidates)[0]
    spec = importlib.util.spec_from_file_location("mcp_tools_json_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load spec for module at {module_path}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def mod():
    return _load_target_module()


@pytest.fixture()
def all_tools(mod):
    return mod.MCPTools.get_all_tools()


@pytest.fixture()
def core_tools(mod):
    return mod.MCPTools.get_core_tools()


def _tool_names(tools):
    return [t["function"]["name"] for t in tools]


def test_constants_have_expected_values(mod):
    assert mod.MCP_SERVER_URL == "https://juggernaut-mcp-production.up.railway.app"
    assert mod.MAX_QUERY_LENGTH == 10000
    assert mod.MAX_RESULTS_DEFAULT == 10


def test_get_all_tools_returns_expected_number_and_valid_schemas(mod, all_tools):
    assert isinstance(all_tools, list)
    assert len(all_tools) == 8

    for tool in all_tools:
        assert isinstance(tool, dict)
        assert tool.get("type") == "function"
        assert "function" in tool
        assert mod.MCPTools.validate_tool_schema(tool) is True

    expected_names = {
        "sql_query",
        "github_list_prs",
        "railway_get_deployments",
        "email_list",
        "web_search",
        "fetch_url",
        "storage_list",
        "ai_chat",
    }
    assert set(_tool_names(all_tools)) == expected_names


def test_get_core_tools_returns_expected_number_and_is_subset_of_all_tools(mod, all_tools, core_tools):
    assert isinstance(core_tools, list)
    assert len(core_tools) == 6

    all_names = set(_tool_names(all_tools))
    core_names = set(_tool_names(core_tools))
    assert core_names.issubset(all_names)

    # Core tools should not include fetch_url or ai_chat (per docstring and implementation)
    assert "fetch_url" not in core_names
    assert "ai_chat" not in core_names

    for tool in core_tools:
        assert mod.MCPTools.validate_tool_schema(tool) is True


@pytest.mark.parametrize(
    "category,expected_names",
    [
        ("database", ["sql_query"]),
        ("github", ["github_list_prs"]),
        ("railway", ["railway_get_deployments"]),
        ("email", ["email_list"]),
        ("web", ["web_search", "fetch_url"]),
        ("storage", ["storage_list"]),
        ("ai", ["ai_chat"]),
    ],
)
def test_get_tools_by_category_returns_expected_tools(mod, category, expected_names):
    tools = mod.MCPTools.get_tools_by_category(category)
    assert _tool_names(tools) == expected_names

    # case-insensitive
    tools_ci = mod.MCPTools.get_tools_by_category(category.upper())
    assert _tool_names(tools_ci) == expected_names


def test_get_tools_by_category_invalid_category_raises_value_error_with_valid_categories(mod):
    with pytest.raises(ValueError) as excinfo:
        mod.MCPTools.get_tools_by_category("not-a-category")

    msg = str(excinfo.value)
    assert "Invalid category" in msg
    for expected in ["database", "github", "railway", "email", "web", "storage", "ai"]:
        assert expected in msg


def test_validate_tool_schema_rejects_non_function_type_logs_warning(mod, caplog):
    caplog.set_level(logging.WARNING)
    bad_tool = {"type": "not_function", "function": {"name": "x", "description": "y", "parameters": {"type": "object"}}}

    assert mod.MCPTools.validate_tool_schema(bad_tool) is False
    assert any("Tool type must be 'function'" in r.message for r in caplog.records)


@pytest.mark.parametrize("missing_field", ["name", "description", "parameters"])
def test_validate_tool_schema_rejects_missing_function_fields(mod, all_tools, missing_field, caplog):
    caplog.set_level(logging.WARNING)
    tool = stdlib_json.loads(stdlib_json.dumps(all_tools[0]))  # deep copy
    del tool["function"][missing_field]

    assert mod.MCPTools.validate_tool_schema(tool) is False
    assert any(f"Missing required function field: {missing_field}" in r.message for r in caplog.records)


def test_validate_tool_schema_rejects_parameters_type_not_object(mod, all_tools, caplog):
    caplog.set_level(logging.WARNING)
    tool = stdlib_json.loads(stdlib_json.dumps(all_tools[0]))  # deep copy
    tool["function"]["parameters"]["type"] = "array"

    assert mod.MCPTools.validate_tool_schema(tool) is False
    assert any("Parameters type must be 'object'" in r.message for r in caplog.records)


def test_validate_tool_schema_returns_false_on_exception_and_logs_error(mod, caplog):
    caplog.set_level(logging.ERROR)
    # Missing 'function' key triggers KeyError inside validate_tool_schema
    tool = {"type": "function"}

    assert mod.MCPTools.validate_tool_schema(tool) is False
    assert any("Tool validation failed" in r.message for r in caplog.records)


def test_get_mcp_tools_json_returns_valid_json_array_all_tools(mod):
    s = mod.get_mcp_tools_json(core_only=False)
    parsed = stdlib_json.loads(s)

    assert isinstance(parsed, list)
    assert len(parsed) == 8
    assert {t["function"]["name"] for t in parsed} == {
        "sql_query",
        "github_list_prs",
        "railway_get_deployments",
        "email_list",
        "web_search",
        "fetch_url",
        "storage_list",
        "ai_chat",
    }


def test_get_mcp_tools_json_core_only_returns_six_tools(mod):
    s = mod.get_mcp_tools_json(core_only=True)
    parsed = stdlib_json.loads(s)

    assert isinstance(parsed, list)
    assert len(parsed) == 6
    names = {t["function"]["name"] for t in parsed}
    assert "fetch_url" not in names
    assert "ai_chat" not in names


def test_get_mcp_tools_json_filters_invalid_tools_and_logs_warning(mod, monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    tools = mod.MCPTools.get_all_tools()

    # Force validation failure for exactly one tool
    original_validate = mod.MCPTools.validate_tool_schema

    def validate_side_effect(tool):
        if tool["function"]["name"] == "fetch_url":
            return False
        return original_validate(tool)

    monkeypatch.setattr(mod.MCPTools, "validate_tool_schema", staticmethod(validate_side_effect))
    monkeypatch.setattr(mod.MCPTools, "get_all_tools", classmethod(lambda cls: tools))

    s = mod.get_mcp_tools_json(core_only=False)
    parsed = stdlib_json.loads(s)
    names = {t["function"]["name"] for t in parsed}

    assert len(parsed) == 7
    assert "fetch_url" not in names
    assert any("Some tools failed validation" in r.message for r in caplog.records)


def test_get_mcp_tools_json_raises_when_json_serialization_fails_and_logs_error(mod, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)

    def boom(*args, **kwargs):
        raise TypeError("nope")

    monkeypatch.setattr(mod.json, "dumps", boom)

    with pytest.raises(TypeError):
        mod.get_mcp_tools_json(core_only=False)

    assert any("Failed to generate MCP tools JSON" in r.message for r in caplog.records)


def test_main_prints_core_tools_when_core_flag(mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--core"])
    monkeypatch.setattr(mod, "get_mcp_tools_json", lambda core_only=False: "CORE-TOOLS-JSON")

    mod.main()
    out = capsys.readouterr().out
    assert "CORE-TOOLS-JSON" in out


def test_main_prints_all_tools_when_no_flag(mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"])
    monkeypatch.setattr(mod, "get_mcp_tools_json", lambda core_only=False: "ALL-TOOLS-JSON")

    mod.main()
    out = capsys.readouterr().out
    assert "ALL-TOOLS-JSON" in out