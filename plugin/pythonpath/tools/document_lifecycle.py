"""
Phase A scaffold: Document and session lifecycle.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Document and session lifecycle" (scope: all document types).

Five tools in that spec section are marked "(existing)" and already live in
plugin/pythonpath/mcp_server.py / uno_bridge.py under the same names --
list_open_documents, create_document_live, get_document_info_live,
save_document_live, export_document_live. They are intentionally NOT
duplicated here; per spec section 6, the original 32 must stay as
compatibility names with unchanged semantics. This module only scaffolds
the remaining new tools in the section.

Most of these need DocumentRegistry (see documents.py) for the document_id
parameter to mean anything; until that lands, treat document_id as
"reserved, currently ignored" in any stub that gets a real implementation
ahead of the registry.
"""

from typing import Any, Dict, Optional

from . import envelope
from .registry import register_tool, schema


@register_tool(
    name="get_active_document_live",
    priority="P1",
    purpose="Return the active document handle and type.",
)
def get_active_document_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_active_document_live", start)


@register_tool(
    name="activate_document_live",
    priority="P1",
    purpose="Bring a specified open document to the active frame.",
    parameters=schema({"document_id": {"type": "string"}}, required=["document_id"]),
)
def activate_document_live(document_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("activate_document_live", start)


@register_tool(
    name="open_document_live",
    priority="P1",
    purpose="Open an existing file with optional read-only/hidden/password/filter options.",
    parameters=schema({
        "file_path": {"type": "string"},
        "read_only": {"type": "boolean", "default": False},
        "hidden": {"type": "boolean", "default": False},
        "password": {"type": "string"},
        "filter_name": {"type": "string"},
    }, required=["file_path"]),
)
def open_document_live(file_path: str, read_only: bool = False, hidden: bool = False,
                        password: Optional[str] = None, filter_name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("open_document_live", start)


@register_tool(
    name="open_from_template_live",
    priority="P2",
    purpose="Create a new document from an ODF or compatible template.",
    parameters=schema({
        "template_path": {"type": "string"},
        "as_template": {"type": "boolean", "default": True},
    }, required=["template_path"]),
)
def open_from_template_live(template_path: str, as_template: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("open_from_template_live", start)


@register_tool(
    name="close_document_live",
    priority="P1",
    purpose="Close a document with explicit save/discard behavior.",
    parameters=schema({
        "document_id": {"type": "string"},
        "save": {"description": "true|false|'prompt'", "default": False},
    }),
)
def close_document_live(document_id: Optional[str] = None, save: Any = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("close_document_live", start)


@register_tool(
    name="get_document_statistics_live",
    priority="P1",
    purpose="Return pages/slides/sheets/words/chars/tables/images/etc. as applicable.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_document_statistics_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_document_statistics_live", start)


@register_tool(
    name="save_as_document_live",
    priority="P1",
    purpose="Explicit Save As with filter and filter options.",
    parameters=schema({
        "file_path": {"type": "string"},
        "filter_name": {"type": "string"},
        "filter_options": {"type": "object"},
        "overwrite": {"type": "boolean", "default": False},
    }, required=["file_path"]),
)
def save_as_document_live(file_path: str, filter_name: Optional[str] = None,
                           filter_options: Optional[Dict[str, Any]] = None,
                           overwrite: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("save_as_document_live", start)


@register_tool(
    name="save_copy_live",
    priority="P2",
    purpose="Store a copy without changing the current document URL.",
    parameters=schema({
        "file_path": {"type": "string"},
        "filter_name": {"type": "string"},
        "overwrite": {"type": "boolean", "default": False},
    }, required=["file_path"]),
)
def save_copy_live(file_path: str, filter_name: Optional[str] = None, overwrite: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("save_copy_live", start)


@register_tool(
    name="convert_document_live",
    priority="P1",
    purpose="Open-convert-save a document between supported formats.",
    parameters=schema({
        "input_path": {"type": "string"},
        "output_path": {"type": "string"},
        "output_format": {"type": "string"},
        "options": {"type": "object"},
    }, required=["input_path", "output_path"]),
)
def convert_document_live(input_path: str, output_path: str, output_format: Optional[str] = None,
                           options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("convert_document_live", start)


@register_tool(
    name="list_export_filters_live",
    priority="P2",
    purpose="List filters available for current document type, extensions, and filter flags.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def list_export_filters_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("list_export_filters_live", start)


@register_tool(
    name="get_document_properties_live",
    priority="P1",
    purpose="Get standard title/subject/author/keywords/description/creation/modification properties.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_document_properties_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_document_properties_live", start)


@register_tool(
    name="set_document_properties_live",
    priority="P1",
    purpose="Set standard document metadata.",
    parameters=schema({
        "properties": {"type": "object"},
        "document_id": {"type": "string"},
    }, required=["properties"]),
)
def set_document_properties_live(properties: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_document_properties_live", start)


@register_tool(
    name="get_custom_properties_live",
    priority="P2",
    purpose="List user-defined/custom document properties.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_custom_properties_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_custom_properties_live", start)


@register_tool(
    name="set_custom_property_live",
    priority="P2",
    purpose="Create or update a custom property.",
    parameters=schema({
        "name": {"type": "string"},
        "value": {},
        "type": {"type": "string"},
    }, required=["name", "value"]),
)
def set_custom_property_live(name: str, value: Any, type: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_custom_property_live", start)


@register_tool(
    name="remove_custom_property_live",
    priority="P2",
    purpose="Delete a custom property.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
)
def remove_custom_property_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("remove_custom_property_live", start)


@register_tool(
    name="get_modified_state_live",
    priority="P2",
    purpose="Return whether document has unsaved changes.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_modified_state_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_modified_state_live", start)


@register_tool(
    name="set_modified_state_live",
    priority="P3",
    purpose="Set/reset modified flag when justified by orchestration code.",
    parameters=schema({
        "modified": {"type": "boolean"},
        "document_id": {"type": "string"},
    }, required=["modified"]),
)
def set_modified_state_live(modified: bool, document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_modified_state_live", start)


@register_tool(
    name="refresh_document_live",
    priority="P1",
    purpose="Refresh fields/links/data supported by the document model.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def refresh_document_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("refresh_document_live", start)


@register_tool(
    name="reload_document_live",
    priority="P3",
    purpose="Reload from storage with explicit unsaved-change policy.",
    parameters=schema({
        "document_id": {"type": "string"},
        "discard_changes": {"type": "boolean", "default": False},
    }),
)
def reload_document_live(document_id: Optional[str] = None, discard_changes: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("reload_document_live", start)


@register_tool(
    name="print_document_live",
    priority="P2",
    purpose="Print with printer/page/copy/options configuration.",
    parameters=schema({
        "printer": {"type": "string"},
        "page_range": {"type": "string"},
        "copies": {"type": "integer", "default": 1},
        "options": {"type": "object"},
    }),
)
def print_document_live(printer: Optional[str] = None, page_range: Optional[str] = None,
                         copies: int = 1, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("print_document_live", start)


@register_tool(
    name="get_print_settings_live",
    priority="P2",
    purpose="Return current print settings.",
    parameters=schema({"document_id": {"type": "string"}}),
)
def get_print_settings_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("get_print_settings_live", start)


@register_tool(
    name="set_print_settings_live",
    priority="P2",
    purpose="Set document print options without printing.",
    parameters=schema({
        "settings": {"type": "object"},
        "document_id": {"type": "string"},
    }, required=["settings"]),
)
def set_print_settings_live(settings: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    return envelope.build_not_implemented("set_print_settings_live", start)
