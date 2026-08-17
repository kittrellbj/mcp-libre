"""
Phase A scaffold: Core runtime, discovery, and capability negotiation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Core runtime, discovery, and capability negotiation" (scope: always available).

Every function here is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. Signatures, docstrings, and registered schemas are the
scaffolded contract; a senior engineer replaces each body with real logic
(most of these read extension/session state rather than the document model,
so they likely belong on a new "ExtensionRuntime" collaborator rather than
UNOBridge directly -- see docs/MCP_TOOLING_SCAFFOLD_PLAN.md).
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="get_server_info_live",
    priority="P1",
    purpose="Return MCP extension/server version, LibreOffice version, Python version, OS, transport, session ID, and build metadata.",
)
def get_server_info_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_server_info_live", start)


@register_tool(
    name="get_capabilities_live",
    priority="P1",
    purpose="Return supported document types, enabled feature groups, optional UNO interfaces, export filters, and security gates.",
    parameters=schema({"document_id": {"type": "string", "description": "Optional document to scope capability results to."}}),
)
def get_capabilities_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_capabilities_live", start)


@register_tool(
    name="get_tool_schema_live",
    priority="P2",
    purpose="Return the full JSON schema and capability requirements for one tool.",
    parameters=schema({"tool_name": {"type": "string", "description": "Name of the tool to describe."}}, required=["tool_name"]),
)
def get_tool_schema_live(tool_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_tool_schema_live", start)


@register_tool(
    name="list_tools_live",
    priority="P1",
    purpose="Return currently exposed tools after document-type/profile filtering.",
    parameters=schema({
        "profile": {"type": "string", "enum": ["auto", "writer", "calc", "impress", "draw", "base", "math", "all", "advanced"]},
        "document_id": {"type": "string"},
    }),
)
def list_tools_live(profile: Optional[str] = None, document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_tools_live", start)


@register_tool(
    name="set_tool_profile_live",
    priority="P1",
    purpose="Select tool exposure profile to keep agent tool lists manageable.",
    parameters=schema({
        "profile": {"type": "string", "enum": ["auto", "writer", "calc", "impress", "draw", "base", "math", "all", "advanced"]},
    }, required=["profile"]),
)
def set_tool_profile_live(profile: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_tool_profile_live", start)


@register_tool(
    name="get_session_state_live",
    priority="P1",
    purpose="Return active document, open document handles, selected object/range, current profile, and pending undo context.",
)
def get_session_state_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_session_state_live", start)


@register_tool(
    name="ping_live",
    priority="P1",
    purpose="Lightweight end-to-end MCP handler ping distinct from HTTP /health.",
    parameters=schema({"echo": {"type": "string", "description": "Optional value echoed back in the result."}}),
)
def ping_live(echo: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("ping_live", start)


@register_tool(
    name="batch_execute_live",
    priority="P1",
    purpose="Execute multiple MCP operations in order, optionally as one undo context.",
    parameters=schema({
        "operations": {"type": "array", "items": {"type": "object"}, "description": "Ordered list of {tool_name, parameters} operations."},
        "stop_on_error": {"type": "boolean", "default": True},
        "undo_label": {"type": "string"},
    }, required=["operations"]),
)
def batch_execute_live(operations: List[Dict[str, Any]], stop_on_error: bool = True,
                        undo_label: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("batch_execute_live", start)


@register_tool(
    name="validate_tool_call_live",
    priority="P2",
    purpose="Validate parameters/capability without mutating the document.",
    parameters=schema({
        "tool_name": {"type": "string"},
        "parameters": {"type": "object"},
    }, required=["tool_name", "parameters"]),
)
def validate_tool_call_live(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("validate_tool_call_live", start)


@register_tool(
    name="get_recent_errors_live",
    priority="P2",
    purpose="Return structured recent extension/tool errors for diagnostics.",
    parameters=schema({
        "limit": {"type": "integer", "default": 50},
        "since": {"type": "string", "description": "ISO-8601 timestamp; only errors after this point."},
    }),
)
def get_recent_errors_live(limit: int = 50, since: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_recent_errors_live", start)


@register_tool(
    name="get_diagnostics_live",
    priority="P2",
    purpose="Return thread/server state, UNO context status, loaded extension path, port binding, and timing counters.",
    parameters=schema({"include_environment": {"type": "boolean", "default": False}}),
)
def get_diagnostics_live(include_environment: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_diagnostics_live", start)


@register_tool(
    name="clear_diagnostics_live",
    priority="P3",
    purpose="Clear in-memory diagnostic/error history.",
)
def clear_diagnostics_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_diagnostics_live", start)
