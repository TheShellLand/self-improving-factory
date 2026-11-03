"""Configuration objects following automonisaur's Config/Client convention."""
import math
import os
from pathlib import Path

from automon.helpers.osWrapper import environ

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DatabaseConfig:
    def __init__(self, database_path=None, schema_path=None):
        self.database_path = Path(database_path if database_path is not None else
                                  environ("SIFH_DB_PATH", str(PROJECT_ROOT / "history_vault.db")))
        self.schema_path = Path(schema_path if schema_path is not None else
                                PROJECT_ROOT / "schema" / "history_vault_schema.sql")


class DockerConfig:
    def __init__(self, timeout=None, docker_socket=None, cleanup_timeout=None):
        self.timeout = float(timeout if timeout is not None else environ("SIFH_TASK_TIMEOUT", 600))
        self.cleanup_timeout = float(cleanup_timeout if cleanup_timeout is not None else
                                     environ("SIFH_CLEANUP_TIMEOUT", 10))
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
                                   environ("SIFH_POLL_INTERVAL", 5))
        if not math.isfinite(self.poll_interval) or self.poll_interval <= 0:
            raise ValueError("poll_interval must be finite and positive")


class ApiConfig:
    def __init__(self, host=None, port=None):
        self.host = host if host is not None else environ("SIFH_API_HOST", "0.0.0.0")
        self.port = int(port if port is not None else environ("SIFH_API_PORT", 8000))
        if not 1 <= self.port <= 65535:
            raise ValueError("API port must be between 1 and 65535")


class PiAgentConfig:
    def __init__(self, executable=None, model=None, provider=None, timeout=None,
                 cleanup_timeout=None, max_record_bytes=None, max_events=None):
        # Preserve literal strings: environ coerces "true" and strips quotes.
        self.executable = self._text(executable, "SIFH_PI_EXECUTABLE", "pi")
        self.model = self._text(model, "SIFH_MODEL")
        self.provider = self._text(provider, "SIFH_PROVIDER")
        self.timeout = self._positive(timeout, "SIFH_TIMEOUT", 120)
        self.cleanup_timeout = self._positive(cleanup_timeout, "SIFH_PI_CLEANUP_TIMEOUT", 5)
        limit = max_record_bytes if max_record_bytes is not None else os.getenv(
            "SIFH_PI_MAX_RECORD_BYTES", "1048576")
        if isinstance(limit, bool) or not isinstance(limit, (str, int)):
            raise ValueError("SIFH_PI_MAX_RECORD_BYTES must be a positive integer")
        try:
            self.max_record_bytes = int(limit)
        except ValueError:
            raise ValueError("SIFH_PI_MAX_RECORD_BYTES must be a positive integer") from None
        if self.max_record_bytes <= 0:
            raise ValueError("SIFH_PI_MAX_RECORD_BYTES must be a positive integer")
        event_limit = max_events if max_events is not None else os.getenv(
            "SIFH_PI_MAX_EVENTS", "10000")
        if isinstance(event_limit, bool) or not isinstance(event_limit, (str, int)):
            raise ValueError("SIFH_PI_MAX_EVENTS must be a positive integer")
        try:
            self.max_events = int(event_limit)
        except ValueError:
            raise ValueError("SIFH_PI_MAX_EVENTS must be a positive integer") from None
        if self.max_events <= 0:
            raise ValueError("SIFH_PI_MAX_EVENTS must be a positive integer")

    @staticmethod
    def _text(value, name, default=None):
        value = value if value is not None else os.getenv(name, default)
        if value is not None and (not isinstance(value, str) or not value.strip() or "\0" in value):
            raise ValueError(f"{name} must be a nonempty string without NUL characters")
        return value

    @staticmethod
    def _positive(value, name, default):
        value = value if value is not None else os.getenv(name, str(default))
        try:
            if isinstance(value, bool):
                raise ValueError
            result = float(value)
            if not math.isfinite(result) or result <= 0:
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{name} must be finite and positive") from None
        return result

    def environment(self):
        # Provider credentials retain their exact environment values. No invented PI_* mappings.
        return os.environ.copy()

    def argv(self):
        args = [self.executable, "--mode", "rpc", "--no-session", "--no-tools",
                "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes"]
        if self.provider:
            args.extend(["--provider", self.provider])
        if self.model:
            args.extend(["--model", self.model])
        return args

class GitConfig:
    def __init__(self, repo_path, create=False):
        self.repo_path = Path(repo_path).resolve()
        self.create = create


# Compatibility exports; runtime clients resolve settings on construction.
DATABASE_PATH = DatabaseConfig().database_path
SCHEMA_PATH = DatabaseConfig().schema_path
