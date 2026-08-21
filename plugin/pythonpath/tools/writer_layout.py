"""
Writer - page layout, publishing, styles, headers, fields, indexes --
real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Writer - page layout, publishing, styles, headers, fields, indexes"
(scope: Writer). No tools in this section are marked "(existing)"; all
43 were scaffolded stubs before this pass. 42 of 43 are real.

Third of the four remaining Phase B/C scaffolds Buddy assigned
(calc_data.py, calc_page.py done -> writer_layout.py -> writer_tables.py).
Page style resolution reuses `_get_style_family(doc, "PageStyles")`, the
same family styles.py/calc_page.py already resolve through. Bookmarks
are addressed by name directly (`doc.getBookmarks()` is a real
UNO-guaranteed-unique-Name `XNameAccess`, confirmed live) -- no
`ObjectRegistry`, same category as sheets/Writer tables/Calc's own named
charts per `docs/OBJECT_HANDLE_DESIGN.md`. Fields, hyperlink text
ranges, and document indexes have no natural unique name and resolve
`field_id`/`hyperlink_id`/`index_id` through the same `ObjectRegistry`
`drawing_objects.py` established (see `list_shapes_live` there for the
pattern this file's own list functions follow: `uno_bridge` returns raw
objects, this file registers them and builds the response).

**`document_index_id`/pivot-table-style caveat, confirmed for ContentIndex
this pass (BUG #12 live-verification):** `list_document_indexes_live`
does have the same identity-across-fetches gap `calc_data.py`'s pivot
tables hit (a fresh `XDataPilotTable`/legacy `ConditionalFormat` entry
fetch not comparing equal to an earlier one of the *same* underlying
object) -- confirmed live, not assumed: a raw-UNO probe against a
running document showed two separate `getDocumentIndexes().getByIndex()`
fetches of the identical `com.sun.star.text.ContentIndex` return proxies
with different `hash()` values, so `ObjectRegistry`'s identity-keyed dict
(`register_object`) never matches them and mints a second `index_id`.
`insert_toc_live`'s BUG #12 get-or-create fix is still correct on its
actual contract -- calling it twice never creates a second *document*
index (`list_document_indexes_live`'s own `count` stays 1, live-verified)
-- but a caller that calls `insert_toc_live` twice and compares the two
`index_id`s for equality will see them differ. Each id still works
correctly for its own later `get`/`update`/`delete` call (all three
resolve through the held reference directly, never by re-locating via
comparison). Flagged proactively rather than assumed safe, per Buddy's
standing note that this kind of caveat belongs in the caller-visible
surface, not just a commit message.

**Hyperlinks confirmed to have the same pivot-table-style id churn --
READ THIS BEFORE CALLING list_hyperlinks_live twice:** live-verified
against a real running server, the hyperlinked text range object does
NOT compare equal to itself across two separate UNO fetches, same as
calc_data.py's pivot tables. `insert_hyperlink_live`'s own returned
`hyperlink_id` and a subsequent `list_hyperlinks_live`'s id for that
same hyperlink are DIFFERENT strings. Each id keeps working correctly
for its own later `update_hyperlink_live`/`remove_hyperlink_live` call
(both resolve through the held reference directly, never by re-locating
via comparison) -- but a caller that lists twice and compares
hyperlink_ids to check "is this still the same link" will get a false
negative every time. `insert_hyperlink`'s own implementation went
through two broken approaches before this: setting `HyperLinkURL` on a
cursor positioned *before* inserting the display text silently no-ops
(the property never applies to text that doesn't exist yet), and
inserting with `bAbsorb=False` then re-selecting the range with a
second, earlier-snapshotted cursor also silently no-ops -- that second
cursor tracks the live edit and moves forward right along with the
insertion point, so the "selection" it ends up with is zero-width.
Neither failure raises; both just produce a hyperlink whose URL never
took, discoverable only by independently reading `HyperLinkURL` back
off a text-portion scan, not by trusting the tool's own success
response. Fixed by inserting with `bAbsorb=True`, which leaves the
cursor itself selecting exactly the text it just inserted.

`set_chapter_numbering_live` stays `status="stub"` -- live-verified
`ChapterNumberingRules.replaceByIndex()` raises a bare
`IllegalArgumentException` even passing back the exact unmodified
sequence `getByIndex()` itself returned; `get_chapter_numbering_live`
(read-only) is real. Same honest-scope-limit precedent as
`drawing_objects.py`'s `insert_embedded_object_live` (`add_chart_series_live`/
`add_animation_live`/`create_external_link_live` have all since gone real).
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .drawing_objects import _get_object_registry
from .registry import register_tool, schema


@register_tool(
    name="get_page_layout_live",
    priority="P1",
    purpose="Return active page style, paper size, orientation, margins, mirrored layout, columns, header/footer settings.",
    parameters=schema({"page_style": {"type": "string"}}),
    status="implemented",
)
def get_page_layout_live(page_style: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_page_layout(doc, page_style)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_page_layout_live",
    priority="P1",
    purpose="Set physical page size and publishing layout; supports 6x9 and other trim sizes.",
    parameters=schema({
        "width": {"type": "number"},
        "height": {"type": "number"},
        "unit": {"type": "string", "enum": ["in", "mm", "pt"]},
        "orientation": {"type": "string"},
        "margins": {"type": "object"},
        "mirrored": {"type": "boolean"},
        "gutter": {"type": "number"},
        "page_style": {"type": "string"},
    }, required=["width", "height", "unit"]),
    status="implemented",
)
def set_page_layout_live(width: float, height: float, unit: str, orientation: Optional[str] = None,
                          margins: Optional[Dict[str, Any]] = None, mirrored: Optional[bool] = None,
                          gutter: Optional[float] = None, page_style: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_page_layout(doc, width, height, unit, orientation, margins, mirrored, gutter, page_style)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="apply_page_preset_live",
    priority="P1",
    purpose=(
        "Apply named layout preset such as novel_6x9, letter, a4, legal, a5, digest_5.5x8.5. "
        "Trim sizes only (industry-standard, objectively verifiable dimensions) -- "
        "genre-specific typography presets (screenplay/manuscript) are not implemented, "
        "their margin/spacing conventions vary across style guides and weren't picked one to ship as authoritative."
    ),
    parameters=schema({
        "preset": {"type": "string"},
        "overrides": {"type": "object"},
    }, required=["preset"]),
    status="implemented",
)
def apply_page_preset_live(preset: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.apply_page_preset(doc, preset, overrides)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_page_styles_live",
    priority="P1",
    purpose="List Writer page styles.",
    status="implemented",
)
def list_page_styles_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        styles = ctx.uno_bridge.list_page_styles(doc)
        return envelope.build_success(result={"page_styles": styles, "count": len(styles)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="create_page_style_live",
    priority="P1",
    purpose="Create/clone Writer page style.",
    parameters=schema({
        "style_name": {"type": "string"},
        "based_on": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["style_name"]),
    status="implemented",
)
def create_page_style_live(style_name: str, based_on: Optional[str] = None,
                            properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.create_page_style(doc, style_name, based_on, properties)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_page_style_live",
    priority="P1",
    purpose="Modify a Writer page style.",
    parameters=schema({
        "style_name": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["style_name", "properties"]),
    status="implemented",
)
def update_page_style_live(style_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.update_page_style(doc, style_name, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="apply_page_style_live",
    priority="P1",
    purpose="Apply page style at current/explicit paragraph, optionally inserting a break.",
    parameters=schema({
        "style_name": {"type": "string"},
        "paragraph": {"type": "integer"},
        "insert_break": {"type": "boolean", "default": False},
    }, required=["style_name"]),
    status="implemented",
)
def apply_page_style_live(style_name: str, paragraph: Optional[int] = None,
                           insert_break: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.apply_page_style(doc, style_name, paragraph, insert_break)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_page_columns_live",
    priority="P2",
    purpose="Configure page or section columns.",
    parameters=schema({
        "count": {"type": "integer"},
        "spacing": {"type": "number"},
        "widths": {"type": "array", "items": {"type": "number"}},
        "separator": {"type": "string"},
    }, required=["count"]),
    status="implemented",
)
def set_page_columns_live(count: int, spacing: Optional[float] = None, widths: Optional[List[float]] = None,
                           separator: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_page_columns(doc, count, spacing, widths, separator)
        return envelope.build_success(result={"count": count}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_page_break_live",
    priority="P1",
    purpose=(
        "Insert page break with optional next page style/page number. Same "
        "at_position contract as insert_paragraph_live -- 1-based, splits before "
        "the target paragraph; an omitted at_position anchors off the last "
        "insert_paragraph_live/insert_heading_live/insert_page_break_live call "
        "in this session (see BUG #7/#5 finding on insert_paragraph_live)."
    ),
    parameters=schema({
        "at_position": {"type": "integer"},
        "page_style": {"type": "string"},
        "page_number": {"type": "integer"},
    }),
    status="implemented",
)
def insert_page_break_live(at_position: Optional[int] = None, page_style: Optional[str] = None,
                            page_number: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_page_break(doc, at_position, page_style, page_number)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="remove_page_break_live",
    priority="P2",
    purpose="Remove page break at paragraph/position.",
    parameters=schema({
        "paragraph": {"type": "integer"},
        "position": {"type": "integer"},
    }),
    status="implemented",
)
def remove_page_break_live(paragraph: Optional[int] = None, position: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.remove_page_break(doc, paragraph, position)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_headers_footers_live",
    priority="P1",
    purpose="Read header/footer enablement and text for page-style variants.",
    parameters=schema({"page_style": {"type": "string"}}),
    status="implemented",
)
def get_headers_footers_live(page_style: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_headers_footers(doc, page_style)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_header_live",
    priority="P1",
    purpose="Enable and set header content for right/left/first page variants.",
    parameters=schema({
        "text": {"type": "string"},
        "page_style": {"type": "string"},
        "variant": {"type": "string", "enum": ["default", "left", "first"]},
        "properties": {"type": "object"},
    }, required=["text"]),
    status="implemented",
)
def set_header_live(text: str, page_style: Optional[str] = None, variant: str = "default",
                     properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_header(doc, text, page_style, variant, properties)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_footer_live",
    priority="P1",
    purpose="Enable and set footer content for right/left/first page variants.",
    parameters=schema({
        "text": {"type": "string"},
        "page_style": {"type": "string"},
        "variant": {"type": "string", "enum": ["default", "left", "first"]},
        "properties": {"type": "object"},
    }, required=["text"]),
    status="implemented",
)
def set_footer_live(text: str, page_style: Optional[str] = None, variant: str = "default",
                     properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_footer(doc, text, page_style, variant, properties)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_header_live",
    priority="P2",
    purpose="Clear/disable specified header.",
    parameters=schema({
        "page_style": {"type": "string"},
        "variant": {"type": "string", "enum": ["default", "left", "first"]},
    }),
    status="implemented",
)
def clear_header_live(page_style: Optional[str] = None, variant: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_header(doc, page_style, variant)
        return envelope.build_success(result={"cleared": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="clear_footer_live",
    priority="P2",
    purpose="Clear/disable specified footer.",
    parameters=schema({
        "page_style": {"type": "string"},
        "variant": {"type": "string", "enum": ["default", "left", "first"]},
    }),
    status="implemented",
)
def clear_footer_live(page_style: Optional[str] = None, variant: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.clear_footer(doc, page_style, variant)
        return envelope.build_success(result={"cleared": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_page_number_field_live",
    priority="P1",
    purpose="Insert page number field at cursor/header/footer.",
    parameters=schema({
        "target": {"type": "string"},
        "format": {"type": "string"},
        "offset": {"type": "integer", "default": 0},
    }),
    status="implemented",
)
def insert_page_number_field_live(target: Optional[str] = None, format: Optional[str] = None,
                                   offset: int = 0) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_page_number_field(doc, target, format, offset)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_page_count_field_live",
    priority="P2",
    purpose="Insert total page count field.",
    parameters=schema({
        "target": {"type": "string"},
        "format": {"type": "string"},
    }),
    status="implemented",
)
def insert_page_count_field_live(target: Optional[str] = None, format: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_page_count_field(doc, target, format)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_date_time_field_live",
    priority="P2",
    purpose="Insert fixed or live date/time field.",
    parameters=schema({
        "target": {"type": "string"},
        "fixed": {"type": "boolean", "default": False},
        "format": {"type": "string"},
    }),
    status="implemented",
)
def insert_date_time_field_live(target: Optional[str] = None, fixed: bool = False,
                                 format: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_date_time_field(doc, target, fixed, format)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_document_property_field_live",
    priority="P2",
    purpose=(
        "Insert title/author/file/custom property field. Standard document-info "
        "properties only (author/title/subject/keywords/description/created/modified) -- "
        "a truly custom (user-defined) property field needs a Name parameter this tool's "
        "schema doesn't expose and isn't implemented."
    ),
    parameters=schema({
        "property_name": {"type": "string"},
        "target": {"type": "string"},
        "fixed": {"type": "boolean", "default": False},
    }, required=["property_name"]),
    status="implemented",
)
def insert_document_property_field_live(property_name: str, target: Optional[str] = None,
                                         fixed: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_document_property_field(doc, property_name, target, fixed)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_fields_live",
    priority="P1",
    purpose="List text fields and anchors.",
    parameters=schema({"field_type": {"type": "string"}}),
    status="implemented",
)
def list_fields_live(field_type: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        fields = ctx.uno_bridge.list_fields(doc, field_type)
        summaries = [
            ctx.uno_bridge.get_field_summary(field, object_registry.register_object(field))
            for field in fields
        ]
        return envelope.build_success(result={"fields": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_fields_live",
    priority="P1",
    purpose="Refresh all or selected fields.",
    parameters=schema({"field_ids": {"type": "array", "items": {"type": "string"}}}),
    status="implemented",
)
def update_fields_live(field_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        objects = None
        if field_ids is not None:
            object_registry = _get_object_registry(ctx, resolved_id)
            objects = [object_registry.resolve_object(fid) for fid in field_ids]
        count = ctx.uno_bridge.update_fields(doc, objects)
        return envelope.build_success(result={"updated": count}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_field_live",
    priority="P2",
    purpose="Remove a field, optionally preserving current presentation text.",
    parameters=schema({
        "field_id": {"type": "string"},
        "keep_text": {"type": "boolean", "default": True},
    }, required=["field_id"]),
    status="implemented",
)
def delete_field_live(field_id: str, keep_text: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        field = object_registry.resolve_object(field_id)
        ctx.uno_bridge.delete_field(field, keep_text)
        object_registry.unregister_object(field_id)
        return envelope.build_success(result={"deleted": field_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_bookmarks_live",
    priority="P1",
    purpose="List bookmarks and ranges.",
    status="implemented",
)
def list_bookmarks_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        bookmarks = ctx.uno_bridge.list_bookmarks(doc)
        return envelope.build_success(result={"bookmarks": bookmarks, "count": len(bookmarks)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_bookmark_live",
    priority="P1",
    purpose="Add bookmark over selection/range.",
    parameters=schema({
        "name": {"type": "string"},
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    }, required=["name"]),
    status="implemented",
)
def add_bookmark_live(name: str, start: Optional[int] = None, end: Optional[int] = None) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.add_bookmark(doc, name, start, end)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start_time))
    except Exception as e:
        return _error_response(e, start_time)


@register_tool(
    name="goto_bookmark_live",
    priority="P1",
    purpose="Move selection/cursor to bookmark.",
    parameters=schema({
        "name": {"type": "string"},
        "select": {"type": "boolean", "default": False},
    }, required=["name"]),
    status="implemented",
)
def goto_bookmark_live(name: str, select: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.goto_bookmark(doc, name, select)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="rename_bookmark_live",
    priority="P2",
    purpose="Rename bookmark.",
    parameters=schema({
        "old_name": {"type": "string"},
        "new_name": {"type": "string"},
    }, required=["old_name", "new_name"]),
    status="implemented",
)
def rename_bookmark_live(old_name: str, new_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.rename_bookmark(doc, old_name, new_name)
        return envelope.build_success(result={"new_name": new_name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_bookmark_live",
    priority="P2",
    purpose="Delete bookmark without deleting content.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def delete_bookmark_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_bookmark(doc, name)
        return envelope.build_success(result={"deleted": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_hyperlink_live",
    priority="P1",
    purpose=(
        "Create hyperlink over selected/ranged text. CAVEAT: the returned "
        "hyperlink_id will not match the id a later list_hyperlinks_live call "
        "returns for this same hyperlink (live-verified identity-comparison "
        "gap) -- keep this id if you need it, it works for update/remove "
        "regardless."
    ),
    parameters=schema({
        "url": {"type": "string"},
        "text": {"type": "string"},
        "target": {"type": "string"},
        "name": {"type": "string"},
    }, required=["url"]),
    status="implemented",
)
def insert_hyperlink_live(url: str, text: Optional[str] = None, target: Optional[str] = None,
                           name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        range_obj = ctx.uno_bridge.insert_hyperlink(doc, url, text, target, name)
        hyperlink_id = object_registry.register_object(range_obj)
        summary = ctx.uno_bridge.get_hyperlink_summary(range_obj, hyperlink_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_hyperlinks_live",
    priority="P2",
    purpose=(
        "List hyperlinks in document. CAVEAT: calling this twice for the same "
        "hyperlink returns a different hyperlink_id each time (a live-verified "
        "LibreOffice identity-comparison gap, not a bug in this tool) -- each "
        "returned id still works correctly for update/remove, but ids from two "
        "separate list calls cannot be compared to check whether they refer to "
        "the same hyperlink. Keep the hyperlink_id from whichever call you "
        "actually need, don't re-list and match by id."
    ),
    status="implemented",
)
def list_hyperlinks_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        ranges = ctx.uno_bridge.list_hyperlinks(doc)
        summaries = [
            ctx.uno_bridge.get_hyperlink_summary(range_obj, object_registry.register_object(range_obj))
            for range_obj in ranges
        ]
        return envelope.build_success(result={"hyperlinks": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_hyperlink_live",
    priority="P2",
    purpose="Change hyperlink target/text.",
    parameters=schema({
        "hyperlink_id": {"type": "string"},
        "url": {"type": "string"},
        "text": {"type": "string"},
    }, required=["hyperlink_id"]),
    status="implemented",
)
def update_hyperlink_live(hyperlink_id: str, url: Optional[str] = None, text: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        range_obj = _get_object_registry(ctx, resolved_id).resolve_object(hyperlink_id)
        applied = ctx.uno_bridge.update_hyperlink(range_obj, url, text)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="remove_hyperlink_live",
    priority="P2",
    purpose="Remove link while keeping display text.",
    parameters=schema({"hyperlink_id": {"type": "string"}}, required=["hyperlink_id"]),
    status="implemented",
)
def remove_hyperlink_live(hyperlink_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        range_obj = object_registry.resolve_object(hyperlink_id)
        ctx.uno_bridge.remove_hyperlink(range_obj)
        object_registry.unregister_object(hyperlink_id)
        return envelope.build_success(result={"removed": hyperlink_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_cross_reference_live",
    priority="P1",
    purpose=(
        "Insert cross-reference to heading/bookmark/caption/numbered item. "
        "reference_type: bookmark/heading/page (to a bookmark name) or "
        "caption/caption_number/caption_full (to a caption category's sequence name, "
        "e.g. \"Figure\"). Only these mappings were live-verified this pass."
    ),
    parameters=schema({
        "reference_type": {"type": "string"},
        "target": {"type": "string"},
        "display": {"type": "string"},
    }, required=["reference_type", "target", "display"]),
    status="implemented",
)
def insert_cross_reference_live(reference_type: str, target: str, display: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_cross_reference(doc, reference_type, target, display)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_caption_live",
    priority="P1",
    purpose="Insert caption for table/figure/frame/object and numbering sequence.",
    parameters=schema({
        "target_id": {"type": "string"},
        "label": {"type": "string", "default": "Figure"},
        "text": {"type": "string"},
        "position": {"type": "string", "default": "below"},
    }, required=["target_id"]),
    status="implemented",
)
def insert_caption_live(target_id: str, label: str = "Figure", text: Optional[str] = None,
                         position: str = "below") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        target = _get_object_registry(ctx, resolved_id).resolve_object(target_id)
        result = ctx.uno_bridge.insert_caption(doc, target, label, text, position)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_document_indexes_live",
    priority="P1",
    purpose=(
        "List TOCs, alphabetical/user/table/illustration/bibliography indexes. "
        "CAVEAT (carried forward from calc_data.py's pivot-table finding, not independently "
        "re-verified for this object type): calling this twice for the same index may return "
        "a different index_id each time -- each id still works correctly for its own later "
        "get/update/delete call."
    ),
    status="implemented",
)
def list_document_indexes_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        indexes = ctx.uno_bridge.list_document_indexes(doc)
        summaries = [
            ctx.uno_bridge.get_index_summary(index, object_registry.register_object(index))
            for index in indexes
        ]
        return envelope.build_success(result={"indexes": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_toc_live",
    priority="P1",
    purpose=(
        "Insert table of contents with level/style/options. Idempotent (BUG #12 "
        "fix): a repeat call that would otherwise match an existing table-of-"
        "contents index (same title when title is given, or any existing ToC "
        "when title is omitted) returns that existing index instead of inserting "
        "a duplicate. Pass a distinct title to intentionally insert a second, "
        "differently-titled TOC."
    ),
    parameters=schema({
        "at_position": {"type": "integer"},
        "title": {"type": "string"},
        "max_level": {"type": "integer", "default": 10},
        "options": {"type": "object"},
    }),
    status="implemented",
)
def insert_toc_live(at_position: Optional[int] = None, title: Optional[str] = None, max_level: int = 10,
                     options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)

        # BUG #12 fix: get-or-create by name instead of always inserting a new
        # index. A ToC is identified by its own service name
        # (com.sun.star.text.ContentIndex, distinct from the alphabetical/
        # bibliography/etc. index types insert_alphabetical_index_live and
        # friends create); a match on title (or, when title is omitted, any
        # existing ToC -- an unnamed request means "the" table of contents)
        # returns the existing index rather than creating a duplicate.
        for existing in ctx.uno_bridge.list_document_indexes(doc):
            if existing.getServiceName() != "com.sun.star.text.ContentIndex":
                continue
            if title is not None and getattr(existing, "Title", None) != title:
                continue
            existing_id = object_registry.register_object(existing)
            summary = ctx.uno_bridge.get_index_summary(existing, existing_id)
            return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
        toc = ctx.uno_bridge.insert_toc(doc, at_position, title, max_level, options)
        index_id = object_registry.register_object(toc)
        summary = ctx.uno_bridge.get_index_summary(toc, index_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_index_live",
    priority="P1",
    purpose="Refresh a TOC/index.",
    parameters=schema({"index_id": {"type": "string"}}, required=["index_id"]),
    status="implemented",
)
def update_index_live(index_id: str) -> Dict[str, Any]:
    """BUG #4 finding (live-verified): a bare index.update() was reported
    to silently revert the whole document to an earlier state, with
    success=true and no error -- reran both of the original report's own
    repro scripts (repro_toc_large.py, repro_save.py) against a session
    with BUG #2's fix applied (explicit frame activation on every
    document-creating call, see uno_bridge.create_document()'s docstring),
    compounding state across both runs (2 stray TOC indexes, 363
    paragraphs incl. an image, 2 update_index_live calls) -- neither
    reproduced any reversion; the saved file matched the live count
    exactly. That points at BUG #2's same root cause (desktop.
    getCurrentComponent() drifting to a stale document across separate
    calls in headless mode) rather than a defect in index.update() itself:
    a later stats/count call re-resolving "the active document" from
    scratch could silently land on an older, smaller document than the one
    just built, and report ITS paragraph count -- indistinguishable from
    data loss to a caller, but nothing was actually deleted.

    Not willing to bet the whole fix on having reproduced the exact
    multi-hour, multi-session drift Brian's original run hit (the log
    itself flagged a second suspect, a possible second soffice instance,
    never fully pinned) -- so this also adds the fail-loud guard Buddy's
    standing decision asked for regardless of mechanism: paragraph count
    is read directly off the SAME resolved `doc` object before and after
    index.update() (not re-resolved via "the active document", which is
    exactly the unstable path under suspicion), and a drop refuses to
    report success. Real index refreshes only ever add/update generated
    entries, never remove body paragraphs, so any decrease is by
    definition either the reversion bug or something equally wrong -- a
    caller must never see success=true either way.
    """
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        index = _get_object_registry(ctx, resolved_id).resolve_object(index_id)
        before = ctx.uno_bridge.get_paragraph_count(doc)
        if not before.get("success"):
            raise RuntimeError(f"update_index_live: could not read paragraph count before update: {before.get('error')}")
        ctx.uno_bridge.update_index(index)
        after = ctx.uno_bridge.get_paragraph_count(doc)
        if not after.get("success"):
            raise RuntimeError(f"update_index_live: could not read paragraph count after update: {after.get('error')}")
        before_count, after_count = before["count"], after["count"]
        if after_count < before_count:
            raise RuntimeError(
                f"update_index_live: paragraph count dropped from {before_count} to {after_count} "
                f"while refreshing index {index_id!r} -- refusing to report success on a document "
                f"that may have reverted to an earlier state."
            )
        return envelope.build_success(
            result={"updated": index_id, "paragraph_count_before": before_count, "paragraph_count_after": after_count},
            document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_index_live",
    priority="P2",
    purpose="Remove a TOC/index.",
    parameters=schema({
        "index_id": {"type": "string"},
        "keep_content": {"type": "boolean", "default": False},
    }, required=["index_id"]),
    status="implemented",
)
def delete_index_live(index_id: str, keep_content: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        index = object_registry.resolve_object(index_id)
        ctx.uno_bridge.delete_index(doc, index, keep_content)
        object_registry.unregister_object(index_id)
        return envelope.build_success(result={"deleted": index_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_alphabetical_index_live",
    priority="P2",
    purpose="Insert alphabetical index.",
    parameters=schema({
        "at_position": {"type": "integer"},
        "title": {"type": "string"},
        "options": {"type": "object"},
    }),
    status="implemented",
)
def insert_alphabetical_index_live(at_position: Optional[int] = None, title: Optional[str] = None,
                                    options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        index = ctx.uno_bridge.insert_alphabetical_index(doc, at_position, title, options)
        index_id = object_registry.register_object(index)
        summary = ctx.uno_bridge.get_index_summary(index, index_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_index_mark_live",
    priority="P2",
    purpose="Mark selected text for an index.",
    parameters=schema({
        "index_type": {"type": "string"},
        "primary_key": {"type": "string"},
        "secondary_key": {"type": "string"},
    }, required=["index_type"]),
    status="implemented",
)
def add_index_mark_live(index_type: str, primary_key: Optional[str] = None,
                         secondary_key: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.add_index_mark(doc, index_type, primary_key, secondary_key)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_chapter_numbering_live",
    priority="P2",
    purpose="Return outline/chapter numbering rules.",
    status="implemented",
)
def get_chapter_numbering_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        levels = ctx.uno_bridge.get_chapter_numbering(doc)
        return envelope.build_success(result={"levels": levels}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_chapter_numbering_live",
    priority="P2",
    purpose="Configure chapter numbering levels/styles/prefixes/suffixes.",
    parameters=schema({"levels": {"type": "array", "items": {"type": "object"}}}, required=["levels"]),
)
def set_chapter_numbering_live(levels: List[Dict[str, Any]]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_chapter_numbering_live", start)


@register_tool(
    name="get_line_numbering_live",
    priority="P3",
    purpose="Return line-numbering settings.",
    status="implemented",
)
def get_line_numbering_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_line_numbering(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_line_numbering_live",
    priority="P3",
    purpose="Configure line numbering.",
    parameters=schema({
        "enabled": {"type": "boolean"},
        "interval": {"type": "integer"},
        "restart_each_page": {"type": "boolean"},
    }, required=["enabled"]),
    status="implemented",
)
def set_line_numbering_live(enabled: bool, interval: Optional[int] = None,
                             restart_each_page: Optional[bool] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_line_numbering(doc, enabled, interval, restart_each_page)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
