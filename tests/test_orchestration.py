import unittest
import subprocess
from unittest.mock import MagicMock, patch
from core.orchestrator_manager import DockerOrchestrationEngine


class TestOrchestration(unittest.TestCase):
    @patch("core.orchestrator_manager.subprocess.Popen")
    def test_success_captures_output(self, popen):
        popen.return_value = MagicMock(returncode=0)
        popen.return_value.communicate.return_value = ("Sandbox active\n", "")
        engine = DockerOrchestrationEngine()
        task = engine.spawn_child("sasias_runtime", ["echo", "Sandbox active"])
        self.assertEqual(engine.get_status(task).status, "COMPLETED")
        self.assertEqual(engine.get_status(task).output, ["Sandbox active"])
        self.assertIn("SASIAS_VIEWPORT=1920x1080", popen.call_args.args[0])
        engine.cleanup_all()
        self.assertIsNone(engine.get_status(task))

    @patch("core.orchestrator_manager.subprocess.run")
    @patch("core.orchestrator_manager.subprocess.Popen")
    def test_failure_is_reported(self, popen, remove):
        remove.return_value = MagicMock(returncode=0)
        popen.return_value = MagicMock(returncode=1)
        popen.return_value.communicate.return_value = ("", "failed")
        engine = DockerOrchestrationEngine()
        task = engine.spawn_child("sasias_runtime", ["false"])
        self.assertEqual(engine.get_status(task).status, "FAILED")
        self.assertEqual(engine.get_status(task).error, "failed")

    @patch("core.orchestrator_manager.subprocess.run")
    @patch("core.orchestrator_manager.subprocess.Popen")
    def test_timeout_kills_client_and_removes_container(self, popen, remove):
        popen.return_value.communicate.side_effect = [
            subprocess.TimeoutExpired("docker", 1), ("partial", "")]
        remove.return_value = MagicMock(returncode=0)
        engine = DockerOrchestrationEngine(timeout=1)
        task = engine.spawn_child("sasias_runtime", ["sleep", "60"])
        popen.return_value.kill.assert_called_once()
        self.assertEqual(remove.call_args.args[0], ["docker", "rm", "-f", task])
        self.assertEqual(engine.get_status(task).status, "FAILED")
        self.assertEqual(engine.get_status(task).output, ["partial"])

    @patch("core.orchestrator_manager.subprocess.Popen", side_effect=FileNotFoundError("docker"))
    def test_missing_docker_is_a_failed_task(self, popen):
        engine = DockerOrchestrationEngine()
        task = engine.spawn_child("sasias_runtime", ["true"])
        self.assertEqual(engine.get_status(task).status, "FAILED")
