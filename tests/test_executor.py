import unittest
from unittest.mock import Mock
from core.executor import ExecutorCore
from core.orchestrator_manager import DockerOrchestrationEngine


class TestExecutor(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_delegates_and_registers_actual_status(self):
        engine = Mock()
        engine.spawn_child.return_value = "container-id"
        engine.get_status.return_value = Mock(status="COMPLETED")
        executor = ExecutorCore(engine=engine)
        result = await executor.dispatch_sandbox("image", "task", command=["true"])
        self.assertEqual(result, "container-id")
        self.assertEqual(executor._registry["task"].status, "COMPLETED")
        engine.spawn_child.assert_called_once_with("image", ["true"], "task", (1920, 1080))

    def test_shell_string_is_not_an_argument_list(self):
        with self.assertRaises(ValueError):
            DockerOrchestrationEngine().spawn_child("image", "echo hello")
