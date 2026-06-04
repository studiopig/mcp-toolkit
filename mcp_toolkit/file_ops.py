"""File Operations MCP Server for AI agents — workspace-sandboxed."""

import json
import os
import sys
import glob as glob_module

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
    """Read a file with line numbers, workspace-bounded.

    Args:
        path: Relative path inside workspace.
        offset: 1-indexed start line.
        limit: Max lines to return.

    Returns:
        Dict with content, total_lines, path.
    """
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
    """Write content to a file, workspace-bounded.

    Requires --allow-write. Overwriting requires --allow-overwrite.

    Args:
        path: Relative path inside workspace.
        content: Text content to write.

    Returns:
        Dict with written byte count, path.
    """
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
    """List workspace directory contents.

    Args:
        path: Relative path inside workspace (default: root).

    Returns:
        Dict with entries list and path.
    """
    try:
        resolved = _resolve(path)
        if not resolved.is_dir():
            return {"error": f"Not a directory: {path}", "path": path}
        entries = []
        for entry in sorted(os.listdir(resolved)):
            if entry.startswith("."):
                continue  # skip hidden
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
    """Search file contents for a substring pattern, workspace-bounded.

    Args:
        pattern: Substring to search for.
        path: Subdirectory inside workspace (default: root).
        file_glob: Glob pattern to filter files (e.g. '*.py').

    Returns:
        Dict with matches list.
    """
    try:
        resolved = _resolve(path)
        search_glob = file_glob or "**/*"
        matches = []
        for fpath in glob_module.glob(str(resolved / search_glob), recursive=True):
            fpath_obj = Path(fpath) if isinstance(fpath, str) else fpath
            fpath_str = str(fpath_obj)

            # Skip excluded dirs and hidden files
            parts = fpath_obj.relative_to(resolved).parts if hasattr(fpath_obj, 'relative_to') else ()
            if any(p in EXCLUDED_DIRS for p in parts):
                continue
            if fpath_obj.name.startswith(".") if hasattr(fpath_obj, 'name') else False:
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

def _resolve(user_path: str):
    """Resolve path within workspace, raising on escape."""
    if _workspace is None:
        raise RuntimeError("Workspace not configured — call serve() first")
    return _workspace.resolve(user_path)


# For type-checker
try:
    from pathlib import Path
except ImportError:
    pass
Path = __import__('pathlib').Path


# ── MCP handler ─────────────────────────────────────────────────

def _handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "read_file",
                    "description": f"Read a file with line numbers (max {MAX_FILE_SIZE//1024//1024}MB)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path inside workspace"},
                            "offset": {"type": "integer", "default": 1},
                            "limit": {"type": "integer", "default": 500},
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "write_file",
                    "description": "Write content to a file (requires --allow-write)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path inside workspace"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
                {
                    "name": "list_dir",
                    "description": "List contents of a directory inside workspace",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": ".", "description": "Relative path"},
                        },
                    },
                },
                {
                    "name": "search_files",
                    "description": "Search file contents with substring matching",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Substring to search for"},
                            "path": {"type": "string", "default": ".", "description": "Subdirectory to search"},
                            "file_glob": {"type": "string", "description": "Glob to filter files (e.g. '*.py')"},
                        },
                        "required": ["pattern"],
                    },
                },
            ]
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        tools = {
            "read_file": read_file,
            "write_file": write_file,
            "list_dir": list_dir,
            "search_files": search_files,
        }
        fn = tools.get(tool_name)
        if fn:
            result = fn(**tool_args)
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

    return {"error": f"Unknown method: {method}"}


# ── Server ──────────────────────────────────────────────────────

def serve(workspace_root: str = ".", allow_write: bool = False,
          allow_overwrite: bool = False):
    """Start MCP File Server with workspace sandbox.

    Args:
        workspace_root: Root directory for all file ops.
        allow_write: Enable write_file (default: read-only).
        allow_overwrite: Allow overwriting existing files.
    """
    global _workspace, _allow_write, _allow_overwrite
    _workspace = Workspace(workspace_root)
    _allow_write = allow_write
    _allow_overwrite = allow_overwrite

    sys.stderr.write(f"MCP File Server starting (workspace={_workspace.root}, "
                     f"write={allow_write}, overwrite={allow_overwrite})\n")
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
