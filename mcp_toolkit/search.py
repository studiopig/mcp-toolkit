"""Web Search MCP Server — DuckDuckGo search with SSRF protection."""

import asyncio
import ipaddress
import json
import re
import socket
import sys
from html.parser import HTMLParser
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


# ── SSRF Protection ─────────────────────────────────────────────

_PRIVATE_RANGES = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("100.64.0.0/10"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
]


def _is_private(host: str) -> bool:
    """Check if a hostname/IP resolves to a private/internal address."""
    try:
        ip = ipaddress.ip_address(host)
        return any(ip in net for net in _PRIVATE_RANGES)
    except ValueError:
        pass
    try:
        for addrinfo in socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            ip_str = addrinfo[4][0]
            ip = ipaddress.ip_address(ip_str)
            if any(ip in net for net in _PRIVATE_RANGES):
                return True
    except (socket.gaierror, socket.herror, OSError):
        pass
    return False


# ── Web Search ──────────────────────────────────────────────────

def web_search(query: str, limit: int = 5) -> dict:
    """Search the web using DuckDuckGo."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=10)
        html = resp.read().decode()
        results = _parse_ddg(html, limit)
        return {"results": results, "engine": "duckduckgo"}
    except Exception as e:
        return {"results": [], "error": str(e), "engine": "duckduckgo"}


def web_extract(url: str) -> dict:
    """Extract text content from a URL (SSRF-protected)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return {"url": url, "error": "Invalid URL: no hostname"}
        if _is_private(host):
            return {"url": url, "error": "SSRF blocked: internal/private IP"}
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=15)
        html = resp.read().decode(errors="ignore")
        text = _html_to_text(html)
        return {"url": url, "content": text[:5000], "length": len(text)}
    except Exception as e:
        return {"url": url, "error": str(e)}


# ── DuckDuckGo HTML Parser ──────────────────────────────────────

def _parse_ddg(html: str, limit: int) -> list:
    class DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_link = False
            self.in_snippet = False
            self.current = {}
            self.results = []

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                self.in_link = True
                self.current["url"] = attrs_dict.get("href", "")
            if tag == "a" and "result__snippet" in attrs_dict.get("class", ""):
                self.in_snippet = True

        def handle_data(self, data):
            if self.in_link and "title" not in self.current:
                self.current["title"] = data.strip()
            if self.in_snippet and "snippet" not in self.current:
                self.current["snippet"] = data.strip()

        def handle_endtag(self, tag):
            if tag == "a" and self.in_link:
                self.in_link = False
                if self.current.get("title"):
                    self.results.append(dict(self.current))
                    self.current = {}
            if tag == "a" and self.in_snippet:
                self.in_snippet = False

    parser = DDGParser()
    parser.feed(html)
    return parser.results[:limit]


# ── HTML to text ────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── MCP Server ──────────────────────────────────────────────────

server = Server("mcp-toolkit-search")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search the web using DuckDuckGo",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="web_extract",
            description="Extract text content from a public URL (SSRF-protected: blocks internal IPs)",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to extract (public addresses only)"},
                },
                "required": ["url"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "web_search":
        result = web_search(**arguments)
    elif name == "web_extract":
        result = web_extract(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def serve_async():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def serve():
    """Start MCP Search Server over stdio."""
    sys.stderr.write("MCP Search Server starting (mcp SDK)...\n")
    sys.stderr.flush()
    asyncio.run(serve_async())


if __name__ == "__main__":
    serve()
