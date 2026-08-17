"""
Common drawing objects, images, shapes, and embedded objects -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Common drawing objects, images, shapes, and embedded objects" (scope:
Writer, Calc, Impress, Draw -- shared across document types rather than
owned by any one of Writer's own Phase B modules). No tools in this
section are marked "(existing)"; all 31 were scaffolded stubs before
this pass. Built first among the remaining Phase C/D modules per
audit #41 (dependency order, not catalog order): charts/impress/draw all
sit on top of this shared shape primitive.

Object-handle design: shape_id/object_id resolve through
DocumentRegistry.get_object_registry(document_id) -- an ObjectRegistry
scoped to the active document, per docs/OBJECT_HANDLE_DESIGN.md
(mandated item #2). None of these 31 tools take a document_id parameter
(matching the spec's own parameter lists, same precedent styles.py/
writer_text.py established), so every tool resolves the active document
via _resolve_and_register(ctx) first, then gets that document's own
object registry.

container (sheet/page addressing) uses live name-or-index resolution
against UNO's own containers -- no registry, per the same design doc's
category split. UNOBridge._resolve_shape_container() does the actual
per-doctype resolution (Writer's single document-wide draw page, a Calc
sheet's own draw page, or a specific Impress/Draw page); this module
only ever passes `container` through unchanged.

combine_shapes_live/split_shape_live/bind_shapes_live/unbind_shape_live
were originally scope-limited to NOT_IMPLEMENTED in this pass, after
live-testing showed .uno:Combine executing successfully but then
crashing headless soffice outright on the very next UNO call
(DisposedException). Re-investigated and re-enabled by the draw.py
pass's dispatch-safety correction: that crash turned out to be an
artifact of the *external test script's* pattern (URP connection +
dispatch + a same-document doc.close() right after), not a defect in
dispatch commands used from the extension's own in-process code -- see
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's draw.py entry for the full
re-investigation. Combine/bind are destructive (unlike group_shapes_live):
live-verified the member shapes' own handles stop resolving as
independent shapes afterward, so their ObjectRegistry entries are
unregistered as part of the operation, the same way ungroup_shape_live
already unregisters a consumed group's handle.

insert_embedded_object_live and activate_embedded_object_live remain
NOT_IMPLEMENTED -- that scope limit was never about dispatch safety
(embedded-object creation covers a wide, uncertain range of OLE types;
OLE activation wasn't exploration-tested this pass either), so it's
unaffected by the correction above. Both are P3 (lowest priority) in
the spec.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


def _get_object_registry(ctx, document_id: str):
    return ctx.document_registry.get_object_registry(document_id)


def _resolve_shape(ctx, document_id: str, shape_id: str) -> Any:
    return _get_object_registry(ctx, document_id).resolve_object(shape_id)


def _resolve_shapes(ctx, document_id: str, shape_ids: List[str]) -> List[Any]:
    registry = _get_object_registry(ctx, document_id)
    return [registry.resolve_object(sid) for sid in shape_ids]


@register_tool(
    name="list_shapes_live",
    status="implemented",
    priority="P1",
    purpose="List shapes on a Writer draw page, Calc sheet, Impress slide, or Draw page.",
    parameters=schema({
        "container": {"type": "string"},
        "type_filter": {"type": "string"},
    }),
)
def list_shapes_live(container: Optional[str] = None, type_filter: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shapes = ctx.uno_bridge.list_shapes_in_container(doc, container, type_filter)
        summaries = [
            ctx.uno_bridge.get_shape_summary(shape, object_registry.register_object(shape))
            for shape in shapes
        ]
        return envelope.build_success(
            result={"shapes": summaries, "count": len(summaries)}, document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_shape_live",
    status="implemented",
    priority="P1",
    purpose="Return type, geometry, style, text, z-order, layer, accessibility metadata.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def get_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        details = ctx.uno_bridge.get_shape_details(shape, shape_id)
        return envelope.build_success(result=details, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_shape_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = ctx.uno_bridge.insert_shape(doc, shape_type, position, size, container, properties)
        shape_id = _get_object_registry(ctx, resolved_id).register_object(shape)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(shape, shape_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_shape_live",
    status="implemented",
    priority="P1",
    purpose="Delete shape.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def delete_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(shape_id)
        ctx.uno_bridge.delete_shape(doc, shape)
        object_registry.unregister_object(shape_id)
        return envelope.build_success(result={"deleted": shape_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="duplicate_shape_live",
    status="implemented",
    priority="P1",
    purpose="Duplicate shape with optional offset.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "offset": {"type": "object"},
    }, required=["shape_id"]),
)
def duplicate_shape_live(shape_id: str, offset: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(shape_id)
        new_shape = ctx.uno_bridge.duplicate_shape(doc, shape, offset)
        new_shape_id = object_registry.register_object(new_shape)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(new_shape, new_shape_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_shape_geometry_live",
    status="implemented",
    priority="P1",
    purpose="Set x/y/width/height/rotation/shear/flip.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "geometry": {"type": "object"},
    }, required=["shape_id", "geometry"]),
)
def set_shape_geometry_live(shape_id: str, geometry: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        applied = ctx.uno_bridge.set_shape_geometry(shape, geometry)
        warnings = [f"Ignored unknown/unsettable geometry field(s): {sorted(set(geometry) - set(applied))}"] if set(geometry) - set(applied) else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_shape_style_live",
    status="implemented",
    priority="P1",
    purpose="Set line/fill/shadow/transparency/text style properties.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["shape_id", "properties"]),
)
def set_shape_style_live(shape_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        applied = ctx.uno_bridge.set_shape_style(shape, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_shape_text_live",
    status="implemented",
    priority="P1",
    purpose="Set text contained by a text-capable shape.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "text": {"type": "string"},
    }, required=["shape_id", "text"]),
)
def set_shape_text_live(shape_id: str, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        ctx.uno_bridge.set_shape_text(shape, text)
        return envelope.build_success(result={"shape_id": shape_id, "text": text}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="format_shape_text_live",
    status="implemented",
    priority="P2",
    purpose="Format selected/all text inside shape.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["shape_id", "properties"]),
)
def format_shape_text_live(shape_id: str, properties: Dict[str, Any], range: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        applied = ctx.uno_bridge.format_shape_text(shape, properties, range)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_shape_alt_text_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        applied = ctx.uno_bridge.set_shape_alt_text(shape, title, description)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_shape_z_order_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        new_z_order = ctx.uno_bridge.set_shape_z_order(shape, action, z_order)
        return envelope.build_success(result={"z_order": new_z_order}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="align_shapes_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shapes = _resolve_shapes(ctx, resolved_id, shape_ids)
        reference_bounds = None
        if reference is not None:
            reference_shape = _resolve_shape(ctx, resolved_id, reference)
            reference_bounds = ctx.uno_bridge._shape_bounds(reference_shape)
        ctx.uno_bridge.align_shapes(shapes, alignment, reference_bounds)
        return envelope.build_success(result={"aligned": shape_ids, "alignment": alignment}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="distribute_shapes_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shapes = _resolve_shapes(ctx, resolved_id, shape_ids)
        ctx.uno_bridge.distribute_shapes(shapes, direction, mode)
        return envelope.build_success(result={"distributed": shape_ids, "direction": direction}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="group_shapes_live",
    status="implemented",
    priority="P1",
    purpose="Group multiple shapes.",
    parameters=schema({"shape_ids": {"type": "array", "items": {"type": "string"}}}, required=["shape_ids"]),
)
def group_shapes_live(shape_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shapes = [object_registry.resolve_object(sid) for sid in shape_ids]
        group = ctx.uno_bridge.group_shapes(shapes)
        group_id = object_registry.register_object(group)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(group, group_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="ungroup_shape_live",
    status="implemented",
    priority="P1",
    purpose="Ungroup shape group.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def ungroup_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(shape_id)
        ctx.uno_bridge.ungroup_shape(shape)
        object_registry.unregister_object(shape_id)
        return envelope.build_success(result={"ungrouped": shape_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="combine_shapes_live",
    priority="P3",
    purpose="Combine shapes using drawing-page combine semantics.",
    parameters=schema({"shape_ids": {"type": "array", "items": {"type": "string"}}}, required=["shape_ids"]),
    status="implemented",
)
def combine_shapes_live(shape_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shapes = [object_registry.resolve_object(sid) for sid in shape_ids]
        combined = ctx.uno_bridge.combine_shapes(doc, shapes)
        # Combine is destructive (unlike group): the member shapes' own
        # geometry is absorbed into one new path shape, live-verified
        # the originals no longer resolve as independent shapes
        # afterward -- unregister them so their old handles fail clean
        # rather than resolving to a disposed/meaningless proxy.
        for sid in shape_ids:
            object_registry.unregister_object(sid)
        combined_id = object_registry.register_object(combined)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(combined, combined_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="split_shape_live",
    priority="P3",
    purpose="Split a combined shape.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
    status="implemented",
)
def split_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(shape_id)
        result_selection = ctx.uno_bridge.split_shape(doc, shape)
        object_registry.unregister_object(shape_id)
        new_ids = [
            object_registry.register_object(result_selection.getByIndex(i))
            for i in range(result_selection.getCount())
        ] if hasattr(result_selection, "getCount") else [object_registry.register_object(result_selection)]
        return envelope.build_success(result={"shape_ids": new_ids, "count": len(new_ids)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="bind_shapes_live",
    priority="P3",
    purpose="Bind shapes into one path/object where supported.",
    parameters=schema({"shape_ids": {"type": "array", "items": {"type": "string"}}}, required=["shape_ids"]),
    status="implemented",
)
def bind_shapes_live(shape_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shapes = [object_registry.resolve_object(sid) for sid in shape_ids]
        bound = ctx.uno_bridge.bind_shapes(doc, shapes)
        for sid in shape_ids:
            object_registry.unregister_object(sid)
        bound_id = object_registry.register_object(bound)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(bound, bound_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="unbind_shape_live",
    priority="P3",
    purpose="Unbind bound shape.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
    status="implemented",
)
def unbind_shape_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(shape_id)
        result_selection = ctx.uno_bridge.unbind_shape(doc, shape)
        object_registry.unregister_object(shape_id)
        new_ids = [
            object_registry.register_object(result_selection.getByIndex(i))
            for i in range(result_selection.getCount())
        ] if hasattr(result_selection, "getCount") else [object_registry.register_object(result_selection)]
        return envelope.build_success(result={"shape_ids": new_ids, "count": len(new_ids)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_connector_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        from_shape_obj = object_registry.resolve_object(from_shape)
        to_shape_obj = object_registry.resolve_object(to_shape)
        connector = ctx.uno_bridge.insert_connector(doc, from_shape_obj, to_shape_obj, from_glue, to_glue, connector_type)
        connector_id = object_registry.register_object(connector)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(connector, connector_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_glue_points_live",
    status="implemented",
    priority="P2",
    purpose="List shape glue points.",
    parameters=schema({"shape_id": {"type": "string"}}, required=["shape_id"]),
)
def list_glue_points_live(shape_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        glue_points = ctx.uno_bridge.list_glue_points(shape)
        return envelope.build_success(result={"glue_points": glue_points, "count": len(glue_points)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_glue_point_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        glue_point_id = ctx.uno_bridge.add_glue_point(shape, position, direction)
        return envelope.build_success(result={"glue_point_id": glue_point_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_glue_point_live",
    status="implemented",
    priority="P3",
    purpose="Delete custom glue point.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "glue_point_id": {"type": "string"},
    }, required=["shape_id", "glue_point_id"]),
)
def delete_glue_point_live(shape_id: str, glue_point_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        ctx.uno_bridge.delete_glue_point(shape, glue_point_id)
        return envelope.build_success(result={"deleted": glue_point_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_image_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = ctx.uno_bridge.insert_image(doc, file_path, container, position, size, anchor, wrap)
        shape_id = _get_object_registry(ctx, resolved_id).register_object(shape)
        return envelope.build_success(
            result=ctx.uno_bridge.get_shape_summary(shape, shape_id), document_id=resolved_id,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="replace_image_live",
    status="implemented",
    priority="P1",
    purpose="Replace image source while preserving geometry where possible.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "file_path": {"type": "string"},
    }, required=["shape_id", "file_path"]),
)
def replace_image_live(shape_id: str, file_path: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        ctx.uno_bridge.replace_image(shape, file_path)
        return envelope.build_success(result={"shape_id": shape_id, "file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_image_properties_live",
    status="implemented",
    priority="P1",
    purpose="Resize/crop/rotate/wrap/anchor/transparency/brightness/contrast.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["shape_id", "properties"]),
)
def set_image_properties_live(shape_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        applied = ctx.uno_bridge.set_image_properties(shape, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="export_shape_live",
    status="implemented",
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
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _resolve_shape(ctx, resolved_id, shape_id)
        ctx.uno_bridge.export_shape(shape, file_path, format, dpi)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_embedded_objects_live",
    status="implemented",
    priority="P2",
    purpose="List embedded/OLE/chart/formula objects.",
    parameters=schema({"container": {"type": "string"}}),
)
def list_embedded_objects_live(container: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shapes = ctx.uno_bridge.list_embedded_objects(doc, container)
        summaries = [
            ctx.uno_bridge.get_shape_summary(shape, object_registry.register_object(shape))
            for shape in shapes
        ]
        return envelope.build_success(result={"objects": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
    priority="P2",
    purpose="Delete embedded object.",
    parameters=schema({"object_id": {"type": "string"}}, required=["object_id"]),
)
def delete_embedded_object_live(object_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(object_id)
        ctx.uno_bridge.delete_embedded_object(doc, shape)
        object_registry.unregister_object(object_id)
        return envelope.build_success(result={"deleted": object_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
