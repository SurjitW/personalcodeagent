"""
Deployment Agent: Containerization, Kubernetes manifests, CI/CD pipelines,
and deployment readiness validation.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from deployment.deployer import DeploymentAgent as BaseDeployer, DeploymentValidationResult


class DevOpsAgent:
    """Automates Docker, Kubernetes, and CI/CD pipelines."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.deployer = BaseDeployer(self.workspace)

    def prepare_deployment(self, app_entrypoint: str = "main.py") -> DeploymentValidationResult:
        self.deployer.generate_dockerfile(app_entrypoint=app_entrypoint)
        self.deployer.generate_k8s_manifests()
        self.deployer.generate_ci_cd()
        return self.deployer.validate_deployment()
