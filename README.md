# Hermes Twenty CRM

[Hermes Agent](https://hermes-agent.nousresearch.com/) integration for [Twenty CRM](https://twenty.com/). It gives Hermes live CRM tools and can run a self-hosted Twenty stack automatically, or connect to an existing Twenty Cloud, local-network, VPN, or remote deployment.

## What Hermes can do

The plugin registers a `twenty` toolset:

- `twenty_describe_workspace` — inspect connection mode, endpoints, available authentication, and OAuth discovery
- `twenty_rest` — use Twenty REST endpoints
- `twenty_graphql` — use the core-record or metadata GraphQL API
- `twenty_schema` — inspect the workspace's live schema before creating queries or mutations
- `/twenty` — inspect, bootstrap, start, stop, and diagnose a managed runtime

It also includes a bundled **Twenty CRM skill** that guides schema-aware record, metadata, workflow, view, and dashboard work.

## Install

Hermes loads directory plugins from `~/.hermes/plugins/`:

```bash
git clone https://github.com/TREE-Ind/hermes-twenty-crm.git ~/.hermes/plugins/twenty-crm
```

Restart Hermes or start a new session. The plugin's managed mode starts only when Twenty tools are used (and at session start when autostart is enabled).

## Connection modes

### Managed self-hosting — default

Managed mode bootstraps and maintains Twenty, PostgreSQL, and Redis through Docker Compose. The stack is isolated at `~/.hermes/projects/twenty-crm`, binds only to `127.0.0.1:3000` by default, and keeps generated application/database secrets in that project's ignored `.env` file.

Prerequisite: Docker Desktop or Docker Engine with Docker Compose.

```dotenv
TWENTY_CONNECTION_MODE=managed
TWENTY_MANAGED_AUTOSTART=true
TWENTY_MANAGED_BIND_HOST=127.0.0.1
TWENTY_MANAGED_PORT=3000
```

First run is seamless: ask Hermes to inspect the workspace or use `/twenty start`. Once Twenty is healthy, open `http://127.0.0.1:3000`, create a Twenty API key, and save it in Hermes' environment:

```dotenv
TWENTY_API_KEY=replace-with-a-twenty-api-key
```

Runtime commands:

```text
/twenty status
/twenty bootstrap
/twenty start
/twenty logs 120
/twenty stop
/twenty doctor
```

### Connect to an existing instance

Use external mode when Twenty is already running—on the same machine, a private LAN, a VPN/Tailscale network, a hosted server, or Twenty Cloud. Hermes never starts or stops that instance.

```dotenv
TWENTY_CONNECTION_MODE=external
TWENTY_BASE_URL=https://crm.example.com
TWENTY_API_KEY=replace-with-a-twenty-api-key
```

Examples:

```dotenv
# Local network
TWENTY_BASE_URL=http://192.168.1.42:3000

# Private remote network, such as Tailscale
TWENTY_BASE_URL=https://crm.tailnet-name.ts.net

# Twenty Cloud
TWENTY_BASE_URL=https://api.twenty.com
```

## Authentication

`auth_mode=auto` chooses the first configured option:

1. `TWENTY_API_KEY`
2. `TWENTY_ACCESS_TOKEN`
3. `TWENTY_CLIENT_ID` plus `TWENTY_CLIENT_SECRET` for OAuth client credentials

Optional:

```dotenv
TWENTY_OAUTH_SCOPE=api
TWENTY_TIMEOUT_SECONDS=30
```

## How Hermes works safely with Twenty

Twenty schemas vary by workspace. For a new workspace or any metadata change, Hermes should call `twenty_schema` before it assumes object names, field names, input types, or enum values. Use REST for known straightforward endpoints and GraphQL for schema-aware records, relations, metadata, views, dashboards, and workflows.

Keep credentials in Hermes environment files; do not commit them. The plugin never returns authorization headers, and cached OAuth tokens remain local to the Hermes cache directory.

## Development

The runtime uses Python's standard library.

```bash
uv run --with pytest pytest -q
python -m py_compile __init__.py runtime.py schemas.py tools.py
uv build
```

## License

[MIT](LICENSE)
