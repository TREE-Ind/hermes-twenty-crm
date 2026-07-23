"""Hermes Agent plugin registration for Twenty CRM."""

import json
from pathlib import Path
from typing import Any

try:
    from . import runtime, schemas, tools
except ImportError:  # Direct-file loading used by Hermes and test runners.
    import runtime  # type: ignore[no-redef]
    import schemas  # type: ignore[no-redef]
    import tools  # type: ignore[no-redef]

_TOOL_NAMES = {
    "twenty_describe_workspace",
    "twenty_rest",
    "twenty_graphql",
    "twenty_schema",
}


def _session_start(**_: Any) -> None:
    if runtime.connection_mode() == "managed" and runtime.autostart_enabled():
        runtime.ensure_running(timeout=120, reason="session_start")


def _pre_tool_call(tool_name: str = "", **_: Any):
    if tool_name not in _TOOL_NAMES:
        return None
    if runtime.connection_mode() != "managed" or not runtime.autostart_enabled():
        return None
    start = runtime.ensure_running(timeout=120, reason=f"pre_tool_call:{tool_name}")
    if not start.get("success"):
        return {"action": "block", "message": start.get("blocking_error", "Managed Twenty could not start.")}
    return None


def _command(raw_args: str) -> str:
    parts = raw_args.strip().split()
    action = parts[0].lower() if parts else "status"
    if action == "status":
        result = runtime.status()
    elif action == "bootstrap":
        result = runtime.bootstrap(force="--force" in parts)
    elif action == "start":
        result = runtime.ensure_running(reason="slash_command")
    elif action == "stop":
        result = runtime.stop()
    elif action == "logs":
        result = runtime.logs(int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 80)
    elif action == "doctor":
        result = runtime.doctor()
    else:
        result = {"success": False, "error": "Usage: /twenty [status|bootstrap [--force]|start|stop|logs [tail]|doctor]"}
    return json.dumps(result, ensure_ascii=False, indent=2)


def register(ctx):
    """Register CRM tools plus managed-runtime lifecycle hooks."""
    ctx.register_tool(name="twenty_describe_workspace", toolset="twenty", schema=schemas.TWENTY_DESCRIBE_WORKSPACE, handler=tools.twenty_describe_workspace)
    ctx.register_tool(name="twenty_rest", toolset="twenty", schema=schemas.TWENTY_REST, handler=tools.twenty_rest)
    ctx.register_tool(name="twenty_graphql", toolset="twenty", schema=schemas.TWENTY_GRAPHQL, handler=tools.twenty_graphql)
    ctx.register_tool(name="twenty_schema", toolset="twenty", schema=schemas.TWENTY_SCHEMA, handler=tools.twenty_schema)
    ctx.register_hook("on_session_start", _session_start)
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_command("twenty", _command, description="Manage the Twenty connection and managed runtime")
    skills_dir = Path(__file__).parent / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            ctx.register_skill(child.name, skill_md)
