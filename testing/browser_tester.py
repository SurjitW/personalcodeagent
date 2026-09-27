"""
Browser Testing Agent: Chrome & Playwright browser automation suite.
Executes browser workflows, validates UI, captures screenshots, and collects console logs.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from web_tester import ChromeWebTester, WorkspaceWebServer

logger = logging.getLogger(__name__)


@dataclass
class BrowserTestResult:
    passed: bool
    url: str
    title: str = ""
    console_logs: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    html_snippet: str = ""


class BrowserTestingAgent:
    """Manages browser workflows and UI validation using headless Chrome and Playwright."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.web_tester = ChromeWebTester(workspace=self.workspace)
        self.screenshots_dir = os.path.join(self.workspace, "reports", "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)

    def test_page(
        self,
        target: str,
        expected_title: Optional[str] = None,
        required_text: Optional[str] = None,
        forbidden_text: Optional[str] = None,
        take_screenshot: bool = True,
    ) -> BrowserTestResult:
        """Test a web URL or local HTML file in headless browser and validate constraints."""
        res_dict = self.web_tester.test_page(
            url_or_path=target,
            expected_title=expected_title,
            required_text=required_text,
            forbidden_text=forbidden_text,
        )

        passed = res_dict.get("passed", False)
        title = res_dict.get("title", "")
        errors = res_dict.get("errors", [])

        # Screenshot capture if supported
        screenshot_file = None
        if take_screenshot:
            screenshot_file = os.path.join(self.screenshots_dir, "test_render.png")
            # If chrome exists, we can capture screenshot via headless cli
            chrome_bin = self.web_tester.chrome_bin
            if chrome_bin and os.path.exists(target):
                try:
                    subprocess.run(
                        [chrome_bin, "--headless", "--disable-gpu", f"--screenshot={screenshot_file}", target],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                except Exception:
                    pass

        return BrowserTestResult(
            passed=passed,
            url=target,
            title=title,
            errors=errors,
            screenshot_path=screenshot_file if (screenshot_file and os.path.exists(screenshot_file)) else None,
            html_snippet=res_dict.get("body_text", "")[:300],
        )
