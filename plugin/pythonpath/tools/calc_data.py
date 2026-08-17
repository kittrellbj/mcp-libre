"""
Calc - data management, analysis, pivots, validation, external data --
real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Calc - data management, analysis, pivots, validation, external data"
(scope: Calc). No tools in this section are marked "(existing)"; all 42
were scaffolded stubs before this pass.

39 of 42 tools are real; create_external_link_live/
refresh_external_link_live/delete_external_link_live stay status="stub"
-- doc.ExternalDocLinks' write side (adding a new link, vs.
list_external_links_live's read-only enumeration, which IS real) wasn't
exploration-tested this pass, same honest-scope-limit precedent as
charts.py's add_chart_series_live and impress.py's add_animation_live.

Conditional format rules and pivot tables resolve `rule_id`/`pivot_id`
through the same ObjectRegistry drawing_objects.py established, but with
a live-verified caveat neither shapes nor documents have: legacy
ConditionalFormat entries and XDataPilotTable objects do NOT compare
equal to themselves across two separate UNO fetches (unlike shapes/
documents), so registering the raw object minted a fresh, non-matching
id on every list call and broke update/delete outright. Conditional
format rules are fixed for real: list_conditional_formats_live/
add_conditional_format_live register a (sheet_name, range_string, index)
address instead of a raw entry object, re-resolved fresh on every call
-- see uno_bridge.py's list_conditional_format_entries() docstring for
the full story and the honest index-shift caveat that approach still
carries.

**Pivot tables have the narrower version of the same gap, NOT fixed the
same way -- READ THIS BEFORE CALLING list_pivot_tables_live twice:**
list_pivot_tables_live still registers the raw XDataPilotTable object
(get_pivot_table_live/update_pivot_table_live/refresh_pivot_table_live/
delete_pivot_table_live all operate on that held reference directly --
reading .Name/.OutputRange or calling .refresh() -- never re-locating it
by comparison, so every pivot_id it returns keeps working correctly for
its own later calls). But because the object itself doesn't compare
equal across fetches, calling list_pivot_tables_live again for the SAME
underlying pivot table mints a DIFFERENT pivot_id, not the same one --
there is no way to tell from the ids alone that two list calls returned
"the same" pivot table. A caller that lists once, keeps that pivot_id,
and uses it later is fine; a caller that lists twice and compares
pivot_ids to check "is this still the same pivot" will get a false
negative every time.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .drawing_objects import _get_object_registry
from .registry import register_tool, schema


@register_tool(
    name="list_named_ranges_live",
    priority="P1",
    purpose="List workbook/sheet named ranges and expressions.",
    parameters=schema({"scope": {"type": "string"}}),
    status="implemented",
)
def list_named_ranges_live(scope: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ranges = ctx.uno_bridge.list_named_ranges(doc, scope)
        return envelope.build_success(result={"named_ranges": ranges, "count": len(ranges)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_named_range_live",
    priority="P1",
    purpose="Create named range/expression.",
    parameters=schema({
        "name": {"type": "string"},
        "refers_to": {"type": "string"},
        "scope": {"type": "string"},
    }, required=["name", "refers_to"]),
    status="implemented",
)
def create_named_range_live(name: str, refers_to: str, scope: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_named_range(doc, name, refers_to, scope)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_named_range_live",
    priority="P1",
    purpose="Update named range expression/position.",
    parameters=schema({
        "name": {"type": "string"},
        "refers_to": {"type": "string"},
    }, required=["name", "refers_to"]),
    status="implemented",
)
def update_named_range_live(name: str, refers_to: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.update_named_range(doc, name, refers_to)
        return envelope.build_success(result={"refers_to": refers_to}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_named_range_live",
    priority="P1",
    purpose="Delete named range.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def delete_named_range_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_named_range(doc, name)
        return envelope.build_success(result={"deleted": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def sort_range_live(range: str, keys: List[Dict[str, Any]], sheet: Optional[str] = None,
                     has_header: Optional[bool] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.sort_range(doc, range, keys, sheet, has_header)
        return envelope.build_success(result={"sorted": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def apply_filter_live(range: str, conditions: List[Dict[str, Any]], sheet: Optional[str] = None,
                       options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.apply_filter(doc, range, conditions, sheet, options)
        return envelope.build_success(result={"filtered": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_filter_live",
    priority="P1",
    purpose="Remove active filter from range/database range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
    status="implemented",
)
def clear_filter_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_filter(doc, sheet, range)
        return envelope.build_success(result={"cleared": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_filter_state_live",
    priority="P2",
    purpose="Return active filter descriptor/conditions.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
    status="implemented",
)
def get_filter_state_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_filter_state(doc, sheet, range)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_conditional_formats_live",
    priority="P1",
    purpose="List conditional formatting rules.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
    status="implemented",
)
def list_conditional_formats_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        entries = ctx.uno_bridge.list_conditional_format_entries(doc, sheet, range)
        summaries = [
            ctx.uno_bridge.get_conditional_format_summary(doc, entry_ref, object_registry.register_object(entry_ref))
            for entry_ref in entries
        ]
        return envelope.build_success(result={"rules": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def add_conditional_format_live(range: str, rule: Dict[str, Any], sheet: Optional[str] = None,
                                 style: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        entry_ref = ctx.uno_bridge.add_conditional_format(doc, range, rule, sheet, style)
        rule_id = object_registry.register_object(entry_ref)
        summary = ctx.uno_bridge.get_conditional_format_summary(doc, entry_ref, rule_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_conditional_format_live",
    priority="P2",
    purpose="Update rule.",
    parameters=schema({
        "rule_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["rule_id", "properties"]),
    status="implemented",
)
def update_conditional_format_live(rule_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        entry_ref = _get_object_registry(ctx, resolved_id).resolve_object(rule_id)
        applied = ctx.uno_bridge.update_conditional_format(doc, entry_ref, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_conditional_format_live",
    priority="P1",
    purpose="Delete rule.",
    parameters=schema({"rule_id": {"type": "string"}}, required=["rule_id"]),
    status="implemented",
)
def delete_conditional_format_live(rule_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        entry_ref = object_registry.resolve_object(rule_id)
        ctx.uno_bridge.delete_conditional_format(doc, entry_ref)
        object_registry.unregister_object(rule_id)
        return envelope.build_success(result={"deleted": rule_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_data_validation_live",
    priority="P1",
    purpose="Get validation rule for range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
    status="implemented",
)
def get_data_validation_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_data_validation(doc, range, sheet)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_data_validation_live",
    priority="P1",
    purpose="Set list/range/custom/numeric/date validation and messages.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "rule": {"type": "object"},
    }, required=["range", "rule"]),
    status="implemented",
)
def set_data_validation_live(range: str, rule: Dict[str, Any], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_data_validation(doc, range, rule, sheet)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_data_validation_live",
    priority="P1",
    purpose="Clear validation.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
    status="implemented",
)
def clear_data_validation_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_data_validation(doc, range, sheet)
        return envelope.build_success(result={"cleared": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def create_subtotals_live(range: str, group_columns: List[int], subtotal_specs: List[Dict[str, Any]],
                           sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.create_subtotals(doc, range, group_columns, subtotal_specs, sheet)
        return envelope.build_success(result={"range": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="remove_subtotals_live",
    priority="P2",
    purpose="Remove subtotal structure.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["range"]),
    status="implemented",
)
def remove_subtotals_live(range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.remove_subtotals(doc, range, sheet)
        return envelope.build_success(result={"range": range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_pivot_tables_live",
    priority="P1",
    purpose=(
        "List DataPilot/pivot tables. CAVEAT: calling this twice for the same "
        "pivot table returns a different pivot_id each time (a live-verified "
        "LibreOffice identity-comparison gap, not a bug in this tool) -- each "
        "returned id still works correctly for get/update/refresh/delete, but "
        "ids from two separate list calls cannot be compared to check whether "
        "they refer to the same pivot table. Keep the pivot_id from whichever "
        "call you actually need, don't re-list and match by id."
    ),
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def list_pivot_tables_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        pivots = ctx.uno_bridge.list_pivot_tables(doc, sheet)
        summaries = [
            ctx.uno_bridge.get_pivot_table_summary(doc, pivot, object_registry.register_object(pivot))
            for pivot in pivots
        ]
        return envelope.build_success(result={"pivot_tables": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def create_pivot_table_live(source: str, destination: str, rows: List[str], columns: List[str],
                             data_fields: List[Dict[str, Any]],
                             filters: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        pivot = ctx.uno_bridge.create_pivot_table(doc, source, destination, rows, columns, data_fields, filters)
        pivot_id = object_registry.register_object(pivot)
        summary = ctx.uno_bridge.get_pivot_table_summary(doc, pivot, pivot_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_pivot_table_live",
    priority="P1",
    purpose="Return source/output ranges and field layout.",
    parameters=schema({"pivot_id": {"type": "string"}}, required=["pivot_id"]),
    status="implemented",
)
def get_pivot_table_live(pivot_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        pivot = _get_object_registry(ctx, resolved_id).resolve_object(pivot_id)
        result = ctx.uno_bridge.get_pivot_table_summary(doc, pivot, pivot_id)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_pivot_table_live",
    priority="P1",
    purpose="Change source/layout/options.",
    parameters=schema({
        "pivot_id": {"type": "string"},
        "configuration": {"type": "object"},
    }, required=["pivot_id", "configuration"]),
    status="implemented",
)
def update_pivot_table_live(pivot_id: str, configuration: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        pivot = _get_object_registry(ctx, resolved_id).resolve_object(pivot_id)
        applied = ctx.uno_bridge.update_pivot_table(pivot, configuration)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="refresh_pivot_table_live",
    priority="P1",
    purpose="Refresh pivot.",
    parameters=schema({"pivot_id": {"type": "string"}}, required=["pivot_id"]),
    status="implemented",
)
def refresh_pivot_table_live(pivot_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        pivot = _get_object_registry(ctx, resolved_id).resolve_object(pivot_id)
        ctx.uno_bridge.refresh_pivot_table(pivot)
        return envelope.build_success(result={"refreshed": pivot_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_pivot_table_live",
    priority="P1",
    purpose="Delete pivot output/table.",
    parameters=schema({"pivot_id": {"type": "string"}}, required=["pivot_id"]),
    status="implemented",
)
def delete_pivot_table_live(pivot_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        pivot = object_registry.resolve_object(pivot_id)
        ctx.uno_bridge.delete_pivot_table(doc, pivot)
        object_registry.unregister_object(pivot_id)
        return envelope.build_success(result={"deleted": pivot_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_scenarios_live",
    priority="P2",
    purpose="List Calc scenarios.",
    parameters=schema({"sheet": {"type": "string"}}),
    status="implemented",
)
def list_scenarios_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        scenarios = ctx.uno_bridge.list_scenarios(doc, sheet)
        return envelope.build_success(result={"scenarios": scenarios, "count": len(scenarios)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def create_scenario_live(name: str, ranges: List[str], comment: Optional[str] = None,
                          options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_scenario(doc, name, ranges, comment, options)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="apply_scenario_live",
    priority="P2",
    purpose="Apply scenario.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def apply_scenario_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.apply_scenario(doc, name)
        return envelope.build_success(result={"applied": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_scenario_live",
    priority="P2",
    purpose="Delete scenario.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def delete_scenario_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_scenario(doc, name)
        return envelope.build_success(result={"deleted": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="goal_seek_live",
    priority="P1",
    purpose="Perform goal seek.",
    parameters=schema({
        "formula_cell": {"type": "string"},
        "target_value": {"type": "number"},
        "variable_cell": {"type": "string"},
    }, required=["formula_cell", "target_value", "variable_cell"]),
    status="implemented",
)
def goal_seek_live(formula_cell: str, target_value: float, variable_cell: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.goal_seek(doc, formula_cell, target_value, variable_cell)
        warnings = [] if result["converged"] else ["Goal seek did not converge -- the variable cell was left unchanged."]
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def solver_solve_live(objective_cell: str, optimize: str, variable_cells: List[str],
                       constraints: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.solver_solve(doc, objective_cell, optimize, variable_cells, constraints)
        warnings = [] if result["success"] else ["Solver did not find a solution."]
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_database_ranges_live",
    priority="P2",
    purpose="List database ranges and sort/filter/subtotal descriptors.",
    status="implemented",
)
def list_database_ranges_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ranges = ctx.uno_bridge.list_database_ranges(doc)
        return envelope.build_success(result={"database_ranges": ranges, "count": len(ranges)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_database_range_live",
    priority="P2",
    purpose="Create named database range.",
    parameters=schema({
        "name": {"type": "string"},
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }, required=["name", "sheet", "range"]),
    status="implemented",
)
def create_database_range_live(name: str, sheet: str, range: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_database_range(doc, name, sheet, range)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_database_range_live",
    priority="P2",
    purpose="Delete database range.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def delete_database_range_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_database_range(doc, name)
        return envelope.build_success(result={"deleted": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_external_links_live",
    priority="P2",
    purpose="List area/external links and refresh state.",
    status="implemented",
)
def list_external_links_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        links = ctx.uno_bridge.list_external_links(doc)
        return envelope.build_success(result={"links": links, "count": len(links)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def import_csv_to_range_live(file_path: str, destination: str, delimiter: str = ",", encoding: str = "utf-8",
                              options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.import_csv_to_range(doc, file_path, destination, delimiter, encoding, options)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def export_range_to_csv_live(range: str, file_path: str, sheet: Optional[str] = None, delimiter: str = ",",
                              encoding: str = "utf-8") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.export_range_to_csv(doc, range, file_path, sheet, delimiter, encoding)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="group_rows_live",
    priority="P2",
    purpose="Create outline group for rows.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
    status="implemented",
)
def group_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.group_rows(doc, rows, sheet)
        return envelope.build_success(result={"grouped_rows": rows}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="ungroup_rows_live",
    priority="P2",
    purpose="Remove row outline group.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
    status="implemented",
)
def ungroup_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.ungroup_rows(doc, rows, sheet)
        return envelope.build_success(result={"ungrouped_rows": rows}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="group_columns_live",
    priority="P2",
    purpose="Create outline group for columns.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
    status="implemented",
)
def group_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.group_columns(doc, columns, sheet)
        return envelope.build_success(result={"grouped_columns": columns}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="ungroup_columns_live",
    priority="P2",
    purpose="Remove column outline group.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
    status="implemented",
)
def ungroup_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.ungroup_columns(doc, columns, sheet)
        return envelope.build_success(result={"ungrouped_columns": columns}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
