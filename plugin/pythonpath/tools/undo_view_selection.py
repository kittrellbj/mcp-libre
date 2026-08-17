"""
Phase A scaffold: Undo, view, selection, events, and orchestration.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Undo, view, selection, events, and orchestration" (scope: all document
types where supported).

UNO basis per spec: XUndoManagerSupplier/XUndoManager, XController/XFrame,
document events, view data. None of these are implemented anywhere in the
repo today (the original 32 tools have no undo/redo/view-state surface).
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="get_undo_state_live",
    priority="P1",
    purpose="Return undo/redo availability and titles.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_undo_state_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_undo_state_live", start)


@register_tool(
    name="undo_live",
    priority="P1",
    purpose="Undo one or more actions.",
    parameters=schema({"count": {"type": "integer", "default": 1}}),
)
def undo_live(count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("undo_live", start)


@register_tool(
    name="redo_live",
    priority="P1",
    purpose="Redo one or more actions.",
    parameters=schema({"count": {"type": "integer", "default": 1}}),
)
def redo_live(count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("redo_live", start)


@register_tool(
    name="begin_undo_context_live",
    priority="P1",
    purpose="Begin a named undo context for a multi-step agent operation.",
    parameters=schema({"title": {"type": "string"}}, required=["title"]),
)
def begin_undo_context_live(title: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("begin_undo_context_live", start)


@register_tool(
    name="end_undo_context_live",
    priority="P1",
    purpose="Commit current named undo context.",
)
def end_undo_context_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("end_undo_context_live", start)


@register_tool(
    name="cancel_undo_context_live",
    priority="P2",
    purpose="Best-effort undo of changes made since context began.",
)
def cancel_undo_context_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("cancel_undo_context_live", start)


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
