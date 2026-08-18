#!/usr/bin/env python3
"""
Unit tests for plugin/pythonpath/mcp_jsonrpc.

mcp_jsonrpc.py has no `uno`/HTTP dependency -- it takes already-parsed
JSON-RPC message dicts plus a plain tools dict and an execute_tool
callable, so this runs without a live LibreOffice instance or HTTP
server. The live transport wiring (ai_interface.py's /mcp route,
Content-Type/session headers) is covered separately by live-verification
against a real MCP client, not here -- see
docs/MCP_TOOLING_SCAFFOLD_PLAN.md's "Real /mcp JSON-RPC transport" pass.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

import mcp_jsonrpc  # noqa: E402

FAKE_TOOLS = {
    "ping_live": {"description": "Health check.", "parameters": {"type": "object", "properties": {}}},
    "get_document_info_live": {
        "description": "Return active document info.",
        "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}},
    },
}


def fake_execute_tool_ok(name, arguments):
    return {"success": True, "result": {"echo": arguments}, "tool": name}


def fake_execute_tool_soft_failure(name, arguments):
    return {"success": False, "error": {"code": "NO_ACTIVE_DOCUMENT", "message": ""}}


def fake_execute_tool_raises(name, arguments):
    raise RuntimeError("boom")


# -- initialize --

def test_initialize_echoes_requested_protocol_version():
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "LibreOffice MCP Extension"
    assert "tools" in resp["result"]["capabilities"]


def test_initialize_without_protocol_version_still_returns_one():
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert isinstance(resp["result"]["protocolVersion"], str) and resp["result"]["protocolVersion"]


def test_initialize_falls_back_to_latest_supported_on_unknown_version():
    """Per the lifecycle spec's version negotiation: an unsupported
    requested version does NOT error the initialize -- the server
    responds with its own supported version instead (hardening Phase 3,
    docs/HARDENING_PLAN.md)."""
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1900-01-01"}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert "error" not in resp
    assert resp["result"]["protocolVersion"] == mcp_jsonrpc.LATEST_PROTOCOL_VERSION


def test_initialize_accepts_every_supported_version_unchanged():
    for version in mcp_jsonrpc.SUPPORTED_PROTOCOL_VERSIONS:
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": version}}
        resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
        assert resp["result"]["protocolVersion"] == version


# -- notifications --

def test_notifications_initialized_gets_no_response():
    msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok) is None


def test_unknown_notification_gets_no_response_not_an_error():
    msg = {"jsonrpc": "2.0", "method": "notifications/some_future_thing"}
    assert mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok) is None


# -- ping --

def test_ping_returns_empty_result():
    msg = {"jsonrpc": "2.0", "id": "abc", "method": "ping"}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp == {"jsonrpc": "2.0", "id": "abc", "result": {}}


# -- tools/list --

def test_tools_list_converts_parameters_to_input_schema():
    msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    tools = {t["name"]: t for t in resp["result"]["tools"]}
    assert set(tools) == set(FAKE_TOOLS)
    assert tools["ping_live"]["description"] == "Health check."
    assert tools["ping_live"]["inputSchema"] == {"type": "object", "properties": {}}
    assert "parameters" not in tools["ping_live"]  # renamed, not duplicated


def test_tools_list_on_empty_registry_returns_empty_list():
    msg = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
    resp = mcp_jsonrpc.dispatch_one(msg, {}, fake_execute_tool_ok)
    assert resp["result"]["tools"] == []


# -- resources/list, prompts/list (always empty -- no MCP resources/prompts exposed) --

def test_resources_and_prompts_list_are_always_empty():
    resources = mcp_jsonrpc.dispatch_one({"jsonrpc": "2.0", "id": 4, "method": "resources/list"}, FAKE_TOOLS, fake_execute_tool_ok)
    prompts = mcp_jsonrpc.dispatch_one({"jsonrpc": "2.0", "id": 5, "method": "prompts/list"}, FAKE_TOOLS, fake_execute_tool_ok)
    assert resources["result"] == {"resources": []}
    assert prompts["result"] == {"prompts": []}


# -- tools/call --

def test_tools_call_success_wraps_envelope_as_text_content():
    msg = {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "ping_live", "arguments": {"x": 1}}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["result"]["isError"] is False
    content = resp["result"]["content"]
    assert len(content) == 1 and content[0]["type"] == "text"
    assert '"echo"' in content[0]["text"] and '"x": 1' in content[0]["text"]


def test_tools_call_tool_level_failure_is_still_a_successful_jsonrpc_response():
    """Per the two-layer error model: a tool-level failure (envelope
    success: False) is isError: true on a 200-shaped JSON-RPC result,
    NOT a JSON-RPC error object -- only protocol-level faults are."""
    msg = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "get_document_info_live", "arguments": {}}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_soft_failure)
    assert "error" not in resp
    assert resp["result"]["isError"] is True
    assert "NO_ACTIVE_DOCUMENT" in resp["result"]["content"][0]["text"]


def test_tools_call_missing_name_is_invalid_params():
    msg = {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"arguments": {}}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["error"]["code"] == mcp_jsonrpc.INVALID_PARAMS


def test_tools_call_non_object_arguments_is_invalid_params():
    msg = {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "ping_live", "arguments": "not-an-object"}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["error"]["code"] == mcp_jsonrpc.INVALID_PARAMS


def test_tools_call_handler_exception_is_internal_error_not_a_crash():
    msg = {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "ping_live", "arguments": {}}}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_raises)
    assert resp["error"]["code"] == mcp_jsonrpc.INTERNAL_ERROR
    assert "boom" in resp["error"]["message"]


# -- protocol-level validation --

def test_unknown_method_is_method_not_found():
    msg = {"jsonrpc": "2.0", "id": 11, "method": "not/a/real/method"}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["error"]["code"] == mcp_jsonrpc.METHOD_NOT_FOUND


def test_wrong_jsonrpc_version_is_invalid_request():
    msg = {"jsonrpc": "1.0", "id": 12, "method": "ping"}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST


def test_missing_method_is_invalid_request():
    msg = {"jsonrpc": "2.0", "id": 13}
    resp = mcp_jsonrpc.dispatch_one(msg, FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST


def test_non_dict_message_is_invalid_request_not_a_crash():
    resp = mcp_jsonrpc.dispatch_one("not a dict", FAKE_TOOLS, fake_execute_tool_ok)
    assert resp["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST


# -- dispatch(): batch/notification/single envelope handling --

def test_dispatch_single_request_returns_single_object_and_200():
    body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    response, status = mcp_jsonrpc.dispatch(body, FAKE_TOOLS, fake_execute_tool_ok)
    assert status == 200
    assert isinstance(response, dict) and response["id"] == 1


def test_dispatch_single_notification_returns_none_and_202():
    body = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    response, status = mcp_jsonrpc.dispatch(body, FAKE_TOOLS, fake_execute_tool_ok)
    assert response is None
    assert status == 202


def test_dispatch_batch_returns_a_list_matching_only_the_requests_with_ids():
    body = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},  # no reply
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ]
    response, status = mcp_jsonrpc.dispatch(body, FAKE_TOOLS, fake_execute_tool_ok)
    assert status == 200
    assert isinstance(response, list)
    assert [r["id"] for r in response] == [1, 2]


def test_dispatch_batch_of_only_notifications_returns_none_and_202():
    body = [{"jsonrpc": "2.0", "method": "notifications/initialized"}]
    response, status = mcp_jsonrpc.dispatch(body, FAKE_TOOLS, fake_execute_tool_ok)
    assert response is None
    assert status == 202


def test_dispatch_empty_batch_is_an_error_not_a_silent_202():
    response, status = mcp_jsonrpc.dispatch([], FAKE_TOOLS, fake_execute_tool_ok)
    assert status == 400
    assert response["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST


# -- SessionRegistry (hardening Phase 3: Mcp-Session-Id enforcement) --

def test_session_registry_created_session_is_active():
    registry = mcp_jsonrpc.SessionRegistry()
    registry.create_session("abc123")
    assert registry.has_session("abc123") is True


def test_session_registry_unknown_session_is_not_active():
    registry = mcp_jsonrpc.SessionRegistry()
    assert registry.has_session("never-created") is False


def test_session_registry_create_is_idempotent():
    registry = mcp_jsonrpc.SessionRegistry()
    registry.create_session("abc123")
    registry.create_session("abc123")  # re-registering is not an error
    assert registry.has_session("abc123") is True


def test_session_registry_end_session_removes_a_known_session():
    registry = mcp_jsonrpc.SessionRegistry()
    registry.create_session("abc123")
    assert registry.end_session("abc123") is True
    assert registry.has_session("abc123") is False


def test_session_registry_end_session_on_unknown_id_reports_false():
    registry = mcp_jsonrpc.SessionRegistry()
    assert registry.end_session("never-created") is False


# -- check_session_header() (hardening Phase 3: Mcp-Session-Id enforcement) --

def test_check_session_header_skips_validation_for_initialize():
    registry = mcp_jsonrpc.SessionRegistry()
    assert mcp_jsonrpc.check_session_header(True, None, registry) is None


def test_check_session_header_missing_is_bad_request():
    registry = mcp_jsonrpc.SessionRegistry()
    status, body = mcp_jsonrpc.check_session_header(False, None, registry)
    assert status == 400
    assert body["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST


def test_check_session_header_unknown_id_is_not_found():
    registry = mcp_jsonrpc.SessionRegistry()
    status, body = mcp_jsonrpc.check_session_header(False, "never-created", registry)
    assert status == 404
    assert body["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST


def test_check_session_header_known_id_passes():
    registry = mcp_jsonrpc.SessionRegistry()
    registry.create_session("abc123")
    assert mcp_jsonrpc.check_session_header(False, "abc123", registry) is None


def test_check_session_header_terminated_id_is_rejected_again():
    """A DELETE'd session must not still validate on a later request --
    the exact spec case (session-management rule #3) this hardening item
    exists to close."""
    registry = mcp_jsonrpc.SessionRegistry()
    registry.create_session("abc123")
    registry.end_session("abc123")
    status, body = mcp_jsonrpc.check_session_header(False, "abc123", registry)
    assert status == 404


# -- check_protocol_version_header() (hardening Phase 3: protocol-version validation) --

def test_check_protocol_version_header_absent_is_allowed():
    """Absent header falls back to DEFAULT_PROTOCOL_VERSION per the
    transport spec's backwards-compatibility clause -- not itself a
    violation."""
    assert mcp_jsonrpc.check_protocol_version_header(None) is None


def test_check_protocol_version_header_every_supported_version_passes():
    for version in mcp_jsonrpc.SUPPORTED_PROTOCOL_VERSIONS:
        assert mcp_jsonrpc.check_protocol_version_header(version) is None


def test_check_protocol_version_header_unsupported_is_bad_request():
    status, body = mcp_jsonrpc.check_protocol_version_header("1900-01-01")
    assert status == 400
    assert body["error"]["code"] == mcp_jsonrpc.INVALID_REQUEST
    assert body["error"]["data"]["requested"] == "1900-01-01"
    assert body["error"]["data"]["supported"] == list(mcp_jsonrpc.SUPPORTED_PROTOCOL_VERSIONS)


if __name__ == "__main__":
    tests = [
        test_initialize_echoes_requested_protocol_version,
        test_initialize_without_protocol_version_still_returns_one,
        test_initialize_falls_back_to_latest_supported_on_unknown_version,
        test_initialize_accepts_every_supported_version_unchanged,
        test_notifications_initialized_gets_no_response,
        test_unknown_notification_gets_no_response_not_an_error,
        test_ping_returns_empty_result,
        test_tools_list_converts_parameters_to_input_schema,
        test_tools_list_on_empty_registry_returns_empty_list,
        test_resources_and_prompts_list_are_always_empty,
        test_tools_call_success_wraps_envelope_as_text_content,
        test_tools_call_tool_level_failure_is_still_a_successful_jsonrpc_response,
        test_tools_call_missing_name_is_invalid_params,
        test_tools_call_non_object_arguments_is_invalid_params,
        test_tools_call_handler_exception_is_internal_error_not_a_crash,
        test_unknown_method_is_method_not_found,
        test_wrong_jsonrpc_version_is_invalid_request,
        test_missing_method_is_invalid_request,
        test_non_dict_message_is_invalid_request_not_a_crash,
        test_dispatch_single_request_returns_single_object_and_200,
        test_dispatch_single_notification_returns_none_and_202,
        test_dispatch_batch_returns_a_list_matching_only_the_requests_with_ids,
        test_dispatch_batch_of_only_notifications_returns_none_and_202,
        test_dispatch_empty_batch_is_an_error_not_a_silent_202,
        test_session_registry_created_session_is_active,
        test_session_registry_unknown_session_is_not_active,
        test_session_registry_create_is_idempotent,
        test_session_registry_end_session_removes_a_known_session,
        test_session_registry_end_session_on_unknown_id_reports_false,
        test_check_session_header_skips_validation_for_initialize,
        test_check_session_header_missing_is_bad_request,
        test_check_session_header_unknown_id_is_not_found,
        test_check_session_header_known_id_passes,
        test_check_session_header_terminated_id_is_rejected_again,
        test_check_protocol_version_header_absent_is_allowed,
        test_check_protocol_version_header_every_supported_version_passes,
        test_check_protocol_version_header_unsupported_is_bad_request,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} mcp_jsonrpc tests passed.")
