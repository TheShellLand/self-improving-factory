"""Async access to bounded Docker execution."""
import asyncio

from core.orchestrator_manager import DockerOrchestrationEngine
from core.signals import SignalPulse  # Compatibility import for existing callers.


class ExecutorCore:
    def __init__(self, docker_socket=None, timeout=600, engine=None):
        self.docker_socket = docker_socket
        self.timeout = timeout
        self.engine = engine or DockerOrchestrationEngine(timeout, docker_socket)
        self._registry = {}

    async def dispatch_sandbox(self, image, task_id, viewports=(1920, 1080), *, command):
        """Execute a host-selected command; agent text must never become argv."""
        container_id = await asyncio.to_thread(
            self.engine.spawn_child, image, command, task_id, viewports)
        self._registry[task_id] = self.engine.get_status(container_id)
        return container_id
