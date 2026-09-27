"""
Repository Analysis Agent: inspects codebase, architecture, dependencies,
testing frameworks, and security risks prior to any modifications.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from repository.scanner import CodeScanner


class RepositoryAnalyzer:
    """Analyzes a codebase and produces repository-analysis.md."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def analyze(self) -> Dict[str, Any]:
        files = CodeScanner.scan_files(self.workspace)

        # Detect primary languages
        ext_counts: Dict[str, int] = {}
        for f in files:
            ext = f["extension"]
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React/JSX",
            ".tsx": "React/TSX",
            ".html": "HTML",
            ".css": "CSS",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".sh": "Shell",
        }
        detected_languages = sorted(
            {lang_map[ext] for ext in ext_counts if ext in lang_map},
            key=lambda l: -sum(ext_counts[k] for k, v in lang_map.items() if v == l),
        )
        primary_language = detected_languages[0] if detected_languages else "Unknown"

        # Detect Frameworks & Libraries
        frameworks = set()
        dependencies: List[str] = []
        req_file = os.path.join(self.workspace, "requirements.txt")
        if os.path.exists(req_file):
            try:
                with open(req_file, "r", encoding="utf-8") as rf:
                    for line in rf:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            pkg = line.split("==")[0].split(">=")[0].split("<")[0].strip()
                            dependencies.append(pkg)
                            if pkg.lower() in ("fastapi", "flask", "django", "tornado", "aiohttp"):
                                frameworks.add(pkg)
                            if pkg.lower() in ("pydantic", "sqlalchemy", "playwright", "pytest", "docker"):
                                frameworks.add(pkg)
            except Exception:
                pass

        pkg_json = os.path.join(self.workspace, "package.json")
        if os.path.exists(pkg_json):
            frameworks.add("Node.js/npm")

        # Detect Entry Points & Important Files
        entry_points = []
        for candidate in ["main.py", "app.py", "server.py", "index.py", "index.js", "app.js"]:
            if os.path.exists(os.path.join(self.workspace, candidate)):
                entry_points.append(candidate)

        important_files = [f["path"] for f in files if f["path"] in (
            "main.py", "agent.py", "sandbox.py", "Agent.md", "SKILL.md",
            "requirements.txt", "docker-compose.yml", "Dockerfile", "pyproject.toml"
        ) or f["path"].startswith("app/") or f["path"].startswith("agent_core/")]

        # Detect Testing Frameworks
        test_frameworks = []
        if any("pytest" in dep.lower() for dep in dependencies):
            test_frameworks.append("pytest")
        if any("test" in f["filename"].lower() for f in files):
            test_frameworks.append("unittest")
        if any("playwright" in dep.lower() for dep in dependencies):
            test_frameworks.append("Playwright")
        if not test_frameworks:
            test_frameworks.append("unittest (Python built-in)")

        # Detect Build Systems
        build_systems = []
        if os.path.exists(os.path.join(self.workspace, "docker-compose.yml")):
            build_systems.append("Docker Compose")
        if os.path.exists(os.path.join(self.workspace, "Dockerfile")):
            build_systems.append("Docker")
        if os.path.exists(os.path.join(self.workspace, "pyproject.toml")):
            build_systems.append("pyproject.toml")
        if os.path.exists(os.path.join(self.workspace, "Makefile")):
            build_systems.append("Make")

        # Identify Security Concerns
        security_concerns = []
        if not os.path.exists(os.path.join(self.workspace, ".gitignore")):
            security_concerns.append("Missing .gitignore file; risk of committing secrets")
        if any(f["filename"] == ".env" for f in files):
            security_concerns.append("Unencrypted .env file detected in workspace")

        # Recommended Changes
        recommended_changes = [
            "Ensure full test coverage across unit, integration, and e2e suites.",
            "Enforce strict Docker container sandbox execution for untrusted code.",
            "Run continuous AST and secret vulnerability scans before deployment.",
        ]

        analysis = {
            "language": primary_language,
            "detected_languages": detected_languages,
            "frameworks": sorted(frameworks) if frameworks else ["Standard Library"],
            "architecture": "Layered Modular Agent Architecture",
            "entry_points": entry_points or ["main.py"],
            "important_files": sorted(important_files),
            "dependencies": dependencies,
            "testing_framework": ", ".join(test_frameworks),
            "build_systems": build_systems or ["Standard Python tooling"],
            "security_concerns": security_concerns or ["None detected (Safe baseline)"],
            "recommended_changes": recommended_changes,
        }
        return analysis

    def generate_markdown(self, output_path: Optional[str] = None) -> str:
        data = self.analyze()
        md = f"""# Repository Analysis

Language:
{data['language']} (All detected: {', '.join(data['detected_languages'])})

Framework:
{', '.join(data['frameworks'])}

Architecture:
{data['architecture']}

Entry Points:
{', '.join(data['entry_points'])}

Important Files:
{chr(10).join(f"- {f}" for f in data['important_files'])}

Dependencies:
{chr(10).join(f"- {d}" for d in data['dependencies'][:20]) or "- Standard library"}

Testing Framework:
{data['testing_framework']}

Security Concerns:
{chr(10).join(f"- {s}" for s in data['security_concerns'])}

Recommended Changes:
{chr(10).join(f"- {r}" for r in data['recommended_changes'])}
"""
        target = output_path or os.path.join(self.workspace, "repository-analysis.md")
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(md)
        return md
