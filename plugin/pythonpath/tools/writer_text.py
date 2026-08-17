"""
Phase B scaffold: Writer - text, navigation, editing, search, review.

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
module only scaffolds the 18 new tools in the section.

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="insert_paragraph_live",
    priority="P1",
    purpose="Insert a paragraph before/after current or specified paragraph.",
    parameters=schema({
        "text": {"type": "string", "default": ""},
        "at_paragraph": {"type": "integer"},
        "position": {"type": "string", "enum": ["before", "after"]},
    }),
)
def insert_paragraph_live(text: str = "", at_paragraph: Optional[int] = None,
                           position: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_paragraph_live", start)


@register_tool(
    name="append_paragraph_live",
    priority="P1",
    purpose="Append a paragraph to the end of the document.",
    parameters=schema({
        "text": {"type": "string", "default": ""},
        "style_name": {"type": "string"},
    }),
)
def append_paragraph_live(text: str = "", style_name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("append_paragraph_live", start)


@register_tool(
    name="insert_heading_live",
    priority="P1",
    purpose="Insert a heading with outline level/style.",
    parameters=schema({
        "text": {"type": "string"},
        "level": {"type": "integer", "default": 1},
        "at_paragraph": {"type": "integer"},
        "position": {"type": "string", "enum": ["before", "after"]},
    }, required=["text"]),
)
def insert_heading_live(text: str, level: int = 1, at_paragraph: Optional[int] = None,
                         position: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("insert_heading_live", start)


@register_tool(
    name="set_paragraph_text_live",
    priority="P1",
    purpose="Replace one paragraph's text while preserving paragraph identity/style when possible.",
    parameters=schema({
        "n": {"type": "integer"},
        "text": {"type": "string"},
    }, required=["n", "text"]),
)
def set_paragraph_text_live(n: int, text: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_paragraph_text_live", start)


@register_tool(
    name="split_paragraph_live",
    priority="P2",
    purpose="Split paragraph at character offset.",
    parameters=schema({
        "n": {"type": "integer"},
        "offset": {"type": "integer"},
    }, required=["n", "offset"]),
)
def split_paragraph_live(n: int, offset: int) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("split_paragraph_live", start)


@register_tool(
    name="merge_paragraphs_live",
    priority="P2",
    purpose="Merge adjacent paragraphs.",
    parameters=schema({
        "first_n": {"type": "integer"},
        "count": {"type": "integer", "default": 2},
        "separator": {"type": "string", "default": " "},
    }, required=["first_n"]),
)
def merge_paragraphs_live(first_n: int, count: int = 2, separator: str = " ") -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("merge_paragraphs_live", start)


@register_tool(
    name="move_paragraphs_live",
    priority="P2",
    purpose="Move a contiguous paragraph range.",
    parameters=schema({
        "start": {"type": "integer"},
        "end": {"type": "integer"},
        "destination": {"type": "integer"},
    }, required=["start", "end", "destination"]),
)
def move_paragraphs_live(start: int, end: int, destination: int) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    return envelope.build_not_implemented("move_paragraphs_live", start_time)


@register_tool(
    name="copy_paragraphs_live",
    priority="P2",
    purpose="Copy a paragraph range to destination.",
    parameters=schema({
        "start": {"type": "integer"},
        "end": {"type": "integer"},
        "destination": {"type": "integer"},
    }, required=["start", "end", "destination"]),
)
def copy_paragraphs_live(start: int, end: int, destination: int) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    return envelope.build_not_implemented("copy_paragraphs_live", start_time)


@register_tool(
    name="set_paragraph_format_live",
    priority="P1",
    purpose="Set alignment, indents, spacing, line spacing, keep/widow/orphan, tabs, borders/background.",
    parameters=schema({
        "target": {"description": "Current selection when omitted; otherwise an explicit range/paragraph selector."},
        "properties": {"type": "object"},
    }, required=["target", "properties"]),
)
def set_paragraph_format_live(target: Any, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_paragraph_format_live", start)


@register_tool(
    name="set_character_format_live",
    priority="P1",
    purpose="Set font/size/weight/posture/color/highlight/case/spacing/language/decoration.",
    parameters=schema({
        "target": {"description": "Current selection when omitted; otherwise an explicit range selector."},
        "properties": {"type": "object"},
    }, required=["target", "properties"]),
)
def set_character_format_live(target: Any, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_character_format_live", start)


@register_tool(
    name="get_text_range_format_live",
    priority="P2",
    purpose="Inspect effective character and paragraph formatting for a range.",
    parameters=schema({
        "start": {"type": "integer"},
        "end": {"type": "integer"},
    }, required=["start", "end"]),
)
def get_text_range_format_live(start: int, end: int) -> Dict[str, Any]:
    start_time = envelope.start_timer()
    return envelope.build_not_implemented("get_text_range_format_live", start_time)


@register_tool(
    name="find_regex_live",
    priority="P1",
    purpose="Find text using LibreOffice regex search.",
    parameters=schema({
        "pattern": {"type": "string"},
        "case_sensitive": {"type": "boolean", "default": False},
    }, required=["pattern"]),
)
def find_regex_live(pattern: str, case_sensitive: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("find_regex_live", start)


@register_tool(
    name="replace_regex_live",
    priority="P1",
    purpose="Regex replacement with first/all choice.",
    parameters=schema({
        "pattern": {"type": "string"},
        "replacement": {"type": "string"},
        "all": {"type": "boolean", "default": True},
    }, required=["pattern", "replacement"]),
)
def replace_regex_live(pattern: str, replacement: str, all: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("replace_regex_live", start)


@register_tool(
    name="find_by_style_live",
    priority="P2",
    purpose="Find paragraphs/runs using a named style.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
    }, required=["family", "style_name"]),
)
def find_by_style_live(family: str, style_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("find_by_style_live", start)


@register_tool(
    name="replace_style_live",
    priority="P2",
    purpose="Replace one paragraph/character style with another.",
    parameters=schema({
        "family": {"type": "string"},
        "old_style": {"type": "string"},
        "new_style": {"type": "string"},
    }, required=["family", "old_style", "new_style"]),
)
def replace_style_live(family: str, old_style: str, new_style: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("replace_style_live", start)


@register_tool(
    name="update_comment_live",
    priority="P1",
    purpose="Edit comment author/content.",
    parameters=schema({
        "comment_id": {"type": "string"},
        "text": {"type": "string"},
        "author": {"type": "string"},
    }, required=["comment_id"]),
)
def update_comment_live(comment_id: str, text: Optional[str] = None, author: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("update_comment_live", start)


@register_tool(
    name="delete_comment_live",
    priority="P1",
    purpose="Delete one comment.",
    parameters=schema({"comment_id": {"type": "string"}}, required=["comment_id"]),
)
def delete_comment_live(comment_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_comment_live", start)


@register_tool(
    name="resolve_comment_live",
    priority="P2",
    purpose="Mark comment resolved where supported; otherwise emulate with metadata.",
    parameters=schema({
        "comment_id": {"type": "string"},
        "resolved": {"type": "boolean", "default": True},
    }, required=["comment_id"]),
)
def resolve_comment_live(comment_id: str, resolved: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("resolve_comment_live", start)
