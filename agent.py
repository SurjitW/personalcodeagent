"""
Autonomous Coding Agent in Python
A lightweight, complete, and autonomous coding agent implementing the ReAct
(Reasoning + Acting) loop with file inspection, editing, code search, command execution,
and workspace sandboxing.
"""

from __future__ import annotations

import ast
from enum import Enum
import inspect
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

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


class AgentMode(str, Enum):
    """Execution modes supported by the autonomous agent."""
    PLANNING = "planning"
    ARCHITECTURE = "architecture"
    CODING = "coding"
    CODE_REVIEW = "code_review"
    SECURITY_REVIEW = "security_review"


# =====================================================================
# 1. Tool Registry & Workspace Sandboxing
# =====================================================================

@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., str]
    parameters: Dict[str, Any]

    def execute(self, **kwargs) -> str:
        try:
            return str(self.func(**kwargs))
        except Exception as e:
            return f"Error executing tool '{self.name}': {type(e).__name__}: {str(e)}"


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any]):
        def decorator(func: Callable[..., str]):
            self._tools[name] = Tool(
                name=name,
                description=description,
                func=func,
                parameters=parameters,
            )
            return func
        return decorator

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            })
        return schemas


def get_safe_path(workspace: str, relative_or_abs_path: str, write: bool = False, policy: Optional[SandboxPolicy] = None) -> str:
    """Ensure that the path stays within the designated workspace root using robust realpath check."""
    return validate_path(workspace, relative_or_abs_path, write=write, policy=policy)


@dataclass
class AgentSkill:
    name: str
    description: str
    content: str
    path: str


class SkillRegistry:
    """Discovers and manages skills in .agents/ and its subfolders."""
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.skills: Dict[str, AgentSkill] = {}
        self.reload()

    def reload(self):
        self.skills.clear()
        agents_dir = os.path.join(self.workspace, ".agents")
        if not os.path.exists(agents_dir):
            return

        for root, dirs, files in os.walk(agents_dir):
            for file in files:
                if file.lower() in ("skill.md", "skills.md"):
                    skill_file = os.path.join(root, file)
                    try:
                        with open(skill_file, "r", encoding="utf-8", errors="replace") as f:
                            raw = f.read().strip()
                        if not raw:
                            continue

                        name = os.path.basename(root)
                        desc = f"Skill in {os.path.relpath(skill_file, self.workspace)}"
                        content = raw

                        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
                        if fm_match:
                            fm_text, body = fm_match.group(1), fm_match.group(2)
                            content = body.strip()
                            n_match = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
                            if n_match:
                                name = n_match.group(1).strip()
                            d_match = re.search(r"^description:\s*(.+)$", fm_text, re.MULTILINE)
                            if d_match:
                                desc = d_match.group(1).strip()

                        self.skills[name] = AgentSkill(
                            name=name,
                            description=desc,
                            content=content,
                            path=skill_file
                        )
                    except Exception:
                        continue

    def list_skills(self) -> List[AgentSkill]:
        return list(self.skills.values())

    def get_skill(self, name: str) -> Optional[AgentSkill]:
        return self.skills.get(name)

    def find_relevant_skills(self, query: str) -> List[AgentSkill]:
        q = query.lower()
        matched = []
        for s in self.skills.values():
            if s.name.lower() in q:
                matched.append(s)
            elif any(w in q for w in ["agentscope", "java", "reactive"] if w in s.name.lower() or w in s.description.lower()):
                matched.append(s)
        return matched


def create_coding_tools(workspace: str, policy: Optional[SandboxPolicy] = None) -> ToolRegistry:
    """Creates the standard suite of autonomous coding and testing tools with sandbox enforcement."""
    registry = ToolRegistry()
    workspace = os.path.abspath(workspace)
    policy = policy or SandboxPolicy()
    skill_registry = SkillRegistry(workspace)
    web_tester = ChromeWebTester(workspace)
    web_server = WorkspaceWebServer(workspace)

    @registry.register(
        name="list_skills",
        description="List all available custom agent skills discovered in .agents/ and its subdirectories.",
        parameters={"type": "object", "properties": {}}
    )
    def list_skills() -> str:
        skill_registry.reload()
        skills = skill_registry.list_skills()
        if not skills:
            return "No skills found in .agents/ directory."
        res = ["Discovered Custom Skills in .agents/:"]
        for s in skills:
            res.append(f"- {s.name}: {s.description}")
        return "\n".join(res)

    @registry.register(
        name="read_skill",
        description="Read the full detailed instructions and guidelines of a skill from .agents/.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the skill to read (e.g. 'agentscope-java')."}
            },
            "required": ["name"]
        }
    )
    def read_skill(name: str) -> str:
        skill_registry.reload()
        s = skill_registry.get_skill(name)
        if not s:
            avail = [x.name for x in skill_registry.list_skills()]
            return f"Skill '{name}' not found. Available skills: {avail}"
        return f"=== Skill: {s.name} ===\nDescription: {s.description}\n\nGuidelines:\n{s.content}"

    @registry.register(
        name="list_directory",
        description="List files and subdirectories in a directory path relative to the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path to list. Defaults to workspace root ('.').",
                    "default": "."
                }
            },
        }
    )
    def list_directory(path: str = ".") -> str:
        try:
            target = validate_path(workspace, path, write=False, policy=policy)
            if not os.path.exists(target):
                return f"Directory not found: {path}"
            if not os.path.isdir(target):
                return f"Path is not a directory: {path}"

            entries = []
            for item in sorted(os.listdir(target)):
                if item in (".git", "__pycache__", ".pytest_cache", ".venv", ".sandbox_tmp"):
                    continue
                item_path = os.path.join(target, item)
                is_dir = os.path.isdir(item_path)
                entries.append(f"{'[DIR]' if is_dir else '[FILE]'} {item}")

            return "\n".join(entries) if entries else "(Empty directory)"
        except Exception as e:
            return f"Error listing directory: {e}"

    @registry.register(
        name="read_file",
        description="Read the contents of a file with 1-based line numbers. Can optionally read a slice.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to file."},
                "start_line": {"type": "integer", "description": "Starting line number (1-indexed). Optional."},
                "end_line": {"type": "integer", "description": "Ending line number (1-indexed, inclusive). Optional."}
            },
            "required": ["path"]
        }
    )
    def read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        try:
            target = validate_path(workspace, path, write=False, policy=policy)
            if not os.path.exists(target):
                return f"File does not exist: {path}"
            if os.path.isdir(target):
                return f"Cannot read: '{path}' is a directory."

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s = max(1, start_line or 1)
            e = min(total_lines, end_line or total_lines)

            if total_lines == 0:
                return "(File is empty)"

            output = []
            for i in range(s - 1, e):
                output.append(f"{i + 1:4d} | {lines[i].rstrip()}")
            return "\n".join(output)
        except Exception as e:
            return f"Error reading file: {e}"

    @registry.register(
        name="write_file",
        description="Create or overwrite a file with given text content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to file."},
                "content": {"type": "string", "description": "The exact full text content to write."}
            },
            "required": ["path", "content"]
        }
    )
    def write_file(path: str, content: str) -> str:
        try:
            target = validate_path(workspace, path, write=True, policy=policy)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            line_count = len(content.splitlines())
            return f"Successfully wrote {len(content)} bytes ({line_count} lines) to '{path}'."
        except Exception as e:
            return f"Error writing file: {e}"

    @registry.register(
        name="edit_file",
        description="Replace a target substring/block in a file with a replacement substring.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to file."},
                "target_content": {"type": "string", "description": "Exact text chunk in file to replace."},
                "replacement_content": {"type": "string", "description": "New text chunk to put in its place."}
            },
            "required": ["path", "target_content", "replacement_content"]
        }
    )
    def edit_file(path: str, target_content: str, replacement_content: str) -> str:
        try:
            target = validate_path(workspace, path, write=True, policy=policy)
            if not os.path.exists(target):
                return f"File does not exist: {path}"

            with open(target, "r", encoding="utf-8") as f:
                content = f.read()

            occurrences = content.count(target_content)
            if occurrences == 0:
                return (
                    f"Error: target_content not found in '{path}'. "
                    f"Please read the file again to ensure exact character and whitespace match."
                )
            if occurrences > 1:
                return (
                    f"Error: target_content found {occurrences} times in '{path}'. "
                    f"Please provide a more specific unique chunk of code."
                )

            new_content = content.replace(target_content, replacement_content, 1)
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully updated '{path}'."
        except Exception as e:
            return f"Error editing file: {e}"

    @registry.register(
        name="search_code",
        description="Search for a text pattern or symbol across files in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "String pattern to search for."},
                "path": {"type": "string", "description": "Subdirectory to search in. Defaults to '.'", "default": "."}
            },
            "required": ["query"]
        }
    )
    def search_code(query: str, path: str = ".") -> str:
        try:
            target_dir = validate_path(workspace, path, write=False, policy=policy)
            matches = []
            query_lower = query.lower()

            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv", ".pytest_cache", "node_modules", ".sandbox_tmp")]
                for file in files:
                    if file.endswith((".pyc", ".png", ".jpg", ".exe", ".bin")):
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, workspace)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for lineno, line in enumerate(f, 1):
                                if query_lower in line.lower():
                                    matches.append(f"{rel_path}:{lineno}: {line.strip()}")
                                    if len(matches) >= 30:
                                        matches.append("... (matches truncated at 30)")
                                        return "\n".join(matches)
                    except Exception:
                        continue

            return "\n".join(matches) if matches else f"No matches found for '{query}'."
        except Exception as e:
            return f"Error searching code: {e}"

    @registry.register(
        name="run_command",
        description="Run a shell command inside the workspace under strict sandboxing.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command line string to run."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (max 60). Defaults to 30.", "default": 30}
            },
            "required": ["command"]
        }
    )
    def run_command(command: str, timeout: int = 30) -> str:
        return execute_sandboxed_command(command=command, cwd=workspace, timeout=timeout, policy=policy)

    @registry.register(
        name="test_web_page",
        description="Run automated web testing with Chrome on a local file or URL. Verifies title, selectors, and text assertions.",
        parameters={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "URL (e.g. 'http://127.0.0.1:8080/index.html') or workspace-relative path ('index.html')."},
                "expected_title": {"type": "string", "description": "Expected text in the page title (optional)."},
                "expected_selectors": {"type": "array", "items": {"type": "string"}, "description": "List of element IDs (#id) or tag names (optional)."},
                "expected_text": {"type": "array", "items": {"type": "string"}, "description": "List of strings that must appear in page content (optional)."},
                "forbidden_text": {"type": "array", "items": {"type": "string"}, "description": "List of strings that must NOT appear in page content (optional)."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (max 30). Defaults to 10."}
            },
            "required": ["target"]
        }
    )
    def test_web_page(
        target: str,
        expected_title: Optional[str] = None,
        expected_selectors: Optional[List[str]] = None,
        expected_text: Optional[List[str]] = None,
        forbidden_text: Optional[List[str]] = None,
        timeout: int = 10
    ) -> str:
        res = web_tester.test_url_or_file(
            target=target,
            expected_title=expected_title,
            expected_selectors=expected_selectors,
            expected_text=expected_text,
            forbidden_text=forbidden_text,
            timeout=timeout
        )
        status = "PASSED" if res["success"] else "FAILED"
        lines = [
            f"[Web Test {status}] Engine: {res['engine']}",
            f"Target: {res['target']}",
            f"Page Title: {res.get('page_title') or '(None)'}",
        ]
        if res.get("errors"):
            lines.append("Errors / Assertions Failed:")
            for err in res["errors"]:
                lines.append(f"  - {err}")
        else:
            lines.append("All assertions passed successfully!")
        if res.get("dom_preview"):
            lines.append(f"DOM Preview:\n{res['dom_preview']}")
        return "\n".join(lines)

    @registry.register(
        name="start_web_server",
        description="Start a local background HTTP web server serving workspace files.",
        parameters={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "Port to bind (optional)."}
            }
        }
    )
    def start_web_server(port: Optional[int] = None) -> str:
        return web_server.start()

    @registry.register(
        name="stop_web_server",
        description="Stop the background workspace web server.",
        parameters={"type": "object", "properties": {}}
    )
    def stop_web_server() -> str:
        return web_server.stop()

    return registry


# =====================================================================
# 2. LLM Client Interfaces (OpenAI-compatible, Gemini, & Mock Demo)
# =====================================================================

@dataclass
class AgentStep:
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    final_answer: Optional[str] = None


class BaseLLMClient:
    """Abstract interface for LLM backends."""
    def generate_step(
        self,
        messages: List[Dict[str, str]],
        tools: List[Tool]
    ) -> AgentStep:
        raise NotImplementedError


def _parse_react_response(raw_text: str) -> AgentStep:
    """
    Parses a model's response in ReAct format:
    Thought: <reasoning>
    Action: <tool_name>
    Action Input: <json_arguments>
    OR
    Thought: <reasoning>
    Final Answer: <answer>
    Also handles reasoning models (DeepSeek-R1) using <think>...</think> tags.
    """
    thought = ""
    action = None
    action_input = None
    final_answer = None

    # Handle <think> tags (common in reasoning models like Seek-R1)
    think_match = re.search(r"<think>(.*?)</think>", raw_text, re.DOTALL | re.IGNORECASE)
    think_content = ""
    if think_match:
        think_content = think_match.group(1).strip()
        raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE).strip()

    # Check for Final Answer first
    fa_match = re.search(r"Final Answer:\s*(.*)", raw_text, re.DOTALL | re.IGNORECASE)
    if fa_match:
        final_answer = fa_match.group(1).strip()
        thought_match = re.search(r"Thought:\s*(.*?)(?=Final Answer:)", raw_text, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else (think_content or raw_text.replace(fa_match.group(0), "").strip())
        return AgentStep(thought=thought or "Task complete.", final_answer=final_answer)

    # Check for Action and Action Input
    action_match = re.search(r"Action:\s*([a-zA-Z0-9_\-]+)", raw_text, re.IGNORECASE)
    if action_match:
        action = action_match.group(1).strip()

        # Extract Thought
        thought_match = re.search(r"Thought:\s*(.*?)(?=Action:)", raw_text, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else think_content

        # Extract Action Input
        input_match = re.search(r"Action Input:\s*(.*)", raw_text, re.DOTALL | re.IGNORECASE)
        if input_match:
            raw_input = input_match.group(1).strip()
            raw_input = re.sub(r"^```(?:json)?\n?", "", raw_input)
            raw_input = re.sub(r"\n?```$", "", raw_input).strip()
            try:
                action_input = json.loads(raw_input)
            except json.JSONDecodeError:
                action_input = {"input": raw_input}
        else:
            action_input = {}

        return AgentStep(thought=thought, action=action, action_input=action_input)

    # Fallback: If no structured markers, treat as Final Answer
    return AgentStep(thought=think_content, final_answer=raw_text.strip())


class OpenAICompatibleClient(BaseLLMClient):
    """
    Client for any OpenAI-compatible API:
    - Official OpenAI (gpt-4o, gpt-4o-mini)
    - OpenRouter (openrouter.ai/api/v1)
    - Ollama (http://localhost:11434/v1)
    - Groq, DeepSeek, Together, vLLM
    Uses pure urllib.request (zero external package dependencies).
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        extra_headers: Optional[Dict[str, str]] = None
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.extra_headers = extra_headers or {}

    def generate_step(self, messages: List[Dict[str, str]], tools: List[Tool]) -> AgentStep:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
        }
        headers.update(self.extra_headers)

        tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            }
            for t in tools
        ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tool_schemas:
            payload["tools"] = tool_schemas
            payload["tool_choice"] = "auto"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={k: v for k, v in headers.items() if v},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choice = res_data["choices"][0]["message"]

                if choice.get("tool_calls"):
                    tool_call = choice["tool_calls"][0]["function"]
                    name = tool_call["name"]
                    try:
                        args = json.loads(tool_call["arguments"])
                    except json.JSONDecodeError:
                        args = {"raw": tool_call["arguments"]}
                    thought = choice.get("content") or f"Calling tool {name}..."
                    return AgentStep(thought=thought, action=name, action_input=args)

                content = choice.get("content") or ""
                return _parse_react_response(content)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            # If the free model doesn't support the tools parameter, retry using prompt-only ReAct
            if "tools" in payload and (e.code == 400 or "tool" in error_body.lower()):
                payload_fallback = dict(payload)
                payload_fallback.pop("tools", None)
                payload_fallback.pop("tool_choice", None)
                try:
                    fallback_req = urllib.request.Request(
                        url,
                        data=json.dumps(payload_fallback).encode("utf-8"),
                        headers={k: v for k, v in headers.items() if v},
                        method="POST"
                    )
                    with urllib.request.urlopen(fallback_req, timeout=60) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        content = res_data["choices"][0]["message"].get("content") or ""
                        return _parse_react_response(content)
                except Exception:
                    pass

            raise RuntimeError(f"API Error ({e.code}): {error_body}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to LLM: {e}")


# Recommended free models available on OpenRouter
OPENROUTER_FREE_MODELS = [
    "nex-agi/nex-n2.5-pro:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
]


class OpenRouterClient(OpenAICompatibleClient):
    """
    Client for OpenRouter API with preconfigured access to free AI models.
    Default free coding model: 'qwen/qwen-2.5-coder-32b-instruct:free'.
    """
    DEFAULT_FREE_MODEL = "qwen/qwen-2.5-coder-32b-instruct:free"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        chosen_model = model or self.DEFAULT_FREE_MODEL
        super().__init__(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            model=chosen_model,
            extra_headers={
                "HTTP-Referer": "https://github.com/personalcodeagent",
                "X-Title": "Personal AI Coding Agent",
            }
        )


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini REST API."""
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        self.model = model

    def generate_step(self, messages: List[Dict[str, str]], tools: List[Tool]) -> AgentStep:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        contents = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m["content"]}]
            })

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.1}
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_react_response(text)


class MockCodingLLM(BaseLLMClient):
    """
    Intelligent simulated coding LLM for demonstration and offline testing.
    Autonomously writes code, runs tests, detects failures, refines the code,
    and re-tests until verification completes successfully.
    """
    def __init__(self):
        self.turn = 0
        self.created_filename = "solution.py"
        self.test_filename = "test_solution.py"
        self.initial_code = ""
        self.refined_code = ""
        self.test_content = ""

    def reset(self):
        self.turn = 0
        self.created_filename = "solution.py"
        self.test_filename = "test_solution.py"
        self.initial_code = ""
        self.refined_code = ""
        self.test_content = ""

    def _determine_solution(self, task: str) -> Tuple[str, str, str, str, str]:
        task_lower = task.lower()

        py_files = re.findall(r'([a-zA-Z0-9_\-]+\.py)', task)
        target_py = "solution.py"
        for pf in py_files:
            if not pf.startswith("test_"):
                target_py = pf
                break

        test_py = f"test_{target_py}" if not target_py.startswith("test_") else "test_suite.py"
        mod_name = target_py[:-3]

        if "fib" in task_lower:
            # Initial code has boundary bug: starts with [1, 1] instead of [0, 1]
            initial = (
                f'"""Fibonacci sequence generator (draft)."""\n\n'
                f'def fibonacci(n: int) -> list[int]:\n'
                f'    if n <= 0:\n'
                f'        return []\n'
                f'    seq = [1, 1]  # Bug: should start with 0\n'
                f'    while len(seq) < n:\n'
                f'        seq.append(seq[-1] + seq[-2])\n'
                f'    return seq[:n]\n'
            )
            # Refined code starts with correct 0, 1 sequence
            refined = (
                f'"""Fibonacci sequence generator (refined)."""\n\n'
                f'def fibonacci(n: int) -> list[int]:\n'
                f'    """Generate the first n Fibonacci numbers starting with 0."""\n'
                f'    if n <= 0:\n'
                f'        return []\n'
                f'    if n == 1:\n'
                f'        return [0]\n'
                f'    seq = [0, 1]\n'
                f'    while len(seq) < n:\n'
                f'        seq.append(seq[-1] + seq[-2])\n'
                f'    return seq[:n]\n'
            )
            tests = (
                f'import unittest\n'
                f'from {mod_name} import fibonacci\n\n'
                f'class TestFibonacci(unittest.TestCase):\n'
                f'    def test_fibonacci(self):\n'
                f'        self.assertEqual(fibonacci(0), [])\n'
                f'        self.assertEqual(fibonacci(1), [0])\n'
                f'        self.assertEqual(fibonacci(5), [0, 1, 1, 2, 3])\n\n'
                f'if __name__ == "__main__":\n'
                f'    unittest.main()\n'
            )
        elif "calc" in task_lower or "math" in task_lower:
            # Initial code misses divide-by-zero check
            initial = (
                f'"""Math utilities (draft)."""\n\n'
                f'def add(a: float, b: float) -> float: return a + b\n'
                f'def subtract(a: float, b: float) -> float: return a - b\n'
                f'def multiply(a: float, b: float) -> float: return a * b\n'
                f'def divide(a: float, b: float) -> float:\n'
                f'    return a / b  # Bug: does not handle zero division with ValueError\n'
            )
            refined = (
                f'"""Math utilities (refined)."""\n\n'
                f'def add(a: float, b: float) -> float: return a + b\n'
                f'def subtract(a: float, b: float) -> float: return a - b\n'
                f'def multiply(a: float, b: float) -> float: return a * b\n'
                f'def divide(a: float, b: float) -> float:\n'
                f'    if b == 0:\n'
                f'        raise ValueError("Division by zero")\n'
                f'    return a / b\n'
            )
            tests = (
                f'import unittest\n'
                f'from {mod_name} import add, subtract, multiply, divide\n\n'
                f'class TestCalculator(unittest.TestCase):\n'
                f'    def test_operations(self):\n'
                f'        self.assertEqual(add(2, 3), 5)\n'
                f'        self.assertEqual(divide(10, 2), 5)\n'
                f'    def test_divide_zero(self):\n'
                f'        with self.assertRaises(ValueError):\n'
                f'            divide(10, 0)\n\n'
                f'if __name__ == "__main__":\n'
                f'    unittest.main()\n'
            )
        elif "palindrome" in task_lower:
            # Initial code naive reverse without stripping punctuation or lowercase
            initial = (
                f'"""Palindrome checker (draft)."""\n\n'
                f'def is_palindrome(text: str) -> bool:\n'
                f'    return str(text) == str(text)[::-1]  # Bug: fails on spaces & case\n'
            )
            refined = (
                f'"""Palindrome checker (refined)."""\n\n'
                f'def is_palindrome(text: str) -> bool:\n'
                f'    cleaned = "".join(c.lower() for c in str(text) if c.isalnum())\n'
                f'    return cleaned == cleaned[::-1]\n'
            )
            tests = (
                f'import unittest\n'
                f'from {mod_name} import is_palindrome\n\n'
                f'class TestPalindrome(unittest.TestCase):\n'
                f'    def test_simple(self):\n'
                f'        self.assertTrue(is_palindrome("racecar"))\n'
                f'    def test_with_spaces_and_casing(self):\n'
                f'        self.assertTrue(is_palindrome("A man a plan a canal Panama"))\n'
                f'        self.assertFalse(is_palindrome("hello world"))\n\n'
                f'if __name__ == "__main__":\n'
                f'    unittest.main()\n'
            )
        else:
            initial = (
                f'"""Module for task: {task[:40]} (draft)"""\n\n'
                f'def execute_solution(data: str = "ok") -> dict:\n'
                f'    return {{"status": "pending", "result": str(data)}}  # Bug: pending\n'
            )
            refined = (
                f'"""Module for task: {task[:40]} (refined)"""\n\n'
                f'def execute_solution(data: str = "ok") -> dict:\n'
                f'    return {{"status": "success", "result": str(data).upper()}}\n'
            )
            tests = (
                f'import unittest\n'
                f'from {mod_name} import execute_solution\n\n'
                f'class TestSolution(unittest.TestCase):\n'
                f'    def test_execute(self):\n'
                f'        res = execute_solution("hello")\n'
                f'        self.assertEqual(res["status"], "success")\n'
                f'        self.assertEqual(res["result"], "HELLO")\n\n'
                f'if __name__ == "__main__":\n'
                f'    unittest.main()\n'
            )

        return target_py, test_py, initial, refined, tests

    def generate_step(self, messages: List[Dict[str, str]], tools: List[Tool]) -> AgentStep:
        self.turn += 1

        user_task = ""
        system_content = ""
        for m in messages:
            if m["role"] == "system":
                system_content = m["content"]
            elif m["role"] == "user":
                user_task = m["content"]

        sys_lower = system_content.lower()
        task_lower = user_task.lower()

        # Mode: Planning
        if "mode: planning" in sys_lower or "planning agent" in sys_lower:
            if self.turn == 1:
                return AgentStep(
                    thought=f"Inspecting workspace files before formulating implementation plan for '{user_task}'.",
                    action="list_directory",
                    action_input={"path": "."}
                )
            return AgentStep(
                thought="Formulated structured implementation plan.",
                final_answer=(
                    f"# Implementation Plan: {user_task}\n\n"
                    f"## 1. Project Goal & Requirements\n"
                    f"- Core Objective: {user_task}\n"
                    f"- Deliverables: Robust module implementation and automated tests.\n\n"
                    f"## 2. Work Breakdown Structure\n"
                    f"- Phase 1: Workspace discovery & environment verification\n"
                    f"- Phase 2: Core module implementation with boundary validation\n"
                    f"- Phase 3: Comprehensive automated test suite\n"
                    f"- Phase 4: Sandboxed execution and test verification\n\n"
                    f"## 3. Verification Strategy\n"
                    f"- Run tests using standard test runner under sandbox policy."
                )
            )

        # Mode: Architecture
        if "mode: architecture" in sys_lower or "architect agent" in sys_lower:
            if self.turn == 1:
                return AgentStep(
                    thought=f"Inspecting workspace directory to design architecture for '{user_task}'.",
                    action="list_directory",
                    action_input={"path": "."}
                )
            return AgentStep(
                thought="Formulated architectural specification.",
                final_answer=(
                    f"# System Architecture Specification: {user_task}\n\n"
                    f"## 1. Architecture Overview\n"
                    f"High-level modular architecture designed for '{user_task}'.\n\n"
                    f"## 2. Component Boundaries & Responsibilities\n"
                    f"- Core Logic Layer: Clean domain functions with strict type hinting.\n"
                    f"- Sandbox Enforcement: Filesystem & command confinement boundary.\n"
                    f"- Verification Engine: Automated testing and Chrome headless assertions.\n\n"
                    f"## 3. Data Flow\n"
                    f"Input Task -> Decomposition -> Sandboxed Implementation -> Test Verification"
                )
            )

        # Mode: Code Review
        if "mode: code_review" in sys_lower or "code reviewer agent" in sys_lower:
            if self.turn == 1:
                return AgentStep(
                    thought=f"Inspecting workspace files for code quality review of '{user_task}'.",
                    action="list_directory",
                    action_input={"path": "."}
                )
            return AgentStep(
                thought="Code review complete. Producing structured findings with suggested correction prompt.",
                final_answer=(
                    f"# Code Review Report\n\n"
                    f"## Summary\n"
                    f"Conducted code quality review for: {user_task}. Found areas for enhancement.\n\n"
                    f"## Findings\n"
                    f"- [solution.py:10] [Severity: Medium]: Missing boundary validation for input arguments.\n"
                    f"- [solution.py:20] [Severity: Low]: Add docstrings and type annotations.\n\n"
                    f"## Suggested Correction Prompt\n"
                    f"Suggested Correction Prompt: Refactor solution.py to add defensive input validation, type annotations, docstrings, and write tests to verify."
                )
            )

        # Mode: Security Review
        if "mode: security_review" in sys_lower or "security audit specialist" in sys_lower:
            if self.turn == 1:
                return AgentStep(
                    thought=f"Inspecting workspace files for security audit of '{user_task}'.",
                    action="list_directory",
                    action_input={"path": "."}
                )
            return AgentStep(
                thought="Security audit complete. Producing structured findings with suggested correction prompt.",
                final_answer=(
                    f"# Security Audit Report\n\n"
                    f"## Summary\n"
                    f"Conducted security audit for: {user_task}. Found potential vulnerabilities.\n\n"
                    f"## Vulnerabilities Found\n"
                    f"- [solution.py:5] [Severity: High]: Path parameter without canonical validation poses path traversal risk (CWE-22).\n"
                    f"- [solution.py:18] [Severity: Medium]: Subprocess invocation without command argument whitelist (CWE-78).\n\n"
                    f"## Suggested Correction Prompt\n"
                    f"Suggested Correction Prompt: Patch solution.py to enforce canonical path validation with realpath, sanitize command arguments, and verify with security tests."
                )
            )

        # Web testing task
        if any(w in task_lower for w in ["web", "chrome", "html", "browser"]):
            if self.turn == 1:
                html_content = (
                    "<!DOCTYPE html>\n"
                    "<html>\n"
                    "<head><title>Personal Code Agent Web App</title></head>\n"
                    "<body>\n"
                    "  <div id='app'>\n"
                    "    <h1>Welcome to AI Code Agent</h1>\n"
                    "    <p>Automated web testing with Chrome</p>\n"
                    "  </div>\n"
                    "</body>\n"
                    "</html>\n"
                )
                return AgentStep(
                    thought="Writing web application HTML file 'index.html'.",
                    action="write_file",
                    action_input={"path": "index.html", "content": html_content}
                )
            if self.turn == 2:
                return AgentStep(
                    thought="Running automated web testing with Chrome on 'index.html'.",
                    action="test_web_page",
                    action_input={
                        "target": "index.html",
                        "expected_title": "Personal Code Agent Web App",
                        "expected_selectors": ["#app", "h1"],
                        "expected_text": ["Welcome to AI Code Agent"]
                    }
                )
            return AgentStep(
                thought="Web testing completed successfully.",
                final_answer=(
                    "Web application implemented and verified with Chrome testing!\n"
                    "- Created `index.html` with title and structured DOM elements.\n"
                    "- Verified page title, '#app' container, and 'Welcome to AI Code Agent' text via web test runner."
                )
            )

        # Mode: Coding (standard ReAct loop)
        if self.turn == 1:
            target_py, test_py, initial, refined, tests = self._determine_solution(user_task)
            self.created_filename = target_py
            self.test_filename = test_py
            self.initial_code = initial
            self.refined_code = refined
            self.test_content = tests

            return AgentStep(
                thought=f"Inspecting workspace directory structure before implementing '{user_task}'.",
                action="list_directory",
                action_input={"path": "."}
            )

        if self.turn == 2:
            return AgentStep(
                thought=f"Writing initial code implementation to '{self.created_filename}'.",
                action="write_file",
                action_input={"path": self.created_filename, "content": self.initial_code}
            )

        if self.turn == 3:
            return AgentStep(
                thought=f"Initial code written. Now writing comprehensive test suite in '{self.test_filename}'.",
                action="write_file",
                action_input={"path": self.test_filename, "content": self.test_content}
            )

        if self.turn == 4:
            return AgentStep(
                thought=f"Running unit tests to verify the initial implementation.",
                action="run_command",
                action_input={"command": f"{sys.executable} -m unittest {self.test_filename}"}
            )

        if self.turn == 5:
            return AgentStep(
                thought=(
                    f"Observation reveals a test failure in initial code. "
                    f"Analyzing failure traceback and refining '{self.created_filename}' to fix the bug."
                ),
                action="write_file",
                action_input={"path": self.created_filename, "content": self.refined_code}
            )

        if self.turn == 6:
            return AgentStep(
                thought=f"Code has been refined. Re-running the test suite to verify that the fix resolves the issue.",
                action="run_command",
                action_input={"command": f"{sys.executable} -m unittest {self.test_filename}"}
            )

        return AgentStep(
            thought="All unit tests passed with exit code 0. Code refinement cycle complete and verified.",
            final_answer=(
                f"Coding task completed successfully after iterative refinement!\n"
                f"- Initial implementation tested and failed on edge cases.\n"
                f"- Diagnosed test failure and refined `{self.created_filename}`.\n"
                f"- Re-ran automated test suite: Verified with exit code 0 (All tests pass)."
            )
        )


# =====================================================================
# 3. AI Coding Agent Core Engine
# =====================================================================

SYSTEM_PROMPT_CODING = """You are an autonomous AI Coding Agent.
You solve coding, debugging, and software engineering tasks by inspecting the workspace, writing clean code, running commands/tests, and CONTINUOUSLY REFINING code until it completes successfully.

You operate in a strict ReAct (Reasoning + Acting) loop:
1. Thought: Analyze the current situation and describe what you plan to do next.
2. Action: The name of the tool to use (MUST be one of the registered tools).
3. Action Input: A valid JSON object containing the arguments for the tool.
4. (The system will execute the tool and return an Observation).
5. Repeat until you have verified the solution with tests.

CRITICAL CONTINUOUS REFINEMENT MANDATE:
- Your primary goal is working, verified code that passes tests with exit code 0.
- If any command or test fails, produces an error, or exits with non-zero code:
  1. DO NOT STOP and DO NOT provide a Final Answer!
  2. Carefully examine the error output and traceback in the Observation.
  3. Identify the bug or missing functionality in the code.
  4. Use `edit_file` or `write_file` to fix and refine the code.
  5. Re-run the tests with `run_command` or `test_web_page`.
  6. Repeat this refine-and-test loop until all tests pass completely.
- Only when all tests pass with [Exit code: 0] (or web assertions pass) should you provide:
  Thought: State that the task is completed and verified.
  Final Answer: Provide a concise summary of the changes, how they were refined, and the test results.

Available Tools:
{tool_descriptions}

Formatting Rules:
- Never guess file contents; use `read_file` or `search_code` first.
- Always run tests or syntax checks with `run_command` or `test_web_page` to verify your changes.
- Ensure your Action Input is strictly valid JSON.
"""

SYSTEM_PROMPT_PLANNING = """You are an expert Software Planning Agent (Mode: Planning).
Your mission is to analyze the user's project requirements, explore the workspace to understand existing assets, and formulate a structured, milestone-driven execution plan.

You operate in a ReAct loop:
1. Thought: Describe your plan analysis.
2. Action: Use `list_directory`, `read_file`, or `search_code` to investigate the workspace.
3. Observation: Evaluate findings.
4. Final Answer: When ready, present a comprehensive Implementation Plan formatted in Markdown:
   # Implementation Plan: [Task Title]
   ## 1. Project Goal & Scope
   ## 2. Requirements Analysis
   ## 3. Work Breakdown Structure (Phases & Milestones)
   ## 4. Technical Risks & Mitigations
   ## 5. Verification & Testing Strategy

Available Tools:
{tool_descriptions}
"""

SYSTEM_PROMPT_ARCHITECTURE = """You are a Principal Software Architect Agent (Mode: Architecture).
Your mission is to inspect the workspace, analyze system requirements, and design a robust, modular system architecture.

You operate in a ReAct loop:
1. Thought: Reason about system boundaries, communication protocols, and design patterns.
2. Action: Use tools (`list_directory`, `read_file`, `search_code`) to understand existing code structure.
3. Observation: Evaluate repository architecture.
4. Final Answer: Present an Architecture Specification formatted in Markdown:
   # System Architecture Specification: [System Name]
   ## 1. Architectural Overview & Design Principles
   ## 2. Component Boundaries & Responsibilities
   ## 3. Data Flow & Interaction Diagrams
   ## 4. Interfaces & Contract Specifications
   ## 5. Non-Functional Requirements (Security, Scalability, Testability)

Available Tools:
{tool_descriptions}
"""

SYSTEM_PROMPT_CODE_REVIEW = """You are a Senior Code Reviewer Agent (Mode: Code_Review).
Your mission is to perform an exhaustive code quality, maintainability, and bug audit on the workspace code.

You operate in a ReAct loop:
1. Thought: Reason about code quality, PEP 8/clean code conventions, edge cases, error handling, and test coverage.
2. Action: Use tools (`list_directory`, `read_file`, `search_code`, `run_command`) to inspect and test the code.
3. Observation: Review code lines and test output.
4. Final Answer: Deliver your code review in the following strict structure:
   # Code Review Report
   ## Summary
   [High-level evaluation]
   ## Findings
   - [filename:line] [Severity: Critical|High|Medium|Low]: Description of issue.
   ## Suggested Correction Prompt
   Suggested Correction Prompt: <A complete, self-contained prompt describing the exact code improvements and tests to run>

Available Tools:
{tool_descriptions}
"""

SYSTEM_PROMPT_SECURITY_REVIEW = """You are an Application Security Audit Specialist Agent (Mode: Security_Review).
Your mission is to conduct a rigorous security audit of the workspace codebase.

Analyze:
- OWASP Top 10 vulnerabilities (Injection, Path Traversal, SSRF, Deserialization, Broken Access Control)
- Command injection & unsafe subprocess execution
- Insecure permissions, privilege escalation risks, and symlink exploits
- Sensitive data exposure or hardcoded secrets
- Input validation, boundary checks, and sandbox safety

You operate in a ReAct loop:
1. Thought: Analyze security risks and attack vectors.
2. Action: Use tools (`list_directory`, `read_file`, `search_code`) to inspect code.
3. Observation: Analyze code vulnerabilities.
4. Final Answer: Deliver your security audit in the following strict structure:
   # Security Audit Report
   ## Summary
   [High-level security evaluation]
   ## Vulnerabilities Found
   - [filename:line] [Severity: Critical|High|Medium|Low]: Description of vulnerability (e.g. CWE ID) and risk.
   ## Suggested Correction Prompt
   Suggested Correction Prompt: <A complete, self-contained prompt describing the exact security patches and tests to verify>

Available Tools:
{tool_descriptions}
"""

SYSTEM_PROMPT = SYSTEM_PROMPT_CODING  # Backwards compatibility


def extract_correction_prompt(text: str) -> Optional[str]:
    """Extracts a suggested correction prompt from review output if present."""
    match = re.search(r"Suggested Correction Prompt:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if match:
        prompt = match.group(1).strip()
        prompt = re.split(r"\n#{1,3}\s+", prompt)[0].strip()
        if prompt.startswith("`") and prompt.endswith("`"):
            prompt = prompt[1:-1].strip()
        if prompt.startswith('"') and prompt.endswith('"'):
            prompt = prompt[1:-1].strip()
        return prompt
    return None


class AICodingAgent:
    """Autonomous coding agent that loops through Thought -> Action -> Observation with multi-mode support and continuous refinement."""

    def __init__(
        self,
        workspace: str = ".",
        llm: Optional[BaseLLMClient] = None,
        max_steps: int = 20,
        verbose: bool = True,
        auto_refine: bool = True,
        max_refinements: int = 5,
        mode: AgentMode = AgentMode.CODING,
        sandbox_policy: Optional[SandboxPolicy] = None,
    ):
        self.workspace = os.path.abspath(workspace)
        os.makedirs(self.workspace, exist_ok=True)
        self.sandbox_policy = sandbox_policy or SandboxPolicy()
        self.tools = create_coding_tools(self.workspace, policy=self.sandbox_policy)
        self.llm = llm or self._auto_detect_llm()
        self.max_steps = max_steps
        self.verbose = verbose
        self.auto_refine = auto_refine
        self.max_refinements = max_refinements
        self.mode = mode
        self.history: List[Dict[str, str]] = []
        self.last_command_exit_code: Optional[int] = None
        self.last_command_output: str = ""
        self.refinement_attempts: int = 0

    def _auto_detect_llm(self) -> BaseLLMClient:
        """Automatically select the best available LLM backend."""
        if os.environ.get("OPENROUTER_API_KEY"):
            return OpenRouterClient()
        if os.environ.get("OPENAI_API_KEY"):
            return OpenAICompatibleClient()
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return GeminiClient()
        return MockCodingLLM()

    def _build_system_prompt(self, mode: Optional[AgentMode] = None) -> str:
        active_mode = mode or self.mode
        prompt_templates = {
            AgentMode.PLANNING: SYSTEM_PROMPT_PLANNING,
            AgentMode.ARCHITECTURE: SYSTEM_PROMPT_ARCHITECTURE,
            AgentMode.CODING: SYSTEM_PROMPT_CODING,
            AgentMode.CODE_REVIEW: SYSTEM_PROMPT_CODE_REVIEW,
            AgentMode.SECURITY_REVIEW: SYSTEM_PROMPT_SECURITY_REVIEW,
        }
        template = prompt_templates.get(active_mode, SYSTEM_PROMPT_CODING)
        tool_desc = []
        for t in self.tools.list_tools():
            args_str = ", ".join(f"{k}: {v.get('type')}" for k, v in t.parameters.get("properties", {}).items())
            tool_desc.append(f"- {t.name}({args_str}): {t.description}")
        return template.format(tool_descriptions="\n".join(tool_desc))

    def _log(self, text: str, color: str = ""):
        if not self.verbose:
            return
        colors = {
            "cyan": "\033[96m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "magenta": "\033[95m",
            "blue": "\033[94m",
            "bold": "\033[1m",
            "reset": "\033[0m"
        }
        prefix = colors.get(color, "")
        suffix = colors.get("reset", "")
        print(f"{prefix}{text}{suffix}")

    def run(self, task: str, mode: Optional[AgentMode] = None) -> str:
        """Executes the autonomous ReAct loop on a user task with continuous self-refinement."""
        if hasattr(self.llm, "reset"):
            self.llm.reset()

        active_mode = mode or self.mode
        self.last_command_exit_code = None
        self.last_command_output = ""
        self.refinement_attempts = 0

        self._log(f"\n{'='*70}", "bold")
        self._log(f"🤖 AI Coding Agent initialized in: {self.workspace}", "cyan")
        self._log(f"🎯 Mode: {active_mode.value.upper()}", "magenta")
        self._log(f"📋 Task: {task}", "bold")
        self._log(f"🧠 LLM Backend: {type(self.llm).__name__}", "cyan")
        self._log(f"🔄 Continuous Refinement: {'Enabled' if self.auto_refine else 'Disabled'}", "green")
        self._log(f"🛡️ Sandbox Policy: Active", "green")
        self._log(f"{'='*70}\n", "bold")

        messages = [
            {"role": "system", "content": self._build_system_prompt(active_mode)},
            {"role": "user", "content": task}
        ]

        for step_idx in range(1, self.max_steps + 1):
            self._log(f"--- Step {step_idx}/{self.max_steps} ---", "bold")

            try:
                step: AgentStep = self.llm.generate_step(messages, self.tools.list_tools())
            except Exception as e:
                err_msg = f"LLM Generation Error: {e}"
                self._log(f"❌ {err_msg}", "yellow")
                return err_msg

            if step.thought:
                self._log(f"🧠 Thought: {step.thought}", "cyan")

            # Check for Final Answer
            if step.final_answer:
                # Intercept if tests previously failed and refinement is required (only in CODING mode)
                if (
                    active_mode == AgentMode.CODING
                    and self.auto_refine
                    and self.last_command_exit_code is not None
                    and self.last_command_exit_code != 0
                    and self.refinement_attempts < self.max_refinements
                ):
                    self.refinement_attempts += 1
                    self._log(
                        f"\n🔄 [Self-Refinement Intercept {self.refinement_attempts}/{self.max_refinements}]: "
                        f"Last test failed with exit code {self.last_command_exit_code}. "
                        f"Refining code before completing...\n",
                        "yellow"
                    )
                    refine_prompt = (
                        f"Automatic Refinement Notice: You attempted to deliver a Final Answer, but the last verification command failed!\n"
                        f"- Exit code: {self.last_command_exit_code}\n"
                        f"- Output snippet:\n{self.last_command_output[:600]}\n\n"
                        f"Please do NOT stop yet. You must:\n"
                        f"1. Analyze the failure output above.\n"
                        f"2. Use 'edit_file' or 'write_file' to refine and fix the code.\n"
                        f"3. Re-run the tests with 'run_command'.\n"
                        f"Continue refining until all tests pass with exit code 0."
                    )
                    messages.append({"role": "user", "content": refine_prompt})
                    continue

                self._log(f"\n🎯 Final Answer:\n{step.final_answer}\n", "green")
                return step.final_answer

            if not step.action:
                self._log("⚠️ No tool action or final answer provided by LLM. Halting.", "yellow")
                return "Agent stopped: No action provided."

            tool = self.tools.get(step.action)
            action_args = step.action_input or {}
            args_formatted = json.dumps(action_args, ensure_ascii=False)
            self._log(f"🛠️  Action: {step.action}({args_formatted})", "yellow")

            if not tool:
                obs = f"Error: Tool '{step.action}' does not exist. Available tools: {list(self.tools._tools.keys())}"
            else:
                obs = tool.execute(**action_args)

            # Track command exit codes to drive continuous refinement
            if step.action == "run_command":
                m = re.search(r"\[Exit code:\s*(-?\d+)\]", obs)
                if m:
                    self.last_command_exit_code = int(m.group(1))
                    self.last_command_output = obs
                    if self.last_command_exit_code != 0:
                        self._log(
                            f"⚠️  Test failed (exit code {self.last_command_exit_code}). Agent will self-refine.",
                            "yellow"
                        )
                    else:
                        self._log("✅ Test passed (exit code 0).", "green")

            obs_preview = obs if len(obs) <= 500 else obs[:500] + f"... [truncated {len(obs)} chars]"
            self._log(f"📋 Observation:\n{obs_preview}\n", "blue")

            step_record = (
                f"Thought: {step.thought}\n"
                f"Action: {step.action}\n"
                f"Action Input: {json.dumps(action_args)}\n"
                f"Observation: {obs}"
            )
            messages.append({"role": "assistant", "content": step_record})

        timeout_msg = f"Agent stopped: Exceeded maximum allowed steps ({self.max_steps})."
        self._log(f"⚠️ {timeout_msg}", "yellow")
        return timeout_msg

    def run_review_and_correct(
        self,
        task: str,
        mode: AgentMode = AgentMode.CODE_REVIEW,
        auto_confirm: bool = False,
        confirm_callback: Optional[Callable[[str], bool]] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Runs a code or security review, extracts any suggested correction prompt,
        and upon confirmation, applies the corrections in coding mode and tests them.
        """
        self._log(f"\n🔍 Executing {mode.value.upper()} on workspace...", "magenta")
        review_result = self.run(task, mode=mode)

        correction_prompt = extract_correction_prompt(review_result)
        if not correction_prompt:
            self._log("ℹ️ No specific correction prompt suggested in review.", "cyan")
            return review_result, None

        self._log(f"\n💡 Suggested Correction Prompt Found:", "yellow")
        self._log(f"   \"{correction_prompt}\"\n", "bold")

        confirmed = False
        if auto_confirm:
            confirmed = True
        elif confirm_callback:
            confirmed = confirm_callback(correction_prompt)
        else:
            try:
                ans = input("\033[1mApply suggested correction and run verification tests? [y/N]: \033[0m").strip().lower()
                confirmed = ans in ("y", "yes")
            except (KeyboardInterrupt, EOFError):
                confirmed = False

        if not confirmed:
            self._log("Correction skipped.", "yellow")
            return review_result, None

        self._log(f"\n🚀 Proceeding with correction & test verification in CODING mode...", "green")
        coding_result = self.run(correction_prompt, mode=AgentMode.CODING)
        return review_result, coding_result
