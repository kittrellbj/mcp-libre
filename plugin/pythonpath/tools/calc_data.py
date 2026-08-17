"""
Phase C scaffold: Calc - data management, analysis, pivots, validation,
external data.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Calc - data management, analysis, pivots, validation, external data"
(scope: Calc). No tools in this section are marked "(existing)"; all 42
rows in the spec table are scaffolded here (matches the plan doc's
running-total estimate of 42 for this section).

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="list_named_ranges_live",
    priority="P1",
    purpose="List workbook/sheet named ranges and expressions.",
    parameters=schema({"scope": {"type": "string"}}),
)
def list_named_ranges_live(scope: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_named_ranges_live", start)


@register_tool(
    name="create_named_range_live",
    priority="P1",
    purpose="Create named range/expression.",
    parameters=schema({
        "name": {"type": "string"},
        "refers_to": {"type": "string"},
        "scope": {"type": "string"},
    }, required=["name", "refers_to"]),
)
def create_named_range_live(name: str, refers_to: str, scope: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_named_range_live", start)


@register_tool(
    name="update_named_range_live",
    priority="P1",
    purpose="Update named range expression/position.",
    parameters=schema({
        "name": {"type": "string"},
        "refers_to": {"type": "string"},
    }, required=["name", "refers_to"]),
)
def update_named_range_live(name: str, refers_to: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("update_named_range_live", start)


@register_tool(
    name="delete_named_range_live",
    priority="P1",
    purpose="Delete named range.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
)
def delete_named_range_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_named_range_live", start)


@register_tool(
    name="sort_range_live",
    priority="P1",
    purpose="Sort range by multiple keys.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "keys": {"type": "array", "items": {"type": "object"}},
        "has_header": {"type": "boolean"},
    }, required=["range", "keys"]),
)
def sort_range_live(range: str, keys: List[Dict[str, Any]], sheet: Optional[str] = None,
                     has_header: Optional[bool] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("sort_range_live", start)


@register_tool(
    name="apply_filter_live",
    priority="P1",
    purpose="Apply standard/advanced filter conditions.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "conditions": {"type": "array", "items": {"type": "object"}},
        "options": {"type": "object"},
    }, required=["range", "conditions"]),
)
def apply_filter_live(range: str, conditions: List[Dict[str, Any]], sheet: Optional[str] = None,
                       options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("apply_filter_live", start)


@register_tool(
    name="clear_filter_live",
    priority="P1",
    purpose="Remove active filter from range/database range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
)
def clear_filter_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_filter_live", start)


@register_tool(
    name="get_filter_state_live",
    priority="P2",
    purpose="Return active filter descriptor/conditions.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
)
def get_filter_state_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_filter_state_live", start)


@register_tool(
    name="list_conditional_formats_live",
    priority="P1",
    purpose="List conditional formatting rules.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
)
def list_conditional_formats_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_conditional_formats_live", start)


@register_tool(
    name="add_conditional_format_live",
    priority="P1",
    purpose="Add conditional formatting rule.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "rule": {"type": "object"},
        "style": {"type": "string"},
    }, required=["range", "rule"]),
)
def add_conditional_format_live(range: str, rule: Dict[str, Any], sheet: Optional[str] = None,
                                 style: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("add_conditional_format_live", start)


@register_tool(
    name="update_conditional_format_live",
    priority="P2",
    purpose="Update rule.",
    parameters=schema({
        "rule_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["rule_id", "properties"]),
)
def update_conditional_format_live(rule_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("update_conditional_format_live", start)


@register_tool(
    name="delete_conditional_format_live",
    priority="P1",
    purpose="Delete rule.",
    parameters=schema({"rule_id": {"type": "string"}}, required=["rule_id"]),
)
def delete_conditional_format_live(rule_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_conditional_format_live", start)


@register_tool(
    name="get_data_validation_live",
    priority="P1",
    purpose="Get validation rule for range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
)
def get_data_validation_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_data_validation_live", start)


@register_tool(
    name="set_data_validation_live",
    priority="P1",
    purpose="Set list/range/custom/numeric/date validation and messages.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "rule": {"type": "object"},
    }, required=["range", "rule"]),
)
def set_data_validation_live(range: str, rule: Dict[str, Any], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_data_validation_live", start)


@register_tool(
    name="clear_data_validation_live",
    priority="P1",
    purpose="Clear validation.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
)
def clear_data_validation_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_data_validation_live", start)


@register_tool(
    name="create_subtotals_live",
    priority="P2",
    purpose="Create grouped subtotals.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "group_columns": {"type": "array", "items": {"type": "integer"}},
        "subtotal_specs": {"type": "array", "items": {"type": "object"}},
    }, required=["range", "group_columns", "subtotal_specs"]),
)
def create_subtotals_live(range: str, group_columns: List[int], subtotal_specs: List[Dict[str, Any]],
                           sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_subtotals_live", start)


@register_tool(
    name="remove_subtotals_live",
    priority="P2",
    purpose="Remove subtotal structure.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
)
def remove_subtotals_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("remove_subtotals_live", start)


@register_tool(
    name="list_pivot_tables_live",
    priority="P1",
    purpose="List DataPilot/pivot tables.",
    parameters=schema({"sheet": {"type": "string"}}),
)
def list_pivot_tables_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_pivot_tables_live", start)


@register_tool(
    name="create_pivot_table_live",
    priority="P1",
    purpose="Create pivot/DataPilot from source range.",
    parameters=schema({
        "source": {"type": "string"},
        "destination": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "string"}},
        "columns": {"type": "array", "items": {"type": "string"}},
        "data_fields": {"type": "array", "items": {"type": "object"}},
        "filters": {"type": "array", "items": {"type": "string"}},
    }, required=["source", "destination", "rows", "columns", "data_fields"]),
)
def create_pivot_table_live(source: str, destination: str, rows: List[str], columns: List[str],
                             data_fields: List[Dict[str, Any]],
                             filters: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_pivot_table_live", start)


@register_tool(
    name="get_pivot_table_live",
    priority="P1",
    purpose="Return source/output ranges and field layout.",
    parameters=schema({"pivot_id": {"type": "string"}}, required=["pivot_id"]),
)
def get_pivot_table_live(pivot_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_pivot_table_live", start)


@register_tool(
    name="update_pivot_table_live",
    priority="P1",
    purpose="Change source/layout/options.",
    parameters=schema({
        "pivot_id": {"type": "string"},
        "configuration": {"type": "object"},
    }, required=["pivot_id", "configuration"]),
)
def update_pivot_table_live(pivot_id: str, configuration: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("update_pivot_table_live", start)


@register_tool(
    name="refresh_pivot_table_live",
    priority="P1",
    purpose="Refresh pivot.",
    parameters=schema({"pivot_id": {"type": "string"}}, required=["pivot_id"]),
)
def refresh_pivot_table_live(pivot_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("refresh_pivot_table_live", start)


@register_tool(
    name="delete_pivot_table_live",
    priority="P1",
    purpose="Delete pivot output/table.",
    parameters=schema({"pivot_id": {"type": "string"}}, required=["pivot_id"]),
)
def delete_pivot_table_live(pivot_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_pivot_table_live", start)


@register_tool(
    name="list_scenarios_live",
    priority="P2",
    purpose="List Calc scenarios.",
    parameters=schema({"sheet": {"type": "string"}}),
)
def list_scenarios_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_scenarios_live", start)


@register_tool(
    name="create_scenario_live",
    priority="P2",
    purpose="Create scenario from ranges/values.",
    parameters=schema({
        "name": {"type": "string"},
        "ranges": {"type": "array", "items": {"type": "string"}},
        "comment": {"type": "string"},
        "options": {"type": "object"},
    }, required=["name", "ranges"]),
)
def create_scenario_live(name: str, ranges: List[str], comment: Optional[str] = None,
                          options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_scenario_live", start)


@register_tool(
    name="apply_scenario_live",
    priority="P2",
    purpose="Apply scenario.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
)
def apply_scenario_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("apply_scenario_live", start)


@register_tool(
    name="delete_scenario_live",
    priority="P2",
    purpose="Delete scenario.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
)
def delete_scenario_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_scenario_live", start)


@register_tool(
    name="goal_seek_live",
    priority="P1",
    purpose="Perform goal seek.",
    parameters=schema({
        "formula_cell": {"type": "string"},
        "target_value": {"type": "number"},
        "variable_cell": {"type": "string"},
    }, required=["formula_cell", "target_value", "variable_cell"]),
)
def goal_seek_live(formula_cell: str, target_value: float, variable_cell: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("goal_seek_live", start)


@register_tool(
    name="solver_solve_live",
    priority="P2",
    purpose="Solve constrained optimization when solver service is available.",
    parameters=schema({
        "objective_cell": {"type": "string"},
        "optimize": {"type": "string", "enum": ["min", "max", "value"]},
        "variable_cells": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "object"}},
    }, required=["objective_cell", "optimize", "variable_cells"]),
)
def solver_solve_live(objective_cell: str, optimize: str, variable_cells: List[str],
                       constraints: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("solver_solve_live", start)


@register_tool(
    name="list_database_ranges_live",
    priority="P2",
    purpose="List database ranges and sort/filter/subtotal descriptors.",
)
def list_database_ranges_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_database_ranges_live", start)


@register_tool(
    name="create_database_range_live",
    priority="P2",
    purpose="Create named database range.",
    parameters=schema({
        "name": {"type": "string"},
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["name", "sheet", "range"]),
)
def create_database_range_live(name: str, sheet: str, range: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_database_range_live", start)


@register_tool(
    name="delete_database_range_live",
    priority="P2",
    purpose="Delete database range.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
)
def delete_database_range_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_database_range_live", start)


@register_tool(
    name="list_external_links_live",
    priority="P2",
    purpose="List area/external links and refresh state.",
)
def list_external_links_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_external_links_live", start)


@register_tool(
    name="create_external_link_live",
    priority="P3",
    purpose="Link external spreadsheet/data area.",
    parameters=schema({
        "source_url": {"type": "string"},
        "source_area": {"type": "string"},
        "destination": {"type": "string"},
        "filter": {"type": "string"},
    }, required=["source_url", "source_area", "destination"]),
)
def create_external_link_live(source_url: str, source_area: str, destination: str,
                               filter: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_external_link_live", start)


@register_tool(
    name="refresh_external_link_live",
    priority="P2",
    purpose="Refresh external link.",
    parameters=schema({"link_id": {"type": "string"}}, required=["link_id"]),
)
def refresh_external_link_live(link_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("refresh_external_link_live", start)


@register_tool(
    name="delete_external_link_live",
    priority="P2",
    purpose="Remove external link.",
    parameters=schema({
        "link_id": {"type": "string"},
        "keep_values": {"type": "boolean", "default": True},
    }, required=["link_id"]),
)
def delete_external_link_live(link_id: str, keep_values: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_external_link_live", start)


@register_tool(
    name="import_csv_to_range_live",
    priority="P1",
    purpose="Import CSV/TSV into a Calc range with delimiter/encoding/type options.",
    parameters=schema({
        "file_path": {"type": "string"},
        "destination": {"type": "string"},
        "delimiter": {"type": "string", "default": ","},
        "encoding": {"type": "string", "default": "utf-8"},
        "options": {"type": "object"},
    }, required=["file_path", "destination"]),
)
def import_csv_to_range_live(file_path: str, destination: str, delimiter: str = ",", encoding: str = "utf-8",
                              options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("import_csv_to_range_live", start)


@register_tool(
    name="export_range_to_csv_live",
    priority="P1",
    purpose="Export range to CSV/TSV.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "file_path": {"type": "string"},
        "delimiter": {"type": "string", "default": ","},
        "encoding": {"type": "string", "default": "utf-8"},
    }, required=["range", "file_path"]),
)
def export_range_to_csv_live(range: str, file_path: str, sheet: Optional[str] = None, delimiter: str = ",",
                              encoding: str = "utf-8") -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("export_range_to_csv_live", start)


@register_tool(
    name="group_rows_live",
    priority="P2",
    purpose="Create outline group for rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
)
def group_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("group_rows_live", start)


@register_tool(
    name="ungroup_rows_live",
    priority="P2",
    purpose="Remove row outline group.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
)
def ungroup_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("ungroup_rows_live", start)


@register_tool(
    name="group_columns_live",
    priority="P2",
    purpose="Create outline group for columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
)
def group_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("group_columns_live", start)


@register_tool(
    name="ungroup_columns_live",
    priority="P2",
    purpose="Remove column outline group.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
)
def ungroup_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("ungroup_columns_live", start)
