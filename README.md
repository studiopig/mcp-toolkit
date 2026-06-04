# MCP Toolkit

Plug-and-play MCP servers for AI agents - Search, File Ops, Shell.

## Install
```bash
pip install mcp-toolkit
```

## Quick Start
```bash
mcp-toolkit search
mcp-toolkit file
mcp-toolkit shell
mcp-toolkit all
```

## Features
- Web Search MCP Server (DuckDuckGo, extensible)
- File Operations MCP Server (read/write/list/search)
- Shell Command MCP Server (run commands, env vars)

## Configure in Claude Desktop
```json
{"mcpServers": {"web-search": {"command": "mcp-toolkit", "args": ["search"]}}}
```

## Star History
[![Stars](https://img.shields.io/github/stars/studiopig/mcp-toolkit?style=social)](https://github.com/studiopig/mcp-toolkit)
