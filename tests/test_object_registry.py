#!/usr/bin/env python3
"""
Unit tests for tools.object_registry.ObjectRegistry.

Same shape as test_document_registry.py: ObjectRegistry only ever stores
and returns whatever object it's given, so it's fully testable with plain
fake objects; no live LibreOffice, `uno`, or `unohelper` needed.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools.object_registry import ObjectNotFoundError, ObjectRegistry  # noqa: E402


class FakeShape:
    """Stand-in for a live UNO shape/chart/table component."""

    def __init__(self, label):
        self.label = label


def test_register_then_resolve_returns_the_same_object():
    registry = ObjectRegistry()
    shape = FakeShape("Shape 1")
    object_id = registry.register_object(shape)
    assert isinstance(object_id, str) and object_id
    assert registry.resolve_object(object_id) is shape


def test_registering_the_same_object_twice_returns_the_same_id():
    registry = ObjectRegistry()
    shape = FakeShape("Shape 1")
    first_id = registry.register_object(shape)
    second_id = registry.register_object(shape)
    assert first_id == second_id
    assert len(registry) == 1


def test_registering_distinct_but_equal_proxy_objects_dedups_by_equality_not_python_id():
    """Same regression this project's DocumentRegistry already guards
    against: PyUNO mints a fresh Python-side proxy object (different
    id()) each time the same remote object is re-enumerated (e.g. a
    later list_shapes_live call re-walking a draw page), but the proxies
    compare equal via __eq__/__hash__. Dedup must key off the object
    itself, not id(obj), or every fresh proxy for an already-registered
    shape mints a spurious duplicate handle."""

    class EqualByUnderlyingId:
        def __init__(self, underlying_id):
            self.underlying_id = underlying_id

        def __eq__(self, other):
            return isinstance(other, EqualByUnderlyingId) and other.underlying_id == self.underlying_id

        def __hash__(self):
            return hash(self.underlying_id)

    registry = ObjectRegistry()
    proxy_a = EqualByUnderlyingId("remote-shape-7")
    proxy_b = EqualByUnderlyingId("remote-shape-7")
    assert proxy_a is not proxy_b
    assert id(proxy_a) != id(proxy_b)

    first_id = registry.register_object(proxy_a)
    second_id = registry.register_object(proxy_b)
    assert first_id == second_id
    assert len(registry) == 1


def test_resolve_with_unknown_object_id_raises():
    registry = ObjectRegistry()
    try:
        registry.resolve_object("not-a-real-id")
        assert False, "expected ObjectNotFoundError"
    except ObjectNotFoundError:
        pass


def test_unregister_then_resolve_raises_not_found():
    registry = ObjectRegistry()
    shape = FakeShape("Shape 1")
    object_id = registry.register_object(shape)
    registry.unregister_object(object_id)
    try:
        registry.resolve_object(object_id)
        assert False, "expected ObjectNotFoundError after unregister"
    except ObjectNotFoundError:
        pass


def test_unregister_unknown_id_is_a_no_op():
    registry = ObjectRegistry()
    registry.unregister_object("never-registered")  # should not raise


def test_list_object_ids_reflects_current_registrations():
    registry = ObjectRegistry()
    id_a = registry.register_object(FakeShape("A"))
    id_b = registry.register_object(FakeShape("B"))
    assert set(registry.list_object_ids()) == {id_a, id_b}
    registry.unregister_object(id_a)
    assert set(registry.list_object_ids()) == {id_b}


def test_two_distinct_objects_never_collide_even_with_identical_labels():
    """Two different live shapes that happen to share the same
    UNO-visible Name (e.g. both anonymously "Shape 1" in two different
    documents) must still get two distinct handles -- registration keys
    off the object itself, never off any property of it."""
    registry = ObjectRegistry()
    shape_a = FakeShape("Shape 1")
    shape_b = FakeShape("Shape 1")
    id_a = registry.register_object(shape_a)
    id_b = registry.register_object(shape_b)
    assert id_a != id_b
    assert len(registry) == 2


if __name__ == "__main__":
    tests = [
        test_register_then_resolve_returns_the_same_object,
        test_registering_the_same_object_twice_returns_the_same_id,
        test_registering_distinct_but_equal_proxy_objects_dedups_by_equality_not_python_id,
        test_resolve_with_unknown_object_id_raises,
        test_unregister_then_resolve_raises_not_found,
        test_unregister_unknown_id_is_a_no_op,
        test_list_object_ids_reflects_current_registrations,
        test_two_distinct_objects_never_collide_even_with_identical_labels,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} ObjectRegistry tests passed.")
