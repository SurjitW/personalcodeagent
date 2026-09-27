"""
Security Scanner: AST-based static application security testing (SAST),
secret detector, and vulnerability audit engine.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SecurityFinding:
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
    category: str
    message: str
    file_path: str
    line_number: int
    snippet: str = ""
    remediation: str = ""


class ASTSecurityVisitor(ast.NodeVisitor):
    """Inspects Python AST for dangerous patterns, insecure functions, and vulnerabilities."""

    def __init__(self, file_path: str, source_lines: List[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.findings: List[SecurityFinding] = []

    def _get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def visit_Call(self, node: ast.Call):
        # 1. Detect eval() and exec()
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("eval", "exec"):
            self.findings.append(SecurityFinding(
                severity="CRITICAL",
                category="Code Injection",
                message=f"Use of dangerous built-in '{func_name}' allows arbitrary code execution.",
                file_path=self.file_path,
                line_number=node.lineno,
                snippet=self._get_line(node.lineno),
                remediation="Refactor to use ast.literal_eval or safe structured parsing.",
            ))

        # 2. Detect subprocess with shell=True
        if func_name in ("Popen", "run", "call", "check_call", "check_output"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.findings.append(SecurityFinding(
                        severity="HIGH",
                        category="Command Injection",
                        message="subprocess invoked with 'shell=True' vulnerable to command injection.",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_line(node.lineno),
                        remediation="Set shell=False and pass arguments as a list of strings.",
                    ))

        # 3. Detect pickle.loads / yaml.load unsafe deserialization
        if func_name in ("loads", "load"):
            parent_mod = ""
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                parent_mod = node.func.value.id
            if parent_mod == "pickle":
                self.findings.append(SecurityFinding(
                    severity="HIGH",
                    category="Insecure Deserialization",
                    message="pickle.load/loads on untrusted data can lead to remote code execution.",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    snippet=self._get_line(node.lineno),
                    remediation="Use json, protobuf, or safe serialization formats instead.",
                ))
            elif parent_mod in ("yaml", "ruamel_yaml"):
                # Check for Loader=SafeLoader
                has_safe_loader = any(kw.arg in ("Loader", "safe_load") for kw in node.keywords)
                if not has_safe_loader and func_name == "load":
                    self.findings.append(SecurityFinding(
                        severity="HIGH",
                        category="Insecure Deserialization",
                        message="yaml.load without SafeLoader allows arbitrary object instantiation.",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        snippet=self._get_line(node.lineno),
                        remediation="Use yaml.safe_load() instead of yaml.load().",
                    ))

        # 4. Weak hash algorithms (MD5, SHA1)
        if func_name in ("md5", "sha1"):
            self.findings.append(SecurityFinding(
                severity="MEDIUM",
                category="Weak Cryptography",
                message=f"Use of cryptographically weak hash algorithm '{func_name}'.",
                file_path=self.file_path,
                line_number=node.lineno,
                snippet=self._get_line(node.lineno),
                remediation="Use sha256 or stronger hashing algorithms.",
            ))

        self.generic_visit(node)


class SecurityScanner:
    """Performs static analysis, secret detection, and dependency checks across workspace."""

    SECRET_PATTERNS = [
        ("AWS Access Key", re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}")),
        ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{32,64}")),
        ("Generic Private Key", re.compile(r"-----BEGIN (?:RSA|OPENSSH|DSA|EC) PRIVATE KEY-----")),
        ("Hardcoded Password", re.compile(r"(?i)(?:password|passwd|secret_key|api_key)\s*=\s*['\"][A-Za-z0-9_\-!@#$%^&*]{8,}['\"]")),
    ]

    IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def scan_file_for_secrets(self, rel_path: str, content: str) -> List[SecurityFinding]:
        findings = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            # Ignore test files or documentation mentioning mock keys
            if "test" in rel_path.lower() or rel_path.endswith(".md"):
                continue
            for name, pattern in self.SECRET_PATTERNS:
                if pattern.search(line):
                    # Exclude placeholders
                    if "os.environ" in line or "os.getenv" in line or "dummy" in line or "mock" in line or "example" in line:
                        continue
                    findings.append(SecurityFinding(
                        severity="CRITICAL",
                        category="Hardcoded Secret",
                        message=f"Potential hardcoded secret detected: {name}",
                        file_path=rel_path,
                        line_number=idx,
                        snippet=line.strip()[:80],
                        remediation="Load secrets dynamically from environment variables or a secret vault.",
                    ))
        return findings

    def scan_file_ast(self, rel_path: str, abs_path: str) -> List[SecurityFinding]:
        if not rel_path.endswith(".py"):
            return []
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=abs_path)
            lines = content.splitlines()
            visitor = ASTSecurityVisitor(rel_path, lines)
            visitor.visit(tree)
            return visitor.findings
        except Exception:
            return []

    def scan(self) -> Dict[str, Any]:
        all_findings: List[SecurityFinding] = []

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for f in files:
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, self.workspace)
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as fp:
                        content = fp.read()
                    all_findings.extend(self.scan_file_for_secrets(rel_path, content))
                    all_findings.extend(self.scan_file_ast(rel_path, abs_path))
                except Exception:
                    continue

        # Sort findings by severity
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        all_findings.sort(key=lambda x: order.get(x.severity, 99))

        critical_count = sum(1 for f in all_findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in all_findings if f.severity == "HIGH")
        passed = (critical_count == 0 and high_count == 0)

        return {
            "passed": passed,
            "total_findings": len(all_findings),
            "critical": critical_count,
            "high": high_count,
            "medium": sum(1 for f in all_findings if f.severity == "MEDIUM"),
            "low": sum(1 for f in all_findings if f.severity == "LOW"),
            "findings": all_findings,
        }

    def generate_report(self, output_path: Optional[str] = None) -> str:
        res = self.scan()
        target = output_path or os.path.join(self.workspace, "reports", "security-report.md")
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)

        md = [
            "# Security Validation Report\n",
            f"**Status**: {'PASSED (Zero High/Critical Findings)' if res['passed'] else 'FAILED (Action Required)'}\n",
            f"- **Total Findings**: {res['total_findings']}",
            f"- **Critical**: {res['critical']}",
            f"- **High**: {res['high']}",
            f"- **Medium**: {res['medium']}",
            f"- **Low**: {res['low']}\n",
        ]

        if not res["findings"]:
            md.append("## Findings\nNo security vulnerabilities or secret leaks detected.\n")
        else:
            md.append("## Detailed Findings\n")
            for f in res["findings"]:
                md.append(f"### [{f.severity}] {f.category} in `{f.file_path}:{f.line_number}`")
                md.append(f"- **Message**: {f.message}")
                if f.snippet:
                    md.append(f"- **Snippet**: `{f.snippet}`")
                md.append(f"- **Remediation**: {f.remediation}\n")

        content = "\n".join(md)
        with open(target, "w", encoding="utf-8") as out:
            out.write(content)
        return content
