import unittest
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

    @patch("core.orchestrator_manager.subprocess.Popen")
    def test_failure_is_reported(self, popen):
        popen.return_value = MagicMock(returncode=1)
        popen.return_value.communicate.return_value = ("", "failed")
        engine = DockerOrchestrationEngine()
        task = engine.spawn_child("sasias_runtime", ["false"])
        self.assertEqual(engine.get_status(task).status, "FAILED")
        self.assertEqual(engine.get_status(task).error, "failed")
