"""
Writer - text, navigation, editing, search, review -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Writer - text, navigation, editing, search, review" (scope: Writer).

27 tools in that spec section are marked "(existing)" and already live in
plugin/pythonpath/mcp_server.py / uno_bridge.py under the same names --
insert_text_live, get_text_content_live, format_text_live,
get_paragraph_count_live, get_document_outline_live, get_paragraph_live,
get_paragraphs_range_live, goto_paragraph_live, goto_position_live,
get_cursor_position_live, get_context_around_cursor_live,
select_paragraph_live, select_text_range_live, delete_selection_live,
replace_selection_live, find_text_live, find_and_replace_live,
find_and_replace_all_live, get_comments_live, add_comment_live,
get_track_changes_status_live, set_track_changes_live,
get_tracked_changes_live, accept_tracked_change_live,
reject_tracked_change_live, accept_all_changes_live,
reject_all_changes_live. They are intentionally NOT duplicated here; this
module implements the 18 new tools in the section, following the same
pattern as core_runtime.py/document_lifecycle.py/undo_view_selection.py/
styles.py: status="implemented", tools.context.get_context() for the live
UNOBridge/DocumentRegistry, _resolve_and_register/_error_response reused
from document_lifecycle.py. None of these 18 tools take a document_id
parameter (matching the spec's own parameter list for each, and the
precedent set by styles.py) -- every one resolves the active document.

`target` resolution for set_paragraph_format_live/set_character_format_live
reuses UNOBridge._resolve_text_target (styles.py's apply_style_live
precedent): omitted/None means the current selection, an explicit
{"start": int, "end": int} means a 0-based Writer character range.
get_text_range_format_live uses the same helper internally but keeps its
own start/end parameter shape (matching its scaffolded schema exactly,
not a target object).

Paragraph editing (insert/append/heading/set-text/split/merge/move/copy)
is all built on the same paragraph-enumeration technique
get_paragraph_live/goto_paragraph_live/select_paragraph_live already use
(text.createEnumeration(), filtered to com.sun.star.text.Paragraph) --
see UNOBridge._get_paragraph_object/_count_paragraphs/_current_paragraph_index.

Regex search/replace (find_regex_live/replace_regex_live) uses Writer's
own XSearchable/XReplaceable with SearchRegularExpression=True (real
ICU/LibreOffice regex, including $1-style backreferences in
replace_regex_live's replacement), not hand-rolled Python re + manual
cursor placement -- confirmed to expose everything these two tools need
(match text/position, replacement count).

Comments (update_comment_live/delete_comment_live/resolve_comment_live)
address the exact same com.sun.star.text.TextField.Annotation fields
get_comments_live/add_comment_live already enumerate/create -- see
UNOBridge's "Comments (update/delete/resolve)" section for the comment_id
scheme this required inventing (get_comments_live had no id field before
this pass; a minimal, additive one was added, see the commit message).

Known landmine avoided, not repeated: the original 32 tools' format_text_live
uses a literal isinstance(doc, XTextDocument) check instead of
supportsService(), and fails against some validly-open Writer documents as
a result (documented, deliberately left unfixed -- see the styles.py pass's
commit message). Every method this pass adds to UNOBridge checks document
type via _get_document_type() (supportsService()-first) through the shared
_require_writer() helper instead.
"""

from typing import Any, Dict, Optional

from . import context
from . import envelope
from .document_lifecycle import _error_response, _resolve_and_register
from .registry import register_tool, schema


@register_tool(
    name="insert_paragraph_live",
    priority="P1",
    purpose=(
        "Insert a paragraph before/after a paragraph. at_paragraph is 1-based; "
        "position defaults to 'after'. If at_paragraph is omitted, the anchor is "
        "wherever the last insert_paragraph_live/insert_heading_live/"
        "insert_page_break_live call (in this session, single or batched) left off, "
        "not a fixed 'current selection' -- pass at_paragraph explicitly for an "
        "absolute target (BUG #7 finding: this was previously undocumented and "
        "flaky under batch_execute_live, see BUG #5's fix)."
    ),
    parameters=schema({
        "text": {"type": "string", "default": ""},
        "at_paragraph": {"type": "integer"},
        "position": {"type": "string", "enum": ["before", "after"]},
    }),
    status="implemented",
)
def insert_paragraph_live(text: str = "", at_paragraph: Optional[int] = None,
                           position: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_paragraph(doc, text=text, at_paragraph=at_paragraph, position=position)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="append_paragraph_live",
    priority="P1",
    purpose=(
        "Append a paragraph to the end of the document. style_name is validated "
        "before anything is inserted, so an unknown name now fails atomically "
        "(nothing appended) rather than partially applying (BUG #9 fix). "
        "Doc note: a fresh Writer document exposes the default body style as "
        "'Standard', not the ODF-standard 'Default Paragraph Style' name."
    ),
    parameters=schema({
        "text": {"type": "string", "default": ""},
        "style_name": {"type": "string"},
    }),
    status="implemented",
)
def append_paragraph_live(text: str = "", style_name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.append_paragraph(doc, text=text, style_name=style_name)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="insert_heading_live",
    priority="P1",
    purpose=(
        "Insert a heading with outline level/style. Same at_paragraph/position "
        "contract as insert_paragraph_live -- 1-based, defaults to 'after', and "
        "an omitted at_paragraph anchors off the last insert in this session "
        "(see BUG #7/#5 finding on insert_paragraph_live)."
    ),
    parameters=schema({
        "text": {"type": "string"},
        "level": {"type": "integer", "default": 1},
        "at_paragraph": {"type": "integer"},
        "position": {"type": "string", "enum": ["before", "after"]},
    }, required=["text"]),
    status="implemented",
)
def insert_heading_live(text: str, level: int = 1, at_paragraph: Optional[int] = None,
                         position: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.insert_heading(doc, text, level=level, at_paragraph=at_paragraph, position=position)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_paragraph_text_live",
    priority="P1",
    purpose="Replace one paragraph's text while preserving paragraph identity/style when possible.",
    parameters=schema({
        "n": {"type": "integer"},
        "text": {"type": "string"},
    }, required=["n", "text"]),
    status="implemented",
)
def set_paragraph_text_live(n: int, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.set_paragraph_text(doc, n, text)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="split_paragraph_live",
    priority="P2",
    purpose="Split paragraph at character offset.",
    parameters=schema({
        "n": {"type": "integer"},
        "offset": {"type": "integer"},
    }, required=["n", "offset"]),
    status="implemented",
)
def split_paragraph_live(n: int, offset: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.split_paragraph(doc, n, offset)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="merge_paragraphs_live",
    priority="P2",
    purpose="Merge adjacent paragraphs.",
    parameters=schema({
        "first_n": {"type": "integer"},
        "count": {"type": "integer", "default": 2},
        "separator": {"type": "string", "default": " "},
    }, required=["first_n"]),
    status="implemented",
)
def merge_paragraphs_live(first_n: int, count: int = 2, separator: str = " ") -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.merge_paragraphs(doc, first_n, count=count, separator=separator)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="move_paragraphs_live",
    priority="P2",
    purpose="Move a contiguous paragraph range.",
    parameters=schema({
        "start": {"type": "integer"},
        "end": {"type": "integer"},
        "destination": {"type": "integer"},
    }, required=["start", "end", "destination"]),
    status="implemented",
)
def move_paragraphs_live(start: int, end: int, destination: int) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.move_paragraphs(doc, start, end, destination)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start_time))
    except Exception as e:
        return _error_response(e, start_time)


@register_tool(
    name="copy_paragraphs_live",
    priority="P2",
    purpose="Copy a paragraph range to destination.",
    parameters=schema({
        "start": {"type": "integer"},
        "end": {"type": "integer"},
        "destination": {"type": "integer"},
    }, required=["start", "end", "destination"]),
    status="implemented",
)
def copy_paragraphs_live(start: int, end: int, destination: int) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.copy_paragraphs(doc, start, end, destination)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start_time))
    except Exception as e:
        return _error_response(e, start_time)


@register_tool(
    name="set_paragraph_format_live",
    priority="P1",
    purpose="Set alignment, indents, spacing, line spacing, keep/widow/orphan, tabs, borders/background.",
    parameters=schema({
        "target": {"description": "Current selection when omitted; otherwise an explicit range/paragraph selector."},
        "properties": {"type": "object"},
    }, required=["target", "properties"]),
    status="implemented",
)
def set_paragraph_format_live(properties: Dict[str, Any], target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_paragraph_format(doc, target, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(
            result={"applied": applied}, document_id=resolved_id, warnings=warnings,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="set_character_format_live",
    priority="P1",
    purpose="Set font/size/weight/posture/color/highlight/case/spacing/language/decoration.",
    parameters=schema({
        "target": {"description": "Current selection when omitted; otherwise an explicit range selector."},
        "properties": {"type": "object"},
    }, required=["target", "properties"]),
    status="implemented",
)
def set_character_format_live(properties: Dict[str, Any], target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        applied = ctx.uno_bridge.set_character_format(doc, target, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(
            result={"applied": applied}, document_id=resolved_id, warnings=warnings,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_text_range_format_live",
    priority="P2",
    purpose="Inspect effective character and paragraph formatting for a range.",
    parameters=schema({
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    }, required=["start", "end"]),
    status="implemented",
)
def get_text_range_format_live(start: int, end: int) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.get_text_range_format(doc, start, end)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start_time))
    except Exception as e:
        return _error_response(e, start_time)


@register_tool(
    name="find_regex_live",
    priority="P1",
    purpose="Find text using LibreOffice regex search.",
    parameters=schema({
        "pattern": {"type": "string"},
        "case_sensitive": {"type": "boolean", "default": False},
    }, required=["pattern"]),
    status="implemented",
)
def find_regex_live(pattern: str, case_sensitive: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.find_regex(doc, pattern, case_sensitive=case_sensitive)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="replace_regex_live",
    priority="P1",
    purpose="Regex replacement with first/all choice.",
    parameters=schema({
        "pattern": {"type": "string"},
        "replacement": {"type": "string"},
        "all": {"type": "boolean", "default": True},
    }, required=["pattern", "replacement"]),
    status="implemented",
)
def replace_regex_live(pattern: str, replacement: str, all: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.replace_regex(doc, pattern, replacement, all=all)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="find_by_style_live",
    priority="P2",
    purpose="Find paragraphs/runs using a named style.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
    }, required=["family", "style_name"]),
    status="implemented",
)
def find_by_style_live(family: str, style_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.find_by_style(doc, family, style_name)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="replace_style_live",
    priority="P2",
    purpose="Replace one paragraph/character style with another.",
    parameters=schema({
        "family": {"type": "string"},
        "old_style": {"type": "string"},
        "new_style": {"type": "string"},
    }, required=["family", "old_style", "new_style"]),
    status="implemented",
)
def replace_style_live(family: str, old_style: str, new_style: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.replace_style(doc, family, old_style, new_style)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="update_comment_live",
    priority="P1",
    purpose="Edit comment author/content.",
    parameters=schema({
        "comment_id": {"type": "string"},
        "text": {"type": "string"},
        "author": {"type": "string"},
    }, required=["comment_id"]),
    status="implemented",
)
def update_comment_live(comment_id: str, text: Optional[str] = None, author: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    if text is None and author is None:
        return envelope.build_error(
            "INVALID_PARAMETER", "Provide at least one of text or author to update.",
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.update_comment(doc, comment_id, text=text, author=author)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="delete_comment_live",
    priority="P1",
    purpose="Delete one comment.",
    parameters=schema({"comment_id": {"type": "string"}}, required=["comment_id"]),
    status="implemented",
)
def delete_comment_live(comment_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.delete_comment(doc, comment_id)
        return envelope.build_success(result={"deleted": comment_id}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="resolve_comment_live",
    priority="P2",
    purpose="Mark comment resolved where supported; otherwise emulate with metadata.",
    parameters=schema({
        "comment_id": {"type": "string"},
        "resolved": {"type": "boolean", "default": True},
    }, required=["comment_id"]),
    status="implemented",
)
def resolve_comment_live(comment_id: str, resolved: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        result = ctx.uno_bridge.resolve_comment(doc, comment_id, resolved=resolved)
        warnings = []
        if result.get("emulated"):
            warnings.append(
                "This LibreOffice build's comments do not expose a native Resolved property; "
                "resolved state was emulated with a Content marker instead."
            )
        return envelope.build_success(result=result, document_id=resolved_id, warnings=warnings, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)
