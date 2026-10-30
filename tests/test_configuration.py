import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.config import ApiConfig, DatabaseConfig, DockerConfig, GitConfig, HotLoaderConfig
from core.database import DatabaseClient
from core.gatekeeper import GitClient
from core.orch_config import SandboxConfig
from core.orchestrator_manager import DockerClient
from scripts.main import ApiServer
from ui_backend.bridge import create_app
from fastapi.testclient import TestClient


class TestConfiguration(unittest.TestCase):
    def test_environment_is_read_when_client_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            first = str(Path(directory) / "first.db")
            second = str(Path(directory) / "second.db")
            with patch.dict(os.environ, {"SIF_DB_PATH": first}):
                client = DatabaseClient()
            with patch.dict(os.environ, {"SIF_DB_PATH": second}):
                other = DatabaseClient()
                with TestClient(create_app()) as api:
                    self.assertEqual(api.get("/api/issues").json(), [])
            self.assertEqual(client.config.database_path, Path(first))
            self.assertEqual(other.config.database_path, Path(second))
            self.assertFalse(Path(first).exists())
            self.assertTrue(Path(second).exists())

    def test_database_rolls_back_and_closes_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            client = DatabaseClient(config=DatabaseConfig(Path(directory) / "vault.db"))
            client.initialize()
            with self.assertRaises(RuntimeError):
                with client.connect() as connection:
                    connection.execute("INSERT INTO issues (issue_id, title) VALUES ('test', 'title')")
                    raise RuntimeError("abort")
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
            with client.connect() as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM issues").fetchone()[0], 0)
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    @patch("core.orchestrator_manager.subprocess.run")
    @patch("core.orchestrator_manager.subprocess.Popen")
    def test_docker_uses_config_for_execution_and_cleanup(self, popen, remove):
        popen.return_value = MagicMock(returncode=1)
        popen.return_value.communicate.return_value = ("", "failed")
        remove.return_value = MagicMock(returncode=0)
        config = DockerConfig(timeout=12, cleanup_timeout=3, docker_socket="/tmp/test.sock")
        client = DockerClient(config=config)
        client.spawn_child("image", ["false"])
        popen.return_value.communicate.assert_called_once_with(timeout=12)
        self.assertEqual(popen.call_args.kwargs["env"]["DOCKER_HOST"], "unix:///tmp/test.sock")
        self.assertEqual(remove.call_args.kwargs["timeout"], 3)

    def test_environment_defaults_and_explicit_overrides(self):
        with patch.dict(os.environ, {"SIF_TASK_TIMEOUT": "23", "SIF_POLL_INTERVAL": "7",
                                     "SIF_API_PORT": "8123", "SIF_IMAGE": "custom-image"}):
            self.assertEqual(DockerConfig().timeout, 23)
            self.assertEqual(DockerConfig(timeout=4).timeout, 4)
            self.assertEqual(HotLoaderConfig().poll_interval, 7)
            self.assertEqual(ApiConfig().port, 8123)
            self.assertEqual(SandboxConfig("test").docker_args()[-1], "custom-image")

    def test_invalid_numeric_settings_are_rejected(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    DockerConfig(timeout=value)
                with self.assertRaises(ValueError):
                    HotLoaderConfig(poll_interval=value)
        with self.assertRaises(ValueError):
            ApiConfig(port=65536)

    @patch("scripts.main.uvicorn.run")
    def test_server_uses_api_config(self, run):
        ApiServer(ApiConfig(host="127.0.0.1", port=8123)).run()
        run.assert_called_once_with("ui_backend.bridge:app", host="127.0.0.1", port=8123)

    def test_git_client_uses_explicit_config(self):
        with tempfile.TemporaryDirectory() as directory:
            client = GitClient(config=GitConfig(directory, create=True))
            self.assertTrue(client.execute_proposed_commit(
                "initial", [{"filename": "example.txt", "content": "example"}]))
            self.assertEqual((Path(directory) / "example.txt").read_text(), "example")
            client.repo.close()
