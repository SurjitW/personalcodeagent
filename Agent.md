# Agent Configuration

Project: Autonomous Software Engineering Agent Platform
Language: Python 3.12+
Framework: FastAPI, Pydantic, SQLAlchemy, asyncio, Docker SDK

## Coding Rules
- Follow PEP 8 and Python 3.12+ idioms (type hints, structural pattern matching, async/await).
- Maintain clean architecture with strict separation of concerns (LLM, Core, Sandbox, Testing, Security, Deployment).
- Write modular, testable, and documented code with explicit error handling.
- Avoid unnecessary modifications and preserve existing public APIs.
- Provide implementation summaries before modifying code:
  - Files Changed
  - Design Reason
  - Potential Risks
  - Testing Approach

## Testing Rules
- Every feature and bugfix requires automated tests.
- Backend testing framework: `pytest` and `unittest`.
- Frontend testing framework: `Jest` and `Playwright`.
- Coverage targets:
  - Critical code: 90%+
  - Normal code: 80%+
- Test directory structure:
  - `tests/unit/`
  - `tests/integration/`
  - `tests/e2e/`

## Security Rules
- No hardcoded secrets, API keys, or plaintext credentials in code.
- Prevent SQL injection, command injection, path traversal, and unvalidated deserialization.
- All external shell commands must be strictly sandboxed with resource and privilege limits.
- Enforce network egress restrictions and non-root execution in containers.
- Run static security scans (Bandit/Semgrep/AST checks) before deployment.

## Deployment Rules
- Docker containerization for isolated runtimes.
- Kubernetes-ready manifests with health probes and resource requests/limits.
- CI/CD automation with GitHub Actions and GitLab CI.
- Validate deployment health checks before marking tasks as complete.
