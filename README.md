# 🔧 MCP Toolkit

> 开箱即用的 MCP (Model Context Protocol) 工具集 — 为 AI Agent 提供搜索、文件、Shell 能力
>
> Plug-and-play MCP tools for AI agents — Search, File Ops, Shell, and more.

[![PyPI](https://img.shields.io/pypi/v/mcp-toolkit?style=flat)](https://pypi.org/project/mcp-toolkit/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-toolkit?style=flat)](https://pypi.org/project/mcp-toolkit/)
[![Stars](https://img.shields.io/github/stars/studiopig/mcp-toolkit?style=social)](https://github.com/studiopig/mcp-toolkit)

---

## 🎯 为什么需要这个？

MCP 生态缺一套**开箱即用、中文友好**的工具集。`mcp-toolkit` 填补这个空白：

- 🚀 一行命令启动 MCP Server
- 🔍 内置 web_search、file_ops、shell_exec 等高频工具
- 🌏 中文搜索源优先（百度、知乎、B站等）
- ⚡ 轻量无依赖（核心仅需 Python 3.10+）

---

## 📦 安装

```bash
pip install mcp-toolkit
```

## 🚀 快速开始

### 1. Web Search Server

```bash
mcp-toolkit search
```

在 Claude Desktop / Cline / Continue 中配置：

```json
{
  "mcpServers": {
    "web-search": {
      "command": "mcp-toolkit",
      "args": ["search"]
    }
  }
}
```

Agent 可调用：
- `web_search(query)` — 多引擎搜索
- `web_extract(url)` — 提取网页内容

### 2. File Operations Server

```bash
mcp-toolkit file --workspace ./my-project
```

提供工具：
- `read_file(path)` — 读取文件
- `write_file(path, content)` — 写入文件
- `list_dir(path)` — 列出目录
- `search_files(pattern)` — 搜索文件

### 3. Shell Command Server

```bash
mcp-toolkit shell
```

提供工具：
- `run_command(cmd, timeout)` — 执行命令
- `get_env(key)` — 读取环境变量

### 4. 一键启动全部

```bash
mcp-toolkit all
```

---

## 🛠 内置工具

| 工具 | 描述 | 模块 |
|------|------|------|
| `web_search` | 多搜索引擎搜索 | search |
| `web_extract` | 提取网页 Markdown | search |
| `read_file` | 读取文件内容 | file |
| `write_file` | 写入文件 | file |
| `list_dir` | 列出目录结构 | file |
| `search_files` | 正则搜索文件 | file |
| `run_command` | 执行 Shell 命令 | shell |
| `get_env` | 读取环境变量 | shell |

---

## 🌏 搜索引擎支持

默认支持中文源优先：

| 引擎 | 类型 | 需要 Key |
|------|------|----------|
| 百度 | 中文通用 | ❌ |
| 知乎 | 中文问答 | ❌ |
| B站 | 视频/教程 | ❌ |
| Google | 国际通用 | 🔑 可选 |
| Bing | 国际通用 | 🔑 可选 |
| DuckDuckGo | 隐私搜索 | ❌ |

```python
from mcp_toolkit import SearchServer

server = SearchServer(engines=["baidu", "google"])
server.serve()
```

---

## 📁 项目结构

```
mcp-toolkit/
├── mcp_toolkit/
│   ├── __init__.py
│   ├── cli.py          # 命令行入口
│   ├── search.py       # Web Search MCP Server
│   ├── file_ops.py     # File Ops MCP Server
│   ├── shell.py        # Shell MCP Server
├── README.md
├── LICENSE
└── pyproject.toml
```

---

## 🤝 贡献

欢迎 PR！特别需要：
- 🌏 更多中文搜索源
- 🔌 新 MCP Server（数据库、API 等）
- 📚 更多 Agent 框架配置示例

---

## ⭐ Star History

有用的话给个 ⭐ ！

---

<p align="center">
  <i>Build agents, not boilerplate.</i>
</p>
