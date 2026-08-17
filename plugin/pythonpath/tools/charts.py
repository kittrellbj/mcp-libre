"""
Phase C scaffold: Charts and data visualizations.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Charts and data visualizations" (scope: Calc primarily; Writer/Impress/Draw
embedded charts). No tools in this section are marked "(existing)"; all 20
are scaffolded here.

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="list_charts_live",
    priority="P1",
    purpose="List embedded charts and anchors.",
    parameters=schema({"container": {"type": "string"}}),
)
def list_charts_live(container: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_charts_live", start)


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
)
def create_chart_live(chart_type: str, source: Optional[str] = None, data: Optional[List[List[Any]]] = None,
                       container: Optional[str] = None, position: Optional[Dict[str, Any]] = None,
                       size: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_chart_live", start)


@register_tool(
    name="get_chart_live",
    priority="P1",
    purpose="Return chart type, data source, titles, axes, legend, series summary.",
    parameters=schema({"chart_id": {"type": "string"}}, required=["chart_id"]),
)
def get_chart_live(chart_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_chart_live", start)


@register_tool(
    name="delete_chart_live",
    priority="P1",
    purpose="Delete chart.",
    parameters=schema({"chart_id": {"type": "string"}}, required=["chart_id"]),
)
def delete_chart_live(chart_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_chart_live", start)


@register_tool(
    name="set_chart_type_live",
    priority="P1",
    purpose="Change chart/diagram type and subtype.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "chart_type": {"type": "string"},
        "subtype": {"type": "string"},
    }, required=["chart_id", "chart_type"]),
)
def set_chart_type_live(chart_id: str, chart_type: str, subtype: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_type_live", start)


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
)
def set_chart_data_live(chart_id: str, source_range: Optional[str] = None, data: Optional[List[List[Any]]] = None,
                         categories: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_data_live", start)


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
)
def set_chart_title_live(chart_id: str, title: Optional[str] = None, subtitle: Optional[str] = None,
                          properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_title_live", start)


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
)
def set_chart_legend_live(chart_id: str, visible: Optional[bool] = None, position: Optional[str] = None,
                           properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_legend_live", start)


@register_tool(
    name="get_chart_series_live",
    priority="P1",
    purpose="List data series, labels, ranges, colors, chart types.",
    parameters=schema({"chart_id": {"type": "string"}}, required=["chart_id"]),
)
def get_chart_series_live(chart_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_chart_series_live", start)


@register_tool(
    name="set_chart_series_live",
    priority="P1",
    purpose="Set series data/label/style and axis assignment.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "series_id", "properties"]),
)
def set_chart_series_live(chart_id: str, series_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_series_live", start)


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
)
def remove_chart_series_live(chart_id: str, series_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("remove_chart_series_live", start)


@register_tool(
    name="set_chart_axis_live",
    priority="P1",
    purpose="Configure axis visibility/title/min/max/scale/log/number format/grid.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "axis": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "axis", "properties"]),
)
def set_chart_axis_live(chart_id: str, axis: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_axis_live", start)


@register_tool(
    name="set_chart_data_labels_live",
    priority="P2",
    purpose="Configure value/category/percent labels.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "properties"]),
)
def set_chart_data_labels_live(chart_id: str, properties: Dict[str, Any],
                                series_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_data_labels_live", start)


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
)
def set_chart_gridlines_live(chart_id: str, axis: str, major: Optional[bool] = None,
                              minor: Optional[bool] = None,
                              properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_gridlines_live", start)


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
)
def add_chart_trendline_live(chart_id: str, series_id: str, type: str,
                              properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("add_chart_trendline_live", start)


@register_tool(
    name="remove_chart_trendline_live",
    priority="P2",
    purpose="Remove trendline.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "trendline_id": {"type": "string"},
    }, required=["chart_id", "series_id"]),
)
def remove_chart_trendline_live(chart_id: str, series_id: str, trendline_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("remove_chart_trendline_live", start)


@register_tool(
    name="set_chart_error_bars_live",
    priority="P3",
    purpose="Configure error bars.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "series_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["chart_id", "series_id", "properties"]),
)
def set_chart_error_bars_live(chart_id: str, series_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_error_bars_live", start)


@register_tool(
    name="set_chart_geometry_live",
    priority="P1",
    purpose="Move/resize chart object.",
    parameters=schema({
        "chart_id": {"type": "string"},
        "position": {"type": "object"},
        "size": {"type": "object"},
    }, required=["chart_id"]),
)
def set_chart_geometry_live(chart_id: str, position: Optional[Dict[str, Any]] = None,
                             size: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chart_geometry_live", start)


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
)
def export_chart_live(chart_id: str, file_path: str, format: str = "png",
                       dpi: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("export_chart_live", start)
