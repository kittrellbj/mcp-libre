"""
Real MCP JSON-RPC 2.0 dispatch (mandated item #4 of Buddy's four-item
order: "Real MCP transport should run in parallel now... there is no
architectural reason to postpone it until the tool catalog is
complete.").

Before this module, `ai_interface.py`'s MCPRequestHandler only served a
bespoke REST shim (GET /, GET /tools, GET /health, POST /execute,
POST /tools/{tool_name}) -- zero occurrences of "initialize"/"tools/list"/
"tools/call"/"jsonrpc" anywhere in the codebase, confirmed by grep before
this pass. This module is the actual JSON-RPC 2.0 message-level dispatch
(request parsing, method routing, response/error shaping); the HTTP
transport concerns (the /mcp route, Content-Type/Accept negotiation,
Mcp-Session-Id/Mcp-Protocol-Version headers, status codes) live in
ai_interface.py, which calls into this module -- kept separate so this
module is unit-testable with a fake tool registry/executor, no HTTP or
UNO involved (see tests/test_mcp_jsonrpc.py).

Read-only architectural reference for this pass: WriterAgent's /mcp
implementation (E:\\Tools\\writeragent, GPLv3+; no code copied -- see
docs/DOCUMENT_TARGETING_DECISION.md's licensing note for the same
constraint applied to this research). What's reused here is standard
MCP/JSON-RPC 2.0 wire format (method names, reserved error codes,
notification-gets-no-response semantics) -- protocol vocabulary, not
WriterAgent's implementation.

Scope of this pass, deliberately: `initialize`, `notifications/initialized`,
`ping`, `tools/list`, `tools/call`, `resources/list` (always empty --
this server exposes no MCP resources), `prompts/list` (always empty --
no MCP prompts). JSON-RPC 2.0 batch arrays are supported (each entry
dispatched independently; notifications get no response entry, matching
spec). Left for a later pass: resources/prompts becoming non-empty if
this project ever wants to expose documents as MCP resources;
`Mcp-Protocol-Version` negotiation is permissive (this server always
echoes back whatever version the client requested in `initialize` rather
than validating against a fixed supported-version list) -- reasonable
for a first real-transport pass with one server version to support, but
a future pass adding real version negotiation should tighten this.
"""

import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

JSONRPC_VERSION = "2.0"

# Reserved JSON-RPC 2.0 error code range, per the spec.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

SERVER_INFO = {"name": "LibreOffice MCP Extension", "version": "1.0.0"}


def build_result(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def build_error(request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}


def tool_entry_to_mcp_schema(name: str, tool_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert this project's internal tool registry shape ({name,
    description, parameters}, see mcp_server.py's get_tool_list()) to
    MCP's tools/list shape ({name, description, inputSchema})."""
    return {
        "name": name,
        "description": tool_entry.get("description", ""),
        "inputSchema": tool_entry.get("parameters") or {"type": "object", "properties": {}},
    }


def _handle_initialize(msg: Dict[str, Any]) -> Dict[str, Any]:
    params = msg.get("params") or {}
    # Permissive version handling -- see module docstring's scope note.
    client_protocol_version = params.get("protocolVersion") or "2025-06-18"
    result = {
        "protocolVersion": client_protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": SERVER_INFO,
        "instructions": (
            "LibreOffice MCP Extension: semantic tools for controlling a "
            "running LibreOffice instance (Writer/Calc/Impress/Draw). "
            "Call tools/list for the current catalog; most tools operate "
            "on the active document unless a document_id parameter is "
            "present."
        ),
    }
    return build_result(msg.get("id"), result)


def _handle_tools_list(msg: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
    tool_list = [tool_entry_to_mcp_schema(name, entry) for name, entry in tools.items()]
    return build_result(msg.get("id"), {"tools": tool_list})


def _handle_tools_call(
    msg: Dict[str, Any],
    execute_tool: Callable[[str, Dict[str, Any]], Any],
) -> Dict[str, Any]:
    params = msg.get("params") or {}
    name = params.get("name")
    if not name:
        return build_error(msg.get("id"), INVALID_PARAMS, "Missing required param 'name'")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return build_error(msg.get("id"), INVALID_PARAMS, "'arguments' must be an object")

    try:
        tool_result = execute_tool(name, arguments)
    except TypeError as e:
        # Wrong/missing arguments for the handler's signature -- an MCP
        # client sending a malformed tools/call, not a server fault.
        return build_error(msg.get("id"), INVALID_PARAMS, str(e))
    except Exception as e:
        return build_error(msg.get("id"), INTERNAL_ERROR, str(e))

    # Per MCP convention: a tool-level failure (this project's envelope
    # sets success: False) is still a successful JSON-RPC response --
    # isError on the tools/call result, not a JSON-RPC error object. Only
    # protocol-level faults (bad method, bad params shape, an exception
    # escaping the handler itself) are JSON-RPC errors, handled above and
    # in dispatch_one()'s method-not-found branch. This mirrors the
    # two-layer error model documented in
    # docs/DOCUMENT_TARGETING_DECISION.md's transport research.
    is_error = isinstance(tool_result, dict) and tool_result.get("success") is False
    content = [{"type": "text", "text": json.dumps(tool_result, default=str)}]
    return build_result(msg.get("id"), {"content": content, "isError": is_error})


def dispatch_one(
    msg: Any,
    tools: Dict[str, Any],
    execute_tool: Callable[[str, Dict[str, Any]], Any],
) -> Optional[Dict[str, Any]]:
    """Dispatch a single parsed JSON-RPC message. Returns None for a
    notification (no "id" field) or an unroutable non-request -- per
    spec, notifications never get a reply."""
    if not isinstance(msg, dict):
        return build_error(None, INVALID_REQUEST, "Invalid Request: expected a JSON object")

    if msg.get("jsonrpc") != JSONRPC_VERSION:
        return build_error(msg.get("id"), INVALID_REQUEST, "Invalid Request: jsonrpc must be \"2.0\"")

    method = msg.get("method")
    if not isinstance(method, str) or not method:
        return build_error(msg.get("id"), INVALID_REQUEST, "Invalid Request: missing 'method'")

    is_notification = "id" not in msg

    if method == "initialize":
        return _handle_initialize(msg)
    if method == "notifications/initialized":
        return None  # Ack notification, no response by design.
    if method == "ping":
        return build_result(msg.get("id"), {})
    if method == "tools/list":
        return _handle_tools_list(msg, tools)
    if method == "tools/call":
        return _handle_tools_call(msg, execute_tool)
    if method == "resources/list":
        return build_result(msg.get("id"), {"resources": []})
    if method == "prompts/list":
        return build_result(msg.get("id"), {"prompts": []})

    if is_notification:
        # Per spec: an unrecognized notification is simply dropped, not
        # answered with an error (there is no "id" to error against).
        return None
    return build_error(msg.get("id"), METHOD_NOT_FOUND, f"Method not found: {method}")


def dispatch(
    body: Union[Dict[str, Any], List[Any]],
    tools: Dict[str, Any],
    execute_tool: Callable[[str, Dict[str, Any]], Any],
) -> Tuple[Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], int]:
    """Dispatch a parsed JSON-RPC POST body (single message or a batch
    array) and return (response_body_or_None, http_status).

    response_body_or_None is None exactly when the caller should send
    "202 Accepted" with an empty body (the request was entirely
    notifications, or an empty batch per spec's "SHOULD NOT respond
    with an empty array" -- an empty batch is treated as a protocol
    error instead, see below).
    """
    if isinstance(body, list):
        if not body:
            return build_error(None, INVALID_REQUEST, "Invalid Request: empty batch"), 400
        responses = [r for r in (dispatch_one(m, tools, execute_tool) for m in body) if r is not None]
        if not responses:
            return None, 202
        return responses, 200

    response = dispatch_one(body, tools, execute_tool)
    if response is None:
        return None, 202
    return response, 200
