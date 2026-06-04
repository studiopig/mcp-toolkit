"""Shell Command MCP Server for AI agents — sandboxed and allowlisted."""

import json
import os
import shlex
import subprocess
import sys


# ── Config ──────────────────────────────────────────────────────

DEFAULT_ALLOWLIST = {"git", "python", "python3", "pytest", "node", "npm", "pnpm",
                     "echo", "cat", "ls", "dir", "pwd", "which", "where"}
MAX_TIMEOUT = 60
MAX_OUTPUT_LINES = 200

_allowlist: set = DEFAULT_ALLOWLIST.copy()


def _resolve_cmd(cmd: str):
    """Split command and check allowlist.

    Returns (args_list, allowed_cmd_name).

    Raises:
        PermissionError: If command is not in the allowlist.
        ValueError: If command string is empty.
    """
    args = shlex.split(cmd.strip())
    if not args:
        raise ValueError("cmd must not be empty")
    cmd_name = os.path.basename(args[0])
    if cmd_name not in _allowlist:
        raise PermissionError(
            f"Command not allowed: '{cmd_name}'. "
            f"Allowed: {', '.join(sorted(_allowlist))}"
        )
    return args, cmd_name


# ── Shell operations ────────────────────────────────────────────

def run_command(cmd: str, timeout: int = 30, cwd: str = None) -> dict:
    """Execute a shell command (safe: no shell pipe, limit enforced).

    Args:
        cmd: Command string (will be shlex.split).
        timeout: Max seconds (clamped to {global_limit}).
        cwd: Working directory.

    Returns:
        Dict with stdout, stderr, exit_code.
    """
    timeout = min(timeout, MAX_TIMEOUT)
    try:
        args, _ = _resolve_cmd(cmd)
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        stdout = "\n".join(result.stdout.splitlines()[-MAX_OUTPUT_LINES:])
        stderr = "\n".join(result.stderr.splitlines()[-MAX_OUTPUT_LINES:])
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.returncode,
        }
    except PermissionError as e:
        return {"error": str(e), "exit_code": -1}
    except ValueError as e:
        return {"error": str(e), "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}


def get_env(key: str = None) -> dict:
    """Read whitelisted environment variables.

    Args:
        key: Specific env var. If None, returns safe subset.

    Returns:
        Dict of env vars or empty string if not found.
    """
    safe_keys = {"HOME", "USER", "USERNAME", "PATH", "SHELL", "LANG",
                 "PYTHONPATH", "NODE_ENV", "VIRTUAL_ENV", "PWD"}
    if key:
        if key in safe_keys:
            return {key: os.environ.get(key, "")}
        return {"error": f"Environment variable not allowed: '{key}'. Allowed: {sorted(safe_keys)}"}
    return {k: os.environ.get(k, "") for k in safe_keys if k in os.environ}


# ── MCP handler ─────────────────────────────────────────────────

def _handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "run_command",
                    "description": f"Execute a safe command (allowlist: {', '.join(sorted(_allowlist))})",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "cmd": {"type": "string", "description": "Command to run (e.g. 'git status')"},
                            "timeout": {"type": "integer", "default": 30,
                                        "description": f"Max seconds (clamped to {MAX_TIMEOUT})"},
                            "cwd": {"type": "string", "description": "Working directory"},
                        },
                        "required": ["cmd"],
                    },
                },
                {
                    "name": "get_env",
                    "description": "Read safe environment variables (whitelisted only)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Specific env var to read"},
                        },
                    },
                },
            ]
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name == "run_command":
            return {"content": [{"type": "text",
                                 "text": json.dumps(run_command(**tool_args), ensure_ascii=False)}]}
        elif tool_name == "get_env":
            return {"content": [{"type": "text",
                                 "text": json.dumps(get_env(**tool_args), ensure_ascii=False)}]}

    return {"error": f"Unknown method: {method}"}


# ── Server ──────────────────────────────────────────────────────

def serve():
    """Start MCP Shell Server."""
    sys.stderr.write(f"MCP Shell Server starting (allowlist: {sorted(_allowlist)})\n")
    sys.stderr.flush()
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = _handle_request(request)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    serve()
