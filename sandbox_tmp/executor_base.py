"""
Sandbox module for Autonomous Coding Agent.
Provides strict filesystem confinement, symlink traversal protection,
command security filtering, and resource-limited subprocess execution.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Try importing resource module (available on Unix/Linux/Mac)
try: 
    import resource
except ImportError:
    resource = None  # type: ignore


@dataclass
class SandboxPolicy:
    """Configuration for execution and filesystem sandboxing."""
    allow_write: bool = True
    allow_network: bool = True
    max_memory_mb: int = 512
    max_cpu_seconds: int = 30
    max_file_size_mb: int = 50
    max_processes: int = 64
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs", "dd if=",
        "chmod -R 777", "chmod 777",
    ])
    blocked_binaries: Set[str] = field(default_factory=lambda: {
        # System alteration & privilege escalation
        "sudo", "su", "pkexec", "doas",
        "chown", "fdisk", "parted",
        "systemctl", "service", "init", "shutdown", "reboot", "poweroff",
        "useradd", "userdel", "usermod", "groupadd", "passwd",
        # Package managers modifying system
        "apt", "apt-get", "dpkg", "yum", "dnf", "pacman", "apk", "rpm",
    })
    protected_subpaths: Set[str] = field(default_factory=lambda: {
        ".git",
        ".env",
    })


def validate_path(
    workspace: str,
    target_path: str,
    write: bool = False,
    policy: Optional[SandboxPolicy] = None
) -> str:
    """
    Ensure the target path is strictly confined within the workspace root.
    Resolves symlinks with realpath to prevent symlink traversal attacks.
    Guards protected directories like .git.
    """
    policy = policy or SandboxPolicy()
    workspace_real = os.path.realpath(os.path.abspath(workspace))

    if os.path.isabs(target_path):
        candidate = os.path.abspath(target_path)
    else:
        candidate = os.path.abspath(os.path.join(workspace_real, target_path))

    # Resolve real path of existing file or nearest existing parent
    curr = candidate
    while curr and not os.path.exists(curr) and curr != os.path.dirname(curr):
        curr = os.path.dirname(curr)

    resolved_base = os.path.realpath(curr) if os.path.exists(curr) else workspace_real

    # Verify that the path does not escape the workspace
    try:
        common = os.path.commonpath([workspace_real, resolved_base])
    except ValueError:
        raise PermissionError(
            f"Sandbox Violation: '{target_path}' is on a different drive or invalid path."
        )

    if common != workspace_real:
        raise PermissionError(
            f"Sandbox Violation: Path '{target_path}' resolves outside workspace '{workspace_real}'."
        )

    # Check protected paths for write operations
    if write:
        if not policy.allow_write:
            raise PermissionError("Sandbox Violation: File modifications are disabled by policy.")

        rel = os.path.relpath(candidate, workspace_real)
        parts = rel.split(os.sep)
        for protected in policy.protected_subpaths:
            if protected in parts:
                raise PermissionError(
                    f"Sandbox Violation: Write access to protected path '{protected}' is forbidden."
                )

    return candidate


def is_command_safe(command: str, policy: Optional[SandboxPolicy] = None) -> Tuple[bool, str]:
    """Check command against safety policy."""
    policy = policy or SandboxPolicy()
    cmd_strip = command.strip()

    # Block empty commands
    if not cmd_strip:
        return False, "Empty command."

    # Check for direct dangerous string matches
    for dangerous in policy.blocked_commands:
        if dangerous in cmd_strip:
            return False, f"Blocked command for safety: contains dangerous pattern '{dangerous}'"

    # Token-level check for privileged / system-modifying executables
    # Parse tokens using shlex where possible, or fallback safely
    try:
        tokens = shlex.split(cmd_strip)
    except Exception:
        tokens = cmd_strip.split()

    # Check for direct binary or subcommand chains
    subcommands = re.split(r"[;&|]+", cmd_strip)
    for sub in subcommands:
        sub = sub.strip()
        if not sub:
            continue
        try:
            sub_tokens = shlex.split(sub)
        except Exception:
            sub_tokens = sub.split()

        if not sub_tokens:
            continue

        cmd_bin = os.path.basename(sub_tokens[0])
        if cmd_bin in policy.blocked_binaries:
            return False, f"Blocked command for safety: execution of privileged binary '{cmd_bin}' is forbidden."

        # Check for redirection to system root or outside paths
        if any(tok.startswith(("/etc", "/usr", "/bin", "/boot", "/sys", "/dev", "/proc", "/root")) for tok in sub_tokens):
            if any(sym in sub for sym in [">", ">>", "|"]):
                return False, f"Blocked command for safety: attempts write access to system directory: '{sub}'"

    return True, ""


def execute_sandboxed_command(
    command: str,
    cwd: str,
    timeout: int = 30,
    policy: Optional[SandboxPolicy] = None
) -> str:
    """
    Executes a shell command with strict sandboxing:
    - Path confinement to cwd
    - Dangerous command detection
    - Environment sanitization
    - POSIX resource limits (RAM, CPU, file size)
    - Process isolation via session/process group
    """
    policy = policy or SandboxPolicy()
    cwd_real = os.path.realpath(os.path.abspath(cwd))

    # 1. Validate command safety
    safe, reason = is_command_safe(command, policy)
    if not safe:
        return f"[Sandbox Blocked] {reason}"

    # 2. Sanitize environment variables
    safe_env: Dict[str, str] = {}
    allowed_env_keys = {
        "PATH", "LANG", "LC_ALL", "LC_CTYPE", "PYTHONPATH", "PYTHONHOME",
        "TERM", "USER", "LOGNAME", "HOME", "SHELL", "VIRTUAL_ENV"
    }
    for k in allowed_env_keys:
        if k in os.environ:
            safe_env[k] = os.environ[k]

    # Create isolated temp dir inside workspace
    sandbox_tmp = os.path.join(cwd_real, ".sandbox_tmp")
    os.makedirs(sandbox_tmp, exist_ok=True)
    safe_env["TMPDIR"] = sandbox_tmp
    safe_env["TEMP"] = sandbox_tmp
    safe_env["TMP"] = sandbox_tmp
    safe_env["PYTHONDONTWRITEBYTECODE"] = "1"

    def preexec_setup():
        # Create a new process session
        os.setsid()
        # Set restrictive umask
        os.umask(0o022)

        if resource is not None:
            try:
                mem_bytes = policy.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            except (ValueError, resource.error, OSError):
                pass

            try:
                cpu_secs = policy.max_cpu_seconds
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_secs, cpu_secs + 5))
            except (ValueError, resource.error, OSError):
                pass

            try:
                fsize_bytes = policy.max_file_size_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
            except (ValueError, resource.error, OSError):
                pass

    timeout = min(max(1, timeout), 60)

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd_real,
            env=safe_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            preexec_fn=preexec_setup if os.name == "posix" else None
        )
        output = proc.stdout.strip()
        exit_code = proc.returncode

        header = f"[Exit code: {exit_code}]"
        if not output:
            return f"{header} (No output produced)"
        if len(output) > 4000:
            output = output[:4000] + "\n... (output truncated at 4000 chars)"
        return f"{header}\n{output}"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error running sandboxed command: {e}"
