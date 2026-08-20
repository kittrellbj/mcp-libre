#!/usr/bin/env python3
"""
Unit tests for the 12 real (status="implemented") core_runtime.py tools.

Uses fakes for UNOBridge (no live LibreOffice needed) but the REAL
DocumentRegistry and RuntimeState classes, wired together through the
REAL tools.context module -- exercising the same integration path
mcp_server.py uses in production, just with a fake at the UNO boundary.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry, merge_into  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type, title="Untitled"):
        self.doc_type = doc_type
        self.title = title


class FakeController:
    def __init__(self, doc):
        self._doc = doc

    def getModel(self):
        return self._doc


class FakeFrame:
    def __init__(self, doc):
        self._doc = doc

    def getController(self):
        return FakeController(self._doc)


class FakeFrames:
    def __init__(self, docs):
        self._docs = docs

    def getCount(self):
        return len(self._docs)

    def getByIndex(self, i):
        return FakeFrame(self._docs[i])


class FakeDesktop:
    def __init__(self, docs):
        self._docs = docs

    def getFrames(self):
        return FakeFrames(self._docs)


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge -- only what core_runtime.py calls."""

    def __init__(self, active_document=None, open_documents=None, version_success=True):
        self.ctx = object()  # sentinel: "a UNO context is available"
        self.active_document = active_document
        self.open_documents = open_documents if open_documents is not None else (
            [active_document] if active_document else []
        )
        self.desktop = FakeDesktop(self.open_documents)
        self._version_success = version_success
        self._undo_stack = []
        self._context_open = False
        self._context_title = None
        self._context_has_action = False

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "modified": False}

    def get_application_version(self):
        if self._version_success:
            return {"success": True, "name": "LibreOffice", "version": "24.2.0.3", "version_about_box": "24.2.0.3 (X86_64)"}
        return {"success": False, "error": "configuration query failed"}

    def get_capabilities(self):
        return {
            "supported_document_types": ["writer", "calc", "impress", "draw"],
            "optional_uno_interfaces": {
                "XTextDocument": True, "XSpreadsheetDocument": True,
                "XPresentationDocument": True, "XDocumentEventListener": True, "XActionListener": True,
            },
        }

    # -- undo manager (only what batch_execute_live's undo_label wiring
    # needs to exercise -- see tests/test_undo_view_selection.py for the
    # fuller fake/tests of the 6 undo tools themselves) --

    def simulate_edit(self):
        """Test helper: mimic a UNO edit landing right now. If a context is
        open, it's flagged as having recorded something (real UNO
        coalesces everything recorded inside a context into one action on
        leaveUndoContext, regardless of how many); otherwise it lands on
        the stack immediately, same as an edit outside any context."""
        if self._context_open:
            self._context_has_action = True
        else:
            self._undo_stack.append("Simulated Edit")

    def begin_undo_context(self, doc, title):
        baseline_count = len(self._undo_stack)
        self._context_open = True
        self._context_title = title
        self._context_has_action = False
        return {"baseline_count": baseline_count}

    def end_undo_context(self, doc):
        if self._context_has_action:
            self._undo_stack.append(self._context_title)
        self._context_open = False
        self._context_has_action = False
        return {"resulting_count": len(self._undo_stack)}

    def cancel_undo_context(self, doc, baseline_count):
        if self._context_has_action:
            self._undo_stack.append(self._context_title)
        self._context_open = False
        self._context_has_action = False
        reverted = 0
        while len(self._undo_stack) > baseline_count:
            self._undo_stack.pop()
            reverted += 1
        return {"reverted_count": reverted, "restored": len(self._undo_stack) <= baseline_count, "resulting_count": len(self._undo_stack)}


def _noop_handler(**kwargs):
    return {"success": True, "result": {}}


def _build_tools_dict(extra=None):
    """Real scaffold registry (366 tools, including the 12 real core_runtime
    ones) reduced to the {description, parameters, handler} shape
    mcp_server.py's self.tools actually has, plus a couple of fake
    legacy-named entries (any handler works -- LEGACY_TOOL_PROFILES looks
    tools up by name before consulting the handler's module)."""
    tools_dict = {}
    merge_into(tools_dict)
    tools_dict["list_open_documents"] = {"description": "legacy", "parameters": {"type": "object", "properties": {}}, "handler": _noop_handler}
    tools_dict["insert_text_live"] = {"description": "legacy", "parameters": {"type": "object", "properties": {}}, "handler": _noop_handler}
    if extra:
        tools_dict.update(extra)
    return tools_dict


def _install(active_document=None, open_documents=None, version_success=True, extra_tools=None):
    """Install a fresh fake context and return (uno_bridge, document_registry, runtime_state, tools_dict, handler_lookup)."""
    uno_bridge = FakeUnoBridge(active_document=active_document, open_documents=open_documents, version_success=version_success)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    tools_dict = _build_tools_dict(extra_tools)
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: tools_dict,
    ))
    return uno_bridge, document_registry, runtime_state, tools_dict


def _handler(name):
    return get_registry()[name]["handler"]


def test_ping_live_echoes_and_reports_session_id():
    context.reset()
    _, _, runtime_state, _ = _install()
    result = _handler("ping_live")(echo="hello")
    assert result["success"] is True
    assert result["result"]["pong"] is True
    assert result["result"]["echo"] == "hello"
    assert result["result"]["session_id"] == runtime_state.session_id


def test_get_server_info_live_reports_real_fields():
    context.reset()
    _install()
    result = _handler("get_server_info_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["extension_version"] == "2.0.6"
    assert r["libreoffice_version"] == "24.2.0.3"
    assert "python_version" in r and r["python_version"]
    assert r["transport"] == "http"
    assert r["http_port"] == 8765
    assert result["warnings"] == []


def test_get_server_info_live_warns_when_version_query_fails():
    context.reset()
    _install(version_success=False)
    result = _handler("get_server_info_live")()
    assert result["success"] is True
    assert result["result"]["libreoffice_version"] == "unknown"
    assert len(result["warnings"]) == 1


def test_get_capabilities_live_with_no_active_document():
    context.reset()
    _install()
    result = _handler("get_capabilities_live")()
    assert result["success"] is True
    assert result["result"]["active_document_type"] is None
    assert result["result"]["supported_document_types"] == ["writer", "calc", "impress", "draw"]
    assert result["result"]["security_gates"]["trusted_localhost_only"] is True


def test_get_capabilities_live_with_registered_document_id():
    context.reset()
    _, document_registry, _, _ = _install()
    doc_id = document_registry.register_document(FakeDocument("calc"))
    result = _handler("get_capabilities_live")(document_id=doc_id)
    assert result["success"] is True
    assert result["result"]["active_document_type"] == "calc"
    assert result["document_id"] == doc_id


def test_get_capabilities_live_with_unknown_document_id():
    context.reset()
    _install()
    result = _handler("get_capabilities_live")(document_id="not-a-real-id")
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_get_tool_schema_live_known_and_unknown_tool():
    context.reset()
    _install()
    ok = _handler("get_tool_schema_live")(tool_name="ping_live")
    assert ok["success"] is True
    assert ok["result"]["tool_name"] == "ping_live"
    assert "parameters" in ok["result"]

    missing = _handler("get_tool_schema_live")(tool_name="does_not_exist_live")
    assert missing["success"] is False
    assert missing["error"]["code"] == "OBJECT_NOT_FOUND"


def test_list_tools_live_all_profile_returns_everything():
    context.reset()
    _, _, _, tools_dict = _install()
    result = _handler("list_tools_live")(profile="all")
    assert result["success"] is True
    assert result["result"]["count"] == len(tools_dict)


def test_list_tools_live_writer_profile_includes_writer_excludes_calc():
    context.reset()
    _install()
    result = _handler("list_tools_live")(profile="writer")
    names = set(result["result"]["tools"])
    assert "insert_text_live" in names  # legacy writer tool
    assert "insert_paragraph_live" in names  # tools/writer_text.py
    assert "ping_live" in names  # always-on
    assert "list_sheets_live" not in names  # tools/calc_sheets.py, calc-only


def test_list_tools_live_auto_profile_follows_active_document_type():
    context.reset()
    _install(active_document=FakeDocument("calc"))
    result = _handler("list_tools_live")(profile="auto")
    names = set(result["result"]["tools"])
    assert "list_sheets_live" in names
    assert "insert_paragraph_live" not in names
    assert "ping_live" in names


def test_list_tools_live_rejects_invalid_profile():
    context.reset()
    _install()
    result = _handler("list_tools_live")(profile="not-a-real-profile")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_set_tool_profile_live_updates_runtime_state():
    context.reset()
    _, _, runtime_state, _ = _install()
    result = _handler("set_tool_profile_live")(profile="calc")
    assert result["success"] is True
    assert runtime_state.get_profile() == "calc"


def test_set_tool_profile_live_rejects_invalid_profile():
    context.reset()
    _install()
    result = _handler("set_tool_profile_live")(profile="not-a-real-profile")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_get_session_state_live_reports_active_and_open_documents():
    context.reset()
    active = FakeDocument("writer", title="Active")
    other = FakeDocument("calc", title="Other")
    _install(active_document=active, open_documents=[active, other])
    result = _handler("get_session_state_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["active_document"]["title"] == "Active"
    assert {d["title"] for d in r["open_documents"]} == {"Active", "Other"}
    assert r["current_profile"] == "auto"
    assert r["pending_undo_context"] is None


def test_batch_execute_live_runs_operations_in_order():
    context.reset()
    calls = []

    def handler_a(**kwargs):
        calls.append("a")
        return {"success": True, "result": {}}

    def handler_b(**kwargs):
        calls.append("b")
        return {"success": True, "result": {}}

    _install(extra_tools={
        "fake_tool_a": {"description": "a", "parameters": {"type": "object", "properties": {}}, "handler": handler_a},
        "fake_tool_b": {"description": "b", "parameters": {"type": "object", "properties": {}}, "handler": handler_b},
    })
    result = _handler("batch_execute_live")(operations=[{"tool_name": "fake_tool_a"}, {"tool_name": "fake_tool_b"}])
    assert result["success"] is True
    assert calls == ["a", "b"]
    assert result["result"]["executed_count"] == 2
    assert result["result"]["failed_count"] == 0


def test_batch_execute_live_stops_on_error_by_default():
    context.reset()
    calls = []

    def failing_handler(**kwargs):
        calls.append("fail")
        return {"success": False, "error": {"code": "INVALID_RANGE", "message": "bad range"}}

    def never_called(**kwargs):
        calls.append("never")
        return {"success": True, "result": {}}

    _install(extra_tools={
        "failing_tool": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": failing_handler},
        "never_tool": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": never_called},
    })
    result = _handler("batch_execute_live")(operations=[{"tool_name": "failing_tool"}, {"tool_name": "never_tool"}])
    assert calls == ["fail"]
    assert result["result"]["failed_count"] == 1
    assert result["result"]["executed_count"] == 1


def test_batch_execute_live_continues_past_error_when_stop_on_error_false():
    context.reset()
    calls = []

    def failing_handler(**kwargs):
        calls.append("fail")
        return {"success": False, "error": {"code": "INVALID_RANGE", "message": "bad range"}}

    def runs_anyway(**kwargs):
        calls.append("runs")
        return {"success": True, "result": {}}

    _install(extra_tools={
        "failing_tool": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": failing_handler},
        "runs_tool": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": runs_anyway},
    })
    result = _handler("batch_execute_live")(
        operations=[{"tool_name": "failing_tool"}, {"tool_name": "runs_tool"}], stop_on_error=False,
    )
    assert calls == ["fail", "runs"]
    assert result["result"]["executed_count"] == 2
    assert result["result"]["failed_count"] == 1


def test_batch_execute_live_reports_unknown_tool_name():
    context.reset()
    _install()
    result = _handler("batch_execute_live")(operations=[{"tool_name": "totally_made_up_tool"}])
    assert result["success"] is True  # the batch call itself succeeds; the per-op result records the failure
    assert result["result"]["results"][0]["error"]["code"] == "OBJECT_NOT_FOUND"


def test_batch_execute_live_with_undo_label_groups_into_one_undo_step():
    context.reset()
    doc = FakeDocument("writer")

    def edit_a(**kwargs):
        context.get_context().uno_bridge.simulate_edit()
        return {"success": True, "result": {}}

    def edit_b(**kwargs):
        context.get_context().uno_bridge.simulate_edit()
        return {"success": True, "result": {}}

    uno_bridge, _, _, _ = _install(active_document=doc, extra_tools={
        "edit_a": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": edit_a},
        "edit_b": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": edit_b},
    })

    result = _handler("batch_execute_live")(
        operations=[{"tool_name": "edit_a"}, {"tool_name": "edit_b"}], undo_label="Test batch",
    )
    assert result["success"] is True
    assert not any("undo_label" in w for w in result["warnings"])  # the old "not implemented" warning is gone
    assert uno_bridge._undo_stack == ["Test batch"]  # both edits coalesced into ONE undo step


def test_batch_execute_live_undo_label_commits_context_even_when_stop_on_error_trips():
    context.reset()
    doc = FakeDocument("writer")

    def edit_then_fail(**kwargs):
        context.get_context().uno_bridge.simulate_edit()
        return {"success": False, "error": {"code": "UNO_EXCEPTION", "message": "boom"}}

    uno_bridge, _, runtime_state, _ = _install(active_document=doc, extra_tools={
        "edit_then_fail": {"description": "", "parameters": {"type": "object", "properties": {}}, "handler": edit_then_fail},
    })

    result = _handler("batch_execute_live")(operations=[{"tool_name": "edit_then_fail"}], undo_label="Partial batch")
    assert result["success"] is True  # the batch call itself succeeds; the per-op failure is in results
    assert result["result"]["failed_count"] == 1
    # Committed (one visible Undo step for the partial progress), not rolled back --
    # see core_runtime.py's batch_execute_live comment for the reasoning.
    assert uno_bridge._undo_stack == ["Partial batch"]
    assert runtime_state.get_undo_context() is None  # context was still closed cleanly


def test_batch_execute_live_undo_label_fails_cleanly_if_context_already_open():
    context.reset()
    doc = FakeDocument("writer")
    _, _, runtime_state, _ = _install(active_document=doc)
    runtime_state.set_undo_context(title="Already open", document_id=None, baseline_count=0)

    result = _handler("batch_execute_live")(operations=[{"tool_name": "list_open_documents"}], undo_label="New batch")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_STATE"


def test_batch_execute_live_rejects_empty_operations():
    context.reset()
    _install()
    result = _handler("batch_execute_live")(operations=[])
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_validate_tool_call_live_accepts_valid_parameters():
    context.reset()
    _install()
    result = _handler("validate_tool_call_live")(tool_name="ping_live", parameters={"echo": "hi"})
    assert result["success"] is True
    assert result["result"]["valid"] is True


def test_validate_tool_call_live_catches_missing_required_parameter():
    context.reset()
    _install()
    result = _handler("validate_tool_call_live")(tool_name="get_tool_schema_live", parameters={})
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"
    assert any("tool_name" in msg for msg in result["error"]["details"]["validation_errors"])


def test_validate_tool_call_live_catches_wrong_type():
    context.reset()
    _install()
    result = _handler("validate_tool_call_live")(tool_name="ping_live", parameters={"echo": 123})
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_validate_tool_call_live_unknown_tool():
    context.reset()
    _install()
    result = _handler("validate_tool_call_live")(tool_name="does_not_exist_live", parameters={})
    assert result["success"] is False
    assert result["error"]["code"] == "OBJECT_NOT_FOUND"


def test_get_recent_errors_live_returns_recorded_errors():
    context.reset()
    _, _, runtime_state, _ = _install()
    runtime_state.record_error("some_tool", "TIMEOUT", "took too long")
    result = _handler("get_recent_errors_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 1
    assert result["result"]["errors"][0]["tool_name"] == "some_tool"


def test_get_recent_errors_live_rejects_bad_since():
    context.reset()
    _install()
    result = _handler("get_recent_errors_live")(since="not-a-timestamp")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_get_diagnostics_live_reports_uno_and_thread_state():
    context.reset()
    _install()
    result = _handler("get_diagnostics_live")()
    assert result["success"] is True
    r = result["result"]
    assert r["uno_context_available"] is True
    assert r["thread_count"] >= 1
    assert r["http_port"] == 8765
    assert "environment" not in r


def test_get_diagnostics_live_includes_environment_when_requested():
    context.reset()
    _install()
    result = _handler("get_diagnostics_live")(include_environment=True)
    assert "environment" in result["result"]
    assert "python_executable" in result["result"]["environment"]


def test_clear_diagnostics_live_clears_error_history():
    context.reset()
    _, _, runtime_state, _ = _install()
    runtime_state.record_error("tool", "TIMEOUT", "boom")
    result = _handler("clear_diagnostics_live")()
    assert result["success"] is True
    assert runtime_state.get_recent_errors() == []


if __name__ == "__main__":
    tests = [
        test_ping_live_echoes_and_reports_session_id,
        test_get_server_info_live_reports_real_fields,
        test_get_server_info_live_warns_when_version_query_fails,
        test_get_capabilities_live_with_no_active_document,
        test_get_capabilities_live_with_registered_document_id,
        test_get_capabilities_live_with_unknown_document_id,
        test_get_tool_schema_live_known_and_unknown_tool,
        test_list_tools_live_all_profile_returns_everything,
        test_list_tools_live_writer_profile_includes_writer_excludes_calc,
        test_list_tools_live_auto_profile_follows_active_document_type,
        test_list_tools_live_rejects_invalid_profile,
        test_set_tool_profile_live_updates_runtime_state,
        test_set_tool_profile_live_rejects_invalid_profile,
        test_get_session_state_live_reports_active_and_open_documents,
        test_batch_execute_live_runs_operations_in_order,
        test_batch_execute_live_stops_on_error_by_default,
        test_batch_execute_live_continues_past_error_when_stop_on_error_false,
        test_batch_execute_live_reports_unknown_tool_name,
        test_batch_execute_live_with_undo_label_groups_into_one_undo_step,
        test_batch_execute_live_undo_label_commits_context_even_when_stop_on_error_trips,
        test_batch_execute_live_undo_label_fails_cleanly_if_context_already_open,
        test_batch_execute_live_rejects_empty_operations,
        test_validate_tool_call_live_accepts_valid_parameters,
        test_validate_tool_call_live_catches_missing_required_parameter,
        test_validate_tool_call_live_catches_wrong_type,
        test_validate_tool_call_live_unknown_tool,
        test_get_recent_errors_live_returns_recorded_errors,
        test_get_recent_errors_live_rejects_bad_since,
        test_get_diagnostics_live_reports_uno_and_thread_state,
        test_get_diagnostics_live_includes_environment_when_requested,
        test_clear_diagnostics_live_clears_error_history,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    context.reset()
    print(f"\nAll {len(tests)} core_runtime tests passed.")
