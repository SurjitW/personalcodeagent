"""
Repository code scanner: AST parsing, symbol indexing, dependency extraction.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, List, Set, Tuple


class CodeScanner:
    """Scans and extracts structural code insights from source trees."""

    IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".idea", ".vscode"}

    @classmethod
    def scan_files(cls, root_dir: str) -> List[Dict[str, Any]]:
        file_list = []
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in cls.IGNORE_DIRS]
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                rel_path = os.path.relpath(full_path, root_dir)
                size = os.path.getsize(full_path)
                ext = os.path.splitext(f)[1].lower()
                file_list.append({
                    "path": rel_path,
                    "filename": f,
                    "extension": ext,
                    "size": size,
                })
        return file_list

    @classmethod
    def extract_python_symbols(cls, file_path: str) -> Dict[str, Any]:
        """Extract functions, classes, and imports from a Python file using AST."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                tree = ast.parse(f.read(), filename=file_path)
        except Exception:
            return {"classes": [], "functions": [], "imports": []}

        classes = []
        functions = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}")

        return {
            "classes": sorted(set(classes)),
            "functions": sorted(set(functions)),
            "imports": sorted(set(imports)),
        }

    @classmethod
    def search_pattern(cls, root_dir: str, pattern: str) -> List[Dict[str, Any]]:
        """Search regex pattern across repository files."""
        results = []
        regex = re.compile(pattern)
        for f in cls.scan_files(root_dir):
            if f["size"] > 1_000_000:  # Skip large binaries (>1MB)
                continue
            abs_path = os.path.join(root_dir, f["path"])
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as fp:
                    for line_no, line in enumerate(fp, start=1):
                        if regex.search(line):
                            results.append({
                                "file": f["path"],
                                "line_number": line_no,
                                "line_content": line.strip(),
                            })
            except Exception:
                continue
        return results
