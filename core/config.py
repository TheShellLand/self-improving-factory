"""Configuration objects following automonisaur's Config/Client convention."""
import math
import os
from pathlib import Path

from automon.helpers.osWrapper import environ

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DatabaseConfig:
    def __init__(self, database_path=None, schema_path=None):
        self.database_path = Path(database_path if database_path is not None else
                                  environ("SIF_DB_PATH", str(PROJECT_ROOT / "history_vault.db")))
        self.schema_path = Path(schema_path if schema_path is not None else
                                PROJECT_ROOT / "schema" / "history_vault_schema.sql")


class DockerConfig:
    def __init__(self, timeout=None, docker_socket=None, cleanup_timeout=None):
        self.timeout = float(timeout if timeout is not None else environ("SIF_TASK_TIMEOUT", 600))
        self.cleanup_timeout = float(cleanup_timeout if cleanup_timeout is not None else
                                     environ("SIF_CLEANUP_TIMEOUT", 10))
        if any(not math.isfinite(value) or value <= 0
               for value in (self.timeout, self.cleanup_timeout)):
            raise ValueError("Docker timeouts must be finite and positive")
        self.docker_host = (f"unix://{docker_socket}" if docker_socket is not None else
                            environ("DOCKER_HOST"))

    def environment(self):
        environment = os.environ.copy()
        if self.docker_host is not None:
            environment["DOCKER_HOST"] = self.docker_host
        return environment


class HotLoaderConfig:
    def __init__(self, poll_interval=None):
        self.poll_interval = float(poll_interval if poll_interval is not None else
                                   environ("SIF_POLL_INTERVAL", 5))
        if not math.isfinite(self.poll_interval) or self.poll_interval <= 0:
            raise ValueError("poll_interval must be finite and positive")


class ApiConfig:
    def __init__(self, host=None, port=None):
        self.host = host if host is not None else environ("SIF_API_HOST", "0.0.0.0")
        self.port = int(port if port is not None else environ("SIF_API_PORT", 8000))
        if not 1 <= self.port <= 65535:
            raise ValueError("API port must be between 1 and 65535")


class GitConfig:
    def __init__(self, repo_path, create=False):
        self.repo_path = Path(repo_path).resolve()
        self.create = create


# Compatibility exports; runtime clients resolve settings on construction.
DATABASE_PATH = DatabaseConfig().database_path
SCHEMA_PATH = DatabaseConfig().schema_path
