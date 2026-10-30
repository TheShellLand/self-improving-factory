"""Bounded, synchronous Docker lifecycle management for the parent host."""
from dataclasses import dataclass, field
import subprocess
import time
import uuid

from core.orch_config import SandboxConfig
from core.config import DockerConfig


@dataclass
class ChildTaskStatus:
    container_id: str
    image_name: str
    command: list[str]
    start_time: float = field(default_factory=time.time)
    status: str = "PENDING"
    output: list[str] = field(default_factory=list)
    error: str = ""
    exit_code: int | None = None
    cleanup_required: bool = False


class DockerClient:
    def __init__(self, timeout=None, docker_socket=None, *, config=None):
        if config is not None and (timeout is not None or docker_socket is not None):
            raise ValueError("Pass Docker options or config, not both")
        self.config = config if config is not None else DockerConfig(timeout, docker_socket)
        self.timeout = self.config.timeout
        self._active_containers = {}
        self.env = self.config.environment()

    def _remove(self, status):
        try:
            result = subprocess.run(["docker", "rm", "-f", status.container_id],
                                    capture_output=True, text=True, timeout=self.config.cleanup_timeout, env=self.env)
            status.cleanup_required = result.returncode != 0 and "No such container" not in result.stderr
            if status.cleanup_required:
                status.error += f"; cleanup failed: {result.stderr.strip()}"
        except (OSError, subprocess.TimeoutExpired) as error:
            status.cleanup_required = True
            status.error += f"; cleanup failed: {error}"

    def spawn_child(self, image, command, task_name=None, viewports=(1920, 1080)):
        if not isinstance(command, (list, tuple)) or not command or any(not isinstance(arg, str) for arg in command):
            raise ValueError("An explicit argument list is required")
        container_id = f"sif_{uuid.uuid4().hex}"
        config = SandboxConfig(container_id, image, viewport=viewports)
        docker_cmd = config.docker_args() + list(command)
        status = ChildTaskStatus(container_id, image, list(command), status="RUNNING")
        self._active_containers[container_id] = status
        try:
            process = subprocess.Popen(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, env=self.env)
            try:
                out, err = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate()
                status.output = out.splitlines()
                status.status = "FAILED"
                status.error = f"Execution exceeded {self.timeout} seconds: {err}"
                self._remove(status)
            else:
                status.output = out.splitlines()
                status.exit_code = process.returncode
                status.status = "COMPLETED" if process.returncode == 0 else "FAILED"
                status.error = err
                if process.returncode != 0:
                    self._remove(status)
        except OSError as error:
            status.status = "FAILED"
            status.error = str(error)
        return container_id

    def get_status(self, container_id):
        return self._active_containers.get(container_id)

    def cleanup_all(self):
        """Retry failed cleanup and retain unresolved registrations for inspection."""
        for status in self._active_containers.values():
            if status.cleanup_required:
                self._remove(status)
        self._active_containers = {key: value for key, value in self._active_containers.items()
                                   if value.status == "RUNNING" or value.cleanup_required}


# Compatibility name for existing integrations.
DockerOrchestrationEngine = DockerClient
