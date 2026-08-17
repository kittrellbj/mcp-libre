"""
Writer - tables, sections, notes, content controls, mail merge -- real
implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Writer - tables, sections, notes, content controls, mail merge"
(scope: Writer). No tools in this section are marked "(existing)"; all 38
were scaffolded stubs before this pass. 37 of 38 are real.

Last of the four remaining Phase B/C scaffolds Buddy assigned
(calc_data.py, calc_page.py, writer_layout.py done -> writer_tables.py).
Tables/sections resolve through their own UNO-native unique Name
(`doc.getTextTables()`/`doc.getTextSections()` are both real `XNameAccess`
containers, confirmed live) -- no `ObjectRegistry`, same category as
bookmarks/page styles per `docs/OBJECT_HANDLE_DESIGN.md`. Footnotes,
endnotes, and content controls have no natural unique name and resolve
`footnote_id`/`endnote_id`/`control_id` through the same `ObjectRegistry`
`drawing_objects.py` established. Live-verified narrower version of
calc_data.py's pivot-table id-churn gap, same shape writer_layout.py's
document indexes turned out to have: two separate `list_*_live` calls for
the SAME footnote/endnote/content control DO return the same id (`doc.
getFootnotes().getByIndex(0) == doc.getFootnotes().getByIndex(0)` is True,
confirmed for all three categories) -- but the id an `add_footnote_live`/
`add_endnote_live`/`insert_content_control_live` call itself returns does
NOT match what a subsequent `list_*_live` call returns for that same
object. Every id keeps working correctly for its own later get/update/
delete call regardless; only comparing an insert-returned id against a
list-returned id for "is this the same object" fails.

**`delete_content_control_live`'s `keep_content` is honored, but the
wrapper itself can never actually be removed in this LibreOffice build --
READ THIS BEFORE RELYING ON IT:** live-verified three different removal
mechanisms (`ContentControl.dispose()`, `doc.getText().removeTextContent
()`, and both together) -- none of them remove the control from `doc.
getContentControls()`; the count stays the same and the surviving entry
is confirmed (via `==`) to be the exact same object, just emptied of
content. This tool clears content when `keep_content=False` (and leaves
it untouched when `True`) and always returns `wrapper_removed: false`
plus a warning -- it does not pretend the wrapper is gone. Same "genuine
UNO limitation, not a shortcut" precedent as writer_layout.py's
`ChapterNumberingRules.replaceByIndex()` resistance.

Two invented conventions this pass, both documented inline in
`uno_bridge.py` where they're used: `convert_text_to_table_live`'s and
`insert_content_control_live`'s `range` parameter -- the only two `range`
params in the whole catalog scaffolded as a bare string rather than
writer_text.py's/writer_layout.py's `{"start": int, "end": int}` object
convention -- accept `"<start>-<end>"` 0-based character offsets (`None`
means use the current selection).

Genuine LibreOffice behavior, not a bug, live-verified: `insert_section_
live` wrapping a PARTIAL paragraph forces a paragraph break at the
selection's end boundary (sections can't occupy less than a full
paragraph), growing the document by one paragraph mark that persists even
after `delete_section_live`'s `keep_content=True` path removes the
wrapper -- see `insert_section()`'s own docstring in `uno_bridge.py`.

`mail_merge_live` stays `status="stub"` -- `preview_mail_merge_live` is
real (an ad hoc, unregistered `com.sun.star.sdb.DataSource` gives a
working SDBC connection over a CSV folder without needing a persisted
`.odb` file, live-verified), but the real `com.sun.star.text.MailMerge`
service needs either a live `Model` (read-only, live-verified) or a
`DataSourceName` resolvable through `com.sun.star.sdb.DatabaseContext`,
which live-verified refuses to register an ad hoc `DataSource` at all
("The data source was not saved. Please use the interface XStorable to
save the data source."). Genuinely blocked without building that
persisted-registration infrastructure this pass, same shape as
calc_data.py's create/refresh/delete_external_link stubs.
"""

from typing import Any, Dict, List, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .drawing_objects import _get_object_registry
from .registry import register_tool, schema


@register_tool(
    name="list_tables_live",
    priority="P1",
    purpose="List Writer tables with IDs, names, dimensions, and anchors.",
    status="implemented",
)
def list_tables_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        tables = ctx.uno_bridge.list_tables(doc)
        return envelope.build_success(result={"tables": tables, "count": len(tables)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_table_live",
    priority="P1",
    purpose="Insert Writer table.",
    parameters=schema({
        "rows": {"type": "integer"},
        "columns": {"type": "integer"},
        "at_position": {"type": "integer"},
        "name": {"type": "string"},
        "style": {"type": "string"},
    }, required=["rows", "columns"]),
    status="implemented",
)
def insert_table_live(rows: int, columns: int, at_position: Optional[int] = None,
                       name: Optional[str] = None, style: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_table(doc, rows, columns, at_position, name, style)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_table_live",
    priority="P1",
    purpose="Return table dimensions/properties and optionally cell values.",
    parameters=schema({
        "table_id": {"type": "string"},
        "include_cells": {"type": "boolean", "default": False},
    }, required=["table_id"]),
    status="implemented",
)
def get_table_live(table_id: str, include_cells: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_table(doc, table_id, include_cells)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_table_range_live",
    priority="P1",
    purpose="Read rectangular Writer table cell range.",
    parameters=schema({
        "table_id": {"type": "string"},
        "start_cell": {"type": "string"},
        "end_cell": {"type": "string"},
    }, required=["table_id", "start_cell", "end_cell"]),
    status="implemented",
)
def get_table_range_live(table_id: str, start_cell: str, end_cell: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        values = ctx.uno_bridge.get_table_range(doc, table_id, start_cell, end_cell)
        return envelope.build_success(result={"values": values}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_table_range_live",
    priority="P1",
    purpose="Write rectangular Writer table cell range.",
    parameters=schema({
        "table_id": {"type": "string"},
        "start_cell": {"type": "string"},
        "values": {"type": "array", "items": {"type": "array"}},
    }, required=["table_id", "start_cell", "values"]),
    status="implemented",
)
def set_table_range_live(table_id: str, start_cell: str, values: List[List[Any]]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.set_table_range(doc, table_id, start_cell, values)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_table_rows_live",
    priority="P1",
    purpose="Insert rows.",
    parameters=schema({
        "table_id": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["table_id", "index"]),
    status="implemented",
)
def insert_table_rows_live(table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_table_rows(doc, table_id, index, count)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_table_rows_live",
    priority="P1",
    purpose="Delete rows.",
    parameters=schema({
        "table_id": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["table_id", "index"]),
    status="implemented",
)
def delete_table_rows_live(table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.delete_table_rows(doc, table_id, index, count)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_table_columns_live",
    priority="P1",
    purpose="Insert columns.",
    parameters=schema({
        "table_id": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["table_id", "index"]),
    status="implemented",
)
def insert_table_columns_live(table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_table_columns(doc, table_id, index, count)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_table_columns_live",
    priority="P1",
    purpose="Delete columns.",
    parameters=schema({
        "table_id": {"type": "string"},
        "index": {"type": "integer"},
        "count": {"type": "integer", "default": 1},
    }, required=["table_id", "index"]),
    status="implemented",
)
def delete_table_columns_live(table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.delete_table_columns(doc, table_id, index, count)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="merge_table_cells_live",
    priority="P2",
    purpose="Merge a rectangular cell selection where Writer permits.",
    parameters=schema({
        "table_id": {"type": "string"},
        "start_cell": {"type": "string"},
        "end_cell": {"type": "string"},
    }, required=["table_id", "start_cell", "end_cell"]),
    status="implemented",
)
def merge_table_cells_live(table_id: str, start_cell: str, end_cell: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.merge_table_cells(doc, table_id, start_cell, end_cell)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="split_table_cell_live",
    priority="P2",
    purpose="Split a cell horizontally/vertically.",
    parameters=schema({
        "table_id": {"type": "string"},
        "cell": {"type": "string"},
        "count": {"type": "integer"},
        "direction": {"type": "string"},
    }, required=["table_id", "cell", "count", "direction"]),
    status="implemented",
)
def split_table_cell_live(table_id: str, cell: str, count: int, direction: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.split_table_cell(doc, table_id, cell, count, direction)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_table_format_live",
    priority="P1",
    purpose="Set width/alignment/borders/background/spacing/repeating header/keep behavior.",
    parameters=schema({
        "table_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["table_id", "properties"]),
    status="implemented",
)
def set_table_format_live(table_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_table_format(doc, table_id, properties)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_table_cell_format_live",
    priority="P1",
    purpose="Set cell text/alignment/background/borders/number format.",
    parameters=schema({
        "table_id": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["table_id", "range", "properties"]),
    status="implemented",
)
def set_table_cell_format_live(table_id: str, range: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.set_table_cell_format(doc, table_id, range, properties)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="sort_table_live",
    priority="P2",
    purpose="Sort Writer table rows by one or more columns.",
    parameters=schema({
        "table_id": {"type": "string"},
        "keys": {"type": "array", "items": {"type": "object"}},
    }, required=["table_id", "keys"]),
    status="implemented",
)
def sort_table_live(table_id: str, keys: List[Dict[str, Any]]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.sort_table(doc, table_id, keys)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_table_live",
    priority="P1",
    purpose="Remove a Writer table.",
    parameters=schema({"table_id": {"type": "string"}}, required=["table_id"]),
    status="implemented",
)
def delete_table_live(table_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.delete_table(doc, table_id)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="convert_text_to_table_live",
    priority="P2",
    purpose=(
        "Convert delimited paragraphs/text into a table. `range` is \"<start>-<end>\" "
        "0-based character offsets (not writer_layout.py's {start,end} object convention -- "
        "this tool's own scaffold typed it as a bare string); omit to use the current selection."
    ),
    parameters=schema({
        "range": {"type": "string"},
        "delimiter": {"type": "string", "default": "\t"},
        "options": {"type": "object"},
    }),
    status="implemented",
)
def convert_text_to_table_live(range: Optional[str] = None, delimiter: str = "\t",
                                options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.convert_text_to_table(doc, range, delimiter, options)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="convert_table_to_text_live",
    priority="P2",
    purpose="Convert table to delimited text.",
    parameters=schema({
        "table_id": {"type": "string"},
        "delimiter": {"type": "string", "default": "\t"},
    }, required=["table_id"]),
    status="implemented",
)
def convert_table_to_text_live(table_id: str, delimiter: str = "\t") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.convert_table_to_text(doc, table_id, delimiter)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_sections_live",
    priority="P1",
    purpose="List text sections and protection/link/column settings.",
    status="implemented",
)
def list_sections_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        sections = ctx.uno_bridge.list_sections(doc)
        return envelope.build_success(result={"sections": sections, "count": len(sections)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_section_live",
    priority="P2",
    purpose="Insert a Writer text section. `range` is {start,end} character offsets.",
    parameters=schema({
        "name": {"type": "string"},
        "range": {"type": "object"},
        "columns": {"type": "object"},
        "protected": {"type": "boolean", "default": False},
    }, required=["name"]),
    status="implemented",
)
def insert_section_live(name: str, range: Optional[Dict[str, Any]] = None, columns: Optional[Dict[str, Any]] = None,
                         protected: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_section(doc, name, range, columns, protected)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_section_live",
    priority="P2",
    purpose="Update section columns/background/protection/link visibility.",
    parameters=schema({
        "section_id": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["section_id", "properties"]),
    status="implemented",
)
def update_section_live(section_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.update_section(doc, section_id, properties)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_section_live",
    priority="P2",
    purpose="Remove section wrapper while optionally preserving text.",
    parameters=schema({
        "section_id": {"type": "string"},
        "keep_content": {"type": "boolean", "default": True},
    }, required=["section_id"]),
    status="implemented",
)
def delete_section_live(section_id: str, keep_content: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.delete_section(doc, section_id, keep_content)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_footnote_live",
    priority="P1",
    purpose="Insert footnote at cursor/range.",
    parameters=schema({
        "text": {"type": "string"},
        "position": {"type": "integer"},
    }, required=["text"]),
    status="implemented",
)
def add_footnote_live(text: str, position: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        footnote = ctx.uno_bridge.add_footnote(doc, text, position)
        footnote_id = object_registry.register_object(footnote)
        summary = ctx.uno_bridge.get_footnote_summary(footnote, footnote_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_footnotes_live",
    priority="P1",
    purpose="List footnotes and anchors/content.",
    status="implemented",
)
def list_footnotes_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        footnotes = ctx.uno_bridge.list_footnotes(doc)
        summaries = [
            ctx.uno_bridge.get_footnote_summary(footnote, object_registry.register_object(footnote))
            for footnote in footnotes
        ]
        return envelope.build_success(result={"footnotes": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_footnote_live",
    priority="P2",
    purpose="Replace footnote content.",
    parameters=schema({
        "footnote_id": {"type": "string"},
        "text": {"type": "string"},
    }, required=["footnote_id", "text"]),
    status="implemented",
)
def update_footnote_live(footnote_id: str, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        footnote = _get_object_registry(ctx, resolved_id).resolve_object(footnote_id)
        result = ctx.uno_bridge.update_footnote(footnote, text)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_footnote_live",
    priority="P2",
    purpose="Remove footnote.",
    parameters=schema({"footnote_id": {"type": "string"}}, required=["footnote_id"]),
    status="implemented",
)
def delete_footnote_live(footnote_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        footnote = object_registry.resolve_object(footnote_id)
        ctx.uno_bridge.delete_footnote(footnote)
        object_registry.unregister_object(footnote_id)
        return envelope.build_success(result={"deleted": footnote_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="add_endnote_live",
    priority="P1",
    purpose="Insert endnote.",
    parameters=schema({
        "text": {"type": "string"},
        "position": {"type": "integer"},
    }, required=["text"]),
    status="implemented",
)
def add_endnote_live(text: str, position: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        endnote = ctx.uno_bridge.add_endnote(doc, text, position)
        endnote_id = object_registry.register_object(endnote)
        summary = ctx.uno_bridge.get_endnote_summary(endnote, endnote_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_endnotes_live",
    priority="P1",
    purpose="List endnotes.",
    status="implemented",
)
def list_endnotes_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        endnotes = ctx.uno_bridge.list_endnotes(doc)
        summaries = [
            ctx.uno_bridge.get_endnote_summary(endnote, object_registry.register_object(endnote))
            for endnote in endnotes
        ]
        return envelope.build_success(result={"endnotes": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_endnote_live",
    priority="P2",
    purpose="Replace endnote content.",
    parameters=schema({
        "endnote_id": {"type": "string"},
        "text": {"type": "string"},
    }, required=["endnote_id", "text"]),
    status="implemented",
)
def update_endnote_live(endnote_id: str, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        endnote = _get_object_registry(ctx, resolved_id).resolve_object(endnote_id)
        result = ctx.uno_bridge.update_endnote(endnote, text)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_endnote_live",
    priority="P2",
    purpose="Remove endnote.",
    parameters=schema({"endnote_id": {"type": "string"}}, required=["endnote_id"]),
    status="implemented",
)
def delete_endnote_live(endnote_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        endnote = object_registry.resolve_object(endnote_id)
        ctx.uno_bridge.delete_endnote(endnote)
        object_registry.unregister_object(endnote_id)
        return envelope.build_success(result={"deleted": endnote_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_note_settings_live",
    priority="P2",
    purpose="Get footnote/endnote numbering and placement settings.",
    parameters=schema({"note_type": {"type": "string"}}, required=["note_type"]),
    status="implemented",
)
def get_note_settings_live(note_type: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_note_settings(doc, note_type)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_note_settings_live",
    priority="P2",
    purpose="Set footnote/endnote numbering and placement settings.",
    parameters=schema({
        "note_type": {"type": "string"},
        "settings": {"type": "object"},
    }, required=["note_type", "settings"]),
    status="implemented",
)
def set_note_settings_live(note_type: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_note_settings(doc, note_type, settings)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_content_controls_live",
    priority="P2",
    purpose="List Writer content controls and tags.",
    status="implemented",
)
def list_content_controls_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        controls = ctx.uno_bridge.list_content_controls(doc)
        summaries = [
            ctx.uno_bridge.get_content_control_summary(cc, object_registry.register_object(cc))
            for cc in controls
        ]
        return envelope.build_success(result={"content_controls": summaries, "count": len(summaries)}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_content_control_live",
    priority="P2",
    purpose=(
        "Wrap selection/range in content control with tag/title/placeholder/lock properties. "
        "`range` is \"<start>-<end>\" 0-based character offsets (same invented convention as "
        "convert_text_to_table_live); omit to use the current selection. `type`: checkbox, "
        "dropdown, date, combobox, picture, plaintext."
    ),
    parameters=schema({
        "range": {"type": "string"},
        "tag": {"type": "string"},
        "title": {"type": "string"},
        "type": {"type": "string"},
    }),
    status="implemented",
)
def insert_content_control_live(range: Optional[str] = None, tag: Optional[str] = None,
                                 title: Optional[str] = None, type: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        cc = ctx.uno_bridge.insert_content_control(doc, range, tag, title, type)
        control_id = object_registry.register_object(cc)
        summary = ctx.uno_bridge.get_content_control_summary(cc, control_id)
        return envelope.build_success(result=summary, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_content_control_live",
    priority="P2",
    purpose="Read content control metadata and content.",
    parameters=schema({"control_id": {"type": "string"}}, required=["control_id"]),
    status="implemented",
)
def get_content_control_live(control_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        cc = _get_object_registry(ctx, resolved_id).resolve_object(control_id)
        result = ctx.uno_bridge.get_content_control(cc, control_id)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_content_control_live",
    priority="P2",
    purpose="Set content and control properties.",
    parameters=schema({
        "control_id": {"type": "string"},
        "text": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["control_id"]),
    status="implemented",
)
def set_content_control_live(control_id: str, text: Optional[str] = None,
                              properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        cc = _get_object_registry(ctx, resolved_id).resolve_object(control_id)
        applied = ctx.uno_bridge.set_content_control(cc, text, properties)
        return envelope.build_success(result={"applied": applied}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_content_control_live",
    priority="P2",
    purpose="Remove control wrapper, optionally preserve content.",
    parameters=schema({
        "control_id": {"type": "string"},
        "keep_content": {"type": "boolean", "default": True},
    }, required=["control_id"]),
    status="implemented",
)
def delete_content_control_live(control_id: str, keep_content: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        object_registry = _get_object_registry(ctx, resolved_id)
        cc = object_registry.resolve_object(control_id)
        wrapper_removed = ctx.uno_bridge.delete_content_control(doc, cc, keep_content)
        object_registry.unregister_object(control_id)
        warnings = []
        if not wrapper_removed:
            warnings.append(
                "LibreOffice does not support removing a content control's wrapper in this build -- "
                "only its content could be cleared/preserved. The empty control still exists in the "
                "document (just no longer tracked under this control_id)."
            )
        result = {"deleted": control_id, "keep_content": keep_content, "wrapper_removed": wrapper_removed}
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="preview_mail_merge_live",
    priority="P3",
    purpose=(
        "Resolve a Writer mail-merge template against selected rows without final output. "
        "`data_source` is a folder path containing CSV files (connected ad hoc, no persisted "
        "data-source registration needed); `command` is the CSV file's base name (its SQL table "
        "name). Does not mutate the live document -- returns each selected row's data alongside "
        "the values any Database merge fields already in the document would resolve to."
    ),
    parameters=schema({
        "data_source": {"type": "string"},
        "command": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
        "output": {"type": "string", "default": "preview"},
    }, required=["data_source", "command"]),
    status="implemented",
)
def preview_mail_merge_live(data_source: str, command: str, rows: Optional[List[int]] = None,
                             output: str = "preview") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.preview_mail_merge(doc, data_source, command, rows, output)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="mail_merge_live",
    priority="P3",
    purpose=(
        "Execute mail merge to individual documents, one file, print, or email-ready outputs. "
        "NOT IMPLEMENTED this pass -- the real com.sun.star.text.MailMerge service needs either "
        "a live Model (read-only, live-verified) or a DataSourceName resolvable through "
        "com.sun.star.sdb.DatabaseContext, which live-verified refuses to register an ad hoc "
        "DataSource without a persisted .odb file first. See preview_mail_merge_live for the "
        "real, working data-connection half of this feature."
    ),
    parameters=schema({
        "data_source": {"type": "string"},
        "command": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
        "output_mode": {"type": "string"},
        "output_dir": {"type": "string"},
        "naming": {"type": "string"},
    }, required=["data_source", "command", "output_mode"]),
)
def mail_merge_live(data_source: str, command: str, output_mode: str, rows: Optional[List[int]] = None,
                     output_dir: Optional[str] = None, naming: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("mail_merge_live", start)
