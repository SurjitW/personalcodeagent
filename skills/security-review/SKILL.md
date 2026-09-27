# Skill: Security Review and Hardening

## Purpose
Perform comprehensive static application security testing (SAST), secret scanning, vulnerability assessments, and automated remediation.

## Inputs
- Target source tree
- Manifest and configuration files
- Security policies

## Process
1. Run AST-based code analysis detecting injection patterns, path traversals, and unsafe deserializations.
2. Scan all files for potential API keys, passwords, and private certificates.
3. Audit dependency manifests for known CVEs.
4. Produce remediation recommendations and generate patches.

## Outputs
- `reports/security-report.md`
- Code patches addressing security violations

## Validation
- Re-run security scanner confirming zero high or critical severity violations.
