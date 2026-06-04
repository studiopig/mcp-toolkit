# 🔧 MCP Toolkit

> 开箱即用的 MCP (Model Context Protocol) 工具集 — 为 AI Agent 提供搜索、文件、Shell 能力
>
> Plug-and-play MCP tools for AI agents — Web Search, File Ops, Shell, and more.

[![PyPI](https://img.shields.io/pypi/v/mcp-toolkit?style=flat)](https://pypi.org/project/mcp-toolkit/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-toolkit?style=flat)](https://pypi.org/project/mcp-toolkit/)
[![Stars](https://img.shields.io/github/stars/studiopig/mcp-toolkit?style=social)](https://github.com/studiopig/mcp-toolkit)

---

## 🎯 为什么需要这个？

MCP 生态缺一套**安全可控、开箱即用**的工具集。`mcp-toolkit` 填补这个空白：

- 🚀 一行命令启动 MCP Server
- 🔍 内置 web_search、file_ops、shell 等高频工具
- 🔒 安全优先：默认只读、workspace 沙箱、命令白名单
- ⚡ 轻量依赖（核心仅需 Python 3.10+ + mcp 库）

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
- `web_search(query)` — DuckDuckGo 搜索
- `web_extract(url)` — 提取网页内容（含 SSRF 防护）

### 2. File Operations Server

```bash
mcp-toolkit file --workspace ./my-project
```

提供工具：
- `read_file(path)` — 读取文件
- `write_file(path, content)` — 写入文件（需 `--allow-write`）
- `list_dir(path)` — 列出目录
- `search_files(pattern)` — 子串搜索文件内容

### 3. Shell Command Server

```bash
mcp-toolkit shell
```

提供工具：
- `run_command(cmd, timeout)` — 执行命令（白名单控制）
- `get_env(key)` — 读取环境变量（白名单控制）

### 4. 一键启动全部

```bash
mcp-toolkit all
```

---

## 🛠 内置工具

| 工具 | 描述 | 模块 |
|------|------|------|
| `web_search` | DuckDuckGo 搜索 | search |
| `web_extract` | 提取网页文本（含 SSRF 防护） | search |
| `read_file` | 读取文件内容 | file |
| `write_file` | 写入文件（需 `--allow-write`） | file |
| `list_dir` | 列出目录结构 | file |
| `search_files` | 子串搜索文件内容 | file |
| `run_command` | 执行 Shell 命令（白名单） | shell |
| `get_env` | 读取环境变量（白名单） | shell |

---

## 🔒 Security

**mcp-toolkit exposes real system access to AI agents.** 安全设计：

### 🔐 权限矩阵

| 能力 | 默认状态 | 开启方式 | 风险等级 |
|------|:--:|------|:--:|
| 文件读取 | ✅ 开启 | 无需额外参数 | 🟢 低 |
| 目录列表 | ✅ 开启 | 无需额外参数 | 🟢 低 |
| 文件写入 | ❌ 关闭 | `--allow-write` | 🟡 中 |
| 文件覆盖 | ❌ 关闭 | `--allow-overwrite` | 🟡 中 |
| Shell 执行 | ❌ 关闭 | 白名单 only | 🔴 高 |
| 网页搜索 | ✅ 开启 | 无需额外参数 | 🟢 低 |
| 网页内容提取 | ✅ 开启 | 无需额外参数 | 🟡 中 |
| 环境变量读取 | ✅ 白名单 | — | 🟡 中 |
| 路径沙箱 | ✅ 强制 | — | 🛡️ 保护 |
| SSRF 防护 | ✅ 内网 IP 拦截 | — | 🛡️ 保护 |
| 大文件限制 | ✅ 10MB | — | 🛡️ 保护 |

### ⚡ 危险组合

以下组合在特定场景下风险较高：

| 组合 | 风险 | 建议 |
|------|------|------|
| `--allow-write` + Shell | Agent 可写入脚本后执行 | 只在隔离环境中同时开启 |
| `web_extract` + `--allow-write` | 网页内容可注入本地文件 | 限制写入目录不在 PATH 中 |
| Shell 白名单含 `python/node` | 等价于给 Agent 本地执行能力 | 仅在完全可信的 workspace 中使用 |
| workspace 指向 `$HOME` 或 `/` | Agent 可操作所有个人文件 | 始终指向独立项目目录 |
| `all` 模式 | 开启所有能力 | 不推荐新手使用，仅限完全隔离环境 |

### 🚀 推荐使用方式

```bash
# 最安全：只开文件读取 + 搜索
mcp-toolkit search          # 搜索 server
mcp-toolkit file --workspace ./project   # 只读文件 server

# 需要写文件时
mcp-toolkit file --workspace ./project --allow-write

# 需要 Shell 时（谨慎）
mcp-toolkit file --workspace ./project --allow-write --allow-shell

# ⚠️ 不推荐新手
mcp-toolkit all  # 所有能力全开，仅限沙箱环境
```

**Never expose write or shell tools to untrusted prompts.** 所有文件操作限定在 `--workspace` 内，路径逃逸被拦截。

---

## 📁 项目结构

```
mcp-toolkit/
├── mcp_toolkit/
│   ├── __init__.py
│   ├── cli.py          # 命令行入口
│   ├── search.py       # Web Search MCP Server + SSRF guard
│   ├── file_ops.py     # File Ops MCP Server + workspace sandbox
│   ├── shell.py        # Shell MCP Server + allowlist
│   └── workspace.py    # Path sandbox implementation
├── tests/
│   └── test_toolkit.py
├── README.md
├── LICENSE
└── pyproject.toml
```

---

## 🤝 贡献

欢迎 PR！特别需要：
- 🌏 更多搜索引擎后端（Baidu、Bing 等）
- 🔌 新 MCP Server（数据库、API 等）
- 📚 更多 Agent 框架配置示例

---

<p align="center">
  <i>Build agents, not boilerplate.</i>
</p>
