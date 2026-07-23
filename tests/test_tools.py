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
        self.hooks = []
        self.commands = []
        self.skills = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, *args):
        self.hooks.append(args)

    def register_command(self, *args, **kwargs):
        self.commands.append((args, kwargs))

    def register_skill(self, *args):
        self.skills.append(args)


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
    monkeypatch.setenv("TWENTY_CONNECTION_MODE", "external")
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
    monkeypatch.setenv("TWENTY_CONNECTION_MODE", "external")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    result = json.loads(tools.twenty_rest({"path": "/graphql"}))
    assert result["success"] is False
    assert "must begin with /rest/" in result["error"]


def test_schema_summary_uses_introspection(monkeypatch):
    monkeypatch.setenv("TWENTY_CONNECTION_MODE", "external")
    monkeypatch.setenv("TWENTY_API_KEY", "test-key")
    schema = {"data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"}, "types": [{"kind": "OBJECT", "name": "Query", "fields": []}, {"kind": "OBJECT", "name": "Company", "fields": []}, {"kind": "SCALAR", "name": "String"}]}}}

    with patch.object(tools, "twenty_graphql", return_value=json.dumps({"success": True, "data": schema})):
        result = json.loads(tools.twenty_schema({"api": "core"}))

    assert result["success"] is True
    assert result["query_type"] == "Query"
    assert result["type_names"] == ["Query", "Company"]


def test_plugin_registers_twenty_tools_hooks_and_command():
    context = FakeContext()
    plugin.register(context)
    assert [tool["name"] for tool in context.tools] == [
        "twenty_describe_workspace",
        "twenty_rest",
        "twenty_graphql",
        "twenty_schema",
    ]
    assert [hook[0] for hook in context.hooks] == ["on_session_start", "pre_tool_call"]
    assert context.commands[0][0][0] == "twenty"
    assert context.skills[0][0] == "twenty-crm"
    assert context.skills[0][1].name == "SKILL.md"


def test_external_mode_never_starts_docker(monkeypatch):
    monkeypatch.setenv("TWENTY_CONNECTION_MODE", "external")
    monkeypatch.setenv("TWENTY_BASE_URL", "https://crm.private-network.test")
    result = plugin.runtime.ensure_running()
    assert result["success"] is True
    assert result["managed"] is False
    assert result["base_url"] == "https://crm.private-network.test"


def test_managed_mode_bootstraps_an_isolated_project(monkeypatch, tmp_path):
    monkeypatch.setenv("TWENTY_CONNECTION_MODE", "managed")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.setenv("TWENTY_MANAGED_PORT", "39123")
    result = plugin.runtime.bootstrap()
    project = tmp_path / "hermes" / "projects" / "twenty-crm"
    assert result["success"] is True
    assert result["base_url"] == "http://127.0.0.1:39123"
    assert (project / "docker-compose.yml").exists()
    env_text = (project / ".env").read_text(encoding="utf-8")
    assert "APP_SECRET=" in env_text
    assert "PG_DATABASE_PASSWORD=" in env_text
