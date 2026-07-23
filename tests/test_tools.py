import json
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "twenty_crm_plugin",
    _ROOT / "__init__.py",
    submodule_search_locations=[str(_ROOT)],
)
assert _SPEC and _SPEC.loader
plugin = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = plugin
_SPEC.loader.exec_module(plugin)
tools = plugin.tools


class FakeContext:
    def __init__(self):
        self.tools = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-RateLimit-Remaining": "99"}

    def read(self):
        return b'{"data":{"ok":true}}'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_graphql_uses_core_endpoint_and_does_not_return_auth_header(monkeypatch):
    monkeypatch.setenv("TWENTY_BASE_URL", "https://crm.example.test")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    with patch.object(tools, "urlopen", return_value=FakeResponse()) as mocked:
        result = json.loads(tools.twenty_graphql({"query": "query { ok }"}))
    request = mocked.call_args.args[0]
    assert request.full_url == "https://crm.example.test/graphql"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert result["success"] is True
    assert "Authorization" not in json.dumps(result)


def test_rest_requires_rest_prefix(monkeypatch):
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    result = json.loads(tools.twenty_rest({"path": "/graphql"}))
    assert result["success"] is False
    assert "must begin with /rest/" in result["error"]


def test_schema_summary_uses_introspection(monkeypatch):
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    schema = {"data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"}, "types": [{"kind": "OBJECT", "name": "Query", "fields": []}, {"kind": "OBJECT", "name": "Company", "fields": []}, {"kind": "SCALAR", "name": "String"}]}}}

    with patch.object(tools, "twenty_graphql", return_value=json.dumps({"success": True, "data": schema})):
        result = json.loads(tools.twenty_schema({"api": "core"}))

    assert result["success"] is True
    assert result["query_type"] == "Query"
    assert result["type_names"] == ["Query", "Company"]


def test_plugin_registers_the_generic_twenty_toolset():
    context = FakeContext()
    plugin.register(context)
    assert [tool["name"] for tool in context.tools] == [
        "twenty_describe_workspace",
        "twenty_rest",
        "twenty_graphql",
        "twenty_schema",
    ]
