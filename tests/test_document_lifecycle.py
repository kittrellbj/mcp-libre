#!/usr/bin/env python3
"""
Unit tests for the 22 real (status="implemented") document_lifecycle.py tools.

Uses a FakeUnoBridge that fakes every new UNOBridge document-lifecycle
method (open/close/save-as/properties/etc.) but the REAL DocumentRegistry,
RuntimeState, and tools.context -- exercising the actual integration path,
including auto-registration of "the active document" into DocumentRegistry
the first time any of these tools touches it.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools import document_lifecycle  # noqa: E402
from tools import documents  # noqa: E402
from tools import object_registry  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type, title="Untitled", url=""):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False
        self.closed = False
        self.activated = False
        self.custom_properties = {}
        self.standard_properties = {"title": title, "subject": None, "author": None, "description": None, "modified_by": None, "keywords": []}
        self.print_settings = {}


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge -- only what document_lifecycle.py calls."""

    def __init__(self, active_document=None, existing_files=None):
        self.ctx = object()
        self.active_document = active_document
        self.existing_files = existing_files or set()
        self.saved_paths = []
        self.converted = []
        self.printed = []
        self.extracted_text = {}
        self.extraction_truncated = False

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    # -- lifecycle --

    def open_document(self, file_path, read_only=False, hidden=False, password=None, filter_name=None):
        if file_path not in self.existing_files:
            raise FileNotFoundError(f"No such file: {file_path}")
        return FakeDocument("writer", title=os.path.basename(file_path), url=file_path)

    def open_from_template(self, template_path, as_template=True):
        if template_path not in self.existing_files:
            raise FileNotFoundError(f"No such template: {template_path}")
        return FakeDocument("writer", title="From Template")

    def close_document(self, doc, save=False):
        if save == "prompt":
            raise ValueError("save='prompt' is not supported by a headless extension; pass true or false explicitly.")
        if save is True:
            if not doc.url:
                raise ValueError("Document has no location to save to; use save_as_document_live first.")
        doc.closed = True

    def activate_document(self, doc):
        doc.activated = True

    def get_document_statistics(self, doc):
        return {"type": doc.doc_type, "word_count": 42, "character_count": 250}

    def get_document_snapshot(self, doc):
        snapshot = {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}
        if doc.doc_type == "writer":
            snapshot["paragraph_count"] = 12
            snapshot["page_count"] = 3
        elif doc.doc_type == "calc":
            snapshot["sheet_count"] = 2
            snapshot["active_sheet"] = {"index": 0, "name": "Sheet1"}
        elif doc.doc_type == "impress":
            snapshot["slide_count"] = 5
            snapshot["active_slide"] = {"index": 0, "name": "Slide 1"}
        elif doc.doc_type == "draw":
            snapshot["page_count"] = 2
            snapshot["active_page"] = {"index": 0, "name": "Page1"}
        else:
            snapshot["warning"] = f"No snapshot detail available for document type '{doc.doc_type}'"
        return snapshot

    def extract_document_text(self, doc):
        text = self.extracted_text.get(doc.doc_type, "")
        result = {"type": doc.doc_type, "text": text, "character_count": len(text)}
        if doc.doc_type == "calc":
            result["truncated"] = self.extraction_truncated
        return result

    def get_document_properties(self, doc):
        return dict(doc.standard_properties)

    def set_document_properties(self, doc, properties):
        settable = {"title", "subject", "author", "description", "keywords"}
        applied = []
        for key, value in properties.items():
            if key in settable:
                doc.standard_properties[key] = value
                applied.append(key)
        return applied

    def get_custom_properties(self, doc):
        return dict(doc.custom_properties)

    def set_custom_property(self, doc, name, value, property_type=None):
        doc.custom_properties[name] = value

    def remove_custom_property(self, doc, name):
        if name not in doc.custom_properties:
            raise KeyError(f"No custom property named '{name}'")
        del doc.custom_properties[name]

    def get_modified_state(self, doc):
        return doc.modified

    def set_modified_state(self, doc, modified):
        doc.modified = modified

    def refresh_document(self, doc):
        if doc.doc_type == "draw":
            raise NotImplementedError("This document does not support XRefreshable.refresh().")
        doc.refreshed = True

    def reload_document(self, doc, discard_changes=False):
        if not doc.url:
            raise ValueError("Document has no stored location to reload from.")
        if doc.modified and not discard_changes:
            raise ValueError("Document has unsaved changes; pass discard_changes=true to reload anyway.")
        return FakeDocument(doc.doc_type, title=doc.title, url=doc.url)

    def save_as_document(self, doc, file_path, filter_name=None, filter_options=None, overwrite=False):
        if not overwrite and file_path in self.existing_files:
            raise FileExistsError(f"{file_path} already exists; pass overwrite=true to replace it.")
        doc.url = file_path
        self.saved_paths.append(file_path)

    def save_copy_document(self, doc, file_path, filter_name=None, overwrite=False):
        if not overwrite and file_path in self.existing_files:
            raise FileExistsError(f"{file_path} already exists; pass overwrite=true to replace it.")
        self.saved_paths.append(file_path)

    def convert_document_file(self, input_path, output_path, output_format=None, options=None):
        if input_path not in self.existing_files:
            raise FileNotFoundError(f"No such file: {input_path}")
        self.converted.append((input_path, output_path))

    def list_export_filters(self, doc):
        return {"document_type": doc.doc_type, "filters": ["writer8", "writer_pdf_Export"]}

    def get_print_settings(self, doc):
        return dict(doc.print_settings)

    def set_print_settings(self, doc, settings):
        doc.print_settings.update(settings)

    def print_document(self, doc, printer=None, page_range=None, copies=1, options=None):
        self.printed.append({"printer": printer, "page_range": page_range, "copies": copies})


def _install(active_document=None, existing_files=None):
    uno_bridge = FakeUnoBridge(active_document=active_document, existing_files=existing_files)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


def test_get_active_document_live_auto_registers():
    context.reset()
    doc = FakeDocument("writer", title="Doc A")
    _, document_registry, _ = _install(active_document=doc)
    result = _handler("get_active_document_live")()
    assert result["success"] is True
    assert result["document_id"] is not None
    assert document_registry.resolve_document(result["document_id"]) is doc


def test_get_active_document_live_no_active_document():
    context.reset()
    _install()
    result = _handler("get_active_document_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_ACTIVE_DOCUMENT"


def test_activate_document_live_success_and_unknown_id():
    context.reset()
    _, document_registry, _ = _install()
    doc = FakeDocument("writer")
    doc_id = document_registry.register_document(doc)

    ok = _handler("activate_document_live")(document_id=doc_id)
    assert ok["success"] is True
    assert doc.activated is True

    missing = _handler("activate_document_live")(document_id="not-a-real-id")
    assert missing["success"] is False
    assert missing["error"]["code"] == "OBJECT_NOT_FOUND"


def test_open_document_live_registers_and_reports_not_found():
    context.reset()
    _, document_registry, _ = _install(existing_files={"/docs/report.odt"})
    ok = _handler("open_document_live")(file_path="/docs/report.odt")
    assert ok["success"] is True
    assert ok["document_id"] is not None
    assert document_registry.resolve_document(ok["document_id"]) is not None

    missing = _handler("open_document_live")(file_path="/docs/missing.odt")
    assert missing["success"] is False
    assert missing["error"]["code"] == "OBJECT_NOT_FOUND"


def test_open_from_template_live():
    context.reset()
    _install(existing_files={"/templates/novel.ott"})
    result = _handler("open_from_template_live")(template_path="/templates/novel.ott")
    assert result["success"] is True
    assert result["document_id"] is not None


def test_close_document_live_unregisters_and_maps_prompt_error():
    context.reset()
    uno_bridge, document_registry, _ = _install()
    doc = FakeDocument("writer")
    doc_id = document_registry.register_document(doc)

    result = _handler("close_document_live")(document_id=doc_id, save=False)
    assert result["success"] is True
    assert doc.closed is True
    try:
        document_registry.resolve_document(doc_id)
        assert False, "expected DocumentNotFoundError after close"
    except Exception:
        pass

    doc2 = FakeDocument("writer")
    doc2_id = document_registry.register_document(doc2)
    prompt_result = _handler("close_document_live")(document_id=doc2_id, save="prompt")
    assert prompt_result["success"] is False
    assert prompt_result["error"]["code"] == "INVALID_PARAMETER"


def test_get_document_statistics_live():
    context.reset()
    _install(active_document=FakeDocument("writer"))
    result = _handler("get_document_statistics_live")()
    assert result["success"] is True
    assert result["result"]["word_count"] == 42


def test_get_document_snapshot_live_writer():
    # New tool, 2026-08-22 (Brian's new-tools assignment, priority #14) --
    # cross-doc-type "what's open right now" snapshot.
    context.reset()
    _install(active_document=FakeDocument("writer", title="Report.odt"))
    result = _handler("get_document_snapshot_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["type"] == "writer" and r["title"] == "Report.odt"
    assert r["paragraph_count"] == 12 and r["page_count"] == 3
    assert "sheet_count" not in r and "slide_count" not in r


def test_get_document_snapshot_live_calc():
    context.reset()
    _install(active_document=FakeDocument("calc"))
    result = _handler("get_document_snapshot_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["type"] == "calc"
    assert r["sheet_count"] == 2
    assert r["active_sheet"] == {"index": 0, "name": "Sheet1"}


def test_get_document_snapshot_live_impress():
    context.reset()
    _install(active_document=FakeDocument("impress"))
    result = _handler("get_document_snapshot_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["type"] == "impress"
    assert r["slide_count"] == 5
    assert r["active_slide"] == {"index": 0, "name": "Slide 1"}


def test_get_document_snapshot_live_draw():
    context.reset()
    _install(active_document=FakeDocument("draw"))
    result = _handler("get_document_snapshot_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["type"] == "draw"
    assert r["page_count"] == 2
    assert r["active_page"] == {"index": 0, "name": "Page1"}


def test_get_document_snapshot_live_no_active_document():
    context.reset()
    _install()
    result = _handler("get_document_snapshot_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_ACTIVE_DOCUMENT"


def test_extract_document_text_live_reports_real_text_and_count():
    # New tool, 2026-08-22 (Brian's new-tools assignment, priority #15,
    # the last item in the Phase 6 new-tools list) -- flat plain-text
    # extraction across all doc types.
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument("writer"))
    uno_bridge.extracted_text["writer"] = "First paragraph\nSecond paragraph"
    result = _handler("extract_document_text_live")()
    assert result["success"] is True
    assert result["result"]["text"] == "First paragraph\nSecond paragraph"
    assert result["result"]["character_count"] == len("First paragraph\nSecond paragraph")
    assert result["warnings"] == []


def test_extract_document_text_live_warns_when_calc_extraction_truncated():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument("calc"))
    uno_bridge.extracted_text["calc"] = "Revenue"
    uno_bridge.extraction_truncated = True
    result = _handler("extract_document_text_live")()
    assert result["success"] is True
    assert result["result"]["truncated"] is True
    assert "backstop" in result["warnings"][0]


def test_extract_document_text_live_no_active_document():
    context.reset()
    _install()
    result = _handler("extract_document_text_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_ACTIVE_DOCUMENT"


def test_save_as_document_live_success_and_file_exists():
    context.reset()
    _install(active_document=FakeDocument("writer"), existing_files={"/out/existing.odt"})
    ok = _handler("save_as_document_live")(file_path="/out/new.odt")
    assert ok["success"] is True

    clash = _handler("save_as_document_live")(file_path="/out/existing.odt")
    assert clash["success"] is False
    assert clash["error"]["code"] == "FILE_EXISTS"

    overwritten = _handler("save_as_document_live")(file_path="/out/existing.odt", overwrite=True)
    assert overwritten["success"] is True


def test_save_copy_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument("writer"))
    result = _handler("save_copy_live")(file_path="/out/copy.odt")
    assert result["success"] is True
    assert "/out/copy.odt" in uno_bridge.saved_paths


def test_convert_document_live_success_and_missing_input():
    context.reset()
    uno_bridge, _, _ = _install(existing_files={"/in/source.odt"})
    ok = _handler("convert_document_live")(input_path="/in/source.odt", output_path="/out/target.pdf")
    assert ok["success"] is True
    assert ("/in/source.odt", "/out/target.pdf") in uno_bridge.converted

    missing = _handler("convert_document_live")(input_path="/in/missing.odt", output_path="/out/target.pdf")
    assert missing["success"] is False
    assert missing["error"]["code"] == "OBJECT_NOT_FOUND"


def test_list_export_filters_live():
    context.reset()
    _install(active_document=FakeDocument("writer"))
    result = _handler("list_export_filters_live")()
    assert result["success"] is True
    assert "writer8" in result["result"]["filters"]


def test_get_and_set_document_properties_live():
    context.reset()
    doc = FakeDocument("writer")
    _install(active_document=doc)

    get_result = _handler("get_document_properties_live")()
    assert get_result["success"] is True

    set_result = _handler("set_document_properties_live")(properties={"title": "New Title", "bogus_field": "x"})
    assert set_result["success"] is True
    assert set_result["result"]["applied"] == ["title"]
    assert any("bogus_field" in w for w in set_result["warnings"])
    assert doc.standard_properties["title"] == "New Title"


def test_custom_properties_full_cycle():
    context.reset()
    _install(active_document=FakeDocument("writer"))

    empty = _handler("get_custom_properties_live")()
    assert empty["result"] == {}

    set_result = _handler("set_custom_property_live")(name="project_code", value="ABC-123")
    assert set_result["success"] is True

    listed = _handler("get_custom_properties_live")()
    assert listed["result"]["project_code"] == "ABC-123"

    removed = _handler("remove_custom_property_live")(name="project_code")
    assert removed["success"] is True

    missing = _handler("remove_custom_property_live")(name="project_code")
    assert missing["success"] is False
    assert missing["error"]["code"] == "OBJECT_NOT_FOUND"


def test_get_and_set_modified_state_live():
    context.reset()
    doc = FakeDocument("writer")
    _install(active_document=doc)

    initial = _handler("get_modified_state_live")()
    assert initial["result"]["modified"] is False

    _handler("set_modified_state_live")(modified=True)
    assert doc.modified is True
    updated = _handler("get_modified_state_live")()
    assert updated["result"]["modified"] is True


def test_refresh_document_live_success_and_unsupported():
    context.reset()
    _install(active_document=FakeDocument("writer"))
    ok = _handler("refresh_document_live")()
    assert ok["success"] is True

    context.reset()
    _install(active_document=FakeDocument("draw"))
    unsupported = _handler("refresh_document_live")()
    assert unsupported["success"] is False
    assert unsupported["error"]["code"] == "UNSUPPORTED_CAPABILITY"


def test_reload_document_live_replaces_registry_entry():
    context.reset()
    _, document_registry, _ = _install()
    doc = FakeDocument("writer", url="/docs/report.odt")
    doc_id = document_registry.register_document(doc)

    result = _handler("reload_document_live")(document_id=doc_id)
    assert result["success"] is True
    assert result["document_id"] == doc_id
    reloaded = document_registry.resolve_document(doc_id)
    assert reloaded is not doc  # a new component, per uno_bridge.reload_document's contract
    assert reloaded.url == "/docs/report.odt"


def test_reload_document_live_refuses_unsaved_changes_without_discard():
    context.reset()
    _, document_registry, _ = _install()
    doc = FakeDocument("writer", url="/docs/report.odt")
    doc.modified = True
    doc_id = document_registry.register_document(doc)

    refused = _handler("reload_document_live")(document_id=doc_id)
    assert refused["success"] is False
    assert refused["error"]["code"] == "INVALID_PARAMETER"

    forced = _handler("reload_document_live")(document_id=doc_id, discard_changes=True)
    assert forced["success"] is True


def test_print_document_live():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument("writer"))
    result = _handler("print_document_live")(printer="Office Printer", copies=2)
    assert result["success"] is True
    assert uno_bridge.printed[-1] == {"printer": "Office Printer", "page_range": None, "copies": 2}


def test_get_and_set_print_settings_live():
    context.reset()
    _install(active_document=FakeDocument("writer"))
    _handler("set_print_settings_live")(settings={"CopyCount": 3})
    result = _handler("get_print_settings_live")()
    assert result["result"]["CopyCount"] == 3


def test_map_exception_to_code_covers_every_branch():
    """Direct unit test of _map_exception_to_code(), the single function
    every real tool in the catalog (~90 tools across 14 modules) routes
    its error responses through via _error_response(). Hardening-pass
    regression guard (#31 error-code audit): WrongDocumentTypeError used
    to be missing entirely -- _require_writer()/_require_calc()/
    _require_draw()/_require_impress() (and apply_style/get_direct_
    formatting/clear_direct_formatting/copy_formatting/_require_chart_
    capable) all raised plain NotImplementedError instead, which
    collapsed onto UNSUPPORTED_CAPABILITY and left the spec's own
    WRONG_DOCUMENT_TYPE code dead -- never reachable from any real tool
    despite being the single most common error path in the whole
    catalog. Covers every isinstance() branch so drift (a new exception
    type added without a matching branch, or a branch reordered behind a
    broader one) fails loudly here instead of surfacing as a wrong error
    code live."""
    assert document_lifecycle._map_exception_to_code(documents.NoActiveDocumentError()) == "NO_ACTIVE_DOCUMENT"
    assert document_lifecycle._map_exception_to_code(documents.DocumentNotFoundError("id")) == "OBJECT_NOT_FOUND"
    assert document_lifecycle._map_exception_to_code(documents.WrongDocumentTypeError("msg")) == "WRONG_DOCUMENT_TYPE"
    assert document_lifecycle._map_exception_to_code(object_registry.ObjectNotFoundError("id")) == "OBJECT_NOT_FOUND"
    assert document_lifecycle._map_exception_to_code(FileNotFoundError()) == "OBJECT_NOT_FOUND"
    assert document_lifecycle._map_exception_to_code(FileExistsError()) == "FILE_EXISTS"
    assert document_lifecycle._map_exception_to_code(PermissionError()) == "PERMISSION_DENIED"
    assert document_lifecycle._map_exception_to_code(KeyError("k")) == "OBJECT_NOT_FOUND"
    assert document_lifecycle._map_exception_to_code(IndexError()) == "INVALID_RANGE"
    assert document_lifecycle._map_exception_to_code(NotImplementedError()) == "UNSUPPORTED_CAPABILITY"
    assert document_lifecycle._map_exception_to_code(ValueError()) == "INVALID_PARAMETER"
    assert document_lifecycle._map_exception_to_code(TypeError()) == "INVALID_PARAMETER"
    assert document_lifecycle._map_exception_to_code(RuntimeError()) == "UNO_EXCEPTION"


if __name__ == "__main__":
    tests = [
        test_get_active_document_live_auto_registers,
        test_get_active_document_live_no_active_document,
        test_activate_document_live_success_and_unknown_id,
        test_open_document_live_registers_and_reports_not_found,
        test_open_from_template_live,
        test_close_document_live_unregisters_and_maps_prompt_error,
        test_get_document_statistics_live,
        test_get_document_snapshot_live_writer,
        test_get_document_snapshot_live_calc,
        test_get_document_snapshot_live_impress,
        test_get_document_snapshot_live_draw,
        test_get_document_snapshot_live_no_active_document,
        test_extract_document_text_live_reports_real_text_and_count,
        test_extract_document_text_live_warns_when_calc_extraction_truncated,
        test_extract_document_text_live_no_active_document,
        test_save_as_document_live_success_and_file_exists,
        test_save_copy_live,
        test_convert_document_live_success_and_missing_input,
        test_list_export_filters_live,
        test_get_and_set_document_properties_live,
        test_custom_properties_full_cycle,
        test_get_and_set_modified_state_live,
        test_refresh_document_live_success_and_unsupported,
        test_reload_document_live_replaces_registry_entry,
        test_reload_document_live_refuses_unsaved_changes_without_discard,
        test_print_document_live,
        test_get_and_set_print_settings_live,
        test_map_exception_to_code_covers_every_branch,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    context.reset()
    print(f"\nAll {len(tests)} document_lifecycle tests passed.")
