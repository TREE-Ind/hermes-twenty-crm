---
name: twenty-crm
description: "Use when operating Twenty CRM through Hermes Agent: managed self-hosting, external connections, records, metadata, views, dashboards, workflows, or schema-aware API work."
version: 0.1.0
author: TREE Industries
license: MIT
metadata:
  hermes:
    tags: [twenty, crm, graphql, rest, self-hosting, docker]
    homepage: https://github.com/TREE-Ind/hermes-twenty-crm
---

# Twenty CRM with Hermes Agent

## Overview

This plugin gives Hermes direct Twenty REST, GraphQL, and schema tools. It can manage a private self-hosted Twenty runtime through Docker Compose or connect to an existing Twenty endpoint. Twenty schemas are workspace-specific: inspect the live schema before creating records or changing metadata.

## When to Use

- A user asks Hermes to read, create, update, relate, or analyze Twenty CRM data.
- A user needs a self-hosted Twenty runtime started or diagnosed.
- A user needs help connecting Hermes to Twenty Cloud, a local-network server, or a private remote endpoint.
- A user asks for custom objects, fields, views, dashboards, workflows, or Twenty Apps.

Do not use this skill for a CRM other than Twenty.

## Connection Discipline

1. Identify the active mode with `twenty_describe_workspace` or `/twenty status`.
   - `managed` is the default: Hermes bootstraps Docker Compose under `~/.hermes/projects/twenty-crm` and starts it when Twenty tools are needed.
   - `external` connects only. It never starts, stops, or edits the remote instance.
   - Completion: base URL and connection mode are confirmed before CRM writes.
2. For external mode, require `TWENTY_CONNECTION_MODE=external`, `TWENTY_BASE_URL`, and one supported authentication method.
   - Local network endpoints may use an RFC1918 address; private remote endpoints should use HTTPS over a VPN/Tailscale-style private network.
   - Completion: `twenty_describe_workspace` returns the expected base URL without an auth configuration error.
3. For managed mode, ensure Docker Compose is available and use `/twenty doctor` if startup is blocked.
   - Completion: `/healthz` reports OK, then create a Twenty API key and configure it in Hermes.

## Schema-First CRM Work

1. Start with `twenty_schema(api="core")`; for data-model changes also call `twenty_schema(api="metadata")`.
   - Completion: exact object/type names and mutation input shape are known.
2. Read a bounded set and deduplicate before creating records.
   - Completion: the intended record does not already exist or an update target is identified.
3. Use REST for known endpoint CRUD and GraphQL for relations, deep reads, metadata, views, dashboards, workflows, and schema introspection.
   - Completion: every write has a readback verification.
4. For custom objects, fields, views, or navigation, create the object first, wait for its generated core type, then inspect it before adding dependent entities.
   - Completion: metadata and core schema both expose the expected entity.

## Safe Write Rules

- Never assume field names, enum values, or nested composite fields. Inspect the relevant input or enum type first.
- Keep GraphQL operations small. If the server rejects repeated root resolvers, split calls instead of aliasing the same root field.
- Create a Note first, then create a NoteTarget in a separate verified call when linking it to another record.
- After an update or create, query the record again and verify the changed fields.
- Do not modify or stop an `external` Twenty deployment through runtime commands.

## Common Pitfalls

1. **Remote UI loads but backend fails.** The Twenty server's canonical `SERVER_URL` must be the remote private HTTPS hostname, not `127.0.0.1`; otherwise other devices call their own localhost.
2. **Authentication is missing after managed startup.** A healthy container stack is separate from API authentication. Create a Twenty API key and set `TWENTY_API_KEY`.
3. **Schema assumptions fail.** Tenant-generated schemas can differ between Twenty versions and workspaces. Run `twenty_schema` instead of guessing.
4. **Duplicate CRM records.** Search first and verify an exact identifier before creation.

## Verification Checklist

- [ ] Connection mode and base URL are correct.
- [ ] Authentication is configured before protected requests.
- [ ] Core schema inspected before record mutations.
- [ ] Metadata schema inspected before data-model changes.
- [ ] Every write has a readback verification.
- [ ] Managed health or external reachability is confirmed.
