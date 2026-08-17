"""
Phase C scaffold: Common drawing objects, images, shapes, and embedded objects.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Common drawing objects, images, shapes, and embedded objects"
(scope: Writer, Calc, Impress, Draw -- shared across document types rather
than owned by any one of Writer's own Phase B modules). No tools in this
section are marked "(existing)"; all 31 are scaffolded here.

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="list_shapes_live",
    priority="P1",
    purpose="List shapes on a Writer draw page, Calc sheet, Impress slide, or Draw page.",
    parameters=schema({
        "container": {"type": "string"},
        "type_filter": {"type": "string"},
    }),
)
def list_shapes_live(container: Optional[str] = None, type_filter: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_shapes_live", start)


@register_tool(
    name="get_shape_live",
    priority="P1",
    purpose="Return type, geometry, style, text, z-order, layer, accessibility metadata.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def get_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_shape_live", start)


@register_tool(
    name="insert_shape_live",
    priority="P1",
    purpose="Insert rectangle/ellipse/line/polyline/polygon/bezier/callout/arrow/custom/text shape.",
    parameters=schema({
        "shape_type": {"type": "string"},
        "container": {"type": "string"},
        "position": {"type": "object"},
        "size": {"type": "object"},
        "properties": {"type": "object"},
    }, required=["shape_type", "position", "size"]),
)
def insert_shape_live(shape_type: str, position: Dict[str, Any], size: Dict[str, Any],
                       container: Optional[str] = None,
                       properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_shape_live", start)


@register_tool(
    name="delete_shape_live",
    priority="P1",
    purpose="Delete shape.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def delete_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_shape_live", start)


@register_tool(
    name="duplicate_shape_live",
    priority="P1",
    purpose="Duplicate shape with optional offset.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "offset": {"type": "object"},
    }, required=["shape_id"]),
)
def duplicate_shape_live(shape_id: str, offset: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("duplicate_shape_live", start)


@register_tool(
    name="set_shape_geometry_live",
    priority="P1",
    purpose="Set x/y/width/height/rotation/shear/flip.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "geometry": {"type": "object"},
    }, required=["shape_id", "geometry"]),
)
def set_shape_geometry_live(shape_id: str, geometry: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_shape_geometry_live", start)


@register_tool(
    name="set_shape_style_live",
    priority="P1",
    purpose="Set line/fill/shadow/transparency/text style properties.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["shape_id", "properties"]),
)
def set_shape_style_live(shape_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_shape_style_live", start)


@register_tool(
    name="set_shape_text_live",
    priority="P1",
    purpose="Set text contained by a text-capable shape.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "text": {"type": "string"},
    }, required=["shape_id", "text"]),
)
def set_shape_text_live(shape_id: str, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_shape_text_live", start)


@register_tool(
    name="format_shape_text_live",
    priority="P2",
    purpose="Format selected/all text inside shape.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["shape_id", "properties"]),
)
def format_shape_text_live(shape_id: str, properties: Dict[str, Any], range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("format_shape_text_live", start)


@register_tool(
    name="set_shape_alt_text_live",
    priority="P1",
    purpose="Set title/description/accessibility text.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
    }, required=["shape_id"]),
)
def set_shape_alt_text_live(shape_id: str, title: Optional[str] = None,
                             description: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_shape_alt_text_live", start)


@register_tool(
    name="set_shape_z_order_live",
    priority="P1",
    purpose="Move shape forward/back/front/back or set explicit z-order.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "action": {"type": "string", "enum": ["forward", "backward", "front", "back"]},
        "z_order": {"type": "integer"},
    }, required=["shape_id"]),
)
def set_shape_z_order_live(shape_id: str, action: Optional[str] = None,
                            z_order: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_shape_z_order_live", start)


@register_tool(
    name="align_shapes_live",
    priority="P1",
    purpose="Align selected shape IDs to edge/center/reference.",
    parameters=schema({
        "shape_ids": {"type": "array", "items": {"type": "string"}},
        "alignment": {"type": "string"},
        "reference": {"type": "string"},
    }, required=["shape_ids", "alignment"]),
)
def align_shapes_live(shape_ids: List[str], alignment: str, reference: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("align_shapes_live", start)


@register_tool(
    name="distribute_shapes_live",
    priority="P2",
    purpose="Evenly distribute shapes horizontally/vertically.",
    parameters=schema({
        "shape_ids": {"type": "array", "items": {"type": "string"}},
        "direction": {"type": "string"},
        "mode": {"type": "string"},
    }, required=["shape_ids", "direction"]),
)
def distribute_shapes_live(shape_ids: List[str], direction: str, mode: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("distribute_shapes_live", start)


@register_tool(
    name="group_shapes_live",
    priority="P1",
    purpose="Group multiple shapes.",
    parameters=schema({"shape_ids": {"type": "array", "items": {"type": "string"}}}, required=["shape_ids"]),
)
def group_shapes_live(shape_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("group_shapes_live", start)


@register_tool(
    name="ungroup_shape_live",
    priority="P1",
    purpose="Ungroup shape group.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def ungroup_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("ungroup_shape_live", start)


@register_tool(
    name="combine_shapes_live",
    priority="P3",
    purpose="Combine shapes using drawing-page combine semantics.",
    parameters=schema({"shape_ids": {"type": "array", "items": {"type": "string"}}}, required=["shape_ids"]),
)
def combine_shapes_live(shape_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("combine_shapes_live", start)


@register_tool(
    name="split_shape_live",
    priority="P3",
    purpose="Split a combined shape.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def split_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("split_shape_live", start)


@register_tool(
    name="bind_shapes_live",
    priority="P3",
    purpose="Bind shapes into one path/object where supported.",
    parameters=schema({"shape_ids": {"type": "array", "items": {"type": "string"}}}, required=["shape_ids"]),
)
def bind_shapes_live(shape_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("bind_shapes_live", start)


@register_tool(
    name="unbind_shape_live",
    priority="P3",
    purpose="Unbind bound shape.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def unbind_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("unbind_shape_live", start)


@register_tool(
    name="insert_connector_live",
    priority="P1",
    purpose="Insert connector between shapes/glue points; Writer supported on current LibreOffice releases.",
    parameters=schema({
        "from_shape": {"type": "string"},
        "to_shape": {"type": "string"},
        "from_glue": {"type": "string"},
        "to_glue": {"type": "string"},
        "connector_type": {"type": "string"},
    }, required=["from_shape", "to_shape"]),
)
def insert_connector_live(from_shape: str, to_shape: str, from_glue: Optional[str] = None,
                           to_glue: Optional[str] = None, connector_type: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_connector_live", start)


@register_tool(
    name="list_glue_points_live",
    priority="P2",
    purpose="List shape glue points.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def list_glue_points_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_glue_points_live", start)


@register_tool(
    name="add_glue_point_live",
    priority="P3",
    purpose="Add custom glue point.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "position": {"type": "object"},
        "direction": {"type": "string"},
    }, required=["shape_id", "position"]),
)
def add_glue_point_live(shape_id: str, position: Dict[str, Any], direction: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("add_glue_point_live", start)


@register_tool(
    name="delete_glue_point_live",
    priority="P3",
    purpose="Delete custom glue point.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "glue_point_id": {"type": "string"},
    }, required=["shape_id", "glue_point_id"]),
)
def delete_glue_point_live(shape_id: str, glue_point_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_glue_point_live", start)


@register_tool(
    name="insert_image_live",
    priority="P1",
    purpose="Insert bitmap/vector image by file path/URL.",
    parameters=schema({
        "file_path": {"type": "string"},
        "container": {"type": "string"},
        "position": {"type": "object"},
        "size": {"type": "object"},
        "anchor": {"type": "string"},
        "wrap": {"type": "string"},
    }, required=["file_path"]),
)
def insert_image_live(file_path: str, container: Optional[str] = None, position: Optional[Dict[str, Any]] = None,
                       size: Optional[Dict[str, Any]] = None, anchor: Optional[str] = None,
                       wrap: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_image_live", start)


@register_tool(
    name="replace_image_live",
    priority="P1",
    purpose="Replace image source while preserving geometry where possible.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "file_path": {"type": "string"},
    }, required=["shape_id", "file_path"]),
)
def replace_image_live(shape_id: str, file_path: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("replace_image_live", start)


@register_tool(
    name="set_image_properties_live",
    priority="P1",
    purpose="Resize/crop/rotate/wrap/anchor/transparency/brightness/contrast.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["shape_id", "properties"]),
)
def set_image_properties_live(shape_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_image_properties_live", start)


@register_tool(
    name="export_shape_live",
    priority="P2",
    purpose="Export one shape/group to PNG/JPEG/SVG where filter permits.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "file_path": {"type": "string"},
        "format": {"type": "string"},
        "dpi": {"type": "integer"},
    }, required=["shape_id", "file_path"]),
)
def export_shape_live(shape_id: str, file_path: str, format: Optional[str] = None,
                       dpi: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("export_shape_live", start)


@register_tool(
    name="list_embedded_objects_live",
    priority="P2",
    purpose="List embedded/OLE/chart/formula objects.",
    parameters=schema({"container": {"type": "string"}}),
)
def list_embedded_objects_live(container: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_embedded_objects_live", start)


@register_tool(
    name="insert_embedded_object_live",
    priority="P3",
    purpose="Insert an embedded object of a supported class/service.",
    parameters=schema({
        "object_type": {"type": "string"},
        "container": {"type": "string"},
        "position": {"type": "object"},
        "size": {"type": "object"},
        "data": {"type": "object"},
    }, required=["object_type"]),
)
def insert_embedded_object_live(object_type: str, container: Optional[str] = None,
                                 position: Optional[Dict[str, Any]] = None, size: Optional[Dict[str, Any]] = None,
                                 data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_embedded_object_live", start)


@register_tool(
    name="activate_embedded_object_live",
    priority="P3",
    purpose="Activate/open embedded object for editing where supported.",
    parameters=schema({
        "object_id": {"type": "string"},
        "verb": {"type": "string"},
    }, required=["object_id"]),
)
def activate_embedded_object_live(object_id: str, verb: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("activate_embedded_object_live", start)


@register_tool(
    name="delete_embedded_object_live",
    priority="P2",
    purpose="Delete embedded object.",
    parameters=schema({"object_id": {"type": "string"}}, required=["object_id"]),
)
def delete_embedded_object_live(object_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_embedded_object_live", start)
