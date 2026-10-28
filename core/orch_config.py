"""Docker command construction shared by sandbox callers."""
from dataclasses import dataclass
import shlex


@dataclass
class SandboxConfig:
    container_name: str
    image_name: str = "sasias_runtime"
    gpu_alloc: int = 0

    def docker_args(self):
        args = ["docker", "run", "--rm", "--name", self.container_name,
                "-e", "SASIAS_VIEWPORT=1920x1080", "--network", "host"]
        if self.gpu_alloc:
            args.extend(["--gpus", str(self.gpu_alloc)])
        return [*args, self.image_name]

    def generate_docker_run(self):
        return shlex.join(self.docker_args())
