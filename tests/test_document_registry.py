#!/usr/bin/env python3
"""
Unit tests for tools.documents.DocumentRegistry.

DocumentRegistry only ever stores and returns whatever object it's given --
it never calls into UNO itself except through the uno_bridge it's handed
(get_active_document / get_document_info). So it's fully testable with a
fake in-memory "uno_bridge" and fake "document" objects; no live
LibreOffice, `uno`, or `unohelper` needed.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools.documents import DocumentNotFoundError, DocumentRegistry, NoActiveDocumentError  # noqa: E402


class FakeDocument:
    """Stand-in for a live UNO document component."""

    def __init__(self, title):
        self.title = title


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge -- only the two methods DocumentRegistry calls."""

    def __init__(self, active_document=None):
        self.active_document = active_document

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": "writer", "title": doc.title, "modified": False}


def test_register_then_resolve_returns_the_same_object():
    registry = DocumentRegistry(FakeUnoBridge())
    doc = FakeDocument("Untitled 1")
    document_id = registry.register_document(doc)
    assert isinstance(document_id, str) and document_id
    assert registry.resolve_document(document_id) is doc


def test_registering_the_same_object_twice_returns_the_same_id():
    registry = DocumentRegistry(FakeUnoBridge())
    doc = FakeDocument("Untitled 1")
    first_id = registry.register_document(doc)
    second_id = registry.register_document(doc)
    assert first_id == second_id
    assert len(registry.list_documents()) == 1


def test_resolve_with_no_document_id_returns_active_document():
    active_doc = FakeDocument("Active")
    registry = DocumentRegistry(FakeUnoBridge(active_document=active_doc))
    assert registry.resolve_document() is active_doc


def test_resolve_with_no_document_id_and_no_active_document_raises():
    registry = DocumentRegistry(FakeUnoBridge(active_document=None))
    try:
        registry.resolve_document()
        assert False, "expected NoActiveDocumentError"
    except NoActiveDocumentError:
        pass


def test_resolve_with_unknown_document_id_raises():
    registry = DocumentRegistry(FakeUnoBridge())
    try:
        registry.resolve_document("not-a-real-id")
        assert False, "expected DocumentNotFoundError"
    except DocumentNotFoundError:
        pass


def test_unregister_then_resolve_raises_not_found():
    registry = DocumentRegistry(FakeUnoBridge())
    doc = FakeDocument("Untitled 1")
    document_id = registry.register_document(doc)
    registry.unregister_document(document_id)
    try:
        registry.resolve_document(document_id)
        assert False, "expected DocumentNotFoundError after unregister"
    except DocumentNotFoundError:
        pass


def test_unregister_unknown_id_is_a_no_op():
    registry = DocumentRegistry(FakeUnoBridge())
    registry.unregister_document("never-registered")  # should not raise


def test_list_documents_reports_shape_from_uno_bridge():
    registry = DocumentRegistry(FakeUnoBridge())
    doc_a = registry.register_document(FakeDocument("A"))
    doc_b = registry.register_document(FakeDocument("B"))
    listed = {entry["document_id"]: entry for entry in registry.list_documents()}
    assert set(listed) == {doc_a, doc_b}
    assert listed[doc_a]["title"] == "A"
    assert listed[doc_a]["type"] == "writer"
    assert listed[doc_a]["modified"] is False


def test_list_documents_survives_a_document_that_raises_on_introspection():
    class ExplodingUnoBridge(FakeUnoBridge):
        def get_document_info(self, doc):
            raise RuntimeError("disposed UNO proxy")

    registry = DocumentRegistry(ExplodingUnoBridge())
    document_id = registry.register_document(FakeDocument("Doomed"))
    listed = registry.list_documents()
    assert len(listed) == 1
    assert listed[0]["document_id"] == document_id
    assert listed[0]["type"] is None


if __name__ == "__main__":
    tests = [
        test_register_then_resolve_returns_the_same_object,
        test_registering_the_same_object_twice_returns_the_same_id,
        test_resolve_with_no_document_id_returns_active_document,
        test_resolve_with_no_document_id_and_no_active_document_raises,
        test_resolve_with_unknown_document_id_raises,
        test_unregister_then_resolve_raises_not_found,
        test_unregister_unknown_id_is_a_no_op,
        test_list_documents_reports_shape_from_uno_bridge,
        test_list_documents_survives_a_document_that_raises_on_introspection,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} DocumentRegistry tests passed.")
