"""
Document and session lifecycle -- real implementation.

Source: LibreOffice_MCP_Complete_Tooling_Specification.md, section
"Document and session lifecycle" (scope: all document types).

Five tools in that spec section are marked "(existing)" and already live in
plugin/pythonpath/mcp_server.py / uno_bridge.py under the same names --
list_open_documents, create_document_live, get_document_info_live,
save_document_live, export_document_live. They are intentionally NOT
duplicated here; this module implements the 22 new tools in the section.

Like core_runtime.py, every tool here is registered status="implemented"
and reads shared server state via tools.context.get_context(). Unlike
core_runtime.py, most of these resolve a document (via
DocumentRegistry.resolve_document) and delegate to a new UNOBridge method
that does the actual UNO work and raises on failure -- _error_response()
below maps the exception type to a spec error code.

Auto-registration: any tool that resolves "the active document" (document_id
omitted) registers it into DocumentRegistry if it wasn't already there (see
_resolve_and_register). This is how DocumentRegistry gradually gets
populated with real documents instead of staying permanently empty --
previously nothing in the codebase ever called register_document().
"""

from typing import Any, Dict, List, Optional

from . import context
from . import documents
from . import envelope
from . import object_registry
from .registry import register_tool, schema


def _resolve_and_register(ctx, document_id: Optional[str] = None):
    """Resolve document_id (or the active document), registering it for a
    stable id if it wasn't already registered. Returns (document, document_id)."""
    doc = ctx.document_registry.resolve_document(document_id)
    resolved_id = document_id if document_id is not None else ctx.document_registry.register_document(doc)
    return doc, resolved_id


def _map_exception_to_code(e: Exception) -> str:
    """Map a Python exception raised by a UNOBridge document-lifecycle
    method (or DocumentRegistry) onto one of the spec's stable error codes."""
    if isinstance(e, documents.NoActiveDocumentError):
        return "NO_ACTIVE_DOCUMENT"
    if isinstance(e, documents.DocumentNotFoundError):
        return "OBJECT_NOT_FOUND"
    if isinstance(e, object_registry.ObjectNotFoundError):
        return "OBJECT_NOT_FOUND"
    if isinstance(e, FileNotFoundError):
        return "OBJECT_NOT_FOUND"
    if isinstance(e, FileExistsError):
        return "FILE_EXISTS"
    if isinstance(e, PermissionError):
        return "PERMISSION_DENIED"
    if isinstance(e, KeyError):
        return "OBJECT_NOT_FOUND"
    if isinstance(e, IndexError):
        return "INVALID_RANGE"
    if isinstance(e, NotImplementedError):
        return "UNSUPPORTED_CAPABILITY"
    if isinstance(e, (ValueError, TypeError)):
        return "INVALID_PARAMETER"
    return "UNO_EXCEPTION"


def _error_response(e: Exception, start: float, document_id: Optional[str] = None) -> Dict[str, Any]:
    return envelope.build_error(
        _map_exception_to_code(e), str(e), document_id=document_id,
        elapsed_ms=envelope.elapsed_ms_since(start),
    )


@register_tool(
    name="get_active_document_live",
    priority="P1",
    purpose="Return the active document handle and type.",
    status="implemented",
)
def get_active_document_live() -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, document_id = _resolve_and_register(ctx)
        info = ctx.uno_bridge.get_document_info(doc)
        return envelope.build_success(result=info, document_id=document_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="activate_document_live",
    priority="P1",
    purpose="Bring a specified open document to the active frame.",
    parameters=schema({"document_id": {"type": "string"}}, required=["document_id"]),
    status="implemented",
)
def activate_document_live(document_id: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc = ctx.document_registry.resolve_document(document_id)
        ctx.uno_bridge.activate_document(doc)
        return envelope.build_success(result={"activated": True}, document_id=document_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


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
    status="implemented",
)
def open_document_live(file_path: str, read_only: bool = False, hidden: bool = False,
                        password: Optional[str] = None, filter_name: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc = ctx.uno_bridge.open_document(file_path, read_only=read_only, hidden=hidden,
                                            password=password, filter_name=filter_name)
        document_id = ctx.document_registry.register_document(doc)
        info = ctx.uno_bridge.get_document_info(doc)
        return envelope.build_success(result=info, document_id=document_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="open_from_template_live",
    priority="P2",
    purpose="Create a new document from an ODF or compatible template.",
    parameters=schema({
        "template_path": {"type": "string"},
        "as_template": {"type": "boolean", "default": True},
    }, required=["template_path"]),
    status="implemented",
)
def open_from_template_live(template_path: str, as_template: bool = True) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc = ctx.uno_bridge.open_from_template(template_path, as_template=as_template)
        document_id = ctx.document_registry.register_document(doc)
        info = ctx.uno_bridge.get_document_info(doc)
        return envelope.build_success(result=info, document_id=document_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="close_document_live",
    priority="P1",
    purpose="Close a document with explicit save/discard behavior.",
    parameters=schema({
        "document_id": {"type": "string"},
        "save": {"description": "true|false|'prompt'", "default": False},
    }),
    status="implemented",
)
def close_document_live(document_id: Optional[str] = None, save: Any = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc = ctx.document_registry.resolve_document(document_id)
        ctx.uno_bridge.close_document(doc, save=save)
        if document_id is not None:
            ctx.document_registry.unregister_document(document_id)
        return envelope.build_success(result={"closed": True}, document_id=document_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="get_document_statistics_live",
    priority="P1",
    purpose="Return pages/slides/sheets/words/chars/tables/images/etc. as applicable.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_document_statistics_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        stats = ctx.uno_bridge.get_document_statistics(doc)
        return envelope.build_success(result=stats, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


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
    status="implemented",
)
def save_as_document_live(file_path: str, filter_name: Optional[str] = None,
                           filter_options: Optional[Dict[str, Any]] = None,
                           overwrite: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.save_as_document(doc, file_path, filter_name=filter_name,
                                         filter_options=filter_options, overwrite=overwrite)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="save_copy_live",
    priority="P2",
    purpose="Store a copy without changing the current document URL.",
    parameters=schema({
        "file_path": {"type": "string"},
        "filter_name": {"type": "string"},
        "overwrite": {"type": "boolean", "default": False},
    }, required=["file_path"]),
    status="implemented",
)
def save_copy_live(file_path: str, filter_name: Optional[str] = None, overwrite: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.save_copy_document(doc, file_path, filter_name=filter_name, overwrite=overwrite)
        return envelope.build_success(result={"file_path": file_path}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


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
    status="implemented",
)
def convert_document_live(input_path: str, output_path: str, output_format: Optional[str] = None,
                           options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        ctx.uno_bridge.convert_document_file(input_path, output_path, output_format=output_format, options=options)
        result = {"input_path": input_path, "output_path": output_path}
        return envelope.build_success(result=result, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="list_export_filters_live",
    priority="P2",
    purpose="List filters available for current document type, extensions, and filter flags.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def list_export_filters_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        result = ctx.uno_bridge.list_export_filters(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="get_document_properties_live",
    priority="P1",
    purpose="Get standard title/subject/author/keywords/description/creation/modification properties.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_document_properties_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        result = ctx.uno_bridge.get_document_properties(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="set_document_properties_live",
    priority="P1",
    purpose="Set standard document metadata.",
    parameters=schema({
        "properties": {"type": "object"},
        "document_id": {"type": "string"},
    }, required=["properties"]),
    status="implemented",
)
def set_document_properties_live(properties: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        applied = ctx.uno_bridge.set_document_properties(doc, properties)
        skipped = sorted(set(properties) - set(applied))
        warnings = [f"Ignored unknown/unsettable property field(s): {skipped}"] if skipped else []
        return envelope.build_success(
            result={"applied": applied}, document_id=resolved_id, warnings=warnings,
            elapsed_ms=envelope.elapsed_ms_since(start),
        )
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="get_custom_properties_live",
    priority="P2",
    purpose="List user-defined/custom document properties.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_custom_properties_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        result = ctx.uno_bridge.get_custom_properties(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="set_custom_property_live",
    priority="P2",
    purpose="Create or update a custom property.",
    parameters=schema({
        "name": {"type": "string"},
        "value": {},
        "type": {"type": "string"},
    }, required=["name", "value"]),
    status="implemented",
)
def set_custom_property_live(name: str, value: Any, type: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.set_custom_property(doc, name, value, property_type=type)
        return envelope.build_success(result={"name": name, "value": value}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="remove_custom_property_live",
    priority="P2",
    purpose="Delete a custom property.",
    parameters=schema({"name": {"type": "string"}}, required=["name"]),
    status="implemented",
)
def remove_custom_property_live(name: str) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.remove_custom_property(doc, name)
        return envelope.build_success(result={"removed": name}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_modified_state_live",
    priority="P2",
    purpose="Return whether document has unsaved changes.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_modified_state_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        modified = ctx.uno_bridge.get_modified_state(doc)
        return envelope.build_success(result={"modified": modified}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="set_modified_state_live",
    priority="P3",
    purpose="Set/reset modified flag when justified by orchestration code.",
    parameters=schema({
        "modified": {"type": "boolean"},
        "document_id": {"type": "string"},
    }, required=["modified"]),
    status="implemented",
)
def set_modified_state_live(modified: bool, document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        ctx.uno_bridge.set_modified_state(doc, modified)
        return envelope.build_success(result={"modified": modified}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="refresh_document_live",
    priority="P1",
    purpose="Refresh fields/links/data supported by the document model.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def refresh_document_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        ctx.uno_bridge.refresh_document(doc)
        return envelope.build_success(result={"refreshed": True}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="reload_document_live",
    priority="P3",
    purpose="Reload from storage with explicit unsaved-change policy.",
    parameters=schema({
        "document_id": {"type": "string"},
        "discard_changes": {"type": "boolean", "default": False},
    }),
    status="implemented",
)
def reload_document_live(document_id: Optional[str] = None, discard_changes: bool = False) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        new_doc = ctx.uno_bridge.reload_document(doc, discard_changes=discard_changes)
        ctx.document_registry.replace_document(resolved_id, new_doc)
        info = ctx.uno_bridge.get_document_info(new_doc)
        return envelope.build_success(result=info, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


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
    status="implemented",
)
def print_document_live(printer: Optional[str] = None, page_range: Optional[str] = None,
                         copies: int = 1, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx)
        ctx.uno_bridge.print_document(doc, printer=printer, page_range=page_range, copies=copies, options=options)
        return envelope.build_success(result={"printed": True, "copies": copies}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start)


@register_tool(
    name="get_print_settings_live",
    priority="P2",
    purpose="Return current print settings.",
    parameters=schema({"document_id": {"type": "string"}}),
    status="implemented",
)
def get_print_settings_live(document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        result = ctx.uno_bridge.get_print_settings(doc)
        return envelope.build_success(result=result, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)


@register_tool(
    name="set_print_settings_live",
    priority="P2",
    purpose="Set document print options without printing.",
    parameters=schema({
        "settings": {"type": "object"},
        "document_id": {"type": "string"},
    }, required=["settings"]),
    status="implemented",
)
def set_print_settings_live(settings: Dict[str, Any], document_id: Optional[str] = None) -> Dict[str, Any]:
    start = envelope.start_timer()
    ctx = context.get_context()
    try:
        doc, resolved_id = _resolve_and_register(ctx, document_id)
        ctx.uno_bridge.set_print_settings(doc, settings)
        return envelope.build_success(result={"applied": list(settings.keys())}, document_id=resolved_id, elapsed_ms=envelope.elapsed_ms_since(start))
    except Exception as e:
        return _error_response(e, start, document_id=document_id)
