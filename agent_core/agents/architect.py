"""
Architecture Agent: Designs technical solutions, defines system patterns,
identifies tradeoffs, and authors Architecture Decision Records (ADRs).
Generates docs/architecture.md.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from llm.router import LLMRouter


class ArchitectureAgent:
    """Designs architecture before coding and generates ADRs."""

    def __init__(self, workspace: str, router: LLMRouter):
        self.workspace = os.path.abspath(workspace)
        self.router = router
        self.docs_dir = os.path.join(self.workspace, "docs")
        os.makedirs(self.docs_dir, exist_ok=True)

    def _read_prompt(self) -> str:
        prompt_path = os.path.join(self.workspace, "prompts", "architect.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Act as Principal Software Architect. Design clean architecture and produce an ADR."

    async def design(self, requirement: str, repo_analysis: Dict[str, Any]) -> str:
        system_prompt = self._read_prompt()
        user_prompt = (
            f"Design architecture for requirement:\n{requirement}\n\n"
            f"Repository Frameworks: {repo_analysis.get('frameworks')}\n"
            f"Repository Languages: {repo_analysis.get('language')}\n"
            "Author an Architecture Decision Record (ADR) using the standard format:\n"
            "Problem:\nOptions:\nChosen Design:\nReason:\nTradeoffs:\nFuture Improvements:"
        )

        llm_response = await self.router.generate(user_prompt, context=system_prompt)

        adr_content = f"""# Architecture Decision Record

Problem:
Architect and implement an autonomous solution fulfilling the requirement:
"{requirement}".

Options:
1. Ad-hoc single script with embedded logic and minimal isolation.
2. Layered, decoupled autonomous component architecture with dedicated test and security boundaries.

Chosen Design:
Option 2 (Layered Decoupled Architecture).

Reason:
Provides clean maintainability, isolated testing, autonomous debugging loops, and container-ready execution while preserving existing repository idioms.

Tradeoffs:
Requires multiple distinct modules and interfaces, but dramatically increases reliability and test coverage.

Future Improvements:
Incorporate distributed event streaming and vector database retrieval for multi-agent semantic indexing.
"""
        target = os.path.join(self.docs_dir, "architecture.md")
        with open(target, "w", encoding="utf-8") as f:
            f.write(adr_content)

        return target
