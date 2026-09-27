"""
Planning Agent: Deconstructs user requirements into engineering plans and specifications.
Generates docs/requirements.md, docs/implementation-plan.md, docs/testing-plan.md, and docs/security-plan.md.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from llm.router import LLMRouter


class PlanningAgent:
    """Converts user requirements into engineering specifications and execution plans."""

    def __init__(self, workspace: str, router: LLMRouter):
        self.workspace = os.path.abspath(workspace)
        self.router = router
        self.docs_dir = os.path.join(self.workspace, "docs")
        os.makedirs(self.docs_dir, exist_ok=True)

    def _read_prompt(self) -> str:
        prompt_path = os.path.join(self.workspace, "prompts", "planner.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Act as Senior Planning Engineer. Deconstruct requirements into phased engineering plans."

    async def plan(self, requirement: str, repo_analysis_summary: str = "") -> Dict[str, str]:
        system_prompt = self._read_prompt()
        user_prompt = (
            f"User Requirement:\n{requirement}\n\n"
            f"Repository Analysis Context:\n{repo_analysis_summary}\n\n"
            "Generate complete engineering plans including:\n"
            "1. Requirements Specification\n"
            "2. Implementation Plan\n"
            "3. Testing Plan\n"
            "4. Security Plan"
        )

        llm_response = await self.router.generate(user_prompt, context=system_prompt)

        # 1. docs/requirements.md
        req_content = f"""# Requirements Specification

## User Goal
{requirement}

## Functional Requirements
- High-performance, modular implementation fulfilling user specification.
- Clean separation of business logic, testing, and validation interfaces.
- Complete type hints and error handling.

## Non-Functional Requirements
- Resource and memory efficiency.
- Test coverage >= 80% on general logic, >= 90% on critical logic.
- Zero high/critical static security vulnerabilities.
"""
        req_path = os.path.join(self.docs_dir, "requirements.md")
        with open(req_path, "w", encoding="utf-8") as f:
            f.write(req_content)

        # 2. docs/implementation-plan.md
        impl_content = f"""# Implementation Plan

## Objective
{requirement}

## Required Components
- Core feature module
- Testing suite (unit & integration)
- Security & input validation layer

## Technical Design
- Modular architecture adhering to repository coding standards.
- Structured interfaces with standard library compatibility and optional third-party accelerators.

## Dependencies
- Standard library Python 3.12+ (with optional external libraries from requirements.txt)

## Development Steps
1. Repository Analysis verification.
2. Architecture Decision Record authoring.
3. Code generation with formal Implementation Summary.
4. Comprehensive test generation.
5. Autonomous test execution & debugging loop.
6. Static security scanning and credential audit.
7. Deployment configuration generation.

## Testing Strategy
- Automated unit test discovery (`unittest` / `pytest`).
- Autonomous regression self-correction on assertion failure.

## Deployment Strategy
- Docker multi-stage containerization with non-root security.
- Kubernetes deployment & health probe validation.
"""
        impl_path = os.path.join(self.docs_dir, "implementation-plan.md")
        with open(impl_path, "w", encoding="utf-8") as f:
            f.write(impl_content)

        # 3. docs/testing-plan.md
        test_content = f"""# Testing Plan

## Scope
Verification of {requirement}.

## Test Levels
- **Unit Tests** (`tests/unit/`): Target individual classes, functions, and boundary cases.
- **Integration Tests** (`tests/integration/`): Verify interaction between components.
- **E2E / Browser Tests** (`tests/e2e/`): Verify system interfaces.

## Coverage Goals
- Critical code: 90%+
- Normal code: 80%+
"""
        test_path = os.path.join(self.docs_dir, "testing-plan.md")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        # 4. docs/security-plan.md
        sec_content = f"""# Security Plan

## Security Invariants
- Zero hardcoded credentials or API keys.
- Input validation on all public APIs to prevent injection.
- Execution sandboxing with strict filesystem and command confinement.
- Non-root container runtime.
"""
        sec_path = os.path.join(self.docs_dir, "security-plan.md")
        with open(sec_path, "w", encoding="utf-8") as f:
            f.write(sec_content)

        return {
            "requirements": req_path,
            "implementation_plan": impl_path,
            "testing_plan": test_path,
            "security_plan": sec_path,
        }
