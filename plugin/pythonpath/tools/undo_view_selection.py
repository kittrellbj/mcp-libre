"""
Phase A scaffold: Undo, view, selection, events, and orchestration.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Undo, view, selection, events, and orchestration" (scope: all document
types where supported).

UNO basis per spec: XUndoManagerSupplier/XUndoManager, XController/XFrame,
document events, view data.

The 6 undo tools (get_undo_state_live, undo_live, redo_live,
begin_undo_context_live, end_undo_context_live, cancel_undo_context_live)
are real (status="implemented"), following the same pattern as
core_runtime.py/document_lifecycle.py: tools.context.get_context() for live
UNOBridge/DocumentRegistry/RuntimeState, _resolve_and_register/
_error_response/_map_exception_to_code reused from document_lifecycle.py
rather than re-derived here (single source of truth for that mapping).

The remaining 8 tools in this module (view state, zoom, selection,
document-update locking, document events) are still NOT_IMPLEMENTED
stubs -- a separate follow-up pass, not part of this one.

Undo-context state (which named context is open, on which document, and
its baseline undo-stack depth) is tracked on RuntimeState -- see
RuntimeState.set_undo_context/get_undo_context/clear_undo_context -- not
in this module, so get_session_state_live (tools/core_runtime.py) can
report it without importing this module.

Nesting: begin_undo_context_live rejects a second begin() while one is
already open (INVALID_STATE) rather than silently supporting nested UNO
undo contexts. Simpler and less surprising for an agent caller: a nested
open would still coalesce correctly at the UNO level, but this module can
only track one {title, document_id, baseline_count} at a time, and
end/cancel take no document_id/title parameter -- there's no way for a
second begin() to say which of two open contexts it's naming or which one
a later end()/cancel() should target.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


@register_tool(
    name="get_undo_state_live",
    priority="P1",
    purpose="Return undo/redo availability and titles.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_undo_state_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        state = ctx.uno_bridge.get_undo_state(doc)
        return envelope.build_success(result=state, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


def _validate_count(count: Any, start: float) -> Optional[Dict[str, Any]]:
    """Return an INVALID_PARAMETER envelope if count isn't a positive int, else None."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        return envelope.build_error(
            "INVALID_PARAMETER", f"count must be a positive integer, got {count!r}",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    return None


@register_tool(
    name="undo_live",
    priority="P1",
    purpose="Undo one or more actions.",
    parameters=schema({"count": {"type": "integer", "default": 1}}),
    status="implemented",
)
def undo_live(count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    error = _validate_count(count, start)
    if error is not None:
        return error
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.undo(doc, count=count)
        warnings = []
        if result["applied"] < count:
            warnings.append(
                f"Requested {count} undo step(s) but only {result['applied']} were available "
                "-- undo stack exhausted."
            )
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="redo_live",
    priority="P1",
    purpose="Redo one or more actions.",
    parameters=schema({"count": {"type": "integer", "default": 1}}),
    status="implemented",
)
def redo_live(count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    error = _validate_count(count, start)
    if error is not None:
        return error
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.redo(doc, count=count)
        warnings = []
        if result["applied"] < count:
            warnings.append(
                f"Requested {count} redo step(s) but only {result['applied']} were available "
                "-- redo stack exhausted."
            )
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="begin_undo_context_live",
    priority="P1",
    purpose="Begin a named undo context for a multi-step agent operation.",
    parameters=schema({"title": {"type": "string"}}, required=["title"]),
    status="implemented",
)
def begin_undo_context_live(title: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    pending = ctx.runtime_state.get_undo_context()
    if pending is not None:
        return envelope.build_error(
            "INVALID_STATE",
            f"An undo context ('{pending['title']}') is already open -- nested undo contexts "
            "are not supported. Call end_undo_context_live or cancel_undo_context_live first.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        info = ctx.uno_bridge.begin_undo_context(doc, title)
        ctx.runtime_state.set_undo_context(title=title, document_id=resolved_id, baseline_count=info["baseline_count"])
        return envelope.build_success(
            result={"title": title, "started": True}, document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="end_undo_context_live",
    priority="P1",
    purpose="Commit current named undo context.",
    status="implemented",
)
def end_undo_context_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    pending = ctx.runtime_state.get_undo_context()
    if pending is None:
        return envelope.build_error(
            "INVALID_STATE", "No undo context is currently open -- call begin_undo_context_live first.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    try:
        doc = ctx.document_registry.resolve_document(pending["document_id"])
        info = ctx.uno_bridge.end_undo_context(doc)
        ctx.runtime_state.clear_undo_context()
        grouped = info["resulting_count"] > pending["baseline_count"]
        return envelope.build_success(
            result={"title": pending["title"], "grouped": grouped},
            document_id=pending["document_id"], elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        # Deliberately NOT clearing runtime_state's undo-context record here
        # -- if leaveUndoContext() itself raised, the UNO-side context is
        # presumably still open, so clearing our tracker would desync it
        # from reality and let a later begin_undo_context_live silently
        # nest a second UNO context under the still-open one.
        return _error_response(e, start, document_id=pending["document_id"])


@register_tool(
    name="cancel_undo_context_live",
    priority="P2",
    purpose="Best-effort undo of changes made since context began.",
    status="implemented",
)
def cancel_undo_context_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    pending = ctx.runtime_state.get_undo_context()
    if pending is None:
        return envelope.build_error(
            "INVALID_STATE", "No undo context is currently open -- call begin_undo_context_live first.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    try:
        doc = ctx.document_registry.resolve_document(pending["document_id"])
        info = ctx.uno_bridge.cancel_undo_context(doc, pending["baseline_count"])
        ctx.runtime_state.clear_undo_context()
        warnings = []
        if not info["restored"]:
            warnings.append(
                "Could not fully restore the document to its pre-context state; some changes "
                "made inside the context may remain."
            )
        return envelope.build_success(
            result={"title": pending["title"], "reverted_count": info["reverted_count"], "restored": info["restored"]},
            document_id=pending["document_id"], warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        # Same reasoning as end_undo_context_live: leave the tracker alone
        # on failure so it doesn't desync from a UNO context that may still
        # be open.
        return _error_response(e, start, document_id=pending["document_id"])


@register_tool(
    name="get_view_state_live",
    priority="P2",
    purpose="Return controller/view mode, zoom, visible sheet/page/slide, cursor/selection summary.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_view_state_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_view_state_live", start)


@register_tool(
    name="set_zoom_live",
    priority="P2",
    purpose="Set zoom percent or fit mode.",
    parameters=schema({
        "percent": {"type": "integer"},
        "mode": {"type": "string", "enum": ["optimal", "page", "width"]},
    }),
)
def set_zoom_live(percent: Optional[int] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_zoom_live", start)


@register_tool(
    name="get_selection_live",
    priority="P1",
    purpose="Return normalized current selection with document-type-specific details.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_selection_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_selection_live", start)


@register_tool(
    name="clear_selection_live",
    priority="P2",
    purpose="Collapse/clear current selection without modifying content.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def clear_selection_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_selection_live", start)


@register_tool(
    name="get_document_events_live",
    priority="P3",
    purpose="Return recent document events captured by the extension.",
    parameters=schema({
        "limit": {"type": "integer", "default": 100},
        "event_types": {"type": "array", "items": {"type": "string"}},
    }),
)
def get_document_events_live(limit: int = 100, event_types: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_document_events_live", start)


@register_tool(
    name="wait_for_document_event_live",
    priority="P3",
    purpose="Block until a matching document event or timeout.",
    parameters=schema({
        "event_types": {"type": "array", "items": {"type": "string"}},
        "timeout_ms": {"type": "integer"},
    }, required=["event_types", "timeout_ms"]),
)
def wait_for_document_event_live(event_types: List[str], timeout_ms: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("wait_for_document_event_live", start)


@register_tool(
    name="lock_document_updates_live",
    priority="P2",
    purpose="Temporarily lock automatic view/model update for bulk operations.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def lock_document_updates_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("lock_document_updates_live", start)


@register_tool(
    name="unlock_document_updates_live",
    priority="P2",
    purpose="Release update lock and refresh.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def unlock_document_updates_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("unlock_document_updates_live", start)
