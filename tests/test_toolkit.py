"""Tests for mcp-toolkit — security, sandbox, shell allowlist, SSRF."""

import os
import shutil
import tempfile

import pytest
from mcp_toolkit import file_ops
from mcp_toolkit.file_ops import list_dir, read_file, write_file
from mcp_toolkit.search import _is_private, web_extract
from mcp_toolkit.shell import _resolve_cmd, get_env, run_command
from mcp_toolkit.workspace import PathEscapeError, Workspace


# ═════════════════════════════════════════════════════════════════
#  Workspace sandbox
# ═════════════════════════════════════════════════════════════════

def test_workspace_normal_path():
    ws = Workspace(tempfile.mkdtemp())
    resolved = ws.resolve("file.txt")
    assert resolved == ws.root / "file.txt"
    assert resolved.is_relative_to(ws.root)
    shutil.rmtree(str(ws.root), ignore_errors=True)


def test_workspace_parent_escape():
    ws = Workspace(tempfile.mkdtemp())
    with pytest.raises(PathEscapeError):
        ws.resolve("../outside.txt")
    shutil.rmtree(str(ws.root), ignore_errors=True)


def test_workspace_absolute_escape():
    import sys
    ws = Workspace(tempfile.mkdtemp())
    # Platform-independent absolute path outside workspace
    evil = "C:/Windows/System32" if sys.platform == "win32" else "/etc"
    with pytest.raises(PathEscapeError):
        ws.resolve(evil)
    shutil.rmtree(str(ws.root), ignore_errors=True)


def test_workspace_deep_escape():
    ws = Workspace(tempfile.mkdtemp())
    with pytest.raises(PathEscapeError):
        ws.resolve("../../etc/passwd")
    shutil.rmtree(str(ws.root), ignore_errors=True)


# ═════════════════════════════════════════════════════════════════
#  Shell allowlist
# ═════════════════════════════════════════════════════════════════

def test_shell_echo():
    result = run_command("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


def test_shell_rm_blocked():
    result = run_command("rm -rf /")
    assert "not allowed" in result.get("error", "").lower()


def test_shell_curl_blocked():
    result = run_command("curl http://evil.com")
    assert "not allowed" in result.get("error", "").lower()


def test_shell_empty_cmd():
    result = run_command("")
    assert "error" in result


def test_shell_resolve_empty():
    with pytest.raises(ValueError, match="must not be empty"):
        _resolve_cmd("")


def test_shell_resolve_blocked():
    with pytest.raises(PermissionError, match="not allowed"):
        _resolve_cmd("curl http://example.com")


# ═════════════════════════════════════════════════════════════════
#  Env whitelist
# ═════════════════════════════════════════════════════════════════

def test_env_safe_key():
    result = get_env("HOME")
    assert "HOME" in result


def test_env_blocked_key():
    result = get_env("OPENAI_API_KEY")
    assert "error" in result
    assert "not allowed" in result["error"].lower()


def test_env_blocked_token():
    result = get_env("DEEPSEEK_API_KEY")
    assert "error" in result
    assert "not allowed" in result["error"].lower()


def test_env_all_safe():
    safe_keys = {"HOME", "USER", "USERNAME", "PATH", "SHELL", "LANG",
                 "PYTHONPATH", "NODE_ENV", "VIRTUAL_ENV", "PWD"}
    result = get_env()
    assert all(k in safe_keys for k in result)


# ═════════════════════════════════════════════════════════════════
#  File ops security
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
def ws_setup():
    tmpdir = tempfile.mkdtemp()
    file_ops._workspace = Workspace(tmpdir)
    file_ops._allow_write = False
    file_ops._allow_overwrite = False
    yield tmpdir
    file_ops._workspace = None
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_read_file_works(ws_setup):
    path = os.path.join(ws_setup, "hello.txt")
    with open(path, "w") as f:
        f.write("hello\nworld\nfoo\nbar")
    result = read_file("hello.txt")
    assert "content" in result
    assert "hello" in result["content"]


def test_read_file_not_found(ws_setup):
    result = read_file("nonexistent.txt")
    assert "error" in result


def test_read_file_escape(ws_setup):
    result = read_file("../outside.txt")
    assert "error" in result
    assert "escape" in result["error"].lower()


def test_write_file_blocked_by_default(ws_setup):
    result = write_file("new.txt", "data")
    assert "error" in result
    assert "not allowed" in result["error"].lower()


def test_write_file_allowed(ws_setup):
    file_ops._allow_write = True
    result = write_file("allowed.txt", "data")
    assert result.get("written") == 4


def test_write_file_overwrite_blocked(ws_setup):
    file_ops._allow_write = True
    write_file("dup.txt", "first")
    result = write_file("dup.txt", "second")
    assert "error" in result
    assert "Overwrite" in result["error"]


def test_write_file_overwrite_allowed(ws_setup):
    file_ops._allow_write = True
    file_ops._allow_overwrite = True
    result = write_file("final.txt", "content")
    assert result.get("written") == 7


def test_write_file_escape(ws_setup):
    file_ops._allow_write = True
    result = write_file("../outside.txt", "data")
    assert "error" in result
    assert "escape" in result["error"].lower()


def test_list_dir_works(ws_setup):
    path = os.path.join(ws_setup, "test.txt")
    with open(path, "w") as f:
        f.write("hello")
    result = list_dir(".")
    assert "entries" in result
    names = [e["name"] for e in result["entries"]]
    assert "test.txt" in names


def test_list_dir_escape(ws_setup):
    result = list_dir("../outside")
    assert "error" in result
    assert "escape" in result["error"].lower()


# ═════════════════════════════════════════════════════════════════
#  SSRF
# ═════════════════════════════════════════════════════════════════

def test_ssrf_localhost():
    assert _is_private("127.0.0.1")
    assert _is_private("::1")
    assert _is_private("localhost")


def test_ssrf_private_ip():
    assert _is_private("10.0.0.1")
    assert _is_private("192.168.1.1")
    assert _is_private("172.16.0.1")


def test_ssrf_public_ip():
    assert not _is_private("8.8.8.8")
    assert not _is_private("1.1.1.1")


def test_ssrf_localhost_extract():
    result = web_extract("http://127.0.0.1:8080/admin")
    assert "error" in result
    assert "SSRF" in result["error"]

    result = web_extract("http://localhost/secret")
    assert "error" in result
    assert "SSRF" in result["error"]


def test_ssrf_private_extract():
    result = web_extract("http://192.168.1.1/")
    assert "error" in result
    assert "SSRF" in result["error"]

    result = web_extract("http://10.0.0.1/api")
    assert "error" in result
    assert "SSRF" in result["error"]
