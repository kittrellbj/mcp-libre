"""
Phase C scaffold: Calc - sheets, cells, ranges, formulas, layout.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Calc - sheets, cells, ranges, formulas, layout" (scope: Calc). No tools in
this section are marked "(existing)"; all 42 are scaffolded here.

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="list_sheets_live",
    priority="P1",
    purpose="List sheets with index/name/visibility/protection.",
)
def list_sheets_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_sheets_live", start)


@register_tool(
    name="get_active_sheet_live",
    priority="P1",
    purpose="Return active sheet.",
)
def get_active_sheet_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_active_sheet_live", start)


@register_tool(
    name="activate_sheet_live",
    priority="P1",
    purpose="Activate sheet by name/index.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
)
def activate_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("activate_sheet_live", start)


@register_tool(
    name="insert_sheet_live",
    priority="P1",
    purpose="Insert new sheet.",
    parameters=schema({
        "name": {"type": "string"},
        "position": {"type": "integer"},
    }, required=["name"]),
)
def insert_sheet_live(name: str, position: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_sheet_live", start)


@register_tool(
    name="delete_sheet_live",
    priority="P1",
    purpose="Delete sheet.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
)
def delete_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_sheet_live", start)


@register_tool(
    name="rename_sheet_live",
    priority="P1",
    purpose="Rename sheet.",
    parameters=schema({
        "sheet": {"type": "string"},
        "new_name": {"type": "string"},
    }, required=["sheet", "new_name"]),
)
def rename_sheet_live(sheet: str, new_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("rename_sheet_live", start)


@register_tool(
    name="move_sheet_live",
    priority="P1",
    purpose="Move sheet position.",
    parameters=schema({
        "sheet": {"type": "string"},
        "destination_index": {"type": "integer"},
    }, required=["sheet", "destination_index"]),
)
def move_sheet_live(sheet: str, destination_index: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("move_sheet_live", start)


@register_tool(
    name="copy_sheet_live",
    priority="P1",
    purpose="Copy sheet within workbook.",
    parameters=schema({
        "sheet": {"type": "string"},
        "new_name": {"type": "string"},
        "destination_index": {"type": "integer"},
    }, required=["sheet", "new_name"]),
)
def copy_sheet_live(sheet: str, new_name: str, destination_index: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("copy_sheet_live", start)


@register_tool(
    name="hide_sheet_live",
    priority="P1",
    purpose="Hide sheet.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
)
def hide_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("hide_sheet_live", start)


@register_tool(
    name="show_sheet_live",
    priority="P1",
    purpose="Show sheet.",
    parameters=schema({"sheet": {"type": "string"}}, required=["sheet"]),
)
def show_sheet_live(sheet: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("show_sheet_live", start)


@register_tool(
    name="get_cell_live",
    priority="P1",
    purpose="Return value/formula/display/format/error for one cell.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
    }, required=["cell"]),
)
def get_cell_live(cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_cell_live", start)


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
)
def set_cell_live(cell: str, sheet: Optional[str] = None, value: Optional[Any] = None,
                   formula: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_cell_live", start)


@register_tool(
    name="get_range_live",
    priority="P1",
    purpose="Read rectangular range as values/formulas/display strings.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "mode": {"type": "string", "enum": ["values", "formulas", "display", "all"], "default": "values"},
    }, required=["range"]),
)
def get_range_live(range: str, sheet: Optional[str] = None, mode: str = "values") -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_range_live", start)


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
)
def set_range_live(values: List[List[Any]], sheet: Optional[str] = None, range: Optional[str] = None,
                    start_cell: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_range_live", start)


@register_tool(
    name="clear_range_live",
    priority="P1",
    purpose="Clear selected contents/types/formats/annotations.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "what": {"type": "string", "default": "contents"},
    }, required=["range"]),
)
def clear_range_live(range: str, sheet: Optional[str] = None, what: str = "contents") -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_range_live", start)


@register_tool(
    name="get_used_range_live",
    priority="P1",
    purpose="Return used area bounds and optional non-empty count.",
    parameters=schema({"sheet": {"type": "string"}}),
)
def get_used_range_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_used_range_live", start)


@register_tool(
    name="insert_rows_live",
    priority="P1",
    purpose="Insert rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
)
def insert_rows_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_rows_live", start)


@register_tool(
    name="delete_rows_live",
    priority="P1",
    purpose="Delete rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
)
def delete_rows_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_rows_live", start)


@register_tool(
    name="insert_columns_live",
    priority="P1",
    purpose="Insert columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
)
def insert_columns_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_columns_live", start)


@register_tool(
    name="delete_columns_live",
    priority="P1",
    purpose="Delete columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["index"]),
)
def delete_columns_live(index: int, sheet: Optional[str] = None, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_columns_live", start)


@register_tool(
    name="insert_cells_live",
    priority="P2",
    purpose="Insert cells and shift right/down.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "shift": {"type": "string"},
    }, required=["range", "shift"]),
)
def insert_cells_live(range: str, shift: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_cells_live", start)


@register_tool(
    name="delete_cells_live",
    priority="P2",
    purpose="Delete cells and shift left/up.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "shift": {"type": "string"},
    }, required=["range", "shift"]),
)
def delete_cells_live(range: str, shift: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_cells_live", start)


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
)
def copy_range_live(source_range: str, dest_cell: str, source_sheet: Optional[str] = None,
                     dest_sheet: Optional[str] = None, include: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("copy_range_live", start)


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
)
def move_range_live(source_range: str, dest_cell: str, source_sheet: Optional[str] = None,
                     dest_sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("move_range_live", start)


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
)
def fill_series_live(range: str, direction: str, mode: str, sheet: Optional[str] = None,
                      start: Optional[Any] = None, step: Optional[float] = None,
                      end: Optional[Any] = None) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    return envelope.build_not_implemented("fill_series_live", start_time)


@register_tool(
    name="autofill_live",
    priority="P2",
    purpose="Extend source pattern/formulas into destination.",
    parameters=schema({
        "sheet": {"type": "string"},
        "source_range": {"type": "string"},
        "destination_range": {"type": "string"},
    }, required=["source_range", "destination_range"]),
)
def autofill_live(source_range: str, destination_range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("autofill_live", start)


@register_tool(
    name="set_range_format_live",
    priority="P1",
    purpose="Set font/alignment/wrap/borders/background/number format/protection.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["range", "properties"]),
)
def set_range_format_live(range: str, properties: Dict[str, Any], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_range_format_live", start)


@register_tool(
    name="get_range_format_live",
    priority="P2",
    purpose="Return effective range formatting summary.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
)
def get_range_format_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_range_format_live", start)


@register_tool(
    name="merge_cells_live",
    priority="P1",
    purpose="Merge range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "center": {"type": "boolean", "default": False},
    }, required=["range"]),
)
def merge_cells_live(range: str, sheet: Optional[str] = None, center: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("merge_cells_live", start)


@register_tool(
    name="unmerge_cells_live",
    priority="P1",
    purpose="Unmerge range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
)
def unmerge_cells_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("unmerge_cells_live", start)


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
)
def set_row_height_live(rows: List[int], sheet: Optional[str] = None, height: Optional[float] = None,
                         unit: Optional[str] = None, optimal: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_row_height_live", start)


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
)
def set_column_width_live(columns: List[int], sheet: Optional[str] = None, width: Optional[float] = None,
                           unit: Optional[str] = None, optimal: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_column_width_live", start)


@register_tool(
    name="hide_rows_live",
    priority="P2",
    purpose="Hide rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
)
def hide_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("hide_rows_live", start)


@register_tool(
    name="show_rows_live",
    priority="P2",
    purpose="Show rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
)
def show_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("show_rows_live", start)


@register_tool(
    name="hide_columns_live",
    priority="P2",
    purpose="Hide columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
)
def hide_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("hide_columns_live", start)


@register_tool(
    name="show_columns_live",
    priority="P2",
    purpose="Show columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
)
def show_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("show_columns_live", start)


@register_tool(
    name="freeze_panes_live",
    priority="P1",
    purpose="Freeze rows/columns at a cell boundary.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
    }, required=["cell"]),
)
def freeze_panes_live(cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("freeze_panes_live", start)


@register_tool(
    name="unfreeze_panes_live",
    priority="P1",
    purpose="Remove freeze panes.",
    parameters=schema({"sheet": {"type": "string"}}),
)
def unfreeze_panes_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("unfreeze_panes_live", start)


@register_tool(
    name="recalculate_live",
    priority="P1",
    purpose="Recalculate current workbook or selected range if supported.",
    parameters=schema({"hard": {"type": "boolean", "default": False}}),
)
def recalculate_live(hard: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("recalculate_live", start)


@register_tool(
    name="evaluate_formula_live",
    priority="P2",
    purpose="Evaluate a Calc formula/expression in workbook context without permanently writing it.",
    parameters=schema({
        "formula": {"type": "string"},
        "sheet": {"type": "string"},
    }, required=["formula"]),
)
def evaluate_formula_live(formula: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("evaluate_formula_live", start)


@register_tool(
    name="get_formula_dependencies_live",
    priority="P2",
    purpose="Return precedents/dependents for cell/range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "direction": {"type": "string", "enum": ["precedents", "dependents", "both"], "default": "both"},
    }, required=["range"]),
)
def get_formula_dependencies_live(range: str, sheet: Optional[str] = None, direction: str = "both") -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_formula_dependencies_live", start)


@register_tool(
    name="get_formula_errors_live",
    priority="P2",
    purpose="Scan range/workbook for formula error cells.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
)
def get_formula_errors_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_formula_errors_live", start)
