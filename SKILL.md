# Skill: Autonomous Software Engineering Platform

## Purpose
Comprehensive autonomous engineering skill defining the execution lifecycle from user requirement decomposition through architecture design, code generation, unit test generation, debugging loop, security scanning, and deployment automation.

## Inputs
- User task / engineering requirement
- Target workspace path
- LLM Router configuration
- Sandbox execution policy

## Process
1. Requirement Analysis: Deconstruct requirements, constraints, and acceptance criteria into `docs/requirements.md`.
2. Repository Analysis: Inspect workspace directory, frameworks, language versions, existing tests, and build tooling into `repository-analysis.md`.
3. Planning & Architecture: Author `docs/implementation-plan.md` and ADR `docs/architecture.md`.
4. Code Generation: Implement modular code accompanied by Implementation Summaries.
5. Test Generation: Generate `tests/unit`, `tests/integration`, and `tests/e2e`.
6. Test Execution & Autonomous Debugging: Execute tests; loop failure analysis, root-cause identification, and automated patching until all tests pass.
7. Security Validation: Scan code for vulnerabilities (AST, secrets, OWASP top 10) and generate `reports/security-report.md`.
8. Deployment Automation: Generate Dockerfile, docker-compose, and Kubernetes manifests, validating deployment health.
9. Final Reporting: Compile comprehensive `reports/engineering-report.md`.

## Outputs
- Production-grade source code
- Comprehensive test suite with coverage
- Engineering documentation (`docs/`)
- Security and audit reports (`reports/`)
- Container and deployment configurations

## Validation
- All unit and integration tests pass cleanly (100% passing rate).
- Zero high/critical security findings.
- Container builds and health probes succeed.
