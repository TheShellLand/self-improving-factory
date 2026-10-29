"""Docker command construction shared by sandbox callers."""
from dataclasses import dataclass
import shlex
from core.signals import Viewport


@dataclass
class SandboxConfig:
    container_name: str
    image_name: str = "sif_runtime"
    gpu_alloc: int = 0
    viewport: tuple[int, int] = (1920, 1080)

    def docker_args(self):
        viewport = Viewport(width=self.viewport[0], height=self.viewport[1])
        if not self.image_name or self.image_name.startswith("-"):
            raise ValueError("An image name is required")
        args = ["docker", "run", "--rm", "--name", self.container_name,
                "-e", f"SIF_VIEWPORT={viewport.width}x{viewport.height}", "--network", "host"]
        if self.gpu_alloc:
            args.extend(["--gpus", str(self.gpu_alloc)])
        return [*args, self.image_name]

    def generate_docker_run(self):
        return shlex.join(self.docker_args())
