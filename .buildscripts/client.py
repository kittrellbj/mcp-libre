"""Shared thin HTTP client for driving the live MCP server while building
the book-layout templates (examples/templates/). Not part of the shipped
extension -- a build-time driver script only, mirrors the repo's own
root-level *-probe-windows.py http_post() idiom.
"""

import json
import urllib.request

HTTP_PORT = 8765

GAPS = []  # (title, detail) tuples -- real tool-surface limitations found live


def call(tool_name, **kwargs):
    """POST /tools/<tool_name> with kwargs as the JSON body. Raises
    RuntimeError with the full response on a non-success result so a
    build script fails loud at the first broken step rather than
    silently building a half-formed document."""
    data = json.dumps(kwargs).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{HTTP_PORT}/tools/{tool_name}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    if not result.get("success", False):
        raise RuntimeError(f"{tool_name}({kwargs}) failed: {json.dumps(result, indent=2)}")
    return result.get("result", result)


def call_soft(tool_name, **kwargs):
    """Like call(), but returns the raw response (success or not) instead
    of raising -- for probing whether something works without aborting
    the whole build."""
    data = json.dumps(kwargs).encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{HTTP_PORT}/tools/{tool_name}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def gap(title, detail):
    GAPS.append((title, detail))
    print(f"  [GAP] {title}: {detail}")


def step(msg):
    print(f"\n== {msg}")
