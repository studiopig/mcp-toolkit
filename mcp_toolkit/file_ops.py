"""File Operations MCP Server for AI agents — workspace-sandboxed."""

import asyncio
import json
import os
import sys
from pathlib import Path
import glob as glob_module

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .workspace import Workspace, PathEscapeError


# ── Config (set by serve) ───────────────────────────────────────

_workspace: Workspace | None = None
_allow_write: bool = False
_allow_overwrite: bool = False
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
                 "dist", "build", ".pytest_cache", ".mypy_cache"}


# ── File operations ─────────────────────────────────────────────

def read_file(path: str, offset: int = 1, limit: int = 500) -> dict:
    try:
        resolved = _resolve(path)
        if resolved.stat().st_size > MAX_FILE_SIZE:
            return {"error": f"File too large ({resolved.stat().st_size} bytes, max {MAX_FILE_SIZE})",
                    "path": str(resolved)}
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        selected = lines[offset - 1 : offset - 1 + limit]
        content = "".join(
            f"{i + offset}|{line}" for i, line in enumerate(selected)
        )
        return {"content": content, "total_lines": total, "path": path}
    except PathEscapeError as e:
        return {"error": str(e), "path": path}
    except FileNotFoundError:
        return {"error": f"File not found: {path}", "path": path}
    except Exception as e:
        return {"error": str(e), "path": path}


def write_file(path: str, content: str) -> dict:
    if not _allow_write:
        return {"error": "Write not allowed (use --allow-write)", "path": path}
    try:
        resolved = _resolve(path)
        if resolved.exists():
            if not _allow_overwrite:
                return {"error": "Overwrite not allowed (use --allow-overwrite)", "path": path}
            if resolved.is_dir():
                return {"error": "Path is a directory", "path": path}
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {"written": len(content), "path": path}
    except PathEscapeError as e:
        return {"error": str(e), "path": path}
    except Exception as e:
        return {"error": str(e), "path": path}


def list_dir(path: str = ".") -> dict:
    try:
        resolved = _resolve(path)
        if not resolved.is_dir():
            return {"error": f"Not a directory: {path}", "path": path}
        entries = []
        for entry in sorted(os.listdir(resolved)):
            if entry.startswith("."):
                continue
            full = resolved / entry
            entries.append({
                "name": entry,
                "type": "dir" if full.is_dir() else "file",
                "size": full.stat().st_size if full.is_file() else 0,
            })
        return {"entries": sorted(entries, key=lambda x: (x["type"], x["name"])),
                "path": path}
    except PathEscapeError as e:
        return {"error": str(e), "path": path}
    except FileNotFoundError:
        return {"error": f"Directory not found: {path}", "path": path}
    except Exception as e:
        return {"error": str(e), "path": path}


def search_files(pattern: str, path: str = ".", file_glob: str = None) -> dict:
    try:
        resolved = _resolve(path)
        search_glob = file_glob or "**/*"
        matches = []
        for fpath in glob_module.glob(str(resolved / search_glob), recursive=True):
            fpath_obj = Path(fpath) if isinstance(fpath, str) else fpath
            fpath_str = str(fpath_obj)

            parts = fpath_obj.relative_to(resolved).parts
            if any(p in EXCLUDED_DIRS for p in parts):
                continue
            if fpath_obj.name.startswith("."):
                continue

            if os.path.isfile(fpath_str):
                try:
                    if os.path.getsize(fpath_str) > MAX_FILE_SIZE:
                        continue
                    with open(fpath_str, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if pattern.lower() in line.lower():
                                rel_path = fpath_str[len(str(resolved)) + 1:]
                                matches.append({
                                    "file": rel_path if rel_path else fpath_str,
                                    "line": i,
                                    "content": line.strip()[:200],
                                })
                                if len(matches) >= 50:
                                    break
                except Exception:
                    pass
            if len(matches) >= 50:
                break
        return {"matches": matches[:50], "pattern": pattern}
    except Exception as e:
        return {"error": str(e)}


# ── Helpers ─────────────────────────────────────────────────────

def _resolve(user_path: str) -> Path:
    if _workspace is None:
        raise RuntimeError("Workspace not configured — call serve() first")
    return _workspace.resolve(user_path)


# ── MCP Server ──────────────────────────────────────────────────

server = Server("mcp-toolkit-file")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description=f"Read a file with line numbers (max {MAX_FILE_SIZE//1024//1024}MB)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside workspace"},
                    "offset": {"type": "integer", "default": 1},
                    "limit": {"type": "integer", "default": 500},
                },
                "required": ["path"],
            },
        ),
        Tool(
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
        ),
        Tool(
            name="list_dir",
            description="List contents of a directory inside workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": ".", "description": "Relative path"},
                },
            },
        ),
        Tool(
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
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    tools = {
        "read_file": read_file,
        "write_file": write_file,
        "list_dir": list_dir,
        "search_files": search_files,
    }
    fn = tools.get(name)
    if not fn:
        raise ValueError(f"Unknown tool: {name}")
    result = fn(**arguments)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def serve_async():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def serve(workspace_root: str = ".", allow_write: bool = False,
          allow_overwrite: bool = False):
    """Start MCP File Server with workspace sandbox."""
    global _workspace, _allow_write, _allow_overwrite
    _workspace = Workspace(workspace_root)
    _allow_write = allow_write
    _allow_overwrite = allow_overwrite

    sys.stderr.write(f"MCP File Server starting (mcp SDK, workspace={_workspace.root}, "
                     f"write={allow_write}, overwrite={allow_overwrite})\n")
    sys.stderr.flush()
    asyncio.run(serve_async())


if __name__ == "__main__":
    serve()
