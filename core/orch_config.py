# SASIAS Orchestrator - Parent Configuration Logic for Host Socket Mounting & Child Spawning Template Verification Prep
"""Description: Definition layer for Phase 3 Deployment logic."""

from dataclasses import dataclass
import os
import subprocess

@dataclass
class SandboxConfig:
    container_name: str
    image_name: str = "sasias-child"
    gpu_alloc: int = 0 # Default no GPU unless specified in metadata signals, One Machine / One LLM Rule applies

    def generate_docker_run(self):
        return (
            f"docker run --rm --name {self.container_name} "
            f"-v /var/run/docker.sock:/var/run/docker.sock "
            f"--network host "
            f"{self.image_name}"
        )
]
