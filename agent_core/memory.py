"""
Agent Memory System: Short-term scratchpad and Long-term project memory.
Stores architecture decisions, coding patterns, previous fixes, and project history.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ArchitectureMemory:
    timestamp: str
    problem: str
    decision: str
    tradeoffs: str


@dataclass
class FixMemory:
    timestamp: str
    error: str
    cause: str
    fix_applied: str
    files: List[str] = field(default_factory=list)


class ProjectMemory:
    """Manages persistent project memory across engineering cycles."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.memory_file = os.path.join(self.workspace, ".agent_memory.json")
        self.short_term_context: List[Dict[str, Any]] = []
        self.architecture_decisions: List[Dict[str, Any]] = []
        self.known_fixes: List[Dict[str, Any]] = []
        self.coding_patterns: Dict[str, str] = {}
        self.load()

    def record_decision(self, problem: str, decision: str, tradeoffs: str = "") -> None:
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "problem": problem,
            "decision": decision,
            "tradeoffs": tradeoffs,
        }
        self.architecture_decisions.append(entry)
        self.save()

    def record_fix(self, error: str, cause: str, fix_applied: str, files: Optional[List[str]] = None) -> None:
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": error,
            "cause": cause,
            "fix_applied": fix_applied,
            "files": files or [],
        }
        self.known_fixes.append(entry)
        self.save()

    def add_short_term(self, role: str, content: str) -> None:
        self.short_term_context.append({"role": role, "content": content})
        if len(self.short_term_context) > 50:
            self.short_term_context.pop(0)

    def load(self) -> None:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.architecture_decisions = data.get("architecture_decisions", [])
                    self.known_fixes = data.get("known_fixes", [])
                    self.coding_patterns = data.get("coding_patterns", {})
            except Exception as e:
                logger.warning(f"Could not load memory file: {e}")

    def save(self) -> None:
        try:
            data = {
                "architecture_decisions": self.architecture_decisions,
                "known_fixes": self.known_fixes,
                "coding_patterns": self.coding_patterns,
            }
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist memory: {e}")
