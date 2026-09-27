"""
Automated test suite for Autonomous Coding Agent.
Tests tool execution, workspace sandboxing, ReAct parsing, and end-to-end agent workflow.
"""

import json
import os
import shutil
import tempfile
import unittest

from agent import (
    AICodingAgent,
    AgentMode,
    AgentStep,
    MockCodingLLM,
    ToolRegistry,
    _parse_react_response,
    create_coding_tools,
    extract_correction_prompt,
    get_safe_path,
)
from sandbox import (
    SandboxPolicy,
    execute_sandboxed_command,
    is_command_safe,
    validate_path,
)
from web_tester import (
    ChromeWebTester,
    WorkspaceWebServer,
)


class TestCodingTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agent_test_")
        self.tools = create_coding_tools(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sandboxing_security(self):
        """Ensure path traversal attacks are blocked."""
        with self.assertRaises(PermissionError):
            get_safe_path(self.test_dir, "../../../etc/passwd")

        with self.assertRaises(PermissionError):
            get_safe_path(self.test_dir, "/etc/shadow")

        # Valid relative path should stay inside test_dir
        safe = get_safe_path(self.test_dir, "foo/bar.py")
        self.assertTrue(safe.startswith(os.path.abspath(self.test_dir)))

    def test_file_lifecycle_tools(self):
        """Test write_file, read_file, edit_file, and list_directory."""
        write_tool = self.tools.get("write_file")
        read_tool = self.tools.get("read_file")
        edit_tool = self.tools.get("edit_file")
        list_tool = self.tools.get("list_directory")

        # 1. Write file
        res = write_tool.execute(path="src/app.py", content="def hello():\n    return 'world'\n")
        self.assertIn("Successfully wrote", res)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "src/app.py")))

        # 2. Read file with line numbering
        read_res = read_tool.execute(path="src/app.py")
        self.assertIn("1 | def hello():", read_res)
        self.assertIn("2 |     return 'world'", read_res)

        # 3. Read slice
        slice_res = read_tool.execute(path="src/app.py", start_line=2, end_line=2)
        self.assertNotIn("def hello():", slice_res)
        self.assertIn("2 |     return 'world'", slice_res)

        # 4. Edit file
        edit_res = edit_tool.execute(
            path="src/app.py",
            target_content="return 'world'",
            replacement_content="return 'antigravity'"
        )
        self.assertIn("Successfully updated", edit_res)
        updated_read = read_tool.execute(path="src/app.py")
        self.assertIn("return 'antigravity'", updated_read)

        # 5. Edit file error on missing target
        err_res = edit_tool.execute(
            path="src/app.py",
            target_content="nonexistent text",
            replacement_content="new"
        )
        self.assertIn("target_content not found", err_res)

        # 6. List directory
        list_res = list_tool.execute(path=".")
        self.assertIn("[DIR] src", list_res)

    def test_search_code(self):
        """Test searching across multiple files."""
        write_tool = self.tools.get("write_file")
        search_tool = self.tools.get("search_code")

        write_tool.execute(path="mod1.py", content="def calculate_total(x): return x * 2\n")
        write_tool.execute(path="mod2.py", content="import math\n# calculate_total used elsewhere\n")

        search_res = search_tool.execute(query="calculate_total")
        self.assertIn("mod1.py:1:", search_res)
        self.assertIn("mod2.py:2:", search_res)

    def test_run_command(self):
        """Test shell command runner, output, and safety blocks."""
        run_tool = self.tools.get("run_command")

        # Normal command
        res = run_tool.execute(command="python3 -c 'print(\"agent_ok\")'")
        self.assertIn("[Exit code: 0]", res)
        self.assertIn("agent_ok", res)

        # Dangerous command block
        danger_res = run_tool.execute(command="rm -rf /")
        self.assertIn("Blocked command for safety", danger_res)


class TestReActParser(unittest.TestCase):
    def test_parse_action(self):
        raw = (
            "Thought: I should check directory files.\n"
            "Action: list_directory\n"
            'Action Input: {"path": "."}\n'
        )
        step = _parse_react_response(raw)
        self.assertEqual(step.thought, "I should check directory files.")
        self.assertEqual(step.action, "list_directory")
        self.assertEqual(step.action_input, {"path": "."})

    def test_parse_final_answer(self):
        raw = (
            "Thought: All tests passed.\n"
            "Final Answer: The feature has been implemented and tested successfully."
        )
    def test_parse_think_tags(self):
        """Test that reasoning models with <think> tags (like DeepSeek-R1) parse correctly."""
        raw = (
            "<think>\n"
            "I need to inspect the current repository to see what files exist.\n"
            "</think>\n"
            "Action: list_directory\n"
            'Action Input: {"path": "."}\n'
        )
        step = _parse_react_response(raw)
        self.assertIn("inspect the current repository", step.thought)
        self.assertEqual(step.action, "list_directory")
        self.assertEqual(step.action_input, {"path": "."})

    def test_openrouter_client_config(self):
        """Test that OpenRouterClient is pre-configured with free models and headers."""
        from agent import OpenRouterClient
        client = OpenRouterClient(api_key="test_key")
        self.assertEqual(client.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(client.model, "qwen/qwen-2.5-coder-32b-instruct:free")
        self.assertEqual(client.extra_headers.get("X-Title"), "Personal AI Coding Agent")

        # Custom free model override
        r1_client = OpenRouterClient(api_key="test_key", model="deepseek/deepseek-r1:free")
        self.assertEqual(r1_client.model, "deepseek/deepseek-r1:free")


class TestAgentEndToEnd(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agent_e2e_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_e2e_mock_workflow(self):
        """Verify the complete autonomous ReAct loop: plan -> write code -> write test -> run test -> finish."""
        mock_llm = MockCodingLLM()
        agent = AICodingAgent(
            workspace=self.test_dir,
            llm=mock_llm,
            max_steps=15,
            verbose=False
        )

        task = "Create a palindrome module and verify it with automated tests."
        final_answer = agent.run(task)

        # Verify files were created
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "solution.py")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test_solution.py")))
        self.assertIn("completed successfully", final_answer)
        self.assertIn("iterative refinement", final_answer)

    def test_e2e_mock_prompt_custom_task(self):
        """Verify the mock agent adapts filenames and code based on prompt keywords."""
        mock_llm = MockCodingLLM()
        agent = AICodingAgent(
            workspace=self.test_dir,
            llm=mock_llm,
            max_steps=15,
            verbose=False
        )

        task = "Write a fibonacci sequence generator in fib.py with tests"
        final_answer = agent.run(task)

        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "fib.py")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test_fib.py")))
        self.assertIn("completed successfully", final_answer)

    def test_self_refinement_interception(self):
        """Verify that AICodingAgent rejects premature Final Answer when last command failed."""
        class PrematureExitLLM:
            def __init__(self):
                self.turn = 0
            def generate_step(self, messages, tools):
                self.turn += 1
                if self.turn == 1:
                    # Run a failing test command
                    return AgentStep(
                        thought="Running test",
                        action="run_command",
                        action_input={"command": "python3 -c 'import sys; sys.exit(1)'"}
                    )
                if self.turn == 2:
                    # Try to prematurely claim done while test failed
                    return AgentStep(
                        thought="Done",
                        final_answer="Premature completion."
                    )
                # Turn 3: Received refinement intercept prompt! Now fix and succeed
                if self.turn == 3:
                    return AgentStep(
                        thought="Fixing code and re-running test",
                        action="run_command",
                        action_input={"command": "python3 -c 'print(\"success\"); exit(0)'"}
                    )
                return AgentStep(
                    thought="All tests pass now",
                    final_answer="Completed after refinement."
                )

        agent = AICodingAgent(
            workspace=self.test_dir,
            llm=PrematureExitLLM(),
            max_steps=10,
            verbose=False,
            auto_refine=True
        )

        final_answer = agent.run("Fix failing test")
        self.assertEqual(final_answer, "Completed after refinement.")
        self.assertEqual(agent.refinement_attempts, 1)
        self.assertEqual(agent.last_command_exit_code, 0)


class TestAgentModesAndCorrection(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agent_modes_")
        self.agent = AICodingAgent(
            workspace=self.test_dir,
            llm=MockCodingLLM(),
            max_steps=10,
            verbose=False
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_planning_mode(self):
        """Verify planning mode generates a structured implementation plan."""
        res = self.agent.run("Build a real-time chat application", mode=AgentMode.PLANNING)
        self.assertIn("# Implementation Plan", res)
        self.assertIn("Work Breakdown Structure", res)
        self.assertIn("Verification Strategy", res)

    def test_architecture_mode(self):
        """Verify architecture mode produces system architecture specifications."""
        res = self.agent.run("Design high throughput payment service", mode=AgentMode.ARCHITECTURE)
        self.assertIn("# System Architecture Specification", res)
        self.assertIn("Component Boundaries", res)
        self.assertIn("Data Flow", res)

    def test_code_review_mode_and_prompt_extraction(self):
        """Verify code review mode produces findings and suggested correction prompt."""
        res = self.agent.run("Review solution.py for code quality", mode=AgentMode.CODE_REVIEW)
        self.assertIn("# Code Review Report", res)
        self.assertIn("Suggested Correction Prompt", res)
        prompt = extract_correction_prompt(res)
        self.assertIsNotNone(prompt)
        self.assertIn("Refactor solution.py", prompt)

    def test_security_review_mode_and_prompt_extraction(self):
        """Verify security review mode produces vulnerability audit and suggested correction prompt."""
        res = self.agent.run("Audit solution.py for security vulnerabilities", mode=AgentMode.SECURITY_REVIEW)
        self.assertIn("# Security Audit Report", res)
        self.assertIn("CWE-22", res)
        self.assertIn("Suggested Correction Prompt", res)
        prompt = extract_correction_prompt(res)
        self.assertIsNotNone(prompt)
        self.assertIn("Patch solution.py", prompt)

    def test_review_and_auto_correct_workflow(self):
        """Verify run_review_and_correct performs review, extracts prompt, applies fix in coding mode, and tests."""
        review_res, coding_res = self.agent.run_review_and_correct(
            task="Security audit solution.py",
            mode=AgentMode.SECURITY_REVIEW,
            auto_confirm=True
        )
        self.assertIn("# Security Audit Report", review_res)
        self.assertIsNotNone(coding_res)
        self.assertIn("Coding task completed successfully", coding_res)
        # Verify the solution and test files were created and verified
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "solution.py")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test_solution.py")))


class TestWebTestingWithChrome(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agent_web_")
        self.tools = create_coding_tools(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_web_page_tool_assertions_pass(self):
        """Verify test_web_page tool validates title, selectors, and expected text."""
        write_tool = self.tools.get("write_file")
        test_web_tool = self.tools.get("test_web_page")

        html_content = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head><title>Dashboard App</title></head>\n"
            "<body>\n"
            "  <div id='container' class='main-view'>\n"
            "    <h1>System Status: Operational</h1>\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )
        write_tool.execute(path="index.html", content=html_content)

        res = test_web_tool.execute(
            target="index.html",
            expected_title="Dashboard App",
            expected_selectors=["#container", "h1"],
            expected_text=["System Status: Operational"],
            forbidden_text=["Fatal Error"]
        )
        self.assertIn("[Web Test PASSED]", res)
        self.assertIn("All assertions passed successfully!", res)

    def test_web_page_tool_assertions_fail(self):
        """Verify test_web_page tool catches missing selectors, title mismatch, and forbidden text."""
        write_tool = self.tools.get("write_file")
        test_web_tool = self.tools.get("test_web_page")

        html_content = (
            "<html><head><title>Wrong Title</title></head>"
            "<body><div>Error: Service Unavailable</div></body></html>"
        )
        write_tool.execute(path="error.html", content=html_content)

        res = test_web_tool.execute(
            target="error.html",
            expected_title="Expected Title",
            expected_selectors=["#nonexistent"],
            expected_text=["Success"],
            forbidden_text=["Service Unavailable"]
        )
        self.assertIn("[Web Test FAILED]", res)
        self.assertIn("Title mismatch", res)
        self.assertIn("Expected element ID '#nonexistent' not found", res)
        self.assertIn("Expected text 'Success' not found", res)
        self.assertIn("Forbidden text 'Service Unavailable' was detected", res)

    def test_workspace_web_server_lifecycle(self):
        """Verify starting, querying, and stopping workspace web server."""
        start_tool = self.tools.get("start_web_server")
        stop_tool = self.tools.get("stop_web_server")
        test_web_tool = self.tools.get("test_web_page")
        write_tool = self.tools.get("write_file")

        write_tool.execute(path="test.html", content="<html><body>Served Over HTTP</body></html>")

        # Start server
        start_res = start_tool.execute()
        self.assertIn("Web server started", start_res)

        # Stop server
        stop_res = stop_tool.execute()
        self.assertEqual(stop_res, "Web server stopped.")


class TestSandboxSecurity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agent_sandbox_")
        self.policy = SandboxPolicy()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_symlink_escape_blocking(self):
        """Ensure symlinks pointing outside workspace are blocked from reads and writes."""
        # Create an outside file
        outside_file = tempfile.NamedTemporaryFile(delete=False)
        outside_file.write(b"sensitive host content")
        outside_file.close()

        try:
            # Create a symlink in the workspace pointing outside
            symlink_path = os.path.join(self.test_dir, "symlink_escape")
            os.symlink(outside_file.name, symlink_path)

            # validate_path must block access
            with self.assertRaises(PermissionError):
                validate_path(self.test_dir, "symlink_escape", write=False, policy=self.policy)

            with self.assertRaises(PermissionError):
                validate_path(self.test_dir, "symlink_escape", write=True, policy=self.policy)
        finally:
            os.unlink(outside_file.name)

    def test_protected_paths_write_blocking(self):
        """Ensure write operations to .git and protected paths are rejected."""
        git_dir = os.path.join(self.test_dir, ".git")
        os.makedirs(git_dir, exist_ok=True)

        with self.assertRaises(PermissionError):
            validate_path(self.test_dir, ".git/config", write=True, policy=self.policy)

    def test_command_blocking_privileged_binaries(self):
        """Ensure privileged binaries (sudo, su, chown, systemctl) are blocked."""
        cmd_sudo = "sudo apt-get install malware"
        safe, reason = is_command_safe(cmd_sudo, self.policy)
        self.assertFalse(safe)
        self.assertIn("Blocked command for safety", reason)

        cmd_chown = "chown root:root file.txt"
        safe, reason = is_command_safe(cmd_chown, self.policy)
        self.assertFalse(safe)
        self.assertIn("Blocked command for safety", reason)

    def test_command_blocking_redirections(self):
        """Ensure command write redirections to system directories are blocked."""
        cmd_redir = "echo 'evil' > /etc/shadow"
        safe, reason = is_command_safe(cmd_redir, self.policy)
        self.assertFalse(safe)
        self.assertIn("Blocked command for safety", reason)


if __name__ == "__main__":
    unittest.main()
