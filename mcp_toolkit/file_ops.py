"""File Operations MCP Server for AI agents."""

import json
import os
import sys
import glob as glob_module


def read_file(path: str, offset: int = 1, limit: int = 500) -> dict:
    """Read a file with line numbers."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        selected = lines[offset - 1 : offset - 1 + limit]
        content = "".join(
            f"{i + offset}|{line}" for i, line in enumerate(selected)
        )
        return {"content": content, "total_lines": total, "path": path}
    except Exception as e:
        return {"error": str(e), "path": path}


def write_file(path: str, content: str) -> dict:
    """Write content to a file."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"written": len(content), "path": path}
    except Exception as e:
        return {"error": str(e), "path": path}


def list_dir(path: str = ".") -> dict:
    """List directory contents."""
    try:
        entries = []
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            entries.append({
                "name": entry,
                "type": "dir" if os.path.isdir(full) else "file",
                "size": os.path.getsize(full) if os.path.isfile(full) else 0,
            })
        return {"entries": sorted(entries, key=lambda x: (x["type"], x["name"])), "path": path}
    except Exception as e:
        return {"error": str(e), "path": path}


def search_files(pattern: str, path: str = ".", file_glob: str = None) -> dict:
    """Search for files matching pattern."""
    try:
        search_pattern = file_glob or "**/*"
        matches = []
        for fpath in glob_module.glob(os.path.join(path, search_pattern), recursive=True):
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if pattern.lower() in line.lower():
                                matches.append({
                                    "file": fpath,
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


def _handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read a file with line numbers",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "offset": {"type": "integer", "default": 1},
                            "limit": {"type": "integer", "default": 500},
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "write_file",
                    "description": "Write content to a file (overwrites)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
                {
                    "name": "list_dir",
                    "description": "List contents of a directory",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": "."},
                        },
                    },
                },
                {
                    "name": "search_files",
                    "description": "Search file contents with substring matching",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "default": "."},
                            "file_glob": {"type": "string"},
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


def serve():
    print("MCP File Server starting...", file=sys.stderr)
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = _handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    serve()
