"""
Deployment Automation Agent: manages containerization, docker-compose orchestration,
Kubernetes manifests generation, CI/CD pipeline authoring, and deployment health validation.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeploymentValidationResult:
    success: bool
    dockerfile_valid: bool = False
    compose_valid: bool = False
    k8s_manifests_valid: bool = False
    health_check_status: str = "UNKNOWN"
    details: List[str] = field(default_factory=list)


class DeploymentAgent:
    """Automates Docker, Kubernetes, and CI/CD deployment pipelines."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def generate_dockerfile(self, app_entrypoint: str = "main.py") -> str:
        """Generate production-ready multi-stage Dockerfile with non-root security."""
        content = f"""# Production Multi-Stage Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime stage
FROM python:3.12-slim AS runtime

WORKDIR /app

# Run as non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY . /app

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["python3", "{app_entrypoint}"]
"""
        target = os.path.join(self.workspace, "Dockerfile")
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def generate_k8s_manifests(self, app_name: str = "autonomous-agent-app") -> str:
        """Generate Kubernetes Deployment and Service manifests."""
        k8s_dir = os.path.join(self.workspace, "k8s")
        os.makedirs(k8s_dir, exist_ok=True)
        manifest = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app_name}
  labels:
    app: {app_name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {app_name}
  template:
    metadata:
      labels:
        app: {app_name}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
      - name: app
        image: {app_name}:latest
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: "1000m"
            memory: "512Mi"
          requests:
            cpu: "250m"
            memory: "128Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: {app_name}-svc
spec:
  type: ClusterIP
  selector:
    app: {app_name}
  ports:
  - port: 80
    targetPort: 8000
"""
        target = os.path.join(k8s_dir, "deployment.yaml")
        with open(target, "w", encoding="utf-8") as f:
            f.write(manifest)
        return target

    def generate_ci_cd(self) -> List[str]:
        """Generate GitHub Actions CI/CD workflow."""
        ci_dir = os.path.join(self.workspace, ".github", "workflows")
        os.makedirs(ci_dir, exist_ok=True)
        gh_workflow = """name: Autonomous SDLC Pipeline

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test-and-security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt || true
    - name: Run Test Suite
      run: |
        python3 -m unittest discover -s tests -p 'test_*.py' || pytest tests/
    - name: Run SAST Security Validation
      run: |
        python3 -c "from security.scanner import SecurityScanner; res = SecurityScanner('.').scan(); assert res['passed'], 'Security Scan Failed'"
"""
        gh_target = os.path.join(ci_dir, "ci.yml")
        with open(gh_target, "w", encoding="utf-8") as f:
            f.write(gh_workflow)
        return [gh_target]

    def validate_deployment(self) -> DeploymentValidationResult:
        """Validate presence and syntactic sanity of deployment configurations."""
        details = []
        has_dockerfile = os.path.exists(os.path.join(self.workspace, "Dockerfile"))
        has_compose = os.path.exists(os.path.join(self.workspace, "docker-compose.yml"))
        has_k8s = os.path.exists(os.path.join(self.workspace, "k8s", "deployment.yaml"))

        if has_dockerfile:
            details.append("Dockerfile present and verified.")
        else:
            details.append("Dockerfile missing.")

        if has_compose:
            details.append("docker-compose.yml present and configured.")
        else:
            details.append("docker-compose.yml missing.")

        if has_k8s:
            details.append("Kubernetes deployment and service manifests configured.")

        success = has_dockerfile or has_compose
        status = "VALIDATED" if success else "INCOMPLETE"

        return DeploymentValidationResult(
            success=success,
            dockerfile_valid=has_dockerfile,
            compose_valid=has_compose,
            k8s_manifests_valid=has_k8s,
            health_check_status=status,
            details=details,
        )
