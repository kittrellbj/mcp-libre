#!/usr/bin/env python3
"""
Contract tests for the Phase A tooling scaffold (plugin/pythonpath/tools/).

These deliberately do NOT require a running LibreOffice instance or the
`uno`/`unohelper` modules -- unlike plugin/test_plugin.py (needs a live
extension) or tests/test_client.py (needs `soffice` on PATH), this suite
only checks the scaffold's own contract:

  * every Phase A tool from the design spec is registered exactly once,
    with the right priority, and none collide with the original 32
    compatibility tool names;
  * every stub handler returns the spec's error envelope shape with code
    NOT_IMPLEMENTED, regardless of the arguments passed in;
  * merge_into() never overwrites a pre-existing tool entry unless told to.

Once a senior engineer replaces a stub body with a real implementation,
that tool's "returns NOT_IMPLEMENTED" assertion in test_stub_shape_contract
should be replaced with a real behavioral test per spec section 9
(schema validation, positive/negative cases, undo/redo, persistence, etc.)
-- this file is not meant to grow real coverage in place.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import get_registry  # noqa: E402
from tools.envelope import ERROR_CODES  # noqa: E402
from tools.registry import merge_into, schema  # noqa: E402

# The 5 spec tools explicitly marked "(existing)" in the Phase A sections
# (core runtime has none; document/session lifecycle has 5). These already
# live in plugin/pythonpath/mcp_server.py and must never be shadowed here.
EXISTING_COMPAT_TOOLS = {
    "list_open_documents",
    "create_document_live",
    "get_document_info_live",
    "save_document_live",
    "export_document_live",
}

EXPECTED_TOOL_COUNT = 60  # 12 core runtime + 22 new lifecycle + 14 undo/view/selection + 12 styles


def _placeholder_for(prop_schema):
    """Return a type-appropriate throwaway value for a required JSON Schema property."""
    prop_type = prop_schema.get("type") if isinstance(prop_schema, dict) else None
    return {
        "string": "test",
        "integer": 1,
        "number": 1.0,
        "boolean": True,
        "array": [],
        "object": {},
    }.get(prop_type, "test")


def _call_with_placeholders(handler, parameters):
    """Call a stub handler with placeholder values for its required parameters."""
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])
    kwargs = {name: _placeholder_for(properties.get(name, {})) for name in required}
    return handler(**kwargs)


def test_registry_has_no_duplicate_or_compat_collisions():
    registry = get_registry()
    assert len(registry) == EXPECTED_TOOL_COUNT, (
        f"expected {EXPECTED_TOOL_COUNT} Phase A stub tools, found {len(registry)}: "
        f"{sorted(registry.keys())}"
    )
    collisions = set(registry.keys()) & EXISTING_COMPAT_TOOLS
    assert not collisions, f"Phase A stubs must not redefine existing compatibility tools: {collisions}"


def test_every_tool_has_a_valid_priority():
    valid_priorities = {"P0", "P1", "P2", "P3"}
    for name, metadata in get_registry().items():
        assert metadata["priority"] in valid_priorities, f"{name} has invalid priority {metadata['priority']!r}"


def test_stub_shape_contract():
    """Every stub, called with placeholder args, returns the spec's NOT_IMPLEMENTED error envelope."""
    for name, metadata in get_registry().items():
        result = _call_with_placeholders(metadata["handler"], metadata["parameters"])
        assert result["success"] is False, f"{name} stub should not report success"
        assert result["error"]["code"] == "NOT_IMPLEMENTED", f"{name} stub returned unexpected error code"
        assert "document_id" in result, f"{name} response is missing document_id"
        assert "elapsed_ms" in result and isinstance(result["elapsed_ms"], int), f"{name} response is missing elapsed_ms"


def test_merge_into_does_not_overwrite_existing_tools_by_default():
    sentinel = object()
    existing_tools = {"ping_live": {"description": "original", "parameters": schema(), "handler": sentinel}}
    added = merge_into(existing_tools)
    assert "ping_live" not in added
    assert existing_tools["ping_live"]["handler"] is sentinel

    # overwrite=True should replace it
    added = merge_into(existing_tools, overwrite=True)
    assert "ping_live" in added
    assert existing_tools["ping_live"]["handler"] is not sentinel


def test_error_envelope_rejects_unknown_codes():
    from tools import envelope

    try:
        envelope.build_error("NOT_A_REAL_CODE", "boom")
        assert False, "expected ValueError for an unknown error code"
    except ValueError:
        pass


def test_error_codes_match_spec_list():
    spec_codes = {
        "NO_ACTIVE_DOCUMENT", "WRONG_DOCUMENT_TYPE", "OBJECT_NOT_FOUND", "AMBIGUOUS_SELECTOR",
        "UNSUPPORTED_CAPABILITY", "INVALID_RANGE", "INVALID_PARAMETER", "FILE_EXISTS",
        "PERMISSION_DENIED", "UNO_EXCEPTION", "DATABASE_ERROR", "TIMEOUT", "SECURITY_POLICY_DENIED",
    }
    # NOT_IMPLEMENTED is a scaffold-only addition, not part of the spec's own list.
    assert spec_codes <= ERROR_CODES
    assert ERROR_CODES - spec_codes == {"NOT_IMPLEMENTED"}


if __name__ == "__main__":
    tests = [
        test_registry_has_no_duplicate_or_compat_collisions,
        test_every_tool_has_a_valid_priority,
        test_stub_shape_contract,
        test_merge_into_does_not_overwrite_existing_tools_by_default,
        test_error_envelope_rejects_unknown_codes,
        test_error_codes_match_spec_list,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} Phase A scaffold contract tests passed.")
