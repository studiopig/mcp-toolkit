"""CLI entry point for MCP Toolkit."""

import argparse
import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .search import web_search, web_extract
from .file_ops import read_file, write_file, list_dir, search_files
from .file_ops import Workspace


# ── Combined server ("all" command) ─────────────────────────────

_all_server = Server("mcp-toolkit")


@_all_server.list_tools()
async def _all_list_tools() -> list[Tool]:
    """Register all tools from search + file + shell modules."""
    tools = []

    # Search tools
    tools.append(Tool(
        name="web_search",
        description="Search the web using DuckDuckGo",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 5},
            },
            "required": ["query"],
        },
    ))
    tools.append(Tool(
        name="web_extract",
        description="Extract text content from a public URL (SSRF-protected)",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to extract (public addresses only)"},
            },
            "required": ["url"],
        },
    ))

    # File tools
    tools.append(Tool(
        name="read_file",
        description="Read a file with line numbers (max 10MB)",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside workspace"},
                "offset": {"type": "integer", "default": 1},
                "limit": {"type": "integer", "default": 500},
            },
            "required": ["path"],
        },
    ))
    tools.append(Tool(
        name="write_file",
        description="Write content to a file (requires --allow-write)",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside workspace"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    ))
    tools.append(Tool(
        name="list_dir",
        description="List contents of a directory inside workspace",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": ".", "description": "Relative path"},
            },
        },
    ))
    tools.append(Tool(
        name="search_files",
        description="Search file contents with substring matching",
        inputSchema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Substring to search for"},
                "path": {"type": "string", "default": ".", "description": "Subdirectory to search"},
                "file_glob": {"type": "string", "description": "Glob to filter files (e.g. '*.py')"},
            },
            "required": ["pattern"],
        },
    ))

    # Shell tools
    from .shell import _allowlist
    tools.append(Tool(
        name="run_command",
        description=f"Execute a safe command (allowlist: {', '.join(sorted(_allowlist))})",
        inputSchema={
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Command to run (e.g. 'git status')"},
                "timeout": {"type": "integer", "default": 30, "description": "Max seconds (clamped to 60)"},
                "cwd": {"type": "string", "description": "Working directory"},
            },
            "required": ["cmd"],
        },
    ))
    tools.append(Tool(
        name="get_env",
        description="Read safe environment variables (whitelisted only)",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Specific env var to read"},
            },
        },
    ))

    return tools


@_all_server.call_tool()
async def _all_call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Search
    if name == "web_search":
        result = web_search(**arguments)
    elif name == "web_extract":
        result = web_extract(**arguments)
    # File
    elif name == "read_file":
        result = read_file(**arguments)
    elif name == "write_file":
        result = write_file(**arguments)
    elif name == "list_dir":
        result = list_dir(**arguments)
    elif name == "search_files":
        result = search_files(**arguments)
    # Shell
    elif name == "run_command":
        from .shell import run_command as _run
        result = _run(**arguments)
    elif name == "get_env":
        from .shell import get_env as _get_env
        result = _get_env(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _serve_all():
    """Unified MCP server handling search, file, and shell tools."""
    from . import file_ops
    file_ops._workspace = Workspace(".")
    file_ops._allow_write = False
    file_ops._allow_overwrite = False

    async def run_all():
        async with stdio_server() as (read, write):
            await _all_server.run(read, write, _all_server.create_initialization_options())

    sys.stderr.write("MCP Toolkit (all, mcp SDK) starting...\n")
    sys.stderr.flush()
    asyncio.run(run_all())


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="mcp-toolkit",
        description="Plug-and-play MCP servers for AI agents",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("search", help="Start web search MCP server")

    file_parser = sub.add_parser("file", help="Start file operations MCP server")
    file_parser.add_argument("--workspace", default=".",
                             help="Workspace root directory (default: .)")
    file_parser.add_argument("--allow-write", action="store_true",
                             help="Enable write_file tool (default: read-only)")
    file_parser.add_argument("--allow-overwrite", action="store_true",
                             help="Allow overwriting existing files")

    sub.add_parser("shell", help="Start shell command MCP server")
    sub.add_parser("all", help="Start all MCP servers (stdio multiplexer)")

    args = parser.parse_args()

    if args.command == "search":
        from .search import serve
        serve()
    elif args.command == "file":
        from .file_ops import serve
        serve(workspace_root=args.workspace,
              allow_write=args.allow_write,
              allow_overwrite=args.allow_overwrite)
    elif args.command == "shell":
        from .shell import serve
        serve()
    elif args.command == "all":
        _serve_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
