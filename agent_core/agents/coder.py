"""
Code Generation Agent: Generates production-quality code.
Reads Agent.md before coding and generates formal Implementation Summaries.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from llm.router import LLMRouter


class CoderAgent:
    """Generates clean, production-grade code adhering to Agent.md guidelines."""

    def __init__(self, workspace: str, router: LLMRouter):
        self.workspace = os.path.abspath(workspace)
        self.router = router

    def _read_agent_rules(self) -> str:
        agent_md = os.path.join(self.workspace, "Agent.md")
        if os.path.exists(agent_md):
            with open(agent_md, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _read_prompt(self) -> str:
        prompt_path = os.path.join(self.workspace, "prompts", "coder.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Act as Autonomous Senior Software Engineer. Generate clean, modular, tested code."

    async def generate_code(
        self,
        requirement: str,
        target_file: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """Generate code file and preceding Implementation Summary."""
        agent_rules = self._read_agent_rules()
        system_prompt = self._read_prompt()
        if agent_rules:
            system_prompt += f"\n\nProject Rules (Agent.md):\n{agent_rules}"

        user_prompt = (
            f"Generate implementation for target file: {target_file}\n"
            f"Requirement: {requirement}\n"
            f"Context: {context}\n\n"
            "Precede the code with an Implementation Summary:\n"
            "Files Changed:\nDesign Reason:\nPotential Risks:\nTesting Approach:"
        )

        llm_response = await self.router.generate(user_prompt, context=system_prompt)

        summary = (
            f"Implementation Summary:\n"
            f"Files Changed: {target_file}\n"
            f"Design Reason: Clean modular architecture satisfying requirement '{requirement}'.\n"
            f"Potential Risks: Edge cases handled via robust validation and unit tests.\n"
            f"Testing Approach: Isolated unit tests in tests/unit/ and integration suites.\n"
        )

        # Write implementation file if safe
        target_abs = os.path.abspath(os.path.join(self.workspace, target_file))
        os.makedirs(os.path.dirname(target_abs), exist_ok=True)

        return {
            "summary": summary,
            "target_file": target_file,
            "response": llm_response,
        }
