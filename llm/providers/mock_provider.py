"""
Deterministic Mock LLM Provider for offline execution, unit tests, and simulations.
Simulates all phases of the Autonomous Engineering lifecycle without API keys.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class MockProvider(LLMProvider):
    """Offline mock provider that produces realistic engineering responses."""

    def __init__(self, model: str = "mock-coding-agent", **kwargs):
        super().__init__(
            name="mock",
            model=model,
            cost_per_million_input=0.0,
            cost_per_million_output=0.0,
            **kwargs,
        )

    async def generate(self, prompt: str, context: str = "") -> str:
        prompt_lower = (prompt + " " + context).lower()
        await asyncio.sleep(0.01)

        # Estimate mock tokens
        p_tokens = self.estimate_tokens(prompt + context)

        if "requirement" in prompt_lower or "planning" in prompt_lower or "planner" in prompt_lower:
            resp = (
                "# Engineering Requirements & Implementation Plan\n\n"
                "## Objective\nFulfill the requested software engineering specification.\n\n"
                "## Required Components\n- Core implementation module\n- Automated unit test suite\n- Security & input validation\n\n"
                "## Development Steps\n1. Design architecture and schemas\n2. Implement core business logic\n3. Generate comprehensive unit tests\n4. Execute and self-correct\n5. Validate security invariants\n"
            )
        elif "architect" in prompt_lower or "decision record" in prompt_lower:
            resp = (
                "# Architecture Decision Record\n\n"
                "Problem: Design a robust, decoupled autonomous module fulfilling user specifications.\n\n"
                "Options:\n1. Monolithic single-file script\n2. Modular layered architecture with explicit interfaces\n\n"
                "Chosen Design: Modular layered architecture\n\n"
                "Reason: Ensures testability, isolation, and future extensibility.\n\n"
                "Tradeoffs: Slightly higher file footprint in exchange for superior maintainability.\n\n"
                "Future Improvements: Add distributed cache and event streaming.\n"
            )
        elif "debug" in prompt_lower or "fix" in prompt_lower or "failure" in prompt_lower:
            resp = (
                "# Debug Report\n\n"
                "Error: AssertionError / Verification test failure\n"
                "Cause: Edge case logic in boundary conditions\n"
                "Affected Files: core implementation\n"
                "Fix Applied: Adjusted boundary condition check to handle zero and negative inputs correctly\n"
                "Validation Result: Resolved, all unit test assertions pass\n"
            )
        elif "security" in prompt_lower:
            resp = (
                "# Security Audit Report\n\n"
                "Status: PASSED\n"
                "Vulnerabilities Identified: 0 Critical, 0 High, 0 Medium\n"
                "Checks Performed:\n- AST injection analysis\n- Secret leakage scanning\n- Path traversal verification\n\n"
                "Remediation: All inputs sanitized and safe execution paths confirmed.\n"
            )
        elif "deployment" in prompt_lower:
            resp = (
                "# Deployment Validation Report\n\n"
                "Status: SUCCESS\n"
                "Artifacts:\n- Dockerfile validated\n- Container health check: HEALTHY\n- Kubernetes manifest verified\n"
            )
        else:
            resp = (
                "Implementation Summary:\n"
                "Files Changed: core implementation module\n"
                "Design Reason: Implemented clean, modular solution with complete error handling.\n"
                "Potential Risks: Low risk, covered by automated test cases.\n"
                "Testing Approach: Unit tests validating normal and edge case behaviors.\n\n"
                "Execution successfully performed.\n"
            )

        c_tokens = self.estimate_tokens(resp)
        self.record_usage(p_tokens, c_tokens)
        self.call_history.append({"prompt": prompt[:100], "response": resp[:100]})
        return resp
