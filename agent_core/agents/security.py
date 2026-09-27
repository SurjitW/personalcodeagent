"""
Security Validation Agent: AST static analysis, secret detection,
vulnerability audit, and compliance report generation.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from security.scanner import SecurityScanner


class SecurityAgent:
    """Automates static application security testing and secret audits."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.scanner = SecurityScanner(self.workspace)

    def validate(self) -> Dict[str, Any]:
        """Perform security scan and generate reports/security-report.md."""
        res = self.scanner.scan()
        self.scanner.generate_report()
        return res
