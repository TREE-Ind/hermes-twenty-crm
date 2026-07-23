# Hermes Twenty CRM

A generic [Hermes Agent](https://hermes-agent.nousresearch.com/) plugin for [Twenty CRM](https://twenty.com/). It provides safe, schema-aware building blocks for any Twenty Cloud or self-hosted workspace:

- `twenty_describe_workspace` — inspect endpoints, configured auth, and OAuth discovery
- `twenty_rest` — call Twenty REST endpoints
- `twenty_graphql` — call core or metadata GraphQL endpoints
- `twenty_schema` — introspect the live GraphQL schema before writing queries or mutations

This project intentionally contains **no company-specific data, custom objects, pricing, CRM seed data, Docker stack, or local-runtime automation**.

## Install

Hermes discovers directory plugins from `~/.hermes/plugins/`.

```bash
git clone https://github.com/TREE-Ind/hermes-twenty-crm.git ~/.hermes/plugins/twenty-crm
```

Restart Hermes or start a new session. The plugin registers a `twenty` toolset.

## Configure

Copy the example values into your Hermes environment (`~/.hermes/.env`, or your deployment's equivalent). For self-hosted Twenty, set `TWENTY_BASE_URL`; for Twenty Cloud, omit it.

```dotenv
# TWENTY_BASE_URL=https://crm.example.com
TWENTY_API_KEY=replace-with-a-twenty-api-key
```

The plugin supports one of these authentication options, in order when `auth_mode=auto`:

1. `TWENTY_API_KEY`
2. `TWENTY_ACCESS_TOKEN`
3. `TWENTY_CLIENT_ID` plus `TWENTY_CLIENT_SECRET` (OAuth client credentials)

Optional settings:

```dotenv
TWENTY_OAUTH_SCOPE=api
TWENTY_TIMEOUT_SECONDS=30
```

## Usage

Start with a prompt such as:

> Inspect my Twenty workspace and list the available CRM objects.

For tenant-specific tasks, call `twenty_schema` before creating queries or mutations. Twenty generates schemas per workspace, so assuming object and field names is unsafe.

### Example GraphQL call

```json
{
  "query": "query { companies(first: 5) { edges { node { id name } } } }",
  "api": "core"
}
```

### Example REST call

```json
{
  "path": "/rest/companies",
  "method": "GET"
}
```

## Development

The plugin has no runtime dependency beyond Python's standard library.

```bash
python -m pytest
python -m compileall -q .
```

## Security

- Keep credentials in Hermes environment files, not plugin source or commits.
- The plugin redacts authorization headers by never returning request headers.
- OAuth access tokens are cached locally under Hermes' cache directory and are never returned by tools.
- Use least-privilege Twenty API keys and rotate them regularly.

## License

[MIT](LICENSE)
