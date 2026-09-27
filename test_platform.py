"""
Comprehensive automated test suite for the Autonomous Software Engineering Agent Platform.
Tests all agents, LLM router & providers, repository analyzer, sandbox, security scanner,
debugger loop, deployment generator, and orchestrator.
"""

import asyncio
import os
import shutil
import tempfile
import unittest

from agent_core.agents import (
    ArchitectureAgent,
    CoderAgent,
    DebuggerAgent,
    DevOpsAgent,
    PlanningAgent,
    SecurityAgent,
    TesterAgent,
)
from agent_core.memory import ProjectMemory
from agent_core.orchestrator import AgentOrchestrator
from agent_core.state import AgentTaskState, SDLCStage, TaskStatus
from agent_core.workflow import SDLCWorkflow
from deployment.deployer import DeploymentAgent
from llm.provider import TokenUsage
from llm.providers.mock_provider import MockProvider
from llm.router import LLMRouter
from repository.analyzer import RepositoryAnalyzer
from repository.scanner import CodeScanner
from sandbox.docker_manager import DockerSandboxConfig, DockerSandboxManager
from sandbox.executor import SandboxExecutor, SandboxPolicy, is_command_safe, validate_path
from security.scanner import SecurityFinding, SecurityScanner
from testing.test_generator import TestGenerator
from testing.test_runner import TestResult, TestRunner


class TestLLMArchitecture(unittest.TestCase):
    """Test LLM provider abstraction, token/cost tracking, and router fallback."""

    def test_mock_provider_token_and_cost_tracking(self):
        prov = MockProvider(cost_per_million_input=1.0, cost_per_million_output=2.0)
        res = asyncio.run(prov.generate("Generate requirements plan"))
        self.assertIn("Requirements", res)

        stats = prov.get_stats()
        self.assertGreater(stats["total_tokens"], 0)
        self.assertEqual(stats["total_calls"], 1)

    def test_router_fallback_chain(self):
        """Test fallback when preferred provider is not reachable or mock is fallback."""
        router = LLMRouter(primary_name="mock", fallback_names=["mock"])
        res = asyncio.run(router.generate("Design architecture decision record"))
        self.assertIn("Architecture", res)

        agg = router.get_aggregated_stats()
        self.assertGreater(agg["total_tokens"], 0)
        self.assertIn("mock", agg["providers"])


class TestRepositoryAnalysis(unittest.TestCase):
    """Test repository analyzer and AST scanner."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="repo_test_")
        # Create a mock repo structure
        os.makedirs(os.path.join(self.test_dir, "app"), exist_ok=True)
        with open(os.path.join(self.test_dir, "app", "server.py"), "w") as f:
            f.write("class Server:\n    pass\n\ndef run():\n    return True\n")
        with open(os.path.join(self.test_dir, "requirements.txt"), "w") as f:
            f.write("fastapi>=0.115.0\npydantic>=2.0.0\npytest\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_analyzer_markdown_generation(self):
        analyzer = RepositoryAnalyzer(self.test_dir)
        data = analyzer.analyze()
        self.assertEqual(data["language"], "Python")
        self.assertIn("fastapi", [f.lower() for f in data["frameworks"]])

        md_path = os.path.join(self.test_dir, "repository-analysis.md")
        analyzer.generate_markdown(md_path)
        self.assertTrue(os.path.exists(md_path))
        with open(md_path, "r") as f:
            content = f.read()
        self.assertIn("# Repository Analysis", content)
        self.assertIn("Language:", content)
        self.assertIn("Testing Framework:", content)

    def test_ast_symbol_extraction(self):
        py_file = os.path.join(self.test_dir, "app", "server.py")
        syms = CodeScanner.extract_python_symbols(py_file)
        self.assertIn("Server", syms["classes"])
        self.assertIn("run", syms["functions"])


class TestSandboxExecution(unittest.TestCase):
    """Test unified sandbox executor and security policies."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sandbox_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_path_confinement(self):
        with self.assertRaises(PermissionError):
            validate_path(self.test_dir, "/etc/passwd", write=True)

    def test_command_safety_filtering(self):
        safe, reason = is_command_safe("rm -rf /")
        self.assertFalse(safe)

        safe, reason = is_command_safe("sudo apt-get update")
        self.assertFalse(safe)

        safe, _ = is_command_safe("echo 'hello world'")
        self.assertTrue(safe)

    def test_sandboxed_command_execution(self):
        executor = SandboxExecutor(self.test_dir)
        out = executor.execute("echo 'autonomous sandbox test'")
        self.assertIn("autonomous sandbox test", out)
        self.assertIn("[Exit code: 0]", out)


class TestSecurityScanner(unittest.TestCase):
    """Test AST static analysis and secret detection."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sec_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_detect_eval_and_shell(self):
        vuln_code = (
            "import os, subprocess\n"
            "user_input = '__import__(\"os\").system(\"id\")'\n"
            "eval(user_input)\n"
            "subprocess.run('ls', shell=True)\n"
        )
        file_path = os.path.join(self.test_dir, "vuln.py")
        with open(file_path, "w") as f:
            f.write(vuln_code)

        scanner = SecurityScanner(self.test_dir)
        res = scanner.scan()
        self.assertFalse(res["passed"])
        self.assertGreater(res["critical"] + res["high"], 0)

        # Generate report
        rep_file = os.path.join(self.test_dir, "sec_report.md")
        report = scanner.generate_report(rep_file)
        self.assertTrue(os.path.exists(rep_file))
        self.assertIn("Code Injection", report)


class TestAutonomousSDLCAndOrchestrator(unittest.TestCase):
    """Test full SDLC workflow and AgentOrchestrator."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="orch_test_")
        # Seed an Agent.md
        with open(os.path.join(self.test_dir, "Agent.md"), "w") as f:
            f.write("# Agent Configuration\nLanguage: Python\nTesting Rules: pytest and unittest\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_workflow_state_machine(self):
        self.assertTrue(SDLCWorkflow.can_transition(SDLCStage.IDLE, SDLCStage.REQUIREMENT_ANALYSIS))
        self.assertTrue(SDLCWorkflow.can_transition(SDLCStage.REQUIREMENT_ANALYSIS, SDLCStage.REPOSITORY_ANALYSIS))
        self.assertTrue(SDLCWorkflow.can_transition(SDLCStage.TEST_EXECUTION, SDLCStage.DEBUGGING))
        self.assertFalse(SDLCWorkflow.can_transition(SDLCStage.IDLE, SDLCStage.DEPLOYMENT))

    def test_end_to_end_orchestrator_execution(self):
        router = LLMRouter(primary_name="mock")
        policy = SandboxPolicy(allow_write=True, allow_network=True)
        orch = AgentOrchestrator(workspace=self.test_dir, router=router, sandbox_policy=policy)

        # Track steps via listener
        recorded_steps = []
        orch.subscribe(lambda state, step: recorded_steps.append(step.stage))

        # Execute task
        task = "Design and implement a thread-safe token bucket rate limiter module with unit tests"
        result_state = asyncio.run(orch.execute_task(requirement=task))

        self.assertEqual(result_state.status, TaskStatus.SUCCESS)
        self.assertEqual(result_state.current_stage, SDLCStage.COMPLETED)
        self.assertGreater(len(recorded_steps), 5)

        # Check documentation generation
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "docs", "requirements.md")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "docs", "implementation-plan.md")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "docs", "architecture.md")))

        # Check engineering report
        report_file = os.path.join(self.test_dir, "reports", "engineering-report.md")
        self.assertTrue(os.path.exists(report_file))
        with open(report_file, "r") as f:
            content = f.read()

        self.assertIn("# Engineering Report", content)
        self.assertIn("## Requirement", content)
        self.assertIn("## Analysis", content)
        self.assertIn("## Architecture", content)
        self.assertIn("## Implementation", content)
        self.assertIn("## Files Changed", content)
        self.assertIn("## Tests Created", content)
        self.assertIn("## Test Results", content)
        self.assertIn("## Security Review", content)
        self.assertIn("## Deployment Status", content)
        self.assertIn("## Remaining Issues", content)
        self.assertIn("## Recommendations", content)

    def test_debugger_loop(self):
        router = LLMRouter(primary_name="mock")
        debugger = DebuggerAgent(self.test_dir, router)

        failing_res = TestResult(
            passed=False,
            total=2,
            passed_count=1,
            failed_count=1,
            failures=[{"test": "test_boundary", "error": "AssertionError: 5 != 10", "trace": "line 42, in test_boundary"}]
        )

        passed, reports = asyncio.run(debugger.debug_loop(failing_res, max_iterations=2))
        self.assertGreater(len(reports), 0)
        self.assertIn("Debug Report", reports[0].to_markdown())


if __name__ == "__main__":
    unittest.main()
