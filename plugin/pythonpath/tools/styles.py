"""
Styles and formatting infrastructure -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Styles and formatting infrastructure" (scope: Writer, Calc, Impress, Draw;
partial Base).

All 12 tools are real (status="implemented"), following the same pattern
as core_runtime.py/document_lifecycle.py/undo_view_selection.py:
tools.context.get_context() for live UNOBridge/DocumentRegistry/
RuntimeState, _resolve_and_register/_error_response reused from
document_lifecycle.py. Only list_style_families_live takes an optional
document_id per the spec's own parameter list -- every other tool here
always resolves the active document (matching spec exactly, same
precedent as e.g. document_lifecycle.py's save_as_document_live/
print_document_live).

Family/style CRUD (list_style_families_live, list_styles_live,
get_style_live, create_style_live, clone_style_live, update_style_live,
rename_style_live, delete_style_live) works across any document type that
implements XStyleFamiliesSupplier (Writer/Calc/Impress/Draw all do) --
create/clone are limited to the 6 families UNOBridge._STYLE_FAMILY_SERVICES
covers; an unrecognized family raises UNSUPPORTED_CAPABILITY rather than
guessing at a UNO service name.

`target` resolution (previously left undecided, flagged for Morgan in an
earlier pass) is now concretely resolved for apply_style_live/
get_direct_formatting_live/clear_direct_formatting_live/
copy_formatting_live: omitted means the current selection; an explicit
{"start": int, "end": int} means a 0-based Writer character range (the
same convention the existing select_text_range_live legacy tool uses).
These four tools are Writer-only this pass -- see
UNOBridge._resolve_text_target's docstring; other document types raise
UNSUPPORTED_CAPABILITY via NotImplementedError.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


@register_tool(
    name="list_style_families_live",
    priority="P1",
    purpose="List style families supported by the active document.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def list_style_families_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        result = ctx.uno_bridge.list_style_families(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="list_styles_live",
    priority="P1",
    purpose="List styles in a family with user-defined/in-use flags.",
    parameters=schema({"family": {"type": "string"}}, required=["family"]),
    status="implemented",
)
def list_styles_live(family: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.list_styles(doc, family)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_style_live",
    priority="P1",
    purpose="Return style properties and parent relationship.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
    }, required=["family", "style_name"]),
    status="implemented",
)
def get_style_live(family: str, style_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_style(doc, family, style_name)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_style_live",
    priority="P1",
    purpose=(
        "Create a user style in a supported family. family selects the kind of "
        "style, not a separate tool -- e.g. family='ParagraphStyles' creates what "
        "a caller might otherwise look for as 'create_paragraph_style_live' (no "
        "such tool exists; this is the one). Supported family values: "
        "ParagraphStyles, CharacterStyles, PageStyles, FrameStyles, "
        "NumberingStyles, CellStyles."
    ),
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
        "parent_style": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["family", "style_name"]),
    status="implemented",
)
def create_style_live(family: str, style_name: str, parent_style: Optional[str] = None,
                       properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.create_style(doc, family, style_name, parent_style=parent_style, properties=properties)
        requested = set((properties or {}).keys())
        skipped = sorted(requested - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(
            result={"created": style_name, "applied_properties": applied}, document_id=resolved_id,
            warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clone_style_live",
    priority="P2",
    purpose="Clone an existing style under a new name.",
    parameters=schema({
        "family": {"type": "string"},
        "source_style": {"type": "string"},
        "new_style": {"type": "string"},
    }, required=["family", "source_style", "new_style"]),
    status="implemented",
)
def clone_style_live(family: str, source_style: str, new_style: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        # clone_style() returns the directly-set property names it failed
        # to copy (a fake/legacy uno_bridge in tests may still return None
        # -- treat that as "nothing to report", not a crash).
        failed = ctx.uno_bridge.clone_style(doc, family, source_style, new_style) or []
        warnings = [f"Could not clone property '{p}'" for p in failed]
        return envelope.build_success(
            result={"cloned": new_style, "from": source_style}, document_id=resolved_id,
            warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_style_live",
    priority="P1",
    purpose="Update selected style properties.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["family", "style_name", "properties"]),
    status="implemented",
)
def update_style_live(family: str, style_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.update_style(doc, family, style_name, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(
            result={"applied": applied}, document_id=resolved_id, warnings=warnings,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="rename_style_live",
    priority="P2",
    purpose="Rename a user-defined style where the family permits it.",
    parameters=schema({
        "family": {"type": "string"},
        "old_name": {"type": "string"},
        "new_name": {"type": "string"},
    }, required=["family", "old_name", "new_name"]),
    status="implemented",
)
def rename_style_live(family: str, old_name: str, new_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.rename_style(doc, family, old_name, new_name)
        return envelope.build_success(result={"renamed_to": new_name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_style_live",
    priority="P2",
    purpose="Delete an unused user-defined style.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
    }, required=["family", "style_name"]),
    status="implemented",
)
def delete_style_live(family: str, style_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_style(doc, family, style_name)
        return envelope.build_success(result={"deleted": style_name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="apply_style_live",
    priority="P1",
    purpose="Apply a named style to current/explicit selection or object.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
        "target": {"description": "Current selection when omitted; otherwise {'start': int, 'end': int} for a 0-based Writer character range."},
    }, required=["family", "style_name"]),
    status="implemented",
)
def apply_style_live(family: str, style_name: str, target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.apply_style(doc, family, style_name, target=target)
        return envelope.build_success(result={"applied": style_name, "family": family}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_direct_formatting_live",
    priority="P2",
    purpose="Return direct formatting overrides on current/explicit target.",
    parameters=schema({"target": {"description": "Current selection when omitted; otherwise {'start': int, 'end': int} for a 0-based Writer character range."}}),
    status="implemented",
)
def get_direct_formatting_live(target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_direct_formatting(doc, target=target)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_direct_formatting_live",
    priority="P1",
    purpose="Clear direct formatting and preserve style-driven formatting.",
    parameters=schema({"target": {"description": "Current selection when omitted; otherwise {'start': int, 'end': int} for a 0-based Writer character range."}}),
    status="implemented",
)
def clear_direct_formatting_live(target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_direct_formatting(doc, target=target)
        return envelope.build_success(result={"cleared": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="copy_formatting_live",
    priority="P2",
    purpose="Copy formatting/style attributes between two targets.",
    parameters=schema({
        "source": {"description": "{'start': int, 'end': int} Writer character range to copy formatting from."},
        "target": {"description": "{'start': int, 'end': int} Writer character range to copy formatting to."},
        "include": {"type": "array", "items": {"type": "string"}, "description": "Optional subset of UNO property names to copy."},
    }, required=["source", "target"]),
    status="implemented",
)
def copy_formatting_live(source: Any, target: Any, include: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.copy_formatting(doc, source, target, include=include)
        return envelope.build_success(result={"applied": applied, "applied_count": len(applied)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
