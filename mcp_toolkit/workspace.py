"""Workspace sandbox — confine file operations to a root directory."""

from pathlib import Path


class PathEscapeError(PermissionError):
    """Raised when a path tries to escape the workspace root."""
    pass


class Workspace:
    """Directory sandbox that resolves all user paths relative to a root.

    Usage:
        ws = Workspace("./my-project")
        path = ws.resolve("src/main.py")    # → workspace/src/main.py
        path = ws.resolve("../outside")      # → raises PathEscapeError
    """

    def __init__(self, root: str = "."):
        self.root = Path(root).resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, user_path: str) -> Path:
        """Resolve a user-supplied path, raising if it escapes the root."""
        target = (self.root / user_path).resolve(strict=False)
        try:
            target.relative_to(self.root)
        except ValueError:
            raise PathEscapeError(
                f"Path escapes workspace: '{user_path}' → '{target}' "
                f"(workspace root: {self.root})"
            )
        return target

    def __repr__(self):
        return f"Workspace(root={self.root})"
