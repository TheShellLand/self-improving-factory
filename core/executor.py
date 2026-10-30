"""Async access to bounded Docker execution."""
import asyncio

from core.orchestrator_manager import DockerClient
from core.signals import SignalPulse  # Compatibility import for existing callers.


class ExecutorCore:
    def __init__(self, docker_socket=None, timeout=None, engine=None, *, config=None):
        if engine is not None and (config is not None or timeout is not None or docker_socket is not None):
            raise ValueError("Pass an engine or Docker configuration, not both")
        self.engine = engine if engine is not None else DockerClient(timeout, docker_socket, config=config)
        self.config = getattr(self.engine, "config", None)
        self._registry = {}

    async def dispatch_sandbox(self, image, task_id, viewports=(1920, 1080), *, command):
        """Execute a host-selected command; agent text must never become argv."""
        container_id = await asyncio.to_thread(
            self.engine.spawn_child, image, command, task_id, viewports)
        self._registry[task_id] = self.engine.get_status(container_id)
        return container_id
