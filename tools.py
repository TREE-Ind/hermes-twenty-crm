"""Generic Twenty API client and Hermes tool handlers.

The plugin deliberately contains no workspace-specific objects, workflows,
branding, pricing, seed data, or local Docker runtime management.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://api.twenty.com"
DEFAULT_TIMEOUT_SECONDS = 30.0
TOKEN_REFRESH_SKEW_SECONDS = 60

_INTROSPECTION_QUERY = """
query TwentyIntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind name description
      fields(includeDeprecated: true) {
        name description defaultValue
        args { name description defaultValue type { ...TypeRef } }
        type { ...TypeRef }
      }
      inputFields { name description defaultValue type { ...TypeRef } }
      enumValues(includeDeprecated: true) { name description }
    }
  }
}
fragment TypeRef on __Type {
  kind name
  ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } } }
}
""".strip()


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _base_url() -> str:
    value = _env("TWENTY_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    if not value.startswith(("https://", "http://")):
        value = f"https://{value}"
    return value.rstrip("/")


def _timeout() -> float:
    try:
        value = float(_env("TWENTY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)) or DEFAULT_TIMEOUT_SECONDS)
        return value if value > 0 else DEFAULT_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _url(path: str) -> str:
    return urljoin(f"{_base_url()}/", path.lstrip("/"))


def _configured_auth_modes() -> list[str]:
    modes: list[str] = []
    if _env("TWENTY_API_KEY"):
        modes.append("api_key")
    if _env("TWENTY_ACCESS_TOKEN"):
        modes.append("access_token")
    if _env("TWENTY_CLIENT_ID") and _env("TWENTY_CLIENT_SECRET"):
        modes.append("oauth_client_credentials")
    return modes


def _token_cache_path() -> Path:
    home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    path = home / "cache" / "twenty-crm-oauth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _oauth_token() -> dict[str, Any]:
    client_id = _env("TWENTY_CLIENT_ID")
    client_secret = _env("TWENTY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("TWENTY_CLIENT_ID and TWENTY_CLIENT_SECRET are required for OAuth client credentials.")

    cache_path = _token_cache_path()
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        cached = {}
    if cached.get("access_token") and cached.get("base_url") == _base_url() and cached.get("client_id") == client_id and cached.get("expires_at", 0) > time.time() + TOKEN_REFRESH_SKEW_SECONDS:
        return {"token": cached["access_token"], "source": "cache"}

    body = urlencode({"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": _env("TWENTY_OAUTH_SCOPE", "api") or "api"}).encode()
    request = Request(_url("/oauth/token"), data=body, headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(request, timeout=_timeout()) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise ValueError("Twenty OAuth response did not include access_token.")
    try:
        cache_path.write_text(_json({"access_token": token, "expires_at": time.time() + int(payload.get("expires_in", 3600)), "base_url": _base_url(), "client_id": client_id}), encoding="utf-8")
    except OSError:
        pass
    return {"token": token, "source": "oauth_server"}


def _auth(auth_mode: str = "auto") -> tuple[dict[str, str], str, str]:
    mode = auth_mode or "auto"
    if mode == "auto":
        mode = _configured_auth_modes()[0] if _configured_auth_modes() else ""
    if mode == "api_key":
        token = _env("TWENTY_API_KEY")
        if token:
            return {"Authorization": f"Bearer {token}"}, mode, "env"
    elif mode == "access_token":
        token = _env("TWENTY_ACCESS_TOKEN")
        if token:
            return {"Authorization": f"Bearer {token}"}, mode, "env"
    elif mode == "oauth_client_credentials":
        token = _oauth_token()
        return {"Authorization": f"Bearer {token['token']}"}, mode, token["source"]
    raise ValueError("Twenty authentication is not configured. Set TWENTY_API_KEY, TWENTY_ACCESS_TOKEN, or TWENTY_CLIENT_ID/TWENTY_CLIENT_SECRET.")


def _safe_headers(headers: Any) -> dict[str, str]:
    keep = {"content-type", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after"}
    return {key: value for key, value in dict(headers).items() if key.lower() in keep}


def _request(method: str, path: str, *, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None, auth_mode: str = "auto", authenticated: bool = True) -> dict[str, Any]:
    url = _url(path)
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    headers = {"Accept": "application/json"}
    active_mode, token_source = "none", None
    if authenticated:
        auth_headers, active_mode, token_source = _auth(auth_mode)
        headers.update(auth_headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=_timeout()) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            payload: Any = json.loads(raw) if "json" in content_type.lower() and raw else raw
            return {"success": True, "status_code": response.status, "url": url, "headers": _safe_headers(response.headers), "data": payload, "auth_mode": active_mode, "token_source": token_source}
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return {"success": False, "status_code": error.code, "url": url, "headers": _safe_headers(error.headers), "data": payload, "error": payload, "auth_mode": active_mode, "token_source": token_source}
    except URLError as error:
        return {"success": False, "url": url, "error": f"Twenty request failed: {error.reason}", "auth_mode": active_mode, "token_source": token_source}


def twenty_describe_workspace(args: dict[str, Any], **_: Any) -> str:
    include_discovery = args.get("include_oauth_discovery", True)
    result: dict[str, Any] = {"success": True, "base_url": _base_url(), "graphql_endpoint": _url("/graphql"), "metadata_graphql_endpoint": _url("/metadata"), "rest_base": _url("/rest/"), "configured_auth_modes": _configured_auth_modes(), "timeout_seconds": _timeout()}
    try:
        _, mode, source = _auth(args.get("auth_mode", "auto"))
        result.update({"active_auth_mode": mode, "token_source": source})
    except ValueError as error:
        result["auth_error"] = str(error)
    if include_discovery:
        result["oauth_discovery"] = _request("GET", "/.well-known/oauth-authorization-server", authenticated=False)
    return _json(result)


def twenty_rest(args: dict[str, Any], **_: Any) -> str:
    path = str(args.get("path", "")).strip()
    if not path.startswith("/rest/"):
        return _json({"success": False, "error": "path must begin with /rest/."})
    return _json(_request(args.get("method", "GET"), path, params=args.get("params"), body=args.get("body"), auth_mode=args.get("auth_mode", "auto")))


def twenty_graphql(args: dict[str, Any], **_: Any) -> str:
    query = str(args.get("query", "")).strip()
    api = args.get("api", "core")
    if not query:
        return _json({"success": False, "error": "query is required."})
    if api not in {"core", "metadata"}:
        return _json({"success": False, "error": "api must be core or metadata."})
    body: dict[str, Any] = {"query": query, "variables": args.get("variables") or {}}
    if args.get("operation_name"):
        body["operationName"] = args["operation_name"]
    result = _request("POST", "/metadata" if api == "metadata" else "/graphql", body=body, auth_mode=args.get("auth_mode", "auto"))
    result["api"] = api
    if result.get("success") and isinstance(result.get("data"), dict) and result["data"].get("errors"):
        result["success"] = False
        result["error"] = result["data"]["errors"]
    return _json(result)


def _type_ref(value: dict[str, Any] | None) -> str:
    if not value:
        return "Unknown"
    if value.get("kind") == "NON_NULL":
        return f"{_type_ref(value.get('ofType'))}!"
    if value.get("kind") == "LIST":
        return f"[{_type_ref(value.get('ofType'))}]"
    return value.get("name") or value.get("kind") or "Unknown"


def twenty_schema(args: dict[str, Any], **_: Any) -> str:
    api = args.get("api", "core")
    if api not in {"core", "metadata"}:
        return _json({"success": False, "error": "api must be core or metadata."})
    raw = json.loads(twenty_graphql({"query": _INTROSPECTION_QUERY, "api": api, "operation_name": "TwentyIntrospectionQuery", "auth_mode": args.get("auth_mode", "auto")}))
    if not raw.get("success"):
        return _json(raw)
    schema = ((raw.get("data") or {}).get("data") or {}).get("__schema") or {}
    types = [item for item in schema.get("types", []) if item.get("name") and not item["name"].startswith("__")]
    target = args.get("type_name")
    result: dict[str, Any] = {"success": True, "api": api, "query_type": (schema.get("queryType") or {}).get("name"), "mutation_type": (schema.get("mutationType") or {}).get("name"), "total_types": len(types)}
    if target:
        item = next((item for item in types if item["name"] == target), None)
        if not item:
            return _json({**result, "success": False, "error": f"Type {target!r} not found."})
        result["type"] = {"name": item["name"], "kind": item["kind"], "description": item.get("description"), "fields": [{"name": field["name"], "type": _type_ref(field.get("type")), "args": [{"name": arg["name"], "type": _type_ref(arg.get("type"))} for arg in field.get("args") or []]} for field in item.get("fields") or []], "input_fields": [{"name": field["name"], "type": _type_ref(field.get("type"))} for field in item.get("inputFields") or []], "enum_values": [item["name"] for item in item.get("enumValues") or []]}
    else:
        maximum = max(1, min(int(args.get("max_types", 80)), 500))
        result["type_names"] = [item["name"] for item in types if item["kind"] in {"OBJECT", "INPUT_OBJECT", "ENUM"}][:maximum]
    return _json(result)
