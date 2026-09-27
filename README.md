# Autonomous Coding Agent in Python

A lightweight, complete, and fully autonomous AI Coding Agent built from first principles in Python (Python 3.12+).

The agent solves complex software engineering tasks by inspecting codebases, planning, writing and editing code, executing tests in a sandboxed terminal, testing web pages in headless Chrome, and iteratively reasoning and self-correcting via a **ReAct (Reasoning + Acting)** execution loop.

---

## Architecture

```
                             +------------------------+
                             |   User Coding Task     |
                             +------------------------+
                                          |
                                          v
                                 +------------------+
                                 |  Autonomous Agent |<-------------------+
                                 +------------------+                    |
                                          |                              |
                                          v                              |
                            +-------------------------------+             |
                            |          LLM Brain            |             |
                            | (OpenRouter / Ollama / OpenAI |             |
                            |    / Gemini / Mock Mode)      |             |
                            +-------------------------------+             |
                                          |                              |
                                          v                              |
                         +---------------------------------+             |
                         | Specialized Modes:              |             |
                         | - Planning       - Architecture |             |
                         | - Coding         - Code Review  |             |
                         | - Security Review               |             |
                         +---------------------------------+             |
                                          |                              |
                           +---------------+---------------+              |
                           |                               |              |
                           v                               v              |
                  [Tool Invocation]                 [Final Answer]        |
                 - list_skills                             |              |
                 - read_skill                              v              |
                 - list_directory                   Task completed        |
                 - read_file                        and verified!         |
                 - write_file                              |              |
                 - edit_file                               |              |
                 - search_code                             | (if tests    |
                 - run_command (sandboxed)                 |  failed)     |
                 - test_web_page (Chrome)                  v              |
                 - start/stop_web_server           [Self-Refinement] ----+
                           |                                              |
                           v                                              |
                 [Observation / Output]                                   |
                 (stdout, exit code, diff)                                |
                           |                                              |
                           +----------------------------------------------+
```

---

## Key Features

- 🧠 **ReAct Execution Loop**: Alternates between *Thought* (analysis & strategy), *Action* (tool call), and *Observation* (feedback from tools/terminal).
- 🎯 **Specialized Execution Modes**:
  - `planning`: Requirements decomposition and step-by-step technical blueprints without code mutation.
  - `architecture`: System design, modular boundaries, interface definitions, and scalability analysis.
  - `coding`: Full autonomous implementation, refactoring, and test-driven development.
  - `code_review`: Deep analysis of code quality, style, potential bugs, edge cases, and actionable remediation.
  - `security_review`: Vulnerability audit (OWASP Top 10, path traversal, injection, hardcoded secrets).
  - `--auto-correct`: Automatically applies and tests suggested corrections from code/security reviews.
- 🔄 **Test-Driven Self-Refinement**:
  - Automatically intercepts final answers if verification commands failed.
  - Feeds stderr, exit codes, and failure traces back into the reasoning loop to fix bugs autonomously (up to 3 refinement passes).
- 🛡️ **Multi-Layered Workspace Sandboxing (`sandbox.py`)**:
  - **Filesystem Confinement**: Strict realpath resolution preventing symlink escapes and directory traversal outside the workspace.
  - **Protected Paths**: Guards sensitive repository files such as `.git` and `.env` against modification.
  - **Command Sanitization**: Filters destructive commands (`rm -rf /`, `mkfs`, `dd`, `chmod 777`, fork bombs).
  - **Privilege Separation**: Blocks root/system altering binaries (`sudo`, `apt`, `systemctl`, `chown`, `useradd`).
  - **Resource Limits**: Linux `resource` limits (RLIMIT_AS for memory, RLIMIT_CPU for CPU time, process caps).
  - **Strict Sandbox Flag (`--strict-sandbox`)**: Restricts memory to 256MB, CPU to 20s, and disables network access.
- 🌐 **Chrome Web Testing Suite (`web_tester.py`)**:
  - Headless Chrome browser integration for automated UI and web verification.
  - Built-in background HTTP web server (`WorkspaceWebServer`) to test workspace web files locally.
  - Robust fallback DOM parser (`SimpleDOMParser`) when Chrome is not installed.
  - Verifies page titles, DOM selectors, required text, and forbidden text.
- 📚 **Custom Skills Discovery (`.agents/`)**:
  - Automatically discovers reusable agent skills and guidelines organized under `.agents/`.
  - Built-in `list_skills` and `read_skill` tools allow the agent to read specialized workflows on demand.
- 🛠️ **Full Coding Tool Suite**:
  - `list_directory`: Discover repository files and folders.
  - `read_file`: Read code with 1-based line numbers and line slice support.
  - `write_file`: Create new source code and test files.
  - `edit_file`: Precise search-and-replace modification of existing files.
  - `search_code`: Search code patterns across the codebase (like ripgrep/grep).
  - `run_command`: Run tests, linters, or scripts with output truncation and timeouts.
  - `test_web_page`: Run headless Chrome browser assertions against URLs or local files.
  - `start_web_server` / `stop_web_server`: Manage local HTTP servers for workspace web code.
  - `list_skills` / `read_skill`: Discover and load modular skills from `.agents/`.
- 🔌 **Pluggable LLM Backends**:
  - **OpenRouter Free Models**: Connect to top-tier free models like `qwen/qwen-2.5-coder-32b-instruct:free` or `deepseek/deepseek-r1:free`.
  - **Local Ollama**: Run completely locally and privately with models like `qwen2.5-coder`.
  - **OpenAI & OpenAI-compatible**: Supports OpenAI, Groq, Together, and vLLM.
  - **Google Gemini**: Connects directly via the Gemini REST API.
  - **Zero-Dependency Mock Mode**: Works out of the box without any API keys.
- ⚡ **Zero External Dependencies**: Implemented using pure Python standard library (`urllib.request`, `json`, `subprocess`, `re`, `ast`, `http.server`, `html.parser`).

---

## Quickstart

### 1. Using Free OpenRouter AI Models (Recommended & Zero Cost)

You can run cutting-edge models like **Qwen 2.5 Coder 32B** or **DeepSeek R1** for free via OpenRouter.

1. Get a free API key at [openrouter.ai/keys](https://openrouter.ai/keys) *(free tier, no credit card required)*.
2. Set your environment variable:
   ```bash
   export OPENROUTER_API_KEY="sk-or-v1-..."
   ```
3. Run the agent:
   ```bash
   python3 main.py --openrouter
   ```

To list all available free models:
```bash
python3 main.py --list-models
```

To run with a specific free model:
```bash
python3 main.py --openrouter --model deepseek/deepseek-r1:free
```

---

### 2. Interactive REPL Mode & Slash Commands

Start an interactive chat session with the agent:

```bash
python3 main.py
```

Inside the interactive prompt, you can use convenient slash commands:
- `/mode <mode>`: Switch mode (`planning`, `architecture`, `coding`, `code_review`, `security_review`)
- `/plan`: Switch directly to `PLANNING` mode
- `/arch`: Switch directly to `ARCHITECTURE` mode
- `/code`: Switch directly to `CODING` mode
- `/review`: Switch directly to `CODE_REVIEW` mode
- `/security`: Switch directly to `SECURITY_REVIEW` mode
- `/web <file_or_url>`: Run automated Chrome web testing on a local HTML file or URL
- `demo`: Run the automated palindrome demonstration
- `exit` / `quit`: Exit the agent session

---

### 3. Execution Modes & Review Auto-Correction

#### Planning Mode
```bash
python3 main.py --mode planning "Design an authentication service with JWT and refresh tokens"
```

#### Code Review & Security Review with Auto-Correction
Run a review and automatically apply and verify suggested corrections:
```bash
python3 main.py --mode security_review --auto-correct "Review src/auth.py for vulnerabilities"
```

---

### 4. Automated Web Testing

Test local HTML files or web services directly with headless Chrome:
```bash
# Direct CLI test
python3 main.py --web-test index.html

# Or run via the agent ReAct loop
python3 main.py "Create an interactive calculator in index.html and verify it using test_web_page"
```

---

### 5. Using with Local Ollama (Free & 100% Offline)

If you have [Ollama](https://ollama.ai) running locally:

```bash
# Pull a coding model
ollama pull qwen2.5-coder

# Run with the agent
python3 main.py --base-url http://localhost:11434/v1 --model qwen2.5-coder
```

---

### 6. Using with OpenAI or Gemini

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."
python3 main.py "Refactor my_module.py to handle edge cases and run the test suite"

# Google Gemini
export GEMINI_API_KEY="AIza..."
python3 main.py "Build a CLI expense calculator and write tests for it"
```

---

## CLI Options

```
usage: main.py [-h] [-t TASK] [-w WORKSPACE] [-m MODEL]
               [--mode {planning,architecture,coding,code_review,security_review}]
               [--auto-correct] [--web-test WEB_TEST] [--strict-sandbox]
               [--openrouter] [--list-models] [--base-url BASE_URL]
               [--api-key API_KEY] [--max-steps MAX_STEPS] [--mock]
               [--no-refine] [-i]
               [task_pos ...]

Options:
  -t, --task TASK       Coding or review task to solve
  -w, --workspace PATH  Target workspace root directory (default: './ws/')
  -m, --model MODEL     LLM model name (e.g. qwen/qwen-2.5-coder-32b-instruct:free)
  --mode MODE           Execution mode: planning, architecture, coding, code_review, security_review (default: coding)
  --auto-correct        Automatically apply and test suggested corrections from reviews
  --web-test TARGET     Run Chrome web testing on a local file or URL
  --strict-sandbox      Enforce ultra-strict sandboxing policies (256MB RAM, 20s CPU, no network)
  --openrouter          Use OpenRouter free models
  --list-models         List popular free OpenRouter models
  --base-url URL        Base URL for custom OpenAI-compatible endpoint (Ollama, Groq, vLLM)
  --api-key KEY         API key override
  --max-steps N         Maximum ReAct execution steps (default: 20)
  --mock                Force run in mock simulation mode
  --no-refine           Disable automatic test-driven self-refinement
  -i, --interactive     Start interactive REPL mode (default when no task provided)
```

---

## Security & Sandboxing Details

The Autonomous Coding Agent executes code under strict boundaries defined in `sandbox.py`:

| Mechanism | Description |
|---|---|
| **Path Confinement** | Validates all paths using `os.path.realpath` to prevent directory traversal (`../`) and symlink attacks. |
| **Protected Subpaths** | Modifying `.git` and `.env` files is blocked by default. |
| **Command Filtering** | Commands matching dangerous patterns (`rm -rf /`, `mkfs`, fork bombs) are blocked before execution. |
| **Binary Restrictions** | Binaries that alter system state or elevate privileges (`sudo`, `apt`, `systemctl`, `passwd`) are forbidden. |
| **Resource Caps** | Subprocesses are governed by POSIX `resource` limits (memory, CPU time, process counts). |
| **Strict Mode** | Restricts memory to 256MB, CPU execution time to 20 seconds, and isolates network access. |

---

## Running the Automated Test Suite

The test suite covers file operations, sandboxing, security barriers, skills discovery, web testing, and review workflows:

```bash
python3 -m unittest test_agent.py -v
```

---

## Extending with Custom Tools

You can register new custom tools on the agent's `ToolRegistry` using the `@registry.register` decorator:

```python
from agent import AICodingAgent

agent = AICodingAgent(workspace="./ws")

@agent.tools.register(
    name="query_database",
    description="Execute a read-only SQL query against the SQLite database.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SQL query to execute"}
        },
        "required": ["query"]
    }
)
def query_database(query: str) -> str:
    # Your custom tool implementation
    return "Query result..."
```
