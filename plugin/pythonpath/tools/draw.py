"""
Phase D scaffold: Draw - pages, masters, layers, vector operations.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Draw - pages, masters, layers, vector operations" (scope: Draw, plus
shared drawing services). No tools in this section are marked "(existing)";
all 16 are scaffolded here.

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="list_draw_pages_live",
    priority="P1",
    purpose="List Draw pages.",
)
def list_draw_pages_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_draw_pages_live", start)


@register_tool(
    name="get_active_draw_page_live",
    priority="P1",
    purpose="Return active Draw page.",
)
def get_active_draw_page_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_active_draw_page_live", start)


@register_tool(
    name="insert_draw_page_live",
    priority="P1",
    purpose="Insert page.",
    parameters=schema({
        "position": {"type": "integer"},
        "name": {"type": "string"},
    }),
)
def insert_draw_page_live(position: Optional[int] = None, name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_draw_page_live", start)


@register_tool(
    name="duplicate_draw_page_live",
    priority="P1",
    purpose="Duplicate page with shapes.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "destination": {"type": "integer"},
    }, required=["page"]),
)
def duplicate_draw_page_live(page: Any, destination: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("duplicate_draw_page_live", start)


@register_tool(
    name="delete_draw_page_live",
    priority="P1",
    purpose="Delete page.",
    parameters=schema({"page": {"description": "Draw page index or name."}}, required=["page"]),
)
def delete_draw_page_live(page: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_draw_page_live", start)


@register_tool(
    name="move_draw_page_live",
    priority="P1",
    purpose="Move page.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "destination_index": {"type": "integer"},
    }, required=["page", "destination_index"]),
)
def move_draw_page_live(page: Any, destination_index: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("move_draw_page_live", start)


@register_tool(
    name="rename_draw_page_live",
    priority="P1",
    purpose="Rename page.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "name": {"type": "string"},
    }, required=["page", "name"]),
)
def rename_draw_page_live(page: Any, name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("rename_draw_page_live", start)


@register_tool(
    name="set_draw_page_size_live",
    priority="P1",
    purpose="Set page dimensions/orientation.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "width": {"type": "number"},
        "height": {"type": "number"},
        "unit": {"type": "string"},
    }, required=["width", "height", "unit"]),
)
def set_draw_page_size_live(width: float, height: float, unit: str, page: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_draw_page_size_live", start)


@register_tool(
    name="set_draw_page_background_live",
    priority="P1",
    purpose="Set page fill/background.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "properties": {"type": "object"},
    }, required=["page", "properties"]),
)
def set_draw_page_background_live(page: Any, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_draw_page_background_live", start)


@register_tool(
    name="list_layers_live",
    priority="P1",
    purpose="List drawing layers with visibility/lock/print state.",
)
def list_layers_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_layers_live", start)


@register_tool(
    name="create_layer_live",
    priority="P1",
    purpose="Create layer.",
    parameters=schema({
        "name": {"type": "string"},
        "visible": {"type": "boolean", "default": True},
        "locked": {"type": "boolean", "default": False},
        "printable": {"type": "boolean", "default": True},
    }, required=["name"]),
)
def create_layer_live(name: str, visible: bool = True, locked: bool = False, printable: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_layer_live", start)


@register_tool(
    name="update_layer_live",
    priority="P1",
    purpose="Rename/change layer state.",
    parameters=schema({
        "layer": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["layer", "properties"]),
)
def update_layer_live(layer: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("update_layer_live", start)


@register_tool(
    name="delete_layer_live",
    priority="P2",
    purpose="Delete empty/removable layer.",
    parameters=schema({"layer": {"type": "string"}}, required=["layer"]),
)
def delete_layer_live(layer: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_layer_live", start)


@register_tool(
    name="assign_shape_layer_live",
    priority="P1",
    purpose="Move shape to layer.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "layer": {"type": "string"},
    }, required=["shape_id", "layer"]),
)
def assign_shape_layer_live(shape_id: str, layer: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("assign_shape_layer_live", start)


@register_tool(
    name="export_draw_page_live",
    priority="P1",
    purpose="Export page to PNG/JPEG/SVG/PDF-compatible filter.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "file_path": {"type": "string"},
        "format": {"type": "string"},
        "options": {"type": "object"},
    }, required=["page", "file_path", "format"]),
)
def export_draw_page_live(page: Any, file_path: str, format: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("export_draw_page_live", start)


@register_tool(
    name="export_selection_live",
    priority="P2",
    purpose="Export selected shapes as image/vector where supported.",
    parameters=schema({
        "file_path": {"type": "string"},
        "format": {"type": "string", "default": "png"},
        "dpi": {"type": "integer"},
    }, required=["file_path"]),
)
def export_selection_live(file_path: str, format: str = "png", dpi: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("export_selection_live", start)
