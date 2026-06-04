"""Web Search MCP Server — multi-engine search for AI agents."""

import ipaddress
import json
import re
import socket
import sys
from html.parser import HTMLParser
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


# ── SSRF Protection ─────────────────────────────────────────────

# RFC 1918 / RFC 6598 / loopback / link-local
_PRIVATE_RANGES = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("100.64.0.0/10"),    # CGNAT
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
]


def _is_private(host: str) -> bool:
    """Check if a hostname/IP resolves to a private/internal address."""
    # Check if literal IP
    try:
        ip = ipaddress.ip_address(host)
        return any(ip in net for net in _PRIVATE_RANGES)
    except ValueError:
        pass

    # Resolve hostname
    try:
        for addrinfo in socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            ip_str = addrinfo[4][0]
            ip = ipaddress.ip_address(ip_str)
            if any(ip in net for net in _PRIVATE_RANGES):
                return True
    except (socket.gaierror, socket.herror, OSError):
        pass

    return False


class SSRFError(Exception):
    """Raised when a URL resolves to an internal/private address."""
    pass


# ── Web Search ──────────────────────────────────────────────────

def web_search(query: str, limit: int = 5) -> dict:
    """Search the web using DuckDuckGo.

    Args:
        query: Search query string.
        limit: Maximum number of results.

    Returns:
        Dict with 'results' key containing search results.
    """
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
    """Extract text content from a URL.

    Blocks URLs that resolve to private/internal IPs (SSRF protection).

    Args:
        url: The URL to extract content from.

    Returns:
        Dict with extracted content.
    """
    try:
        # SSRF guard: check host before making request
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
    except SSRFError as e:
        return {"url": url, "error": str(e)}
    except Exception as e:
        return {"url": url, "error": str(e)}


# ── DuckDuckGo HTML Parser ──────────────────────────────────────

def _parse_ddg(html: str, limit: int) -> list:
    """Parse DuckDuckGo HTML results."""

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
    """Simple HTML to text conversion."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── MCP handler ─────────────────────────────────────────────────

def _handle_request(request: dict) -> dict:
    """Handle a JSON-RPC style MCP request."""
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "web_search",
                    "description": "Search the web using DuckDuckGo",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "description": "Max results", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "web_extract",
                    "description": "Extract text content from a public URL (SSRF-protected: blocks internal IPs)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to extract (public addresses only)"},
                        },
                        "required": ["url"],
                    },
                },
            ]
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name == "web_search":
            return {"content": [{"type": "text", "text": json.dumps(web_search(**tool_args), ensure_ascii=False)}]}
        elif tool_name == "web_extract":
            return {"content": [{"type": "text", "text": json.dumps(web_extract(**tool_args), ensure_ascii=False)}]}

    return {"error": f"Unknown method: {method}"}


# ── Server ──────────────────────────────────────────────────────

def serve():
    """Start MCP server over stdio."""
    sys.stderr.write("MCP Search Server starting...\n")
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
