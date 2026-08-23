"""
Calc - sheets, cells, ranges, formulas, layout -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Calc - sheets, cells, ranges, formulas, layout" (scope: Calc). No tools
in this section are marked "(existing)"; all 42 were scaffolded stubs
before this pass.

Sheet addressing: `sheet` resolves live against UNO's own named/indexed
`XSpreadsheets` container -- no registry, per docs/OBJECT_HANDLE_DESIGN.md's
category split (sheets are never anonymous, unlike shapes).
`UNOBridge._resolve_sheet()` handles the "omitted -> active sheet"
fallback on top of the already-shared `_resolve_sheet_by_name_or_index()`
(the same helper `drawing_objects.py`'s container resolution uses).
None of these 42 tools take a `document_id` parameter (matching the
spec's own parameter lists, same precedent every prior real-
implementation module has followed), so every tool resolves the active
document via `_resolve_and_register(ctx)` first.

Cell/range addressing uses plain A1-notation strings
(`sheet.getCellRangeByName("B3")` / `"A1:C3"`) directly -- no manual
address parsing, live-verified this accepts both single cells and
ranges.

Known landmine avoided, not repeated: `set_range_live`'s `values` matrix
is written via `UNOBridge.set_range()`'s `setFormulaArray()` call, not
`setDataArray()` -- live-verified `setDataArray()` stores a
formula-looking string like `"=1+1"` as literal text, not an evaluated
formula, while `setFormulaArray()` genuinely parses every entry the same
way typing into a cell would (numbers, text, and formulas all
auto-detected). See uno_bridge.py's `set_range()` docstring/comment for
the live evidence.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


@register_tool(
    name="list_sheets_live",
    priority="P1",
    purpose="List sheets with index/name/visibility/protection.",
    status="implemented",
)
def list_sheets_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        sheets = ctx.uno_bridge.list_sheets(doc)
        return envelope.build_success(result={"sheets": sheets, "count": len(sheets)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_active_sheet_live",
    priority="P1",
    purpose="Return active sheet.",
    status="implemented",
)
def get_active_sheet_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_active_sheet(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="activate_sheet_live",
    priority="P1",
    purpose="Activate sheet by name/index.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
    status="implemented",
)
def activate_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.activate_sheet(doc, sheet)
        return envelope.build_success(result={"activated": sheet}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_sheet_live",
    priority="P1",
    purpose="Insert new sheet.",
    parameters=schema({
        "name": {"type": "string"},
        "position": {"type": "integer"},
    }, required=["name"]),
    status="implemented",
)
def insert_sheet_live(name: str, position: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.insert_sheet(doc, name, position)
        return envelope.build_success(result={"name": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_sheet_live",
    priority="P1",
    purpose="Delete sheet.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
    status="implemented",
)
def delete_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_sheet(doc, sheet)
        return envelope.build_success(result={"deleted": sheet}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="rename_sheet_live",
    priority="P1",
    purpose="Rename sheet.",
    parameters=schema({
        "sheet": {"type": "string"},
        "new_name": {"type": "string"},
    }, required=["sheet", "new_name"]),
    status="implemented",
)
def rename_sheet_live(sheet: str, new_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.rename_sheet(doc, sheet, new_name)
        return envelope.build_success(result={"new_name": new_name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="move_sheet_live",
    priority="P1",
    purpose="Move sheet position.",
    parameters=schema({
        "sheet": {"type": "string"},
        "destination_index": {"type": "integer"},
    }, required=["sheet", "destination_index"]),
    status="implemented",
)
def move_sheet_live(sheet: str, destination_index: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.move_sheet(doc, sheet, destination_index)
        return envelope.build_success(result={"destination_index": destination_index}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="copy_sheet_live",
    priority="P1",
    purpose="Copy sheet within workbook.",
    parameters=schema({
        "sheet": {"type": "string"},
        "new_name": {"type": "string"},
        "destination_index": {"type": "integer"},
    }, required=["sheet", "new_name"]),
    status="implemented",
)
def copy_sheet_live(sheet: str, new_name: str, destination_index: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.copy_sheet(doc, sheet, new_name, destination_index)
        return envelope.build_success(result={"new_name": new_name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="hide_sheet_live",
    priority="P1",
    purpose="Hide sheet.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
    status="implemented",
)
def hide_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.hide_sheet(doc, sheet)
        return envelope.build_success(result={"hidden": sheet}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="show_sheet_live",
    priority="P1",
    purpose="Show sheet.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
    status="implemented",
)
def show_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.show_sheet(doc, sheet)
        return envelope.build_success(result={"shown": sheet}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_cell_live",
    priority="P1",
    purpose="Return value/formula/display/format/error for one cell.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
    }, required=["cell"]),
    status="implemented",
)
def get_cell_live(cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_cell(doc, cell, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_cell_live",
    priority="P1",
    purpose="Set one cell value/text/formula using explicit type or inference.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
        "value": {},
        "formula": {"type": "string"},
    }, required=["cell"]),
    status="implemented",
)
def set_cell_live(cell: str, sheet: Optional[str] = None, value: Optional[Any] = None,
                   formula: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.set_cell(doc, cell, sheet, value, formula)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_range_live",
    priority="P1",
    purpose="Read rectangular range as values/formulas/display strings.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "mode": {"type": "string", "enum": ["values", "formulas", "display", "all"], "default": "values"},
    }, required=["range"]),
    status="implemented",
)
def get_range_live(range: str, sheet: Optional[str] = None, mode: str = "values") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_range(doc, range, sheet, mode)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_range_live",
    priority="P1",
    purpose="Write rectangular matrix of values/formulas.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "start_cell": {"type": "string"},
        "values": {"type": "array", "items": {"type": "array"}},
    }, required=["values"]),
    status="implemented",
)
def set_range_live(values: List[List[Any]], sheet: Optional[str] = None, range: Optional[str] = None,
                    start_cell: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.set_range(doc, values, sheet, range, start_cell)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_range_live",
    priority="P1",
    purpose="Clear selected contents/types/formats/annotations.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "what": {"type": "string", "default": "contents"},
    }, required=["range"]),
    status="implemented",
)
def clear_range_live(range: str, sheet: Optional[str] = None, what: str = "contents") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_range(doc, range, sheet, what)
        return envelope.build_success(result={"cleared": range, "what": what}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_used_range_live",
    priority="P1",
    purpose="Return used area bounds and optional non-empty count.",
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def get_used_range_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_used_range(doc, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_sheet_summary_live",
    priority="P1",
    purpose=(
        "Return an at-a-glance sheet summary (name, visibility, "
        "protection, used-range dimensions, formula+error counts, "
        "freeze-panes state) in one call -- Brian's new-tools assignment "
        "priority #13, instead of get_active_sheet_live + "
        "get_used_range_live + get_freeze_panes_live + reading "
        "protection separately."
    ),
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def get_sheet_summary_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_sheet_summary(doc, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="find_cells_live",
    priority="P1",
    purpose=(
        "Search cell values/formulas/comments for a query string, across "
        "one sheet or the whole workbook -- the Calc search primitive "
        "this catalog was missing (Brian's priority #2, 2026-08-21 new-"
        "tools assignment: 'the biggest obvious Calc hole'). Scoped to "
        "the given range, else each searched sheet's own used range, "
        "never the full 1M+-row grid."
    ),
    parameters=schema({
        "query": {"type": "string"},
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "look_in": {"type": "string", "enum": ["values", "formulas", "comments", "all"], "default": "values"},
        "match": {"type": "string", "enum": ["contains", "exact", "regex"], "default": "contains"},
        "case_sensitive": {"type": "boolean", "default": False},
        "max_results": {"type": "integer", "default": 100},
    }, required=["query"]),
    status="implemented",
)
def find_cells_live(query: str, sheet: Optional[str] = None, range: Optional[str] = None,
                     look_in: str = "values", match: str = "contains", case_sensitive: bool = False,
                     max_results: int = 100) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.find_cells(
            doc, query, sheet=sheet, range=range, look_in=look_in, match=match,
            case_sensitive=case_sensitive, max_results=max_results,
        )
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_rows_live",
    priority="P1",
    purpose="Insert rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
    status="implemented",
)
def insert_rows_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.insert_rows(doc, index, sheet, count)
        return envelope.build_success(result={"index": index, "count": count}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_rows_live",
    priority="P1",
    purpose="Delete rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
    status="implemented",
)
def delete_rows_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_rows(doc, index, sheet, count)
        return envelope.build_success(result={"index": index, "count": count}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_columns_live",
    priority="P1",
    purpose="Insert columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
    status="implemented",
)
def insert_columns_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.insert_columns(doc, index, sheet, count)
        return envelope.build_success(result={"index": index, "count": count}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_columns_live",
    priority="P1",
    purpose="Delete columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
    status="implemented",
)
def delete_columns_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_columns(doc, index, sheet, count)
        return envelope.build_success(result={"index": index, "count": count}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_cells_live",
    priority="P2",
    purpose="Insert cells and shift right/down.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "shift": {"type": "string"},
    }, required=["range", "shift"]),
    status="implemented",
)
def insert_cells_live(range: str, shift: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.insert_cells(doc, range, shift, sheet)
        return envelope.build_success(result={"range": range, "shift": shift}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_cells_live",
    priority="P2",
    purpose="Delete cells and shift left/up.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "shift": {"type": "string"},
    }, required=["range", "shift"]),
    status="implemented",
)
def delete_cells_live(range: str, shift: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_cells(doc, range, shift, sheet)
        return envelope.build_success(result={"range": range, "shift": shift}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="copy_range_live",
    priority="P1",
    purpose="Copy range to destination.",
    parameters=schema({
        "source_sheet": {"type": "string"},
        "source_range": {"type": "string"},
        "dest_sheet": {"type": "string"},
        "dest_cell": {"type": "string"},
        "include": {"type": "object"},
    }, required=["source_range", "dest_cell"]),
    status="implemented",
)
def copy_range_live(source_range: str, dest_cell: str, source_sheet: Optional[str] = None,
                     dest_sheet: Optional[str] = None, include: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.copy_range(doc, source_range, dest_cell, source_sheet, dest_sheet, include)
        return envelope.build_success(result={"source_range": source_range, "dest_cell": dest_cell}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="move_range_live",
    priority="P1",
    purpose="Move range.",
    parameters=schema({
        "source_sheet": {"type": "string"},
        "source_range": {"type": "string"},
        "dest_sheet": {"type": "string"},
        "dest_cell": {"type": "string"},
    }, required=["source_range", "dest_cell"]),
    status="implemented",
)
def move_range_live(source_range: str, dest_cell: str, source_sheet: Optional[str] = None,
                     dest_sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.move_range(doc, source_range, dest_cell, source_sheet, dest_sheet)
        return envelope.build_success(result={"source_range": source_range, "dest_cell": dest_cell}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="fill_series_live",
    priority="P2",
    purpose="Fill numeric/date series.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "direction": {"type": "string"},
        "mode": {"type": "string"},
        "start": {},
        "step": {"type": "number"},
        "end": {},
    }, required=["range", "direction", "mode"]),
    status="implemented",
)
def fill_series_live(range: str, direction: str, mode: str, sheet: Optional[str] = None,
                      start: Optional[Any] = None, step: Optional[float] = None,
                      end: Optional[Any] = None) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.fill_series(doc, range, direction, mode, sheet, start, step, end)
        return envelope.build_success(result={"range": range, "direction": direction, "mode": mode}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start_time))
    except Exception as e:
        return _error_response(e, start_time)


@register_tool(
    name="autofill_live",
    priority="P2",
    purpose="Extend source pattern/formulas into destination.",
    parameters=schema({
        "sheet": {"type": "string"},
        "source_range": {"type": "string"},
        "destination_range": {"type": "string"},
    }, required=["source_range", "destination_range"]),
    status="implemented",
)
def autofill_live(source_range: str, destination_range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.autofill(doc, source_range, destination_range, sheet)
        return envelope.build_success(result={"source_range": source_range, "destination_range": destination_range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_range_format_live",
    priority="P1",
    purpose="Set font/alignment/wrap/borders/background/number format/protection.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["range", "properties"]),
    status="implemented",
)
def set_range_format_live(range: str, properties: Dict[str, Any], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_range_format(doc, range, properties, sheet)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_range_format_live",
    priority="P2",
    purpose="Return effective range formatting summary.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
    status="implemented",
)
def get_range_format_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_range_format(doc, range, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="merge_cells_live",
    priority="P1",
    purpose="Merge range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "center": {"type": "boolean", "default": False},
    }, required=["range"]),
    status="implemented",
)
def merge_cells_live(range: str, sheet: Optional[str] = None, center: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.merge_cells(doc, range, sheet, center)
        return envelope.build_success(result={"merged": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="unmerge_cells_live",
    priority="P1",
    purpose="Unmerge range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
    status="implemented",
)
def unmerge_cells_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.unmerge_cells(doc, range, sheet)
        return envelope.build_success(result={"unmerged": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_row_height_live",
    priority="P1",
    purpose="Set or optimize row height.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
        "height": {"type": "number"},
        "unit": {"type": "string"},
        "optimal": {"type": "boolean", "default": False},
    }, required=["rows"]),
    status="implemented",
)
def set_row_height_live(rows: List[int], sheet: Optional[str] = None, height: Optional[float] = None,
                         unit: Optional[str] = None, optimal: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_row_height(doc, rows, sheet, height, unit, optimal)
        return envelope.build_success(result={"rows": rows}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_column_width_live",
    priority="P1",
    purpose="Set or optimize column width.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
        "width": {"type": "number"},
        "unit": {"type": "string"},
        "optimal": {"type": "boolean", "default": False},
    }, required=["columns"]),
    status="implemented",
)
def set_column_width_live(columns: List[int], sheet: Optional[str] = None, width: Optional[float] = None,
                           unit: Optional[str] = None, optimal: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_column_width(doc, columns, sheet, width, unit, optimal)
        return envelope.build_success(result={"columns": columns}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="hide_rows_live",
    priority="P2",
    purpose="Hide rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
    status="implemented",
)
def hide_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.hide_rows(doc, rows, sheet)
        return envelope.build_success(result={"rows": rows}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="show_rows_live",
    priority="P2",
    purpose="Show rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
    status="implemented",
)
def show_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.show_rows(doc, rows, sheet)
        return envelope.build_success(result={"rows": rows}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="hide_columns_live",
    priority="P2",
    purpose="Hide columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
    status="implemented",
)
def hide_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.hide_columns(doc, columns, sheet)
        return envelope.build_success(result={"columns": columns}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="show_columns_live",
    priority="P2",
    purpose="Show columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
    status="implemented",
)
def show_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.show_columns(doc, columns, sheet)
        return envelope.build_success(result={"columns": columns}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="freeze_panes_live",
    priority="P1",
    purpose="Freeze rows/columns at a cell boundary.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
    }, required=["cell"]),
    status="implemented",
)
def freeze_panes_live(cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.freeze_panes(doc, cell, sheet)
        return envelope.build_success(result={"frozen_at": cell}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="unfreeze_panes_live",
    priority="P1",
    purpose="Remove freeze panes.",
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def unfreeze_panes_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.unfreeze_panes(doc, sheet)
        return envelope.build_success(result={"unfrozen": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_freeze_panes_live",
    priority="P1",
    purpose=(
        "Return the current freeze-panes state -- Brian's new-tools "
        "assignment priority #12, the getter freeze_panes_live/"
        "unfreeze_panes_live never had. sheet omitted -> the active "
        "sheet; reading a non-active sheet's freeze state does not "
        "change which sheet is active afterward."
    ),
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def get_freeze_panes_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_freeze_panes(doc, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="recalculate_live",
    priority="P1",
    purpose="Recalculate current workbook or selected range if supported.",
    parameters=schema({"hard": {"type": "boolean", "default": False}}),
    status="implemented",
)
def recalculate_live(hard: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.recalculate(doc, hard)
        return envelope.build_success(result={"hard": hard}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="evaluate_formula_live",
    priority="P2",
    purpose="Evaluate a Calc formula/expression in workbook context without permanently writing it.",
    parameters=schema({
        "formula": {"type": "string"},
        "sheet": {"type": "string"},
    }, required=["formula"]),
    status="implemented",
)
def evaluate_formula_live(formula: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.evaluate_formula(doc, formula, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_formula_dependencies_live",
    priority="P2",
    purpose="Return precedents/dependents for cell/range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "direction": {"type": "string", "enum": ["precedents", "dependents", "both"], "default": "both"},
    }, required=["range"]),
    status="implemented",
)
def get_formula_dependencies_live(range: str, sheet: Optional[str] = None, direction: str = "both") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_formula_dependencies(doc, range, sheet, direction)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_formula_errors_live",
    priority="P2",
    purpose="Scan range/workbook for formula error cells.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
    status="implemented",
)
def get_formula_errors_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        errors = ctx.uno_bridge.get_formula_errors(doc, sheet, range)
        return envelope.build_success(result={"errors": errors, "count": len(errors)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
