"""
Web testing module for Autonomous Coding Agent.
Supports running a local workspace web server and performing automated
web-based code testing with Chrome (headless) or built-in DOM fallback.
"""

from __future__ import annotations

import functools
import http.server
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple


def find_free_port(start_port: int = 8080) -> int:
    """Find an available port starting from start_port."""
    for p in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class WorkspaceWebServer:
    """Lightweight background HTTP server for testing workspace web code."""

    def __init__(self, workspace: str, port: Optional[int] = None):
        self.workspace = os.path.abspath(workspace)
        self.port = port or find_free_port()
        self.server: Optional[http.server.HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self) -> str:
        if self._is_running:
            return f"Web server already running at http://127.0.0.1:{self.port}"

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.workspace)
        try:
            self.server = http.server.HTTPServer(("127.0.0.1", self.port), handler)
        except OSError as e:
            self.port = find_free_port(self.port + 1)
            self.server = http.server.HTTPServer(("127.0.0.1", self.port), handler)

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._is_running = True
        return f"Web server started at http://127.0.0.1:{self.port}"

    def stop(self) -> str:
        if not self._is_running or not self.server:
            return "Web server is not running."
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        self._is_running = False
        return "Web server stopped."

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


class SimpleDOMParser(HTMLParser):
    """Fallback HTML parser to inspect tags, attributes, and text when Chrome is unavailable."""

    def __init__(self):
        super().__init__()
        self.title: Optional[str] = None
        self.in_title: bool = False
        self.tags: List[str] = []
        self.ids: Set[str] = set()
        self.classes: Set[str] = set()
        self.text_content: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        self.tags.append(tag)
        if tag == "title":
            self.in_title = True
        for name, val in attrs:
            if not val:
                continue
            if name == "id":
                self.ids.add(val)
            elif name == "class":
                for c in val.split():
                    self.classes.add(c)

    def handle_endtag(self, tag: str):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str):
        cleaned = data.strip()
        if self.in_title and cleaned:
            self.title = cleaned
        if cleaned:
            self.text_content.append(cleaned)


class ChromeWebTester:
    """Runs web tests against URLs or local HTML files using Chrome (headless) or DOM fallback."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.chrome_bin = self._find_chrome()

    def _find_chrome(self) -> Optional[str]:
        """Detect Chrome/Chromium executable."""
        custom = os.environ.get("CHROME_PATH") or os.environ.get("CHROME_BIN")
        if custom and os.path.isfile(custom) and os.access(custom, os.X_OK):
            return custom

        candidates = [
            "google-chrome-stable",
            "google-chrome",
            "chromium",
            "chromium-browser",
        ]
        for c in candidates:
            path = shutil.which(c)
            if path:
                return path
        return None

    def test_url_or_file(
        self,
        target: str,
        expected_title: Optional[str] = None,
        expected_selectors: Optional[List[str]] = None,
        expected_text: Optional[List[str]] = None,
        forbidden_text: Optional[List[str]] = None,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """
        Tests a web page or file.
        `target` can be:
        - A full URL (e.g. 'http://127.0.0.1:8080/index.html')
        - A workspace-relative file path (e.g. 'index.html')
        """
        errors: List[str] = []
        is_local_file = False
        target_url = target

        if not (target.startswith("http://") or target.startswith("https://")):
            # It's a local file path
            local_path = os.path.join(self.workspace, target) if not os.path.isabs(target) else target
            if not os.path.exists(local_path) and os.path.exists(target):
                local_path = os.path.abspath(target)
            if not os.path.exists(local_path):
                return {
                    "success": False,
                    "target": target,
                    "engine": "none",
                    "error": f"Target file '{target}' does not exist in workspace.",
                    "errors": [f"Target file '{target}' does not exist in workspace."],
                    "details": []
                }
            is_local_file = True
            target_url = f"file://{os.path.abspath(local_path)}"

        # 1. Attempt Headless Chrome execution if binary exists
        dom_html = ""
        engine = "none"

        if self.chrome_bin:
            try:
                cmd = [
                    self.chrome_bin,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--dump-dom",
                    target_url
                ]
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout
                )
                if proc.returncode == 0 and proc.stdout:
                    dom_html = proc.stdout
                    engine = f"Chrome Headless ({os.path.basename(self.chrome_bin)})"
                else:
                    err_msg = proc.stderr.strip()
                    pass
            except Exception:
                pass

        # 2. Fallback to urllib / local file reading & parser if Chrome wasn't available or failed
        if not dom_html:
            try:
                if is_local_file:
                    with open(os.path.abspath(local_path), "r", encoding="utf-8", errors="replace") as f:
                        dom_html = f.read()
                    engine = "Local File Parser (Chrome fallback)"
                else:
                    req = urllib.request.Request(target_url, headers={"User-Agent": "PersonalCodeAgent/1.0"})
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        dom_html = resp.read().decode("utf-8", errors="replace")
                    engine = "HTTP DOM Engine (Chrome fallback)"
            except Exception as e:
                return {
                    "success": False,
                    "target": target,
                    "engine": engine,
                    "error": f"Failed to retrieve target '{target}': {e}",
                    "errors": [f"Failed to retrieve target '{target}': {e}"],
                    "details": []
                }

        # 3. Parse and assert DOM assertions
        parser = SimpleDOMParser()
        try:
            parser.feed(dom_html)
        except Exception as e:
            errors.append(f"HTML Parse Warning: {e}")

        # Check title
        if expected_title:
            actual_title = parser.title or ""
            if expected_title.lower() not in actual_title.lower():
                errors.append(
                    f"Title mismatch: Expected title to contain '{expected_title}', got '{actual_title}'."
                )

        # Check expected text
        all_text = " ".join(parser.text_content) + " " + dom_html
        if expected_text:
            for exp in expected_text:
                if exp.lower() not in all_text.lower():
                    errors.append(f"Expected text '{exp}' not found in rendered DOM.")

        # Check forbidden text
        if forbidden_text:
            for forb in forbidden_text:
                if forb.lower() in all_text.lower():
                    errors.append(f"Forbidden text '{forb}' was detected in rendered DOM.")

        # Check selectors (ids or tag names)
        if expected_selectors:
            for sel in expected_selectors:
                sel = sel.strip()
                if sel.startswith("#"):
                    elem_id = sel[1:]
                    if elem_id not in parser.ids:
                        errors.append(f"Expected element ID '{sel}' not found in DOM.")
                elif sel.startswith("."):
                    cls = sel[1:]
                    if cls not in parser.classes:
                        errors.append(f"Expected class '{sel}' not found in DOM.")
                else:
                    # Tag name
                    if sel.lower() not in [t.lower() for t in parser.tags]:
                        errors.append(f"Expected HTML tag '<{sel}>' not found in DOM.")

        success = len(errors) == 0
        dom_preview = dom_html[:500] + ("..." if len(dom_html) > 500 else "")

        return {
            "success": success,
            "engine": engine,
            "target": target,
            "page_title": parser.title,
            "errors": errors,
            "dom_preview": dom_preview
        }
