"""Web Search MCP Server — multi-engine search for AI agents."""

import json
import sys
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import quote


def web_search(query: str, limit: int = 5) -> dict:
    """Search the web using configured engines.

    Args:
        query: Search query string.
        limit: Maximum number of results.

    Returns:
        Dict with 'results' key containing search results.
    """
    # DuckDuckGo HTML search (no API key needed)
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

    Args:
        url: The URL to extract content from.

    Returns:
        Dict with extracted content.
    """
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=15)
        html = resp.read().decode(errors="ignore")
        text = _html_to_text(html)
        return {"url": url, "content": text[:5000], "length": len(text)}
    except Exception as e:
        return {"url": url, "error": str(e)}


def _parse_ddg(html: str, limit: int) -> list:
    """Parse DuckDuckGo HTML results."""
    results = []
    from html.parser import HTMLParser

    class DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_result = False
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


def _html_to_text(html: str) -> str:
    """Simple HTML to text conversion."""
    import re
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _handle_request(request: dict) -> dict:
    """Handle a JSON-RPC style MCP request."""
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "web_search",
                    "description": "Search the web using multiple search engines",
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
                    "description": "Extract text content from a web page URL",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to extract"},
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


def serve():
    """Start MCP server over stdio."""
    print("MCP Search Server starting...", file=sys.stderr)
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = _handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    serve()
