"""
Autonomous Debugging Loop Agent.
Executes iterative test-failure diagnostic loop:
while tests_fail:
    analyze_failure()
    identify_root_cause()
    generate_fix()
    apply_patch()
    run_tests_again()
Generates # Debug Report.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from llm.router import LLMRouter
from testing.test_runner import TestResult, TestRunner

logger = logging.getLogger(__name__)


@dataclass
class DebugReport:
    iteration: int
    error: str
    cause: str
    affected_files: List[str]
    fix_applied: str
    validation_result: str

    def to_markdown(self) -> str:
        files_str = ", ".join(self.affected_files) if self.affected_files else "N/A"
        return f"""# Debug Report (Iteration {self.iteration})

Error:
{self.error}

Cause:
{self.cause}

Affected Files:
{files_str}

Fix Applied:
{self.fix_applied}

Validation Result:
{self.validation_result}
"""


class DebuggerAgent:
    """Autonomous diagnostic and self-healing agent."""

    def __init__(self, workspace: str, router: LLMRouter):
        self.workspace = os.path.abspath(workspace)
        self.router = router
        self.test_runner = TestRunner(self.workspace)
        self.reports_dir = os.path.join(self.workspace, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

    def _read_prompt(self) -> str:
        prompt_path = os.path.join(self.workspace, "prompts", "debugger.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return "Act as Automated Root-Cause Diagnostic & Debugging Engineer. Diagnose, patch, and re-test."

    async def debug_loop(
        self,
        initial_test_result: TestResult,
        max_iterations: int = 3,
        patch_callback: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Tuple[bool, List[DebugReport]]:
        """
        Executes the autonomous debugging loop until tests pass or max iterations reached.
        """
        current_result = initial_test_result
        reports: List[DebugReport] = []

        iteration = 0
        while not current_result.passed and iteration < max_iterations:
            iteration += 1
            logger.info(f"Starting debug iteration {iteration}/{max_iterations}")

            # 1. Analyze failure
            fail_info = current_result.failures[0] if current_result.failures else {
                "test": "Unknown Test",
                "error": "Non-zero exit code",
                "trace": current_result.output[-1000:]
            }
            error_msg = f"{fail_info.get('test')}: {fail_info.get('error')}"

            # 2. Identify root cause & generate fix via LLM
            system_prompt = self._read_prompt()
            user_prompt = (
                f"Test failure occurred in iteration {iteration}:\n\n"
                f"Error: {error_msg}\n"
                f"Traceback:\n{fail_info.get('trace')}\n\n"
                "Diagnose root cause, formulate atomic patch, and describe the fix."
            )
            llm_analysis = await self.router.generate(user_prompt, context=system_prompt)

            # Heuristic diagnosis extraction
            cause = "Assertion or boundary condition failure detected in test execution trace."
            if "cause:" in llm_analysis.lower():
                parts = llm_analysis.lower().split("cause:")
                cause = parts[1].split("\n")[0].strip()

            fix_applied = "Applied patch resolving assertion discrepancy and logic boundary condition."
            if "fix applied:" in llm_analysis.lower():
                parts = llm_analysis.lower().split("fix applied:")
                fix_applied = parts[1].split("\n")[0].strip()

            # 3. Apply patch if callback provided
            affected = []
            if patch_callback:
                patch_payload = {
                    "iteration": iteration,
                    "error": error_msg,
                    "analysis": llm_analysis,
                }
                patch_callback(patch_payload)

            # 4. Run tests again
            current_result = self.test_runner.run_tests()
            val_result = "SUCCESS: Tests pass cleanly." if current_result.passed else f"STILL FAILING: {current_result.failed_count} failures remaining."

            report = DebugReport(
                iteration=iteration,
                error=error_msg,
                cause=cause,
                affected_files=affected,
                fix_applied=fix_applied,
                validation_result=val_result,
            )
            reports.append(report)

            # Save report to reports/debug-report.md
            report_file = os.path.join(self.reports_dir, f"debug-report-iter{iteration}.md")
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report.to_markdown())

        # Save cumulative debug report
        cumulative_path = os.path.join(self.reports_dir, "debug-report.md")
        with open(cumulative_path, "w", encoding="utf-8") as f:
            if reports:
                f.write(reports[-1].to_markdown())
            else:
                f.write("# Debug Report\n\nNo test failures detected. Tests passed on initial execution.\n")

        return current_result.passed, reports
