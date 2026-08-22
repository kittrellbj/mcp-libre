"""
Draw - pages, masters, layers, vector operations -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Draw - pages, masters, layers, vector operations" (scope: Draw, plus
shared drawing services). No tools in this section are marked
"(existing)"; all 16 were scaffolded stubs before this pass.

Page addressing (`page`: index or name) uses the same live name-or-index
resolution docs/OBJECT_HANDLE_DESIGN.md designed for Impress/Draw pages --
`UNOBridge._resolve_page_by_name_or_index()` (already shared with
`drawing_objects.py`'s container resolution) is reused directly, wrapped
by `_resolve_draw_page()` for the "omitted -> active page" fallback.
`shape_id` (assign_shape_layer_live) resolves through the same
`ObjectRegistry` `drawing_objects.py` established.

Dispatch-safety correction, carried from this pass's own investigation
(see uno_bridge.py's "-- Draw --" section docstring and
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's draw.py entry for the full writeup):
drawing_objects.py's prior pass concluded .uno: dispatch commands were
broadly unsafe after .uno:Combine crashed headless soffice. This pass
re-investigated that conclusion before assuming it also blocked
move_draw_page_live (no non-dispatch UNO API exists for arbitrary page
reordering), and found the crash was specific to an *external test
script* calling doc.close() on the same document right after a dispatch
-- not a defect in dispatch commands used from the extension's own
in-process code, which this pass live-verified directly through the
real running server. move_draw_page_live/duplicate_draw_page_live's
`destination` therefore ARE implemented for real via
.uno:MovePageUp/.uno:MovePageDown dispatch.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .drawing_objects import _get_object_registry
from .registry import register_tool, schema


@register_tool(
    name="list_draw_pages_live",
    priority="P1",
    purpose="List Draw pages.",
    status="implemented",
)
def list_draw_pages_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        pages = ctx.uno_bridge.list_draw_pages(doc)
        return envelope.build_success(result={"pages": pages, "count": len(pages)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_active_draw_page_live",
    priority="P1",
    purpose="Return active Draw page.",
    status="implemented",
)
def get_active_draw_page_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_active_draw_page(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="activate_draw_page_live",
    priority="P1",
    purpose=(
        "Activate a Draw page by index or name -- Brian's new-tools "
        "assignment priority #9, the Draw counterpart to Impress's "
        "activate_slide_live."
    ),
    parameters=schema({"page": {"description": "Page index or name."}}, required=["page"]),
    status="implemented",
)
def activate_draw_page_live(page: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.activate_draw_page(doc, page)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_draw_page_live",
    priority="P1",
    purpose=(
        "Return all text content of a Draw page (shapes with text) in one "
        "call, instead of list_shapes_live + N get_shape_live -- Brian's "
        "new-tools assignment priority #10, the Draw counterpart to "
        "Impress's get_slide_content_live. page omitted -> the active page."
    ),
    parameters=schema({
        "page": {"description": "Page index or name. Omitted -> the active page."},
        "include_shape_metadata": {"type": "boolean"},
    }),
    status="implemented",
)
def get_draw_page_live(page: Any = None, include_shape_metadata: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_draw_page(doc, page, include_shape_metadata)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_draw_page_live",
    priority="P1",
    purpose="Insert page.",
    parameters=schema({
        "position": {"type": "integer"},
        "name": {"type": "string"},
    }),
    status="implemented",
)
def insert_draw_page_live(position: Optional[int] = None, name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_draw_page(doc, position, name)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="duplicate_draw_page_live",
    priority="P1",
    purpose="Duplicate page with shapes.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "destination": {"type": "integer"},
    }, required=["page"]),
    status="implemented",
)
def duplicate_draw_page_live(page: Any, destination: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.duplicate_draw_page(doc, page, destination)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_draw_page_live",
    priority="P1",
    purpose="Delete page.",
    parameters=schema({"page": {"description": "Draw page index or name."}}, required=["page"]),
    status="implemented",
)
def delete_draw_page_live(page: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_draw_page(doc, page)
        return envelope.build_success(result={"deleted": page}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="move_draw_page_live",
    priority="P1",
    purpose="Move page.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "destination_index": {"type": "integer"},
    }, required=["page", "destination_index"]),
    status="implemented",
)
def move_draw_page_live(page: Any, destination_index: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.move_draw_page(doc, page, destination_index)
        return envelope.build_success(result={"destination_index": destination_index}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="rename_draw_page_live",
    priority="P1",
    purpose="Rename page.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "name": {"type": "string"},
    }, required=["page", "name"]),
    status="implemented",
)
def rename_draw_page_live(page: Any, name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.rename_draw_page(doc, page, name)
        return envelope.build_success(result={"name": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def set_draw_page_size_live(width: float, height: float, unit: str, page: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_draw_page_size(doc, width, height, unit, page)
        return envelope.build_success(result={"width": width, "height": height, "unit": unit}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_draw_page_background_live",
    priority="P1",
    purpose="Set page fill/background.",
    parameters=schema({
        "page": {"description": "Draw page index or name."},
        "properties": {"type": "object"},
    }, required=["page", "properties"]),
    status="implemented",
)
def set_draw_page_background_live(page: Any, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_draw_page_background(doc, page, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_layers_live",
    priority="P1",
    purpose="List drawing layers with visibility/lock/print state.",
    status="implemented",
)
def list_layers_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        layers = ctx.uno_bridge.list_layers(doc)
        return envelope.build_success(result={"layers": layers, "count": len(layers)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def create_layer_live(name: str, visible: bool = True, locked: bool = False, printable: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_layer(doc, name, visible, locked, printable)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_layer_live",
    priority="P1",
    purpose="Rename/change layer state.",
    parameters=schema({
        "layer": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["layer", "properties"]),
    status="implemented",
)
def update_layer_live(layer: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.update_layer(doc, layer, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_layer_live",
    priority="P2",
    purpose="Delete empty/removable layer.",
    parameters=schema({"layer": {"type": "string"}}, required=["layer"]),
    status="implemented",
)
def delete_layer_live(layer: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_layer(doc, layer)
        return envelope.build_success(result={"deleted": layer}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="assign_shape_layer_live",
    priority="P1",
    purpose="Move shape to layer.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "layer": {"type": "string"},
    }, required=["shape_id", "layer"]),
    status="implemented",
)
def assign_shape_layer_live(shape_id: str, layer: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _get_object_registry(ctx, resolved_id).resolve_object(shape_id)
        ctx.uno_bridge.assign_shape_layer(doc, shape, layer)
        return envelope.build_success(result={"shape_id": shape_id, "layer": layer}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def export_draw_page_live(page: Any, file_path: str, format: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.export_draw_page(doc, page, file_path, format, options)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="export_selection_live",
    priority="P2",
    purpose="Export selected shapes as image/vector where supported.",
    parameters=schema({
        "file_path": {"type": "string"},
        "format": {"type": "string", "default": "png"},
        "dpi": {"type": "integer"},
    }, required=["file_path"]),
    status="implemented",
)
def export_selection_live(file_path: str, format: str = "png", dpi: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.export_selection(doc, file_path, format, dpi)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
