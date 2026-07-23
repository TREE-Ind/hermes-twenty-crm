"""Tool schemas for the generic Twenty CRM Hermes plugin."""

_AUTH_MODE = {
    "type": "string",
    "enum": ["auto", "api_key", "access_token", "oauth_client_credentials"],
    "description": "Authentication mode. auto selects API key, access token, then OAuth client credentials.",
}

TWENTY_DESCRIBE_WORKSPACE = {
    "name": "twenty_describe_workspace",
    "description": "Inspect the configured Twenty CRM workspace, its endpoints, available authentication, and optional OAuth discovery metadata. Use before a new Twenty task.",
    "parameters": {
        "type": "object",
        "properties": {
            "include_oauth_discovery": {"type": "boolean", "description": "Fetch OAuth discovery metadata. Defaults to true."},
            "auth_mode": _AUTH_MODE,
        },
    },
}

TWENTY_REST = {
    "name": "twenty_rest",
    "description": "Call a Twenty REST API endpoint using configured workspace authentication. Use paths such as /rest/companies or /rest/metadata/objects.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative Twenty path beginning with /rest/."},
            "method": {"type": "string", "enum": ["GET", "POST", "PATCH", "PUT", "DELETE"], "description": "HTTP method. Defaults to GET."},
            "params": {"type": "object", "description": "Optional query parameters."},
            "body": {"type": "object", "description": "Optional JSON request body."},
            "auth_mode": _AUTH_MODE,
        },
        "required": ["path"],
    },
}

TWENTY_GRAPHQL = {
    "name": "twenty_graphql",
    "description": "Call Twenty's GraphQL API. Use api=core for CRM records and api=metadata for schema, views, roles, and workspace administration.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "GraphQL query or mutation."},
            "variables": {"type": "object", "description": "Optional GraphQL variables."},
            "api": {"type": "string", "enum": ["core", "metadata"], "description": "GraphQL endpoint. Defaults to core."},
            "operation_name": {"type": "string", "description": "Optional operation name."},
            "auth_mode": _AUTH_MODE,
        },
        "required": ["query"],
    },
}

TWENTY_SCHEMA = {
    "name": "twenty_schema",
    "description": "Introspect the live Twenty GraphQL schema. Use before writing queries or mutations because Twenty schemas vary by workspace.",
    "parameters": {
        "type": "object",
        "properties": {
            "api": {"type": "string", "enum": ["core", "metadata"], "description": "Schema endpoint. Defaults to core."},
            "type_name": {"type": "string", "description": "Optional exact GraphQL type to inspect."},
            "auth_mode": _AUTH_MODE,
            "max_types": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum type names in summary output. Defaults to 80."},
        },
    },
}
