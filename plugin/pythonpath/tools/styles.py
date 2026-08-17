"""
Phase A scaffold: Styles and formatting infrastructure.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Styles and formatting infrastructure" (scope: Writer, Calc, Impress, Draw;
partial Base).

UNO basis per spec: XStyleFamiliesSupplier, StyleFamilies, PageStyle/
PageProperties, character/paragraph/cell/graphic styles. `target` in
apply_style_live/get_direct_formatting_live/etc. is left untyped
(Any/Optional[str]) pending a decision on the shared "target selector"
shape used across the whole catalog (current selection vs. an explicit
range/object id) -- see docs/MCP_TOOLING_SCAFFOLD_PLAN.md, flagged for
Morgan.
"""

from typing import Any, Dict, List, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="list_style_families_live",
    priority="P1",
    purpose="List style families supported by the active document.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def list_style_families_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_style_families_live", start)


@register_tool(
    name="list_styles_live",
    priority="P1",
    purpose="List styles in a family with user-defined/in-use flags.",
    parameters=schema({"family": {"type": "string"}}, required=["family"]),
)
def list_styles_live(family: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_styles_live", start)


@register_tool(
    name="get_style_live",
    priority="P1",
    purpose="Return style properties and parent relationship.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
    }, required=["family", "style_name"]),
)
def get_style_live(family: str, style_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_style_live", start)


@register_tool(
    name="create_style_live",
    priority="P1",
    purpose="Create a user style in a supported family.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
        "parent_style": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["family", "style_name"]),
)
def create_style_live(family: str, style_name: str, parent_style: Optional[str] = None,
                       properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("create_style_live", start)


@register_tool(
    name="clone_style_live",
    priority="P2",
    purpose="Clone an existing style under a new name.",
    parameters=schema({
        "family": {"type": "string"},
        "source_style": {"type": "string"},
        "new_style": {"type": "string"},
    }, required=["family", "source_style", "new_style"]),
)
def clone_style_live(family: str, source_style: str, new_style: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clone_style_live", start)


@register_tool(
    name="update_style_live",
    priority="P1",
    purpose="Update selected style properties.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
        "properties": {"type": "object"},
    }, required=["family", "style_name", "properties"]),
)
def update_style_live(family: str, style_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("update_style_live", start)


@register_tool(
    name="rename_style_live",
    priority="P2",
    purpose="Rename a user-defined style where the family permits it.",
    parameters=schema({
        "family": {"type": "string"},
        "old_name": {"type": "string"},
        "new_name": {"type": "string"},
    }, required=["family", "old_name", "new_name"]),
)
def rename_style_live(family: str, old_name: str, new_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("rename_style_live", start)


@register_tool(
    name="delete_style_live",
    priority="P2",
    purpose="Delete an unused user-defined style.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
    }, required=["family", "style_name"]),
)
def delete_style_live(family: str, style_name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("delete_style_live", start)


@register_tool(
    name="apply_style_live",
    priority="P1",
    purpose="Apply a named style to current/explicit selection or object.",
    parameters=schema({
        "family": {"type": "string"},
        "style_name": {"type": "string"},
        "target": {"description": "Current selection when omitted; otherwise an explicit range/object selector."},
    }, required=["family", "style_name"]),
)
def apply_style_live(family: str, style_name: str, target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("apply_style_live", start)


@register_tool(
    name="get_direct_formatting_live",
    priority="P2",
    purpose="Return direct formatting overrides on current/explicit target.",
    parameters=schema({"target": {"description": "Current selection when omitted; otherwise an explicit range/object selector."}}),
)
def get_direct_formatting_live(target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_direct_formatting_live", start)


@register_tool(
    name="clear_direct_formatting_live",
    priority="P1",
    purpose="Clear direct formatting and preserve style-driven formatting.",
    parameters=schema({"target": {"description": "Current selection when omitted; otherwise an explicit range/object selector."}}),
)
def clear_direct_formatting_live(target: Optional[Any] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("clear_direct_formatting_live", start)


@register_tool(
    name="copy_formatting_live",
    priority="P2",
    purpose="Copy formatting/style attributes between two targets.",
    parameters=schema({
        "source": {"description": "Explicit range/object selector to copy formatting from."},
        "target": {"description": "Explicit range/object selector to copy formatting to."},
        "include": {"type": "array", "items": {"type": "string"}, "description": "Optional subset of attribute groups to copy."},
    }, required=["source", "target"]),
)
def copy_formatting_live(source: Any, target: Any, include: Optional[List[str]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("copy_formatting_live", start)
