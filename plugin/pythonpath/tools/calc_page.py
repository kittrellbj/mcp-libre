"""
Phase C scaffold: Calc - page setup, print ranges, annotations, protection.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Calc - page setup, print ranges, annotations, protection" (scope: Calc).
No tools in this section are marked "(existing)"; all 15 are scaffolded
here.

Every function is a stub: it returns envelope.build_not_implemented(...)
without touching UNO. See docs/MCP_TOOLING_SCAFFOLD_PLAN.md.
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="get_sheet_page_layout_live",
    priority="P2",
    purpose="Return Calc page style, paper, margins, scaling, headers/footers.",
    parameters=schema({"sheet": {"type": "string"}}),
)
def get_sheet_page_layout_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_sheet_page_layout_live", start)


@register_tool(
    name="set_sheet_page_layout_live",
    priority="P2",
    purpose="Set Calc paper/page orientation/margins/scaling.",
    parameters=schema({
        "sheet": {"type": "string"},
        "width": {"type": "number"},
        "height": {"type": "number"},
        "unit": {"type": "string"},
        "orientation": {"type": "string"},
        "margins": {"type": "object"},
        "scale": {"type": "object"},
    }),
)
def set_sheet_page_layout_live(sheet: Optional[str] = None, width: Optional[float] = None,
                                height: Optional[float] = None, unit: Optional[str] = None,
                                orientation: Optional[str] = None, margins: Optional[Dict[str, Any]] = None,
                                scale: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_sheet_page_layout_live", start)


@register_tool(
    name="set_print_area_live",
    priority="P1",
    purpose="Set one or more print ranges.",
    parameters=schema({
        "sheet": {"type": "string"},
        "ranges": {"type": "array", "items": {"type": "string"}},
    }, required=["ranges"]),
)
def set_print_area_live(ranges: List[str], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_print_area_live", start)


@register_tool(
    name="clear_print_area_live",
    priority="P1",
    purpose="Clear explicit print ranges.",
    parameters=schema({"sheet": {"type": "string"}}),
)
def clear_print_area_live(sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_print_area_live", start)


@register_tool(
    name="set_repeating_print_rows_live",
    priority="P2",
    purpose="Set rows repeated at top of printed pages.",
    parameters=schema({
        "sheet": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "integer"}},
    }, required=["rows"]),
)
def set_repeating_print_rows_live(rows: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_repeating_print_rows_live", start)


@register_tool(
    name="set_repeating_print_columns_live",
    priority="P2",
    purpose="Set columns repeated at left of printed pages.",
    parameters=schema({
        "sheet": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "integer"}},
    }, required=["columns"]),
)
def set_repeating_print_columns_live(columns: List[int], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_repeating_print_columns_live", start)


@register_tool(
    name="add_cell_comment_live",
    priority="P1",
    purpose="Add/update Calc cell annotation.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
        "text": {"type": "string"},
        "author": {"type": "string"},
    }, required=["cell", "text"]),
)
def add_cell_comment_live(cell: str, text: str, sheet: Optional[str] = None,
                           author: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("add_cell_comment_live", start)


@register_tool(
    name="list_cell_comments_live",
    priority="P1",
    purpose="List Calc cell annotations.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
    }),
)
def list_cell_comments_live(sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_cell_comments_live", start)


@register_tool(
    name="delete_cell_comment_live",
    priority="P1",
    purpose="Delete cell annotation.",
    parameters=schema({
        "sheet": {"type": "string"},
        "cell": {"type": "string"},
    }, required=["cell"]),
)
def delete_cell_comment_live(cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_cell_comment_live", start)


@register_tool(
    name="protect_sheet_live",
    priority="P2",
    purpose="Protect sheet with optional password and permissions.",
    parameters=schema({
        "sheet": {"type": "string"},
        "password": {"type": "string"},
        "options": {"type": "object"},
    }),
)
def protect_sheet_live(sheet: Optional[str] = None, password: Optional[str] = None,
                        options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("protect_sheet_live", start)


@register_tool(
    name="unprotect_sheet_live",
    priority="P2",
    purpose="Unprotect sheet.",
    parameters=schema({
        "sheet": {"type": "string"},
        "password": {"type": "string"},
    }),
)
def unprotect_sheet_live(sheet: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("unprotect_sheet_live", start)


@register_tool(
    name="set_cell_protection_live",
    priority="P2",
    purpose="Set locked/hidden/formula-hidden flags for range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["range", "properties"]),
)
def set_cell_protection_live(range: str, properties: Dict[str, Any], sheet: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_cell_protection_live", start)


@register_tool(
    name="list_number_formats_live",
    priority="P2",
    purpose="List number formats/keys/locales.",
    parameters=schema({"locale": {"type": "string"}}),
)
def list_number_formats_live(locale: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_number_formats_live", start)


@register_tool(
    name="create_number_format_live",
    priority="P2",
    purpose="Create/reuse number format string.",
    parameters=schema({
        "format_code": {"type": "string"},
        "locale": {"type": "string"},
    }, required=["format_code"]),
)
def create_number_format_live(format_code: str, locale: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_number_format_live", start)


@register_tool(
    name="apply_number_format_live",
    priority="P1",
    purpose="Apply number format to range.",
    parameters=schema({
        "sheet": {"type": "string"},
        "range": {"type": "string"},
        "format_code": {"type": "string"},
        "format_key": {"type": "integer"},
    }, required=["range"]),
)
def apply_number_format_live(range: str, sheet: Optional[str] = None, format_code: Optional[str] = None,
                              format_key: Optional[int] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("apply_number_format_live", start)
