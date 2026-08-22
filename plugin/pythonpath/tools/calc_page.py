"""
Calc - page setup, print ranges, annotations, protection -- real
implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Calc - page setup, print ranges, annotations, protection" (scope:
Calc). No tools in this section are marked "(existing)"; all 15 were
scaffolded stubs before this pass. All 15 are real.

Second of the four remaining Phase B/C scaffolds Buddy assigned after
the draw/charts/impress trio (calc_data.py -> calc_page.py ->
writer_layout.py -> writer_tables.py). Page layout resolves through the
sheet's own PageStyle (a com.sun.star.style.PageStyle in the workbook's
"PageStyles" StyleFamilies family, same family styles.py already
resolves via _get_style_family()) -- not a direct sheet property.
list_number_formats_live has a documented scope limit: XNumberFormats
has no "list every format" API (keyed/query access only), so it lists
the standard format for each well-known NumberFormat category instead
of every custom format ever created in the document -- see
uno_bridge.py's list_number_formats() docstring.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


@register_tool(
    name="get_sheet_page_layout_live",
    priority="P2",
    purpose="Return Calc page style, paper, margins, scaling, headers/footers.",
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def get_sheet_page_layout_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_sheet_page_layout(doc, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_sheet_page_layout_live",
    priority="P2",
    purpose="Set Calc paper/page orientation/margins/scaling.",
    parameters=schema({
        "sheet": {"type": "string"},
        "width": {"type": "number"},
        "height": {"type": "number"},
        "unit": {"type": "string"},
        "orientation": {"type": "string"},
        "margins": {"type": "object"},
        "scale": {"type": "object"},
    }),
    status="implemented",
)
def set_sheet_page_layout_live(sheet: Optional[str] = None, width: Optional[float] = None,
                                height: Optional[float] = None, unit: Optional[str] = None,
                                orientation: Optional[str] = None, margins: Optional[Dict[str, Any]] = None,
                                scale: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_sheet_page_layout(doc, sheet, width, height, unit, orientation, margins, scale)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_print_area_live",
    priority="P1",
    purpose="Set one or more print ranges.",
    parameters=schema({
        "sheet": {"type": "string"},
        "ranges": {"type": "array", "items": {"type": "string"}},
    }, required=["ranges"]),
    status="implemented",
)
def set_print_area_live(ranges: List[str], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_print_area(doc, ranges, sheet)
        return envelope.build_success(result={"ranges": ranges}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_print_area_live",
    priority="P1",
    purpose="Clear explicit print ranges.",
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def clear_print_area_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_print_area(doc, sheet)
        return envelope.build_success(result={"cleared": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_repeating_print_rows_live",
    priority="P2",
    purpose="Set rows repeated at top of printed pages.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
    status="implemented",
)
def set_repeating_print_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_repeating_print_rows(doc, rows, sheet)
        return envelope.build_success(result={"rows": rows}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_repeating_print_columns_live",
    priority="P2",
    purpose="Set columns repeated at left of printed pages.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
    status="implemented",
)
def set_repeating_print_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_repeating_print_columns(doc, columns, sheet)
        return envelope.build_success(result={"columns": columns}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_cell_comment_live",
    priority="P1",
    purpose="Add/update Calc cell annotation.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
        "text": {"type": "string"},
        "author": {"type": "string"},
    }, required=["cell", "text"]),
    status="implemented",
)
def add_cell_comment_live(cell: str, text: str, sheet: Optional[str] = None,
                           author: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.add_cell_comment(doc, cell, text, sheet, author)
        warnings = []
        if author is not None and not result.get("author_applied"):
            warnings.append("author is read-only in this LibreOffice build -- the comment text was applied, but the author was not changed.")
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_cell_comment_live",
    priority="P1",
    purpose=(
        "Update an existing Calc cell comment's text/author/visibility -- "
        "Brian's new-tools assignment priority #11. Distinct from "
        "add_cell_comment_live's upsert semantics: requires the comment to "
        "already exist (OBJECT_NOT_FOUND if not) and is the only cell-"
        "comment tool that can toggle IsVisible."
    ),
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
        "text": {"type": "string"},
        "author": {"type": "string"},
        "visible": {"type": "boolean"},
    }, required=["cell"]),
    status="implemented",
)
def update_cell_comment_live(cell: str, sheet: Optional[str] = None, text: Optional[str] = None,
                              author: Optional[str] = None, visible: Optional[bool] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.update_cell_comment(doc, cell, sheet, text, author, visible)
        warnings = []
        if author is not None and not result.get("author_applied"):
            warnings.append("author is read-only in this LibreOffice build -- other fields were applied, but the author was not changed.")
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_cell_comments_live",
    priority="P1",
    purpose="List Calc cell annotations.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
    status="implemented",
)
def list_cell_comments_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        comments = ctx.uno_bridge.list_cell_comments(doc, sheet, range)
        return envelope.build_success(result={"comments": comments, "count": len(comments)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_cell_comment_live",
    priority="P1",
    purpose="Delete cell annotation.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
    }, required=["cell"]),
    status="implemented",
)
def delete_cell_comment_live(cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_cell_comment(doc, cell, sheet)
        return envelope.build_success(result={"deleted": cell}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="protect_sheet_live",
    priority="P2",
    purpose="Protect sheet with optional password and permissions.",
    parameters=schema({
        "sheet": {"type": "string"},
        "password": {"type": "string"},
        "options": {"type": "object"},
    }),
    status="implemented",
)
def protect_sheet_live(sheet: Optional[str] = None, password: Optional[str] = None,
                        options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.protect_sheet(doc, sheet, password, options)
        skipped = sorted(set(options or {}) - set(applied))
        warnings = [f"Ignored unknown/unsettable option field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="unprotect_sheet_live",
    priority="P2",
    purpose="Unprotect sheet.",
    parameters=schema({
        "sheet": {"type": "string"},
        "password": {"type": "string"},
    }),
    status="implemented",
)
def unprotect_sheet_live(sheet: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.unprotect_sheet(doc, sheet, password)
        return envelope.build_success(result={"unprotected": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_cell_protection_live",
    priority="P2",
    purpose="Set locked/hidden/formula-hidden flags for range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["range", "properties"]),
    status="implemented",
)
def set_cell_protection_live(range: str, properties: Dict[str, Any], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_cell_protection(doc, range, properties, sheet)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_number_formats_live",
    priority="P2",
    purpose=(
        "List number formats/keys/locales. Lists the standard format for each "
        "well-known category (date/time/currency/number/scientific/fraction/"
        "percent/text/datetime/logical), not every custom format in the "
        "document -- XNumberFormats has no direct enumerate-all API."
    ),
    parameters=schema({"locale": {"type": "string"}}),
    status="implemented",
)
def list_number_formats_live(locale: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        formats = ctx.uno_bridge.list_number_formats(doc, locale)
        return envelope.build_success(result={"formats": formats, "count": len(formats)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_number_format_live",
    priority="P2",
    purpose="Create/reuse number format string.",
    parameters=schema({
        "format_code": {"type": "string"},
        "locale": {"type": "string"},
    }, required=["format_code"]),
    status="implemented",
)
def create_number_format_live(format_code: str, locale: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_number_format(doc, format_code, locale)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="apply_number_format_live",
    priority="P1",
    purpose="Apply number format to range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "format_code": {"type": "string"},
        "format_key": {"type": "integer"},
    }, required=["range"]),
    status="implemented",
)
def apply_number_format_live(range: str, sheet: Optional[str] = None, format_code: Optional[str] = None,
                              format_key: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.apply_number_format(doc, range, sheet, format_code, format_key)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
