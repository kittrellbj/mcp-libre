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


def test_registering_distinct_but_equal_proxy_objects_dedups_by_equality_not_python_id():
    """Regression test: live-verified against a real LibreOffice instance
    that PyUNO mints a fresh Python-side proxy object (different id())
    each time the same remote document is fetched (e.g. two separate
    desktop.getCurrentComponent() calls) -- but the proxies compare equal
    via __eq__/__hash__. Registry dedup must key off the object itself
    (relying on __eq__/__hash__), not id(obj), or every fresh proxy for an
    already-registered document mints a spurious duplicate id."""

    class EqualByDocumentId:
        """Stands in for two distinct PyUNO proxy objects representing the
        same remote document: different Python identity, equal by value."""

        def __init__(self, underlying_id):
            self.underlying_id = underlying_id

        def __eq__(self, other):
            return isinstance(other, EqualByDocumentId) and other.underlying_id == self.underlying_id

        def __hash__(self):
            return hash(self.underlying_id)

    registry = DocumentRegistry(FakeUnoBridge())
    proxy_a = EqualByDocumentId("remote-doc-42")
    proxy_b = EqualByDocumentId("remote-doc-42")
    assert proxy_a is not proxy_b
    assert id(proxy_a) != id(proxy_b)

    first_id = registry.register_document(proxy_a)
    second_id = registry.register_document(proxy_b)
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


def test_list_documents_surfaces_the_introspection_error_instead_of_hiding_it():
    """Regression: list_documents() used to catch introspection failures with
    a bare `except Exception: info = {}`, so a genuinely dangling proxy and a
    real bug in get_document_info() (e.g. a typo'd property name that raises
    for every document) produced the identical all-None result -- a caller
    had no way to tell "nothing wrong, proxy is gone" from "something is
    broken". introspection_error must carry the real exception type/message."""
    class ExplodingUnoBridge(FakeUnoBridge):
        def get_document_info(self, doc):
            raise RuntimeError("disposed UNO proxy")

    registry = DocumentRegistry(ExplodingUnoBridge())
    registry.register_document(FakeDocument("Doomed"))
    listed = registry.list_documents()
    assert listed[0]["introspection_error"] == "RuntimeError: disposed UNO proxy"


def test_list_documents_introspection_error_is_none_on_the_success_path():
    registry = DocumentRegistry(FakeUnoBridge())
    registry.register_document(FakeDocument("Fine"))
    listed = registry.list_documents()
    assert listed[0]["introspection_error"] is None


def test_replace_document_keeps_the_same_id_pointing_at_a_new_object():
    """Used by reload_document_live: the reloaded UNO component has a new
    object identity, but callers should keep using the same document_id."""
    registry = DocumentRegistry(FakeUnoBridge())
    old_doc = FakeDocument("Before Reload")
    document_id = registry.register_document(old_doc)

    new_doc = FakeDocument("After Reload")
    registry.replace_document(document_id, new_doc)

    assert registry.resolve_document(document_id) is new_doc
    # The old object's identity is no longer reserved -- re-registering it
    # (e.g. if some other code still held a reference) mints a fresh id
    # rather than resurrecting the one that now belongs to new_doc.
    assert registry.register_document(old_doc) != document_id


def test_replace_document_unknown_id_raises():
    registry = DocumentRegistry(FakeUnoBridge())
    try:
        registry.replace_document("never-registered", FakeDocument("New"))
        assert False, "expected DocumentNotFoundError"
    except DocumentNotFoundError:
        pass


def test_get_object_registry_creates_one_lazily_per_document_id():
    registry = DocumentRegistry(FakeUnoBridge())
    document_id = registry.register_document(FakeDocument("Doc"))
    object_registry = registry.get_object_registry(document_id)
    assert object_registry is not None
    assert len(object_registry) == 0


def test_get_object_registry_returns_the_same_instance_for_the_same_document_id():
    registry = DocumentRegistry(FakeUnoBridge())
    document_id = registry.register_document(FakeDocument("Doc"))
    first = registry.get_object_registry(document_id)
    second = registry.get_object_registry(document_id)
    assert first is second


def test_get_object_registry_gives_different_documents_independent_registries():
    registry = DocumentRegistry(FakeUnoBridge())
    doc_a = registry.register_document(FakeDocument("A"))
    doc_b = registry.register_document(FakeDocument("B"))
    registry_a = registry.get_object_registry(doc_a)
    registry_b = registry.get_object_registry(doc_b)
    assert registry_a is not registry_b

    class FakeShape:
        pass

    handle = registry_a.register_object(FakeShape())
    assert len(registry_a) == 1
    assert len(registry_b) == 0
    try:
        registry_b.resolve_object(handle)
        assert False, "a shape handle from doc A must not resolve against doc B's registry"
    except Exception:
        pass


def test_unregister_document_drops_its_object_registry():
    """A handle minted for a document must not survive that document
    closing -- outliving its document is never meaningful (see
    get_object_registry()'s docstring)."""
    registry = DocumentRegistry(FakeUnoBridge())
    document_id = registry.register_document(FakeDocument("Doc"))
    object_registry = registry.get_object_registry(document_id)

    class FakeShape:
        pass

    handle = object_registry.register_object(FakeShape())
    assert object_registry.resolve_object(handle) is not None

    registry.unregister_document(document_id)

    # A fresh get_object_registry() call for the same (now-unregistered)
    # id must not resurrect the old registry's contents -- it's a new,
    # empty instance, proving the old one was actually dropped rather
    # than merely orphaned-but-still-referenced.
    fresh_object_registry = registry.get_object_registry(document_id)
    assert fresh_object_registry is not object_registry
    assert len(fresh_object_registry) == 0


if __name__ == "__main__":
    tests = [
        test_register_then_resolve_returns_the_same_object,
        test_registering_the_same_object_twice_returns_the_same_id,
        test_registering_distinct_but_equal_proxy_objects_dedups_by_equality_not_python_id,
        test_resolve_with_no_document_id_returns_active_document,
        test_resolve_with_no_document_id_and_no_active_document_raises,
        test_resolve_with_unknown_document_id_raises,
        test_unregister_then_resolve_raises_not_found,
        test_unregister_unknown_id_is_a_no_op,
        test_list_documents_reports_shape_from_uno_bridge,
        test_list_documents_survives_a_document_that_raises_on_introspection,
        test_list_documents_surfaces_the_introspection_error_instead_of_hiding_it,
        test_list_documents_introspection_error_is_none_on_the_success_path,
        test_replace_document_keeps_the_same_id_pointing_at_a_new_object,
        test_replace_document_unknown_id_raises,
        test_get_object_registry_creates_one_lazily_per_document_id,
        test_get_object_registry_returns_the_same_instance_for_the_same_document_id,
        test_get_object_registry_gives_different_documents_independent_registries,
        test_unregister_document_drops_its_object_registry,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} DocumentRegistry tests passed.")
