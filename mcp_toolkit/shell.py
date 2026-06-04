"""Shell Command MCP Server for AI agents."""

import json
import os
import subprocess
import sys


def run_command(cmd: str, timeout: int = 30, cwd: str = None) -> dict:
    """Execute a shell command.

    Args:
        cmd: Command string to execute.
        timeout: Maximum seconds to wait.
        cwd: Working directory.

    Returns:
        Dict with stdout, stderr, and exit code.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-5000:],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}


def get_env(key: str = None) -> dict:
    """Read environment variables."""
    if key:
        return {key: os.environ.get(key, "")}
    # Return safe subset
    safe = {}
    for k, v in os.environ.items():
        if any(s in k.upper() for s in ["HOME", "USER", "PATH", "SHELL", "LANG", "PYTHON", "NODE", "VIRTUAL"]):
            safe[k] = v
    return safe


def _handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "run_command",
                    "description": "Execute a shell command and return the output",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "cmd": {"type": "string", "description": "Shell command to run"},
                            "timeout": {"type": "integer", "default": 30},
                            "cwd": {"type": "string", "description": "Working directory"},
                        },
                        "required": ["cmd"],
                    },
                },
                {
                    "name": "get_env",
                    "description": "Read environment variables",
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
            return {"content": [{"type": "text", "text": json.dumps(run_command(**tool_args), ensure_ascii=False)}]}
        elif tool_name == "get_env":
            return {"content": [{"type": "text", "text": json.dumps(get_env(**tool_args), ensure_ascii=False)}]}

    return {"error": f"Unknown method: {method}"}


def serve():
    print("MCP Shell Server starting...", file=sys.stderr)
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = _handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    serve()
