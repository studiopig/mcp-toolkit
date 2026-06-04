"""CLI entry point for MCP Toolkit."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="mcp-toolkit",
        description="Plug-and-play MCP servers for AI agents",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("search", help="Start web search MCP server")
    sub.add_parser("file", help="Start file operations MCP server")
    sub.add_parser("shell", help="Start shell command MCP server")
    sub.add_parser("all", help="Start all MCP servers")

    args = parser.parse_args()

    if args.command == "search":
        from .search import serve
        serve()
    elif args.command == "file":
        from .file_ops import serve
        serve()
    elif args.command == "shell":
        from .shell import serve
        serve()
    elif args.command == "all":
        print("Starting all MCP servers...")
        from .search import serve as serve_search
        from .file_ops import serve as serve_file
        from .shell import serve as serve_shell
        import threading
        threading.Thread(target=serve_search, daemon=True).start()
        threading.Thread(target=serve_file, daemon=True).start()
        serve_shell()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
