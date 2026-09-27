#!/usr/bin/env python3
"""
Main entry point for the Autonomous Coding Agent.
Supports one-shot task execution, interactive REPL, and offline demonstration mode.
"""

import argparse
import os
import sys

from agent import (
    AICodingAgent,
    AgentMode,
    GeminiClient,
    MockCodingLLM,
    OpenAICompatibleClient,
    OpenRouterClient,
    OPENROUTER_FREE_MODELS,
)
from sandbox import SandboxPolicy
from web_tester import ChromeWebTester


def print_banner():
    banner = r"""
   ___ ___  ___ ___ _  _  ___     _   ___ ___ _  _ _____ 
  / __/ _ \|   \_ _| \| |/ __|   /_\ / __| __| \| |_   _|
 | (_| (_) | |) | || .` | (_ |  / _ \ (_ | _|| .` | | |  
  \___\___/|___/___|_|\_|\___| /_/ \_\___|___|_|\_| |_|  
    """
    print(f"\033[96m{banner}\033[0m")
    print("\033[1m Autonomous AI Coding Agent (ReAct Loop + Tool Execution)\033[0m")
    print(" --------------------------------------------------------\n")


def print_free_models():
    print("\033[1m\033[96mAvailable Free AI Models on OpenRouter (No cost / Free tier):\033[0m")
    for m in OPENROUTER_FREE_MODELS:
        star = " (Default)" if m == OpenRouterClient.DEFAULT_FREE_MODEL else ""
        print(f"  • \033[92m{m}\033[0m{star}")
    print("\nTo use any of these models, pass:\n  python main.py --openrouter --model <model_name>\n")


def build_agent(args) -> AICodingAgent:
    """Instantiate the agent configured with the appropriate LLM client, mode, and sandbox."""
    workspace = os.path.abspath(args.workspace)
    auto_refine = not getattr(args, "no_refine", False)
    mode_str = getattr(args, "mode", "coding")
    try:
        mode = AgentMode(mode_str)
    except ValueError:
        mode = AgentMode.CODING

    # Configure sandbox policy
    strict = getattr(args, "strict_sandbox", False)
    policy = SandboxPolicy(
        allow_write=True,
        allow_network=not strict,
        max_memory_mb=256 if strict else 512,
        max_cpu_seconds=20 if strict else 30
    )

    # 1. Explicit mock requested
    if args.mock:
        client = MockCodingLLM()
        return AICodingAgent(workspace=workspace, llm=client, max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)

    # 2. OpenRouter requested or detected
    if args.openrouter or os.environ.get("OPENROUTER_API_KEY"):
        api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print("\033[93m[OpenRouter Setup] No OPENROUTER_API_KEY found in environment.\033[0m")
            print("You can get a free key at: \033[4mhttps://openrouter.ai/keys\033[0m (Free, no credit card required)")
            try:
                entered = input("Paste your OpenRouter API key (or press Enter to run in offline Mock mode): ").strip()
                if entered:
                    api_key = entered
                else:
                    print("\033[90mFalling back to offline Mock simulation mode.\033[0m\n")
                    return AICodingAgent(workspace=workspace, llm=MockCodingLLM(), max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)
            except (KeyboardInterrupt, EOFError):
                return AICodingAgent(workspace=workspace, llm=MockCodingLLM(), max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)

        model = args.model or OpenRouterClient.DEFAULT_FREE_MODEL
        client = OpenRouterClient(api_key=api_key, model=model)
        return AICodingAgent(workspace=workspace, llm=client, max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)

    # 3. Custom base URL (e.g., Ollama or custom gateway)
    if args.base_url:
        client = OpenAICompatibleClient(
            api_key=args.api_key or os.environ.get("OPENAI_API_KEY", "ollama"),
            base_url=args.base_url,
            model=args.model or "qwen2.5-coder"
        )
        return AICodingAgent(workspace=workspace, llm=client, max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)

    # 4. OpenAI or OpenAI-compatible key
    if args.api_key or os.environ.get("OPENAI_API_KEY"):
        client = OpenAICompatibleClient(
            api_key=args.api_key,
            model=args.model or "gpt-4o-mini"
        )
        return AICodingAgent(workspace=workspace, llm=client, max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)

    # 5. Google Gemini key
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        client = GeminiClient(
            model=args.model or "gemini-2.5-flash"
        )
        return AICodingAgent(workspace=workspace, llm=client, max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)

    # 6. Fallback to Mock
    print("\033[93m[Notice] No API key detected.\033[0m")
    print("\033[93mRunning in autonomous Mock Simulation Mode.\033[0m\n")
    print("\033[1m🚀 To use FREE live AI models with OpenRouter:\033[0m")
    print("  1. Get a free API key at: \033[4mhttps://openrouter.ai/keys\033[0m (No credit card needed)")
    print("  2. export OPENROUTER_API_KEY='sk-or-v1-...'")
    print("  3. Run: python main.py --openrouter\n")
    print("Other options:")
    print("  - Local Ollama: python main.py --base-url http://localhost:11434/v1 --model qwen2.5-coder")
    print("  - List free models: python main.py --list-models\n")
    client = MockCodingLLM()
    return AICodingAgent(workspace=workspace, llm=client, max_steps=args.max_steps, auto_refine=auto_refine, mode=mode, sandbox_policy=policy)


def prompt_user_to_code(agent: AICodingAgent, auto_correct: bool = False):
    """Interactively prompt the user for what to code, execute the agent, and loop."""
    print("\033[92m✨ What would you like me to do today?\033[0m")
    print("\033[90mModes available:\033[0m \033[35mplanning, architecture, coding, code_review, security_review\033[0m")
    print("\033[90mCommands:\033[0m")
    print("  • \033[33m/mode <mode>\033[0m (e.g. /mode security_review, /mode planning)")
    print("  • \033[33m/plan\033[0m, \033[33m/arch\033[0m, \033[33m/code\033[0m, \033[33m/review\033[0m, \033[33m/security\033[0m")
    print("  • \033[33m/web <file_or_url>\033[0m to test web page with Chrome")
    print("  • Type \033[33m'demo'\033[0m to run the automated palindrome demo")
    print("  • Type \033[33m'exit'\033[0m to quit\n")

    while True:
        try:
            mode_badge = f"\033[35m[{agent.mode.value.upper()}]\033[0m"
            task = input(f"\033[1m\033[96mEnter task {mode_badge} > \033[0m").strip()
            if not task:
                continue
            if task.lower() in ("exit", "quit", "q"):
                print("\n👋 Happy coding! Goodbye.\n")
                break

            # Handle slash commands
            if task.startswith("/mode "):
                new_mode_str = task.split(maxsplit=1)[1].strip().lower()
                try:
                    agent.mode = AgentMode(new_mode_str)
                    print(f"\033[92mSwitched mode to: {agent.mode.value.upper()}\033[0m\n")
                except ValueError:
                    print(f"\033[91mUnknown mode '{new_mode_str}'. Valid: {[m.value for m in AgentMode]}\033[0m\n")
                continue

            if task == "/plan":
                agent.mode = AgentMode.PLANNING
                print("\033[92mSwitched to PLANNING mode.\033[0m\n")
                continue
            if task == "/arch":
                agent.mode = AgentMode.ARCHITECTURE
                print("\033[92mSwitched to ARCHITECTURE mode.\033[0m\n")
                continue
            if task == "/code":
                agent.mode = AgentMode.CODING
                print("\033[92mSwitched to CODING mode.\033[0m\n")
                continue
            if task == "/review":
                agent.mode = AgentMode.CODE_REVIEW
                print("\033[92mSwitched to CODE_REVIEW mode.\033[0m\n")
                continue
            if task == "/security":
                agent.mode = AgentMode.SECURITY_REVIEW
                print("\033[92mSwitched to SECURITY_REVIEW mode.\033[0m\n")
                continue

            if task.startswith("/web "):
                web_target = task.split(maxsplit=1)[1].strip()
                tester = ChromeWebTester(workspace=agent.workspace)
                res = tester.test_url_or_file(web_target)
                status = "PASSED" if res["success"] else "FAILED"
                print(f"\n[Web Test {status}] Engine: {res['engine']} | Target: {res['target']}")
                if res.get("errors"):
                    for err in res["errors"]:
                        print(f"  ❌ {err}")
                else:
                    print("  ✅ All web assertions passed.")
                print()
                continue

            if task.lower() == "demo":
                task = (
                    "Inspect the repository, create a palindrome verification module in `solution.py`, "
                    "write unit tests in `test_solution.py`, and run the tests to verify the solution."
                )

            # Route execution based on active mode
            if agent.mode in (AgentMode.CODE_REVIEW, AgentMode.SECURITY_REVIEW):
                agent.run_review_and_correct(task, mode=agent.mode, auto_confirm=auto_correct)
            else:
                agent.run(task, mode=agent.mode)

            print("\n" + "=" * 60)
            print(f"\033[92m✅ Operation complete! What would you like to do next? (or type 'exit')\033[0m\n")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Exiting...")
            break


def main():
    parser = argparse.ArgumentParser(description="Autonomous Coding Agent")
    parser.add_argument("task_pos", nargs="*", help="Task to execute (positional)")
    parser.add_argument("-t", "--task", type=str, help="Coding or review task to solve")
    parser.add_argument("-w", "--workspace", type=str, default="./ws/", help="Target workspace root directory")
    parser.add_argument("-m", "--model", type=str, default=None, help="LLM model name (e.g. qwen/qwen-2.5-coder-32b-instruct:free)")
    parser.add_argument("--mode", type=str, default="coding",
                        choices=["planning", "architecture", "coding", "code_review", "security_review"],
                        help="Execution mode (default: coding)")
    parser.add_argument("--auto-correct", action="store_true",
                        help="Automatically apply and test suggested corrections from reviews")
    parser.add_argument("--web-test", type=str, default=None,
                        help="Run Chrome web testing on a local file or URL")
    parser.add_argument("--strict-sandbox", action="store_true",
                        help="Enforce ultra-strict sandboxing policies")
    parser.add_argument("--openrouter", action="store_true", help="Use OpenRouter free models")
    parser.add_argument("--list-models", action="store_true", help="List popular free OpenRouter models")
    parser.add_argument("--base-url", type=str, default=None, help="Base URL for custom OpenAI-compatible endpoint")
    parser.add_argument("--api-key", type=str, default=None, help="API key override")
    parser.add_argument("--max-steps", type=int, default=20, help="Maximum ReAct steps allowed (default: 20)")
    parser.add_argument("--mock", action="store_true", help="Force run in mock simulation mode")
    parser.add_argument("--no-refine", action="store_true", help="Disable automatic test-driven self-refinement")
    parser.add_argument("-i", "--interactive", action="store_true", help="Start interactive REPL mode (default when no task provided)")

    args = parser.parse_args()

    if args.list_models:
        print_free_models()
        return

    # Direct Web Test option
    if args.web_test:
        tester = ChromeWebTester(workspace=args.workspace)
        res = tester.test_url_or_file(args.web_test)
        status = "PASSED" if res["success"] else "FAILED"
        print(f"\n[Web Test {status}] Engine: {res['engine']} | Target: {res['target']}")
        print(f"Title: {res.get('page_title') or '(None)'}")
        if res.get("errors"):
            for err in res["errors"]:
                print(f"  ❌ {err}")
            sys.exit(1)
        else:
            print("  ✅ All web assertions passed.")
            sys.exit(0)

    # Collect task from arguments if any
    task = args.task
    if not task and args.task_pos:
        task = " ".join(args.task_pos)

    print_banner()
    agent = build_agent(args)

    if task:
        if agent.mode in (AgentMode.CODE_REVIEW, AgentMode.SECURITY_REVIEW):
            agent.run_review_and_correct(task, mode=agent.mode, auto_confirm=args.auto_correct)
        else:
            agent.run(task, mode=agent.mode)
    else:
        prompt_user_to_code(agent, auto_correct=args.auto_correct)


if __name__ == "__main__":
    main()
