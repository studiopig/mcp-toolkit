"""CLI entry point for MCP Toolkit."""

import argparse
import json
import sys

from .search import _handle_request as _handle_search
from .file_ops import _handle_request as _handle_file
from .shell import _handle_request as _handle_shell


def _serve_all():
    """Unified MCP server handling search, file, and shell tools.

    File ops run read-only with a default workspace of the current directory.
    For write access or custom workspace, use 'mcp-toolkit file --workspace ...' separately.
    """
    from .workspace import Workspace
    from . import file_ops
    file_ops._workspace = Workspace(".")
    file_ops._allow_write = False
    file_ops._allow_overwrite = False

    import sys as _sys
    _sys.stderr.write("MCP Toolkit (all) starting...\n")
    _sys.stderr.flush()
    for line in _sys.stdin:
        try:
            request = json.loads(line.strip())
            method = request.get("method", "")
            params = request.get("params", {})
            tool_name = params.get("name", "")

            if method == "tools/list":
                tools = []
                for handler in [_handle_search, _handle_file, _handle_shell]:
                    resp = handler({"method": "tools/list", "params": {}})
                    tools.extend(resp.get("tools", []))
                print(json.dumps({"tools": tools}), flush=True)

            elif method == "tools/call":
                if tool_name in ("web_search", "web_extract"):
                    resp = _handle_search(request)
                elif tool_name in ("read_file", "write_file", "list_dir", "search_files"):
                    resp = _handle_file(request)
                elif tool_name in ("run_command", "get_env"):
                    resp = _handle_shell(request)
                else:
                    resp = {"error": f"Unknown tool: {tool_name}"}
                print(json.dumps(resp, ensure_ascii=False), flush=True)

            else:
                print(json.dumps({"error": f"Unknown method: {method}"}), flush=True)
        except json.JSONDecodeError:
            pass


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
