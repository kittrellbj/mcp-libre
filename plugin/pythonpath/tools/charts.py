"""
Charts and data visualizations -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Charts and data visualizations" (scope: Calc primarily; Writer/Impress/Draw
embedded charts). No tools in this section are marked "(existing)"; all 20
were scaffolded stubs before this pass.

Scope, deliberate (see uno_bridge.py's "-- Charts --" section docstring for
the full rationale): Calc-native embedded charts only this pass. `chart_id`
resolves via `XTablesSupplier.getCharts()`, the UNO-guaranteed-unique-Name
container docs/OBJECT_HANDLE_DESIGN.md already designed this exact
resolution for -- no ObjectRegistry needed, same category as sheets/Writer
tables. Every tool below therefore raises a documented `NotImplementedError`
(mapped to UNSUPPORTED_CAPABILITY by `_error_response`) when called against
a non-Calc document; extending to Writer/Impress/Draw embedded charts
(generic OLE2Shape wrapping a chart document, no dedicated named container)
is left for a follow-up.

`add_chart_series_live` stays a pure NOT_IMPLEMENTED stub (no `uno_bridge`
call at all) rather than a function with an always-raising real code path --
same precedent as drawing_objects.py's `insert_embedded_object_live`/
`activate_embedded_object_live`: building a new XDataSeries from raw
in-memory values (not a sheet range) needs XDataProvider data-sequence
construction that was not exploration-tested this pass. `create_chart_live`
and `set_chart_data_live` DO reach real UNO code in their common case
(explicit `source`/`source_range`); only their `data`-array branch raises,
so both keep `status="implemented"`.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


@register_tool(
    name="list_charts_live",
    priority="P1",
    purpose="List embedded charts and anchors.",
    parameters=schema({"container": {"type": "string"}}),
    status="implemented",
)
def list_charts_live(container: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        charts = ctx.uno_bridge.list_charts(doc, container)
        return envelope.build_success(result={"charts": charts, "count": len(charts)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_chart_live",
    priority="P1",
    purpose="Create chart from source range or explicit data.",
    parameters=schema({
        "chart_type": {"type": "string"},
        "source": {"type": "string"},
        "data": {"type": "array", "items": {"type": "array"}},
        "container": {"type": "string"},
        "position": {"type": "object"},
        "size": {"type": "object"},
    }, required=["chart_type"]),
    status="implemented",
)
def create_chart_live(chart_type: str, source: Optional[str] = None, data: Optional[List[List[Any]]] = None,
                       container: Optional[str] = None, position: Optional[Dict[str, Any]] = None,
                       size: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_chart(doc, chart_type, source, data, container, position, size)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_chart_live",
    priority="P1",
    purpose="Return chart type, data source, titles, axes, legend, series summary.",
    parameters=schema({"chart_id": {"type": "string"}}, required=["chart_id"]),
    status="implemented",
)
def get_chart_live(chart_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_chart(doc, chart_id)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_chart_live",
    priority="P1",
    purpose="Delete chart.",
    parameters=schema({"chart_id": {"type": "string"}}, required=["chart_id"]),
    status="implemented",
)
def delete_chart_live(chart_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_chart(doc, chart_id)
        return envelope.build_success(result={"deleted": chart_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_type_live",
    priority="P1",
    purpose="Change chart/diagram type and subtype.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "chart_type": {"type": "string"},
        "subtype": {"type": "string"},
    }, required=["chart_id", "chart_type"]),
    status="implemented",
)
def set_chart_type_live(chart_id: str, chart_type: str, subtype: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_chart_type(doc, chart_id, chart_type, subtype)
        return envelope.build_success(result={"chart_type": chart_type}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_data_live",
    priority="P1",
    purpose="Replace or retarget chart data.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "source_range": {"type": "string"},
        "data": {"type": "array", "items": {"type": "array"}},
        "categories": {"type": "array", "items": {"type": "string"}},
    }, required=["chart_id"]),
    status="implemented",
)
def set_chart_data_live(chart_id: str, source_range: Optional[str] = None, data: Optional[List[List[Any]]] = None,
                         categories: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_chart_data(doc, chart_id, source_range, data, categories)
        return envelope.build_success(result={"source_range": source_range}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_title_live",
    priority="P1",
    purpose="Set main/subtitle and formatting.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id"]),
    status="implemented",
)
def set_chart_title_live(chart_id: str, title: Optional[str] = None, subtitle: Optional[str] = None,
                          properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_title(doc, chart_id, title, subtitle, properties)
        skipped = sorted(set(properties or {}) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_legend_live",
    priority="P1",
    purpose="Show/hide/position/style legend.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "visible": {"type": "boolean"},
        "position": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id"]),
    status="implemented",
)
def set_chart_legend_live(chart_id: str, visible: Optional[bool] = None, position: Optional[str] = None,
                           properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_legend(doc, chart_id, visible, position, properties)
        skipped = sorted(set(properties or {}) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_chart_series_live",
    priority="P1",
    purpose="List data series, labels, ranges, colors, chart types.",
    parameters=schema({"chart_id": {"type": "string"}}, required=["chart_id"]),
    status="implemented",
)
def get_chart_series_live(chart_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        series = ctx.uno_bridge.get_chart_series(doc, chart_id)
        return envelope.build_success(result={"series": series, "count": len(series)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_series_live",
    priority="P1",
    purpose="Set series data/label/style and axis assignment.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "series_id", "properties"]),
    status="implemented",
)
def set_chart_series_live(chart_id: str, series_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_series(doc, chart_id, series_id, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_chart_series_live",
    priority="P2",
    purpose="Add a data series.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "values": {"type": "array", "items": {"type": "number"}},
        "label": {"type": "string"},
        "categories": {"type": "array", "items": {"type": "string"}},
    }, required=["chart_id", "values"]),
)
def add_chart_series_live(chart_id: str, values: List[float], label: Optional[str] = None,
                           categories: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("add_chart_series_live", start)


@register_tool(
    name="remove_chart_series_live",
    priority="P2",
    purpose="Remove a data series.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
    }, required=["chart_id", "series_id"]),
    status="implemented",
)
def remove_chart_series_live(chart_id: str, series_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.remove_chart_series(doc, chart_id, series_id)
        return envelope.build_success(result={"removed": series_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_axis_live",
    priority="P1",
    purpose="Configure axis visibility/title/min/max/scale/log/number format/grid.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "axis": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "axis", "properties"]),
    status="implemented",
)
def set_chart_axis_live(chart_id: str, axis: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_axis(doc, chart_id, axis, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_data_labels_live",
    priority="P2",
    purpose="Configure value/category/percent labels.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "properties"]),
    status="implemented",
)
def set_chart_data_labels_live(chart_id: str, properties: Dict[str, Any],
                                series_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_data_labels(doc, chart_id, properties, series_id)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_gridlines_live",
    priority="P2",
    purpose="Configure major/minor gridlines.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "axis": {"type": "string"},
        "major": {"type": "boolean"},
        "minor": {"type": "boolean"},
        "properties": {"type": "object"},
    }, required=["chart_id", "axis"]),
    status="implemented",
)
def set_chart_gridlines_live(chart_id: str, axis: str, major: Optional[bool] = None,
                              minor: Optional[bool] = None,
                              properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_gridlines(doc, chart_id, axis, major, minor, properties)
        skipped = sorted(set(properties or {}) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_chart_trendline_live",
    priority="P2",
    purpose="Add supported regression/trendline.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "type": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "series_id", "type"]),
    status="implemented",
)
def add_chart_trendline_live(chart_id: str, series_id: str, type: str,
                              properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.add_chart_trendline(doc, chart_id, series_id, type, properties)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="remove_chart_trendline_live",
    priority="P2",
    purpose="Remove trendline.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "trendline_id": {"type": "string"},
    }, required=["chart_id", "series_id"]),
    status="implemented",
)
def remove_chart_trendline_live(chart_id: str, series_id: str, trendline_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.remove_chart_trendline(doc, chart_id, series_id, trendline_id)
        return envelope.build_success(result={"removed": trendline_id or "0"}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_error_bars_live",
    priority="P3",
    purpose="Configure error bars.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "series_id", "properties"]),
    status="implemented",
)
def set_chart_error_bars_live(chart_id: str, series_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_error_bars(doc, chart_id, series_id, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chart_geometry_live",
    priority="P1",
    purpose="Move/resize chart object.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "position": {"type": "object"},
        "size": {"type": "object"},
    }, required=["chart_id"]),
    status="implemented",
)
def set_chart_geometry_live(chart_id: str, position: Optional[Dict[str, Any]] = None,
                             size: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_chart_geometry(doc, chart_id, position, size)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="export_chart_live",
    priority="P2",
    purpose="Export chart to raster/vector file.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "file_path": {"type": "string"},
        "format": {"type": "string", "default": "png"},
        "dpi": {"type": "integer"},
    }, required=["chart_id", "file_path"]),
    status="implemented",
)
def export_chart_live(chart_id: str, file_path: str, format: str = "png",
                       dpi: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.export_chart(doc, chart_id, file_path, format, dpi)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
