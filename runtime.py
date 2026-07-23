"""Managed and external Twenty connection support for Hermes Agent."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_PORT = 3000
DEFAULT_TAG = "latest"

COMPOSE = """name: twenty-crm
services:
  server:
    image: twentycrm/twenty:${TWENTY_IMAGE_TAG:-latest}
    ports:
      - "${TWENTY_BIND_HOST:-127.0.0.1}:${TWENTY_SERVER_PORT:-3000}:3000"
    volumes:
      - server-local-data:/app/packages/twenty-server/.local-storage
    environment:
      NODE_PORT: 3000
      PG_DATABASE_URL: postgres://${PG_DATABASE_USER:-postgres}:${PG_DATABASE_PASSWORD}@db:5432/${PG_DATABASE_NAME:-default}
      SERVER_URL: ${SERVER_URL}
      REDIS_URL: redis://redis:6379
      APP_SECRET: ${APP_SECRET}
      STORAGE_TYPE: local
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl --fail http://localhost:3000/healthz"]
      interval: 5s
      timeout: 5s
      retries: 30
    restart: unless-stopped
  worker:
    image: twentycrm/twenty:${TWENTY_IMAGE_TAG:-latest}
    command: ["yarn", "worker:prod"]
    volumes:
      - server-local-data:/app/packages/twenty-server/.local-storage
    environment:
      PG_DATABASE_URL: postgres://${PG_DATABASE_USER:-postgres}:${PG_DATABASE_PASSWORD}@db:5432/${PG_DATABASE_NAME:-default}
      SERVER_URL: ${SERVER_URL}
      REDIS_URL: redis://redis:6379
      APP_SECRET: ${APP_SECRET}
      DISABLE_DB_MIGRATIONS: "true"
      DISABLE_CRON_JOBS_REGISTRATION: "true"
      STORAGE_TYPE: local
    depends_on:
      db:
        condition: service_healthy
      server:
        condition: service_healthy
    restart: unless-stopped
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: ${PG_DATABASE_NAME:-default}
      POSTGRES_USER: ${PG_DATABASE_USER:-postgres}
      POSTGRES_PASSWORD: ${PG_DATABASE_PASSWORD}
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_DATABASE_USER:-postgres} -d ${PG_DATABASE_NAME:-default}"]
      interval: 5s
      timeout: 5s
      retries: 20
    restart: unless-stopped
  redis:
    image: redis:7
    command: ["redis-server", "--maxmemory-policy", "noeviction"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 20
    restart: unless-stopped
volumes:
  db-data:
  server-local-data:
"""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def hermes_home() -> Path:
    return Path(_env("HERMES_HOME") or (Path.home() / ".hermes")).expanduser()


def connection_mode() -> str:
    mode = (_env("TWENTY_CONNECTION_MODE", "managed") or "managed").lower()
    if mode not in {"managed", "external"}:
        raise ValueError("TWENTY_CONNECTION_MODE must be managed or external.")
    return mode


def managed_project_dir() -> Path:
    configured = _env("TWENTY_MANAGED_PROJECT_DIR")
    return Path(configured).expanduser().resolve() if configured else (hermes_home() / "projects" / "twenty-crm").resolve()


def bind_host() -> str:
    return _env("TWENTY_MANAGED_BIND_HOST", "127.0.0.1") or "127.0.0.1"


def port() -> int:
    try:
        value = int(_env("TWENTY_MANAGED_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT)
        return value if 1 <= value <= 65535 else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


def managed_base_url() -> str:
    return f"http://{bind_host()}:{port()}"


def base_url() -> str:
    if connection_mode() == "managed":
        return managed_base_url()
    value = _env("TWENTY_BASE_URL", "https://api.twenty.com") or "https://api.twenty.com"
    return value if value.startswith(("https://", "http://")) else f"https://{value}"


def autostart_enabled() -> bool:
    return _truthy(_env("TWENTY_MANAGED_AUTOSTART", "true"))


def docker_command() -> list[str] | None:
    docker = shutil.which("docker") or shutil.which("docker.exe")
    return [docker, "compose"] if docker else None


def _compose(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    command = docker_command()
    if not command:
        raise FileNotFoundError("Docker with Docker Compose is required for managed mode.")
    return subprocess.run(command + args, cwd=managed_project_dir(), text=True, capture_output=True, timeout=timeout, check=False)


def _replace(text: str, name: str, value: str) -> str:
    lines = text.splitlines()
    prefix = f"{name}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{value}"
            return "\n".join(lines) + "\n"
    return "\n".join(lines + [f"{prefix}{value}"]) + "\n"


def bootstrap(force: bool = False) -> dict[str, Any]:
    project = managed_project_dir()
    project.mkdir(parents=True, exist_ok=True)
    compose_path, env_path = project / "docker-compose.yml", project / ".env"
    if force or not compose_path.exists():
        compose_path.write_text(COMPOSE, encoding="utf-8")
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    values = {
        "TWENTY_IMAGE_TAG": _env("TWENTY_MANAGED_IMAGE_TAG", DEFAULT_TAG) or DEFAULT_TAG,
        "TWENTY_BIND_HOST": bind_host(),
        "TWENTY_SERVER_PORT": str(port()),
        "SERVER_URL": managed_base_url(),
        "APP_SECRET": _env("TWENTY_MANAGED_APP_SECRET") or secrets.token_urlsafe(48),
        "PG_DATABASE_PASSWORD": _env("TWENTY_MANAGED_PG_PASSWORD") or secrets.token_urlsafe(32),
    }
    for key, value in values.items():
        text = _replace(text, key, value)
    env_path.write_text(text, encoding="utf-8")
    return {"success": True, "project_dir": str(project), "base_url": managed_base_url(), "docker_available": docker_command() is not None}


def healthcheck(url: str | None = None, timeout: float = 3.0) -> dict[str, Any]:
    target = f"{(url or base_url()).rstrip('/')}/healthz"
    try:
        with urlopen(Request(target, headers={"Accept": "application/json"}), timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "url": target, "status_code": response.status, "body": response.read(500).decode("utf-8", errors="replace")}
    except (URLError, OSError) as error:
        return {"ok": False, "url": target, "error": str(error)}


def ensure_running(timeout: int = 120, reason: str = "tool_call") -> dict[str, Any]:
    if connection_mode() == "external":
        return {"success": True, "managed": False, "base_url": base_url(), "reason": "external_connection"}
    bootstrap()
    before = healthcheck(managed_base_url())
    if before.get("ok"):
        return {"success": True, "managed": True, "already_running": True, "base_url": managed_base_url(), "health": before, "reason": reason}
    if not docker_command():
        return {"success": False, "blocking_error": "Managed Twenty requires Docker Desktop or Docker Engine with Docker Compose. Set TWENTY_CONNECTION_MODE=external to connect to an existing instance.", "doctor": doctor()}
    process = _compose(["up", "-d"], timeout=timeout)
    if process.returncode:
        return {"success": False, "blocking_error": "Failed to start managed Twenty.", "details": (process.stderr or process.stdout)[-2000:]}
    deadline = time.time() + timeout
    latest: dict[str, Any] = {}
    while time.time() < deadline:
        latest = healthcheck(managed_base_url())
        if latest.get("ok"):
            return {"success": True, "managed": True, "already_running": False, "base_url": managed_base_url(), "health": latest, "reason": reason}
        time.sleep(2)
    return {"success": False, "blocking_error": f"Managed Twenty did not become healthy within {timeout}s.", "health": latest}


def stop() -> dict[str, Any]:
    if connection_mode() == "external":
        return {"success": False, "error": "External Twenty instances are not managed by this plugin."}
    try:
        process = _compose(["down"])
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        return {"success": False, "error": str(error)}
    return {"success": process.returncode == 0, "details": (process.stderr or process.stdout)[-2000:]}


def status() -> dict[str, Any]:
    mode = connection_mode()
    health = healthcheck()
    result: dict[str, Any] = {"success": True, "connection_mode": mode, "base_url": base_url(), "health": health, "auth_configured": bool(_env("TWENTY_API_KEY") or _env("TWENTY_ACCESS_TOKEN") or (_env("TWENTY_CLIENT_ID") and _env("TWENTY_CLIENT_SECRET")))}
    if mode == "managed":
        result.update({"autostart": autostart_enabled(), "project_dir": str(managed_project_dir()), "docker_available": docker_command() is not None, "compose_exists": (managed_project_dir() / "docker-compose.yml").exists()})
    return result


def logs(tail: int = 80) -> dict[str, Any]:
    if connection_mode() == "external":
        return {"success": False, "error": "External Twenty instances are not managed by this plugin."}
    try:
        process = _compose(["logs", "--tail", str(max(1, tail))])
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        return {"success": False, "error": str(error)}
    return {"success": process.returncode == 0, "stdout": process.stdout, "stderr": process.stderr}


def doctor() -> dict[str, Any]:
    mode = connection_mode()
    return {"success": True, "connection_mode": mode, "base_url": base_url(), "docker_path": (docker_command() or [None])[0], "project_dir": str(managed_project_dir()) if mode == "managed" else None, "next_step": "Create a Twenty API key and set TWENTY_API_KEY after the workspace is available." if mode == "managed" else "Set TWENTY_BASE_URL and one supported authentication method."}
