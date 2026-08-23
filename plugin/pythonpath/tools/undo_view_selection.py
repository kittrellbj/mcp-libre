"""
Phase A scaffold: Undo, view, selection, events, and orchestration.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Undo, view, selection, events, and orchestration" (scope: all document
types where supported).

UNO basis per spec: XUndoManagerSupplier/XUndoManager, XController/XFrame,
document events, view data.

All 14 of this module's original-spec tools are real (status=
"implemented"), following the same pattern as core_runtime.py/
document_lifecycle.py: tools.context.get_context() for live UNOBridge/
DocumentRegistry/RuntimeState, _resolve_and_register/_error_response/
_map_exception_to_code reused from document_lifecycle.py rather than
re-derived here (single source of truth for that mapping). A 15th tool,
goto_page_live, was added 2026-08-22 (Brian's new-tools assignment,
priority #7) -- not part of the original spec, see its own docstring.
  - The 6 undo tools: get_undo_state_live, undo_live, redo_live,
    begin_undo_context_live, end_undo_context_live, cancel_undo_context_live.
  - The 6 view/selection/locking tools: get_view_state_live, set_zoom_live,
    get_selection_live, clear_selection_live, lock_document_updates_live,
    unlock_document_updates_live.
  - goto_page_live: Writer-only page navigation, the write-side companion
    to get_view_state_live's current_page_number addition (#6) -- see
    below for details.
  - The 2 event tools: get_document_events_live, wait_for_document_event_live
    -- landed in a deliberately separate pass from the other 12 (this
    module's own history has them as the last two stubs closed out): event
    capture needs a persistent listener registered against the process-wide
    com.sun.star.frame.GlobalEventBroadcaster singleton and a bounded event
    buffer with its own lifecycle, a different (and more complex) concern
    than the otherwise-synchronous UNO calls the rest of this module makes.
    The real mechanism lives in uno_bridge.py (_DocumentEventCapture,
    UNOBridge._ensure_document_event_capture/_record_document_event/
    get_document_events/wait_for_document_event); this module only adds the
    envelope plumbing plus best-effort document_id correlation via
    DocumentRegistry.find_document_id (a captured event's source document
    may have been opened directly in the LibreOffice GUI rather than
    through open_document_live/create_document_live, in which case
    document_id is reported as None rather than raised or dropped).

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
    status="implemented",
)
def get_view_state_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        state = ctx.uno_bridge.get_view_state(doc)
        # get_view_state() nests a "warnings" key in its result on a
        # partial read failure (e.g. active sheet name unreadable); lift it
        # to the envelope's top-level warnings field where every other tool
        # surfaces non-fatal issues, rather than leaving two inconsistent
        # warnings locations in the response.
        warnings = state.pop("warnings", [])
        return envelope.build_success(
            result=state, document_id=resolved_id, warnings=warnings,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="set_zoom_live",
    priority="P2",
    purpose="Set zoom percent or fit mode.",
    parameters=schema({
        "percent": {"type": "integer"},
        "mode": {"type": "string", "enum": ["optimal", "page", "width"]},
    }),
    status="implemented",
)
def set_zoom_live(percent: Optional[int] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.set_zoom(doc, percent=percent, mode=mode)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="goto_page_live",
    priority="P2",
    purpose=(
        "Move the Writer view cursor to a given page number (1-based, same "
        "numbering get_view_state_live's current_page_number reports) -- "
        "Brian's new-tools assignment priority #7, the write-side companion "
        "to that read-only addition (#6)."
    ),
    parameters=schema({"page": {"type": "integer"}}, required=["page"]),
    status="implemented",
)
def goto_page_live(page: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.goto_page(doc, page)
        warnings = result.pop("warnings", [])
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings,
                                       elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_selection_live",
    priority="P1",
    purpose="Return normalized current selection with document-type-specific details.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_selection_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        result = ctx.uno_bridge.get_selection(doc)
        # get_selection() nests a "warnings" key in its result on a partial
        # read failure (e.g. selection details unreadable for this
        # document type); lift it to the envelope's top-level warnings
        # field, same pattern get_view_state_live already uses above.
        warnings = result.pop("warnings", [])
        return envelope.build_success(
            result=result, document_id=resolved_id, warnings=warnings,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="clear_selection_live",
    priority="P2",
    purpose="Collapse/clear current selection without modifying content.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def clear_selection_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        ctx.uno_bridge.clear_selection(doc)
        return envelope.build_success(result={"cleared": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


def _validate_event_types(event_types: Any, start: float, required: bool) -> Optional[Dict[str, Any]]:
    """Return an INVALID_PARAMETER envelope if event_types is present but
    malformed (not a list of strings), else None. `required` controls
    whether None/omitted itself is an error -- wait_for_document_event_live
    requires it, get_document_events_live treats it as "no filter"."""
    if event_types is None:
        if required:
            return envelope.build_error(
                "INVALID_PARAMETER", "event_types is required.", elapsed_ms=envelope.elapsed_ms_since(start),
            )
        return None
    if not isinstance(event_types, list) or not all(isinstance(item, str) for item in event_types):
        return envelope.build_error(
            "INVALID_PARAMETER", f"event_types must be a list of strings, got {event_types!r}",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    return None


def _validate_timeout_ms(timeout_ms: Any, start: float) -> Optional[Dict[str, Any]]:
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
        return envelope.build_error(
            "INVALID_PARAMETER", f"timeout_ms must be a non-negative integer, got {timeout_ms!r}",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    return None


def _public_document_event(ctx, captured_event: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an internal uno_bridge captured-event dict (which carries
    the raw UNO `source` component so the tools layer can correlate it) to
    the public envelope shape -- drops `source`, adds `document_id` via
    DocumentRegistry.find_document_id (best-effort, None when the source
    document was never registered through this extension)."""
    source = captured_event.get("source")
    document_id = None
    if source is not None:
        try:
            document_id = ctx.document_registry.find_document_id(source)
        except Exception:
            # Best-effort only -- a correlation failure (e.g. a disposed
            # proxy from a since-closed document) should never take down
            # an otherwise-successful events read.
            document_id = None
    return {
        "seq": captured_event["seq"],
        "event_type": captured_event["event_type"],
        "document_url": captured_event.get("document_url"),
        "document_id": document_id,
    }


@register_tool(
    name="get_document_events_live",
    priority="P3",
    purpose="Return recent document events captured by the extension.",
    parameters=schema({
        "limit": {"type": "integer", "default": 100},
        "event_types": {"type": "array", "items": {"type": "string"}},
    }),
    status="implemented",
)
def get_document_events_live(limit: int = 100, event_types: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    error = _validate_count(limit, start) or _validate_event_types(event_types, start, required=False)
    if error is not None:
        return error
    ctx = context.get_context()
    try:
        captured = ctx.uno_bridge.get_document_events(limit=limit, event_types=event_types)
        events = [_public_document_event(ctx, e) for e in captured]
        return envelope.build_success(
            result={"events": events, "count": len(events)}, elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="wait_for_document_event_live",
    priority="P3",
    purpose=(
        "Block until a matching document event or timeout. Waits are "
        "capped at uno_bridge._MAX_WAIT_LOCK_HOLD_MS (500ms) per call "
        "regardless of the requested timeout_ms, since this call holds "
        "the process-wide UNO execution lock for its full wait duration "
        "-- an uncapped wait would starve any OTHER concurrent tool call "
        "queued behind it for up to the full requested timeout_ms. "
        "IMPORTANT, live-verified 2026-08-21: this cap bounds that "
        "starvation, but does NOT make this tool able to observe an "
        "event caused by your OWN edit call through this same HTTP "
        "surface, even by re-polling -- both calls serialize on the same "
        "lock, so your edit can only run in the gap between one wait call "
        "ending and the next starting, and by the time it completes "
        "(firing its event synchronously) that event is already 'in the "
        "past' relative to the next wait call's fresh snapshot. Reliably "
        "works only for events from OUTSIDE this tool's own lock (a "
        "separate raw UNO connection, or a human editing in the GUI) -- "
        "see docs/EVENT_WAIT_CONCURRENCY_DECISION.md for the fix and "
        "docs/HARDENING_PLAN.md's Phase 5 note for this finding and its "
        "live evidence."
    ),
    parameters=schema({
        "event_types": {"type": "array", "items": {"type": "string"}},
        "timeout_ms": {"type": "integer"},
    }, required=["event_types", "timeout_ms"]),
    status="implemented",
)
def wait_for_document_event_live(event_types: List[str], timeout_ms: int) -> Dict[str, Any]:
    """Waits are internally clamped to uno_bridge._MAX_WAIT_LOCK_HOLD_MS
    per call -- see that constant's comment and this tool's own `purpose`
    string for why, and for the live-verified limitation on observing
    same-HTTP-path self-triggered events even with the cap in place."""
    start = envelope.start_timer()
    error = _validate_event_types(event_types, start, required=True) or _validate_timeout_ms(timeout_ms, start)
    if error is not None:
        return error
    ctx = context.get_context()
    try:
        captured = ctx.uno_bridge.wait_for_document_event(event_types=event_types, timeout_ms=timeout_ms)
        if captured is None:
            return envelope.build_success(
                result={"event": None, "timed_out": True}, elapsed_ms=envelope.elapsed_ms_since(start),
            )
        return envelope.build_success(
            result={"event": _public_document_event(ctx, captured), "timed_out": False},
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="lock_document_updates_live",
    priority="P2",
    purpose="Temporarily lock automatic view/model update for bulk operations.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def lock_document_updates_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        ctx.uno_bridge.lock_document_updates(doc)
        return envelope.build_success(result={"locked": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="unlock_document_updates_live",
    priority="P2",
    purpose="Release update lock and refresh.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def unlock_document_updates_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        ctx.uno_bridge.unlock_document_updates(doc)
        return envelope.build_success(result={"unlocked": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)
