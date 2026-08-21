"""
Core runtime, discovery, and capability negotiation -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Core runtime, discovery, and capability negotiation" (scope: always available).

Unlike every other module in this package, these 12 tools are registered
with status="implemented" (see registry.register_tool) and carry real
logic backed by tools.context.get_context() -- the live UNOBridge,
DocumentRegistry, RuntimeState, and tool registry mcp_server.py installs
at startup (tools.context.install(...)). They are merged into
LibreOfficeMCPServer.tools unconditionally, like the original 32, not
gated behind MCP_LIBRE_ENABLE_SCAFFOLD_STUBS.

Known scope limits (documented rather than hidden):
  - list_tools_live's profile filtering is derived from which module a
    tool's handler was defined in (handler.__module__), not per-tool
    metadata -- accurate at module granularity, so a module that mixes
    tools for different document types (e.g. drawing_objects.py, shared
    across Writer/Calc/Impress/Draw) is tagged with the union, not
    filtered tool-by-tool within that module.
  - validate_tool_call_live implements a minimal subset of JSON Schema
    (required-field presence, declared `type`, `enum` membership) -- see
    _validate_against_schema. Sufficient for the flat schemas
    registry.schema() produces across this package; not a general-purpose
    validator.
  - batch_execute_live's `undo_label`, when supplied, wraps the operations
    in a real named undo context via tools.undo_view_selection's
    begin_undo_context_live/end_undo_context_live (see that call below) --
    the batch is always committed as one coalesced Undo step, whether or
    not stop_on_error stopped it early; it is never rolled back
    automatically (see the comment at the call site for the reasoning).
"""

import os
import sys
import platform
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from . import context
from . import documents
from . import envelope
from . import runtime_state as runtime_state_module
from . import undo_view_selection
from .registry import register_tool, schema

# Kept in sync manually with plugin/description.xml's <version value="..."/>.
EXTENSION_VERSION = "2.0.9"

# registration.py hardcodes ai_interface.start_ai_interface(port=8765, ...)
# with no configuration path that changes it -- safe to report as a constant.
DEFAULT_HTTP_PORT = 8765


# -- list_tools_live profile derivation ------------------------------------

# The 5 cross-document-type tools from the original 32 (create/open any
# type, or act on whichever document is active/relevant).
_LEGACY_ALWAYS_TOOLS = frozenset({
    "list_open_documents", "create_document_live", "get_document_info_live",
    "save_document_live", "export_document_live",
})

# The remaining 27 original tools: paragraph navigation, text selection,
# search/replace, comments, track changes -- all Writer-specific.
_LEGACY_WRITER_TOOLS = frozenset({
    "insert_text_live", "get_text_content_live", "format_text_live",
    "get_paragraph_count_live", "get_document_outline_live", "get_paragraph_live",
    "get_paragraphs_range_live", "goto_paragraph_live", "goto_position_live",
    "get_cursor_position_live", "get_context_around_cursor_live", "select_paragraph_live",
    "select_text_range_live", "delete_selection_live", "replace_selection_live",
    "find_text_live", "find_and_replace_live", "find_and_replace_all_live",
    "get_comments_live", "add_comment_live", "get_track_changes_status_live",
    "set_track_changes_live", "get_tracked_changes_live", "accept_tracked_change_live",
    "reject_tracked_change_live", "accept_all_changes_live", "reject_all_changes_live",
})

LEGACY_TOOL_PROFILES: Dict[str, frozenset] = {
    **{name: frozenset({"always"}) for name in _LEGACY_ALWAYS_TOOLS},
    **{name: frozenset({"writer"}) for name in _LEGACY_WRITER_TOOLS},
}

# tools/*.py module name -> the profile(s) its tools apply to. "always"
# means exposed regardless of active document type.
MODULE_PROFILES: Dict[str, frozenset] = {
    "tools.core_runtime": frozenset({"always"}),
    "tools.document_lifecycle": frozenset({"always"}),
    "tools.undo_view_selection": frozenset({"always"}),
    "tools.styles": frozenset({"writer", "calc", "impress", "draw"}),
    "tools.writer_text": frozenset({"writer"}),
    "tools.writer_layout": frozenset({"writer"}),
    "tools.writer_tables": frozenset({"writer"}),
    "tools.drawing_objects": frozenset({"writer", "calc", "impress", "draw"}),
    "tools.charts": frozenset({"writer", "calc", "impress", "draw"}),
    "tools.calc_sheets": frozenset({"calc"}),
    "tools.calc_data": frozenset({"calc"}),
    "tools.calc_page": frozenset({"calc"}),
    "tools.impress": frozenset({"impress"}),
    "tools.draw": frozenset({"draw"}),
}


def _tool_profiles(tool_name: str, handler: Callable) -> frozenset:
    """Best-effort profile-applicability tags for a registered tool.

    See MODULE_PROFILES/LEGACY_TOOL_PROFILES and the module docstring's
    scope-limits note. A tool this mapping doesn't recognize (e.g. a
    future module added without updating MODULE_PROFILES) defaults to
    "always" rather than being silently hidden from every profile.
    """
    if tool_name in LEGACY_TOOL_PROFILES:
        return LEGACY_TOOL_PROFILES[tool_name]
    module_name = getattr(handler, "__module__", "")
    return MODULE_PROFILES.get(module_name, frozenset({"always"}))


# -- validate_tool_call_live's minimal JSON Schema subset -------------------

_JSON_SCHEMA_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def _validate_against_schema(parameters: Dict[str, Any], tool_schema: Dict[str, Any]) -> List[str]:
    """Minimal JSON Schema validation: required-field presence, declared
    `type`, and `enum` membership for each supplied property. See the
    module docstring's scope-limits note for what this does not cover.
    """
    errors = []
    properties = tool_schema.get("properties", {}) if isinstance(tool_schema, dict) else {}
    required = tool_schema.get("required", []) if isinstance(tool_schema, dict) else []

    for name in required:
        if name not in parameters:
            errors.append(f"missing required parameter '{name}'")

    for name, value in parameters.items():
        prop_schema = properties.get(name)
        if prop_schema is None:
            continue  # unknown parameter -- permissive, not flagged as an error
        expected_type = prop_schema.get("type")
        check = _JSON_SCHEMA_TYPE_CHECKS.get(expected_type)
        if check and not check(value):
            errors.append(f"parameter '{name}' expected type '{expected_type}', got {type(value).__name__}")
        enum_values = prop_schema.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"parameter '{name}' must be one of {enum_values}, got {value!r}")

    return errors


# -- tools -------------------------------------------------------------------


@register_tool(
    name="ping_live",
    priority="P1",
    purpose="Lightweight end-to-end MCP handler ping distinct from HTTP /health.",
    parameters=schema({"echo": {"type": "string", "description": "Optional value echoed back in the result."}}),
    status="implemented",
)
def ping_live(echo: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    result = {"pong": True, "echo": echo, "session_id": ctx.runtime_state.session_id}
    return envelope.build_success(result=result, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="get_server_info_live",
    priority="P1",
    purpose="Return MCP extension/server version, LibreOffice version, Python version, OS, transport, session ID, and build metadata.",
    status="implemented",
)
def get_server_info_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    version_info = ctx.uno_bridge.get_application_version()
    warnings = []
    if not version_info.get("success"):
        warnings.append("Could not read LibreOffice application version via UNO configuration.")

    result = {
        "extension_name": "LibreOffice MCP Extension",
        "extension_version": EXTENSION_VERSION,
        "libreoffice_name": version_info.get("name") if version_info.get("success") else "unknown",
        "libreoffice_version": version_info.get("version") if version_info.get("success") else "unknown",
        "python_version": sys.version,
        "os": platform.platform(),
        "transport": "http",
        "http_port": DEFAULT_HTTP_PORT,
        "session_id": ctx.runtime_state.session_id,
        "uptime_seconds": round(ctx.runtime_state.uptime_seconds, 1),
    }
    return envelope.build_success(result=result, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="get_capabilities_live",
    priority="P1",
    purpose="Return supported document types, enabled feature groups, optional UNO interfaces, export filters, and security gates.",
    parameters=schema({"document_id": {"type": "string", "description": "Optional document to scope capability results to."}}),
    status="implemented",
)
def get_capabilities_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()

    active_document_type = None
    resolved_document_id = None
    try:
        doc = ctx.document_registry.resolve_document(document_id)
        info = ctx.uno_bridge.get_document_info(doc)
        active_document_type = info.get("type")
        resolved_document_id = document_id
    except documents.NoActiveDocumentError:
        pass  # document_id omitted and nothing active -- capabilities are still reportable
    except documents.DocumentNotFoundError:
        return envelope.build_error(
            "OBJECT_NOT_FOUND", f"No document registered under document_id '{document_id}'",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )

    result = dict(ctx.uno_bridge.get_capabilities())
    result["active_document_type"] = active_document_type
    result["security_gates"] = {
        "macro_execution": False,
        "raw_uno_dispatch": False,
        "remote_access": False,
        "trusted_localhost_only": True,
    }
    return envelope.build_success(result=result, document_id=resolved_document_id, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="get_tool_schema_live",
    priority="P2",
    purpose="Return the full JSON schema and capability requirements for one tool.",
    parameters=schema({"tool_name": {"type": "string", "description": "Name of the tool to describe."}}, required=["tool_name"]),
    status="implemented",
)
def get_tool_schema_live(tool_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    tools_dict = ctx.get_tools()

    if tool_name not in tools_dict:
        return envelope.build_error(
            "OBJECT_NOT_FOUND", f"No tool named '{tool_name}' is registered.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )

    metadata = tools_dict[tool_name]
    result = {
        "tool_name": tool_name,
        "description": metadata.get("description"),
        "parameters": metadata.get("parameters"),
    }
    return envelope.build_success(result=result, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="list_tools_live",
    priority="P1",
    purpose="Return currently exposed tools after document-type/profile filtering.",
    parameters=schema({
        "profile": {"type": "string", "enum": sorted(runtime_state_module.VALID_PROFILES)},
        "document_id": {"type": "string"},
    }),
    status="implemented",
)
def list_tools_live(profile: Optional[str] = None, document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    active_profile = profile if profile is not None else ctx.runtime_state.get_profile()

    if active_profile not in runtime_state_module.VALID_PROFILES:
        return envelope.build_error(
            "INVALID_PARAMETER",
            f"Unknown profile '{active_profile}', expected one of {sorted(runtime_state_module.VALID_PROFILES)}",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )

    tools_dict = ctx.get_tools()

    if active_profile in ("all", "advanced"):
        # "advanced" == "all" for now: no tool in this catalog is yet gated
        # behind the security/advanced-feature policy the spec describes
        # (section 3/7) since Phase F's escape-hatch tools aren't built.
        selected = list(tools_dict.keys())
    else:
        wanted = {"always"}
        if active_profile == "auto":
            doc = None
            try:
                doc = ctx.document_registry.resolve_document(document_id)
            except documents.NoActiveDocumentError:
                doc = None
            except documents.DocumentNotFoundError:
                return envelope.build_error(
                    "OBJECT_NOT_FOUND", f"No document registered under document_id '{document_id}'",
                    elapsed_ms=envelope.elapsed_ms_since(start),
                )
            if doc is not None:
                info = ctx.uno_bridge.get_document_info(doc)
                if info.get("type"):
                    wanted.add(info["type"])
        else:
            wanted.add(active_profile)
        selected = [name for name, meta in tools_dict.items() if _tool_profiles(name, meta["handler"]) & wanted]

    result = {"profile": active_profile, "tools": sorted(selected), "count": len(selected)}
    return envelope.build_success(result=result, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="set_tool_profile_live",
    priority="P1",
    purpose="Select tool exposure profile to keep agent tool lists manageable.",
    parameters=schema({
        "profile": {"type": "string", "enum": sorted(runtime_state_module.VALID_PROFILES)},
    }, required=["profile"]),
    status="implemented",
)
def set_tool_profile_live(profile: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        ctx.runtime_state.set_profile(profile)
    except ValueError as e:
        return envelope.build_error("INVALID_PARAMETER", str(e), elapsed_ms=envelope.elapsed_ms_since(start))
    return envelope.build_success(result={"profile": profile}, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="get_session_state_live",
    priority="P1",
    purpose="Return active document, open document handles, selected object/range, current profile, and pending undo context.",
    status="implemented",
)
def get_session_state_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    warnings = []

    active_document = None
    try:
        active_doc = ctx.uno_bridge.get_active_document()
        if active_doc is not None:
            active_document = ctx.uno_bridge.get_document_info(active_doc)
    except Exception as e:
        warnings.append(f"Could not read active document info: {e}")

    open_documents = []
    try:
        frames = ctx.uno_bridge.desktop.getFrames()
        for i in range(frames.getCount()):
            frame = frames.getByIndex(i)
            controller = frame.getController()
            doc = controller.getModel() if controller else None
            if doc:
                open_documents.append(ctx.uno_bridge.get_document_info(doc))
    except Exception as e:
        warnings.append(f"Could not enumerate open documents: {e}")

    result = {
        "active_document": active_document,
        "open_documents": open_documents,
        "registered_document_handles": ctx.document_registry.list_documents(),
        "current_profile": ctx.runtime_state.get_profile(),
        "pending_undo_context": ctx.runtime_state.get_undo_context(),
        "session_id": ctx.runtime_state.session_id,
        "uptime_seconds": round(ctx.runtime_state.uptime_seconds, 1),
    }
    return envelope.build_success(result=result, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="batch_execute_live",
    priority="P1",
    purpose=(
        "Execute multiple MCP operations in order, optionally as one undo context. "
        "BUG #15, deliberately not fixed this pass, flagged for an architecture "
        "decision rather than a band-aid: each op runs synchronously in-process, "
        "holding the same process-wide UNO execution lock every tool call already "
        "shares, so there is no per-op timeout -- a single hung op (a wedged UNO "
        "round-trip) blocks the whole batch and the HTTP response indefinitely, "
        "with no partial results visible until it returns. A real fix needs "
        "either subprocess-level isolation per op or a cooperative cancellation "
        "token threaded through uno_bridge -- a thread-based fake timeout would "
        "abandon a zombie thread that keeps holding the process-wide lock, "
        "blocking every future tool call, not just this batch. Keep operations "
        "short and known-safe; avoid batching anything that could genuinely hang."
    ),
    parameters=schema({
        "operations": {"type": "array", "items": {"type": "object"}, "description": "Ordered list of {tool_name, parameters} operations."},
        "stop_on_error": {"type": "boolean", "default": True},
        "undo_label": {"type": "string"},
    }, required=["operations"]),
    status="implemented",
)
def batch_execute_live(operations: List[Dict[str, Any]], stop_on_error: bool = True,
                        undo_label: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()

    if not isinstance(operations, list) or not operations:
        return envelope.build_error(
            "INVALID_PARAMETER", "operations must be a non-empty list.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )

    tools_dict = ctx.get_tools()
    warnings = []
    undo_context_open = False
    if undo_label:
        begin_result = undo_view_selection.begin_undo_context_live(title=undo_label)
        if not begin_result.get("success"):
            # Fail the whole batch rather than silently running ungrouped --
            # e.g. a context from a previous call was never closed. The
            # caller asked for one undo step; if that can't be set up, no
            # operations should run under a false promise of grouping.
            return envelope.build_error(
                begin_result["error"]["code"],
                f"Could not start undo context for batch_execute_live: {begin_result['error']['message']}",
                elapsed_ms=envelope.elapsed_ms_since(start),
            )
        undo_context_open = True

    results = []
    try:
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict) or "tool_name" not in operation:
                results.append({
                    "index": index, "success": False,
                    "error": {"code": "INVALID_PARAMETER", "message": "Each operation must be an object with a 'tool_name' key."},
                })
                if stop_on_error:
                    break
                continue

            tool_name = operation["tool_name"]
            parameters = operation.get("parameters", {})

            if tool_name not in tools_dict:
                results.append({
                    "index": index, "tool_name": tool_name, "success": False,
                    "error": {"code": "OBJECT_NOT_FOUND", "message": f"No tool named '{tool_name}' is registered."},
                })
                if stop_on_error:
                    break
                continue

            try:
                op_result = tools_dict[tool_name]["handler"](**parameters)
                if not isinstance(op_result, dict):
                    op_result = {"success": False, "error": {"code": "UNO_EXCEPTION", "message": "handler returned a non-dict result"}}
            except TypeError as e:
                op_result = {"success": False, "error": {"code": "INVALID_PARAMETER", "message": str(e)}}
            except Exception as e:
                op_result = {"success": False, "error": {"code": "UNO_EXCEPTION", "message": str(e)}}

            results.append({"index": index, "tool_name": tool_name, **op_result})

            # Legacy tools (the original 32) don't always set "success" on their
            # happy path (see mcp_server.py) -- treat an absent key as success
            # rather than a failure so this doesn't misreport them as erroring.
            if op_result.get("success") is False and stop_on_error:
                break
    finally:
        # Always close a context this call opened -- success, an early
        # stop_on_error break, or even an unexpected exception escaping the
        # loop above (belt-and-suspenders; every op is already wrapped in
        # its own try/except). Deliberately committed (end), never rolled
        # back (cancel), regardless of failed_count: the spec's requirement
        # is that the batch "produce one user-visible Undo step", not that
        # a partial failure erase partial progress -- an agent or user can
        # still inspect/manually undo that one step. See the module
        # docstring's batch_execute_live bullet.
        if undo_context_open:
            end_result = undo_view_selection.end_undo_context_live()
            if not end_result.get("success"):
                warnings.append(
                    f"Failed to cleanly close the batch's undo context: {end_result['error']['message']}"
                )

    result = {
        "results": results,
        "requested_count": len(operations),
        "executed_count": len(results),
        "failed_count": sum(1 for r in results if r.get("success") is False),
    }
    return envelope.build_success(result=result, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="validate_tool_call_live",
    priority="P2",
    purpose="Validate parameters/capability without mutating the document.",
    parameters=schema({
        "tool_name": {"type": "string"},
        "parameters": {"type": "object"},
    }, required=["tool_name", "parameters"]),
    status="implemented",
)
def validate_tool_call_live(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    tools_dict = ctx.get_tools()

    if tool_name not in tools_dict:
        return envelope.build_error(
            "OBJECT_NOT_FOUND", f"No tool named '{tool_name}' is registered.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    if not isinstance(parameters, dict):
        return envelope.build_error(
            "INVALID_PARAMETER", "parameters must be an object.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )

    errors = _validate_against_schema(parameters, tools_dict[tool_name].get("parameters", {}))
    if errors:
        return envelope.build_error(
            "INVALID_PARAMETER", "; ".join(errors),
            elapsed_ms=envelope.elapsed_ms_since(start), details={"validation_errors": errors},
        )
    return envelope.build_success(result={"valid": True, "tool_name": tool_name}, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="get_recent_errors_live",
    priority="P2",
    purpose="Return structured recent extension/tool errors for diagnostics.",
    parameters=schema({
        "limit": {"type": "integer", "default": 50},
        "since": {"type": "string", "description": "ISO-8601 timestamp; only errors after this point."},
    }),
    status="implemented",
)
def get_recent_errors_live(limit: int = 50, since: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()

    since_ts = None
    if since is not None:
        try:
            since_ts = datetime.fromisoformat(since).timestamp()
        except ValueError:
            return envelope.build_error(
                "INVALID_PARAMETER", f"'since' must be an ISO-8601 timestamp, got {since!r}",
                elapsed_ms=envelope.elapsed_ms_since(start),
            )

    entries = ctx.runtime_state.get_recent_errors(limit=limit, since=since_ts)
    result = {"errors": entries, "count": len(entries)}
    return envelope.build_success(result=result, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="get_diagnostics_live",
    priority="P2",
    purpose="Return thread/server state, UNO context status, loaded extension path, port binding, and timing counters.",
    parameters=schema({"include_environment": {"type": "boolean", "default": False}}),
    status="implemented",
)
def get_diagnostics_live(include_environment: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()

    result = {
        "session_id": ctx.runtime_state.session_id,
        "uptime_seconds": round(ctx.runtime_state.uptime_seconds, 1),
        "uno_context_available": getattr(ctx.uno_bridge, "ctx", None) is not None,
        # plugin/pythonpath/tools/core_runtime.py -> plugin/
        "extension_path": os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "http_port": DEFAULT_HTTP_PORT,
        "thread_count": threading.active_count(),
        "registered_tool_count": len(ctx.get_tools()),
        **ctx.runtime_state.get_diagnostics_counters(),
    }
    if include_environment:
        result["environment"] = {"python_executable": sys.executable, "cwd": os.getcwd()}
    return envelope.build_success(result=result, elapsed_ms=envelope.elapsed_ms_since(start))


@register_tool(
    name="clear_diagnostics_live",
    priority="P3",
    purpose="Clear in-memory diagnostic/error history.",
    status="implemented",
)
def clear_diagnostics_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    ctx.runtime_state.clear_errors()
    return envelope.build_success(result={"cleared": True}, elapsed_ms=envelope.elapsed_ms_since(start))
