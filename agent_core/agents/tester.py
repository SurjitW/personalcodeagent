"""
Unit Test Generation Agent: Ensures every code change has automated tests.
Generates tests/unit/, tests/integration/, tests/e2e/ with coverage targets.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from testing.test_generator import TestGenerator
from testing.test_runner import TestRunner, TestResult


class TesterAgent:
    """Creates automated test suites and validates execution results."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.generator = TestGenerator(self.workspace)
        self.runner = TestRunner(self.workspace)

    def generate_and_save_test(
        self,
        category: str,
        filename: str,
        module_name: str,
        classes: List[str],
        functions: List[str],
    ) -> str:
        code = self.generator.generate_unit_test(
            module_name=module_name,
            classes=classes,
            functions=functions,
        )
        return self.generator.write_test_file(category, filename, code)

    def run_all_tests(self, test_path: str = "tests") -> TestResult:
        result = self.runner.run_tests(test_path=test_path)
        self.runner.generate_report(result)
        return result
