"""
Impress - slides, masters, notes, transitions, animations, slideshow --
real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Impress - slides, masters, notes, transitions, animations, slideshow"
(scope: Impress). No tools in this section are marked "(existing)"; all 41
were scaffolded stubs before this pass. 34 of 41 are real; the other 7
stay status="stub" (see below).

Third of charts.py/impress.py/draw.py per Buddy's go-ahead -- draw.py and
charts.py done, this one last. Slide addressing (`slide`: index or name)
reuses `_resolve_page_by_name_or_index()`, the same resolution draw.py/
drawing_objects.py already share; `shape` params (set_shape_click_action_
live) take the shape directly through the same `ObjectRegistry` those
modules established.

3 tools stay status="stub" (down from 7): next_slideshow_effect_live/
previous_slideshow_effect_live/goto_slideshow_slide_live, a genuine "not
exploration-tested this pass" scope limit rather than a shortcut (same
precedent as drawing_objects.py's insert/activate_embedded_object_live;
charts.py's add_chart_series_live has since gone real -- see that
module's docstring).

add_animation_live/update_animation_live/delete_animation_live/
reorder_animations_live are now real: constructing/mutating a
com.sun.star.animations.XAnimationNode tree via the generic animations
module (AnimateSet wrapped in a ParallelTimeContainer, tagged with the
requested trigger and appended to the slide's main sequence -- found by
reading sd's own C++ source, sd/source/core/CustomAnimationEffect.cxx,
since the public UNO API docs don't cover node construction). Scoped to
a small, honest effect set (appear/disappear via AnimateSet's Visibility
attribute) rather than LibreOffice's full preset library, which is
built by internal C++ not reachable from the public UNO API at all --
see uno_bridge.py's _EFFECT_PRESETS docstring. Click-advance runtime
behavior isn't verifiable in headless mode (XSlideShowController is
always None, same dead end as the 3 still-stubbed slideshow tools below)
-- only tree construction is live-verified.

- next_slideshow_effect_live/previous_slideshow_effect_live/
  goto_slideshow_slide_live: all three need a live
  com.sun.star.presentation.XSlideShowController
  (Presentation.Controller), confirmed via live-verification this pass to
  always be None in headless mode -- no window manager to render a
  slideshow view to. start_slideshow_live/stop_slideshow_live (which
  don't need the Controller, just XPresentation.start()/end()) ARE real.

move_slide_live/duplicate_slide_live's `destination` also carry a
verification caveat, NOT a stub -- see uno_bridge.py's section docstring:
the code is real and correct (same dispatch-based reorder draw.py proved
safe and effective for Draw), but this pass could not observe it taking
effect for Impress specifically in headless mode, despite the dispatch
pipeline itself being confirmed working via a control test.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .drawing_objects import _get_object_registry
from .registry import register_tool, schema


@register_tool(
    name="list_slides_live",
    priority="P1",
    purpose="List slides with index/name/layout/master/hidden state.",
    status="implemented",
)
def list_slides_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        slides = ctx.uno_bridge.list_slides(doc)
        return envelope.build_success(result={"slides": slides, "count": len(slides)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_active_slide_live",
    priority="P1",
    purpose="Return active slide.",
    status="implemented",
)
def get_active_slide_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_active_slide(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="activate_slide_live",
    priority="P1",
    purpose="Activate slide.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def activate_slide_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.activate_slide(doc, slide)
        return envelope.build_success(result={"activated": slide}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_slide_live",
    priority="P1",
    purpose="Insert slide with optional layout/master.",
    parameters=schema({
        "position": {"type": "integer"},
        "layout": {"type": "string"},
        "master": {"type": "string"},
    }),
    status="implemented",
)
def insert_slide_live(position: Optional[int] = None, layout: Optional[str] = None,
                       master: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_slide(doc, position, layout, master)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="duplicate_slide_live",
    priority="P1",
    purpose="Duplicate slide including shapes.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "destination": {"type": "integer"},
    }, required=["slide"]),
    status="implemented",
)
def duplicate_slide_live(slide: Any, destination: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.duplicate_slide(doc, slide, destination)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_slide_live",
    priority="P1",
    purpose="Delete slide.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def delete_slide_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_slide(doc, slide)
        return envelope.build_success(result={"deleted": slide}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="move_slide_live",
    priority="P1",
    purpose="Move slide.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "destination_index": {"type": "integer"},
    }, required=["slide", "destination_index"]),
    status="implemented",
)
def move_slide_live(slide: Any, destination_index: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.move_slide(doc, slide, destination_index)
        return envelope.build_success(result={"destination_index": destination_index}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="rename_slide_live",
    priority="P2",
    purpose="Rename slide/link target.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "name": {"type": "string"},
    }, required=["slide", "name"]),
    status="implemented",
)
def rename_slide_live(slide: Any, name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.rename_slide(doc, slide, name)
        return envelope.build_success(result={"name": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="hide_slide_live",
    priority="P1",
    purpose="Exclude slide from normal show.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def hide_slide_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.hide_slide(doc, slide)
        return envelope.build_success(result={"hidden": slide}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="show_slide_live",
    priority="P1",
    purpose="Include hidden slide.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def show_slide_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.show_slide(doc, slide)
        return envelope.build_success(result={"shown": slide}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_slide_layout_live",
    priority="P1",
    purpose="Return page size/layout/master/header/footer/background.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def get_slide_layout_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_slide_layout(doc, slide)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_slide_layout_live",
    priority="P1",
    purpose="Set standard presentation layout.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "layout": {"type": "string"},
    }, required=["slide", "layout"]),
    status="implemented",
)
def set_slide_layout_live(slide: Any, layout: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_slide_layout(doc, slide, layout)
        return envelope.build_success(result={"layout": layout}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_slide_size_live",
    priority="P2",
    purpose="Set presentation page width/height/orientation.",
    parameters=schema({
        "width": {"type": "number"},
        "height": {"type": "number"},
        "unit": {"type": "string"},
    }, required=["width", "height", "unit"]),
    status="implemented",
)
def set_slide_size_live(width: float, height: float, unit: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_slide_size(doc, width, height, unit)
        return envelope.build_success(result={"width": width, "height": height, "unit": unit}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_slide_background_live",
    priority="P1",
    purpose="Set slide background fill/gradient/image.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "properties": {"type": "object"},
    }, required=["slide", "properties"]),
    status="implemented",
)
def set_slide_background_live(slide: Any, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_slide_background(doc, slide, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_master_pages_live",
    priority="P1",
    purpose="List presentation master pages.",
    status="implemented",
)
def list_master_pages_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        masters = ctx.uno_bridge.list_master_pages(doc)
        return envelope.build_success(result={"masters": masters, "count": len(masters)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="apply_master_page_live",
    priority="P1",
    purpose="Apply master page to slide(s).",
    parameters=schema({
        "master": {"type": "string"},
        "slides": {"type": "array", "items": {}},
    }, required=["master", "slides"]),
    status="implemented",
)
def apply_master_page_live(master: str, slides: List[Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.apply_master_page(doc, master, slides)
        return envelope.build_success(result={"applied_to": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_master_page_live",
    priority="P2",
    purpose="Create/duplicate master page.",
    parameters=schema({
        "name": {"type": "string"},
        "based_on": {"type": "string"},
    }, required=["name"]),
    status="implemented",
)
def create_master_page_live(name: str, based_on: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_master_page(doc, name, based_on)
        warnings = ["based_on is not implemented this pass -- the new master page is a fresh default, not a copy."] if based_on is not None else []
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_master_page_live",
    priority="P2",
    purpose="Delete unused master page.",
    parameters=schema({"master": {"type": "string"}}, required=["master"]),
    status="implemented",
)
def delete_master_page_live(master: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_master_page(doc, master)
        return envelope.build_success(result={"deleted": master}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_speaker_notes_live",
    priority="P1",
    purpose="Read slide notes text.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def get_speaker_notes_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        text = ctx.uno_bridge.get_speaker_notes(doc, slide)
        return envelope.build_success(result={"text": text}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_speaker_notes_live",
    priority="P1",
    purpose="Set slide notes text.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "text": {"type": "string"},
    }, required=["slide", "text"]),
    status="implemented",
)
def set_speaker_notes_live(slide: Any, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_speaker_notes(doc, slide, text)
        return envelope.build_success(result={"text": text}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_slide_transition_live",
    priority="P1",
    purpose="Return transition/effect/duration/advance settings.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def get_slide_transition_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_slide_transition(doc, slide)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_slide_transition_live",
    priority="P1",
    purpose="Set transition/effect/speed/duration/advance mode.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "effect": {"type": "string"},
        "duration": {"type": "number"},
        "advance": {"type": "string"},
        "auto_after": {"type": "number"},
    }, required=["slide"]),
    status="implemented",
)
def set_slide_transition_live(slide: Any, effect: Optional[str] = None, duration: Optional[float] = None,
                               advance: Optional[str] = None, auto_after: Optional[float] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_slide_transition(doc, slide, effect, duration, advance, auto_after)
        warnings = []
        if duration is not None and auto_after is not None:
            # Live-verified this LibreOffice build two-way-couples
            # page.Duration (auto_after) and page.HighResDuration
            # (duration) instead of keeping them independent -- see
            # uno_bridge.py's set_slide_transition docstring. duration
            # is applied last so it's honored exactly; auto_after is
            # only approximately honored (rounded to match) when both
            # are given together.
            warnings.append(
                "duration and auto_after were both given -- this LibreOffice build keeps them linked, "
                "so duration was applied exactly but auto_after may have been rounded to match it. "
                "Set them in separate calls if both need to be exact."
            )
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_animations_live",
    priority="P2",
    purpose="List animation nodes/effects/order for slide shapes.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
    status="implemented",
)
def list_animations_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        nodes = ctx.uno_bridge.list_animations(doc, slide)
        # Every animation_id is a registered (node, parent_node) pair, not
        # a bare node -- delete/reorder_animations_live need the parent
        # container to remove/reorder against (delete_animation_live's
        # schema has no shape_id/slide to re-derive one from), and
        # add_animation_live registers that exact same shape for the
        # effect it creates. parent_lookup lets a child's parent_id
        # resolve to the SAME id its parent gets as its own entry's
        # animation_id (ObjectRegistry dedups by identity, so registering
        # the identical (node, its_parent) tuple twice is safe).
        parent_lookup = {node: parent_node for node, parent_node in nodes}

        def _id_for(node: Any) -> Optional[str]:
            if node is None:
                return None
            return object_registry.register_object((node, parent_lookup.get(node)))

        animations = []
        for node, parent_node in nodes:
            entry = ctx.uno_bridge.describe_animation_node(node)
            entry["animation_id"] = _id_for(node)
            entry["parent_id"] = _id_for(parent_node)
            animations.append(entry)
        return envelope.build_success(result={"animations": animations, "count": len(animations)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_animation_live",
    priority="P2",
    purpose="Add entrance/emphasis/exit/motion animation to shape/text.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "effect": {"type": "string", "description": "Supported: appear, disappear. See uno_bridge.py's _EFFECT_PRESETS for the honest-scope-limit note on why the rest of LibreOffice's preset library isn't reachable from the public UNO API."},
        "trigger": {"type": "string", "description": "on_click (default), with_previous, after_previous."},
        "duration": {"type": "number"},
        "delay": {"type": "number"},
    }, required=["shape_id", "effect"]),
    status="implemented",
)
def add_animation_live(shape_id: str, effect: str, trigger: Optional[str] = None,
                        duration: Optional[float] = None, delay: Optional[float] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        shape = object_registry.resolve_object(shape_id)
        wrapper, main_sequence = ctx.uno_bridge.add_animation(doc, shape, effect, trigger, duration, delay)
        animation_id = object_registry.register_object((wrapper, main_sequence))
        return envelope.build_success(result={"animation_id": animation_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_animation_live",
    priority="P2",
    purpose="Update animation timing/effect/order.",
    parameters=schema({
        "animation_id": {"type": "string"},
        "properties": {"type": "object", "description": "Supported keys: duration, delay, trigger. Switching effect type isn't supported -- see uno_bridge.py's update_animation() docstring."},
    }, required=["animation_id", "properties"]),
    status="implemented",
)
def update_animation_live(animation_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        wrapper, _main_sequence = _get_object_registry(ctx, resolved_id).resolve_object(animation_id)
        applied = ctx.uno_bridge.update_animation(wrapper, properties)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_animation_live",
    priority="P2",
    purpose="Remove animation.",
    parameters=schema({"animation_id": {"type": "string"}}, required=["animation_id"]),
    status="implemented",
)
def delete_animation_live(animation_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        wrapper, main_sequence = object_registry.resolve_object(animation_id)
        ctx.uno_bridge.delete_animation(wrapper, main_sequence)
        object_registry.unregister_object(animation_id)
        return envelope.build_success(result={"deleted": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="reorder_animations_live",
    priority="P2",
    purpose="Set animation execution order.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "animation_ids": {"type": "array", "items": {"type": "string"}, "description": "Complete, exact current effect set for this slide's main sequence, in the desired order -- a partial or mismatched list is rejected, see uno_bridge.py's reorder_animations()."},
    }, required=["slide", "animation_ids"]),
    status="implemented",
)
def reorder_animations_live(slide: Any, animation_ids: List[str]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        wrappers = [object_registry.resolve_object(aid)[0] for aid in animation_ids]
        ctx.uno_bridge.reorder_animations(doc, slide, wrappers)
        return envelope.build_success(result={"applied": ["order"]}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_shape_click_action_live",
    priority="P2",
    purpose="Set presentation shape click action/bookmark/URL/verb/sound.",
    parameters=schema({
        "shape_id": {"type": "string"},
        "action": {"type": "string"},
        "target": {"type": "string"},
    }, required=["shape_id", "action"]),
    status="implemented",
)
def set_shape_click_action_live(shape_id: str, action: str, target: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shape = _get_object_registry(ctx, resolved_id).resolve_object(shape_id)
        applied = ctx.uno_bridge.set_shape_click_action(doc, shape, action, target)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_presentation_settings_live",
    priority="P1",
    purpose="Return slideshow settings: first page, loop, animations, full-screen, mouse visibility, custom show.",
    status="implemented",
)
def get_presentation_settings_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_presentation_settings(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_presentation_settings_live",
    priority="P1",
    purpose="Set slideshow settings.",
    parameters=schema({"settings": {"type": "object"}}, required=["settings"]),
    status="implemented",
)
def set_presentation_settings_live(settings: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_presentation_settings(doc, settings)
        skipped = sorted(set(settings) - set(applied))
        warnings = [f"Ignored unknown/unsettable setting(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_custom_shows_live",
    priority="P2",
    purpose="List custom slide shows.",
    status="implemented",
)
def list_custom_shows_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        shows = ctx.uno_bridge.list_custom_shows(doc)
        return envelope.build_success(result={"custom_shows": shows, "count": len(shows)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_custom_show_live",
    priority="P2",
    purpose="Create custom show.",
    parameters=schema({
        "name": {"type": "string"},
        "slides": {"type": "array", "items": {}},
    }, required=["name", "slides"]),
    status="implemented",
)
def create_custom_show_live(name: str, slides: List[Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_custom_show(doc, name, slides)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_custom_show_live",
    priority="P2",
    purpose="Change custom show order/content.",
    parameters=schema({
        "name": {"type": "string"},
        "slides": {"type": "array", "items": {}},
    }, required=["name", "slides"]),
    status="implemented",
)
def update_custom_show_live(name: str, slides: List[Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.update_custom_show(doc, name, slides)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_custom_show_live",
    priority="P2",
    purpose="Delete custom show.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def delete_custom_show_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_custom_show(doc, name)
        return envelope.build_success(result={"deleted": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="start_slideshow_live",
    priority="P2",
    purpose="Start presentation using current settings/custom show.",
    parameters=schema({
        "custom_show": {"type": "string"},
        "first_slide": {"description": "Slide index or name."},
    }),
    status="implemented",
)
def start_slideshow_live(custom_show: Optional[str] = None, first_slide: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.start_slideshow(doc, custom_show, first_slide)
        return envelope.build_success(result={"started": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="stop_slideshow_live",
    priority="P2",
    purpose="Stop active slideshow.",
    status="implemented",
)
def stop_slideshow_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.stop_slideshow(doc)
        return envelope.build_success(result={"stopped": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="next_slideshow_effect_live",
    priority="P3",
    purpose="Advance one animation/effect.",
)
def next_slideshow_effect_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("next_slideshow_effect_live", start)


@register_tool(
    name="previous_slideshow_effect_live",
    priority="P3",
    purpose="Go back one effect where supported.",
)
def previous_slideshow_effect_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("previous_slideshow_effect_live", start)


@register_tool(
    name="goto_slideshow_slide_live",
    priority="P3",
    purpose="Jump active slideshow to slide.",
    parameters=schema({"slide": {"description": "Slide index or name."}}, required=["slide"]),
)
def goto_slideshow_slide_live(slide: Any) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("goto_slideshow_slide_live", start)


@register_tool(
    name="export_slide_image_live",
    priority="P1",
    purpose="Export slide to PNG/JPEG/SVG.",
    parameters=schema({
        "slide": {"description": "Slide index or name."},
        "file_path": {"type": "string"},
        "format": {"type": "string", "default": "png"},
        "width": {"type": "integer"},
        "height": {"type": "integer"},
        "dpi": {"type": "integer"},
    }, required=["slide", "file_path"]),
    status="implemented",
)
def export_slide_image_live(slide: Any, file_path: str, format: str = "png", width: Optional[int] = None,
                             height: Optional[int] = None, dpi: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.export_slide(doc, slide, file_path, format, width, height, dpi)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="export_all_slides_images_live",
    priority="P2",
    purpose="Batch-export all/selected slides to images.",
    parameters=schema({
        "output_dir": {"type": "string"},
        "format": {"type": "string", "default": "png"},
        "slides": {"type": "array", "items": {}},
        "naming": {"type": "string"},
    }, required=["output_dir"]),
    status="implemented",
)
def export_all_slides_images_live(output_dir: str, format: str = "png", slides: Optional[List[Any]] = None,
                                   naming: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        files = ctx.uno_bridge.export_all_slides(doc, output_dir, format, slides, naming)
        return envelope.build_success(result={"files": files, "count": len(files)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
