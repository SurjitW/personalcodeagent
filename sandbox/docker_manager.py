"""
Docker Container Sandbox Manager.
Manages isolated execution environments with strict resource constraints,
network blocking, non-root user enforcement, and execution timeouts.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DockerSandboxConfig:
    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    timeout_seconds: int = 30
    network_disabled: bool = True
    read_only_root: bool = False
    user: str = "1000:1000"
    env_vars: Dict[str, str] = field(default_factory=dict)


class DockerSandboxManager:
    """Manages Docker execution containers for sandboxed tool execution."""

    def __init__(self, workspace: str, config: Optional[DockerSandboxConfig] = None):
        self.workspace = os.path.abspath(workspace)
        self.config = config or DockerSandboxConfig()
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        if self._docker_available is not None:
            return self._docker_available
        if not shutil.which("docker"):
            self._docker_available = False
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            self._docker_available = (res.returncode == 0)
        except Exception:
            self._docker_available = False
        return self._docker_available

    def run_command(
        self,
        cmd: str,
        timeout: Optional[int] = None,
        workspace_subpath: str = ".",
    ) -> Tuple[int, str, str]:
        """
        Execute command inside an isolated Docker container with resource and network limits.
        """
        if not self.is_docker_available():
            raise RuntimeError("Docker daemon is not available or accessible.")

        timeout_sec = timeout or self.config.timeout_seconds
        target_dir = os.path.abspath(os.path.join(self.workspace, workspace_subpath))

        docker_cmd = [
            "docker", "run", "--rm",
            "--memory", self.config.memory_limit,
            "--cpus", str(self.config.cpu_limit),
            "-v", f"{target_dir}:/workspace:rw",
            "-w", "/workspace",
        ]

        if self.config.network_disabled:
            docker_cmd.extend(["--network", "none"])

        if self.config.user:
            docker_cmd.extend(["--user", self.config.user])

        docker_cmd.extend([self.config.image, "sh", "-c", cmd])

        try:
            proc = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout_sec} seconds in Docker container."
        except Exception as e:
            return -1, "", f"Docker execution error: {e}"
