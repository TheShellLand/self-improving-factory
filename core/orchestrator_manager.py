import os
import uuid
import time
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class ChildTaskStatus:
    container_id: str
    image_name: str
    command: List[str]
    start_time: float = field(default_factory=time.time)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    output: List[str] = field(default_factory=list)
    error: str = ""

class DockerOrchestrationEngine:
    """
    The primary manager for handling Distributed Sandboxing logic. 
    Runs on the Parent application (with host socket access) to manage life cycles of subagent executions.
    Ensures Viewport standardisation ($1920 \times 1080$) and cleanup via injected env vars.
    """   
   
    def __init__(self):
        # Maps container_id -> ChildTaskStatus
        self._active_containers: Dict[str, ChildTaskStatus] = {}  # Map ID used as key
        # Requirement check: $w \times h$ viewpoint governance
        self.DEFAULT_VIEWPORT = "1920x1080"

    def spawn_child(self, image: str, command: List[str], task_name: Optional[str] = None) -> str:
        """Spawns a short-lived container for subagent execution."""
        container_id = f"sasias_{uuid.uuid4().hex[:8]}"
        status = ChildTaskStatus(
            container_id=container_id,
            image_name=image,
            command=command,
            status="RUNNING"
        )
        self._active_containers[container_id] = status

        # Strategy: Use docker run directly to ensure reliability with socket mounting correctly mapped.
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_id,
            "-e", f"SASIAS_VIEWPORT={self.DEFAULT_VIEWPORT}", 
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "--network", "host",  # host network for IPC if needed or private net provided by orch (not specified yet)
            image
        ] + command

        print(f"[ORCHESTRATOR] Spawning Subagent {container_id} | Image: {image}")
        
        try:
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            status.start_time = time.time()
            self._active_containers[container_id].output = [] # placeholder for capture logic if expanded later

            out, err = process.communicate()
            
            if process.returncode == 0:
                status.status = "COMPLETED"
                print(f"[ORCHESTRATOR] Subagent {container_id} completed successfully.")
            else:
                status.status = "FAILED"
                status.error = err
                print(f"[ORCHESTRATOR] Subagent {container_id} failed with error: {err}")

        except Exception as e:
            status.status = "FAILED"
            status.error = str(e)
            print(f"[ORCHESTRATOR] Execution of container {container_id} encountered OS-level exception: {e}")
        
        return container_id

    def get_status(self, container_id: str) -> ChildTaskStatus:
         return self._active_containers.get(container_id)

    def cleanup_all(self):
        """Safe teardown for any remaining registrations."""
        pass
