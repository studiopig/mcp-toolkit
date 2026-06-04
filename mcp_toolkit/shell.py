"""Shell Command MCP Server for AI agents — sandboxed and allowlisted."""

import asyncio
import json
import os
import shlex
import subprocess
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


# ── Config ──────────────────────────────────────────────────────

DEFAULT_ALLOWLIST = {"git", "python", "python3", "pytest", "node", "npm", "pnpm",
                     "echo", "cat", "ls", "dir", "pwd", "which", "where"}
MAX_TIMEOUT = 60
MAX_OUTPUT_LINES = 200

_allowlist: set = DEFAULT_ALLOWLIST.copy()


def _resolve_cmd(cmd: str) -> tuple:
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
    timeout = min(timeout, MAX_TIMEOUT)
    try:
        args, _ = _resolve_cmd(cmd)
        result = subprocess.run(
            args, shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
        )
        stdout = "\n".join(result.stdout.splitlines()[-MAX_OUTPUT_LINES:])
        stderr = "\n".join(result.stderr.splitlines()[-MAX_OUTPUT_LINES:])
        return {"stdout": stdout, "stderr": stderr, "exit_code": result.returncode}
    except PermissionError as e:
        return {"error": str(e), "exit_code": -1}
    except ValueError as e:
        return {"error": str(e), "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "exit_code": -1}
    except Exception as e:
        return {"error": str(e), "exit_code": -1}


def get_env(key: str = None) -> dict:
    safe_keys = {"HOME", "USER", "USERNAME", "PATH", "SHELL", "LANG",
                 "PYTHONPATH", "NODE_ENV", "VIRTUAL_ENV", "PWD"}
    if key:
        if key in safe_keys:
            return {key: os.environ.get(key, "")}
        return {"error": f"Environment variable not allowed: '{key}'. Allowed: {sorted(safe_keys)}"}
    return {k: os.environ.get(k, "") for k in safe_keys if k in os.environ}


# ── MCP Server ──────────────────────────────────────────────────

server = Server("mcp-toolkit-shell")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="run_command",
            description=f"Execute a safe command (allowlist: {', '.join(sorted(_allowlist))})",
            inputSchema={
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Command to run (e.g. 'git status')"},
                    "timeout": {"type": "integer", "default": 30, "description": f"Max seconds (clamped to {MAX_TIMEOUT})"},
                    "cwd": {"type": "string", "description": "Working directory"},
                },
                "required": ["cmd"],
            },
        ),
        Tool(
            name="get_env",
            description="Read safe environment variables (whitelisted only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Specific env var to read"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "run_command":
        result = run_command(**arguments)
    elif name == "get_env":
        result = get_env(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def serve_async():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def serve():
    """Start MCP Shell Server over stdio."""
    sys.stderr.write(f"MCP Shell Server starting (mcp SDK, allowlist: {sorted(_allowlist)})\n")
    sys.stderr.flush()
    asyncio.run(serve_async())


if __name__ == "__main__":
    serve()
