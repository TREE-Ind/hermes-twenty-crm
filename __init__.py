"""Hermes Agent plugin registration for Twenty CRM."""

try:
    from . import schemas, tools
except ImportError:  # Direct-file loading used by Hermes and test runners.
    import schemas  # type: ignore[no-redef]
    import tools  # type: ignore[no-redef]


def register(ctx):
    """Register generic Twenty CRM tools with Hermes."""
    ctx.register_tool(
        name="twenty_describe_workspace",
        toolset="twenty",
        schema=schemas.TWENTY_DESCRIBE_WORKSPACE,
        handler=tools.twenty_describe_workspace,
    )
    ctx.register_tool(
        name="twenty_rest",
        toolset="twenty",
        schema=schemas.TWENTY_REST,
        handler=tools.twenty_rest,
    )
    ctx.register_tool(
        name="twenty_graphql",
        toolset="twenty",
        schema=schemas.TWENTY_GRAPHQL,
        handler=tools.twenty_graphql,
    )
    ctx.register_tool(
        name="twenty_schema",
        toolset="twenty",
        schema=schemas.TWENTY_SCHEMA,
        handler=tools.twenty_schema,
    )
