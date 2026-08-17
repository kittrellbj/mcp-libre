#!/usr/bin/env python3
"""
Unit tests for tools.runtime_state.RuntimeState.

Pure Python, no UNO dependency -- runs without live LibreOffice.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools.runtime_state import DEFAULT_PROFILE, MAX_ERROR_HISTORY, RuntimeState, VALID_PROFILES  # noqa: E402


def test_starts_with_default_profile_and_fresh_session_id():
    state = RuntimeState()
    assert state.get_profile() == DEFAULT_PROFILE
    assert isinstance(state.session_id, str) and state.session_id


def test_two_instances_get_different_session_ids():
    assert RuntimeState().session_id != RuntimeState().session_id


def test_uptime_seconds_increases():
    state = RuntimeState()
    first = state.uptime_seconds
    # Windows' time.monotonic() has ~15.6ms timer granularity by default,
    # so a shorter sleep can show a 0.0 delta -- not a RuntimeState bug,
    # just an unreliable probe. Sleep comfortably past that.
    time.sleep(0.05)
    assert state.uptime_seconds > first


def test_set_profile_accepts_every_valid_profile():
    state = RuntimeState()
    for profile in VALID_PROFILES:
        state.set_profile(profile)
        assert state.get_profile() == profile


def test_set_profile_rejects_unknown_profile():
    state = RuntimeState()
    try:
        state.set_profile("not-a-real-profile")
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert state.get_profile() == DEFAULT_PROFILE  # unchanged after the rejected call


def test_record_error_then_get_recent_errors_newest_first():
    state = RuntimeState()
    state.record_error("tool_a", "INVALID_PARAMETER", "first")
    state.record_error("tool_b", "OBJECT_NOT_FOUND", "second")
    entries = state.get_recent_errors()
    assert [e["tool_name"] for e in entries] == ["tool_b", "tool_a"]
    assert entries[0]["code"] == "OBJECT_NOT_FOUND"
    assert entries[0]["message"] == "second"


def test_get_recent_errors_respects_limit():
    state = RuntimeState()
    for i in range(5):
        state.record_error(f"tool_{i}", "UNO_EXCEPTION", str(i))
    entries = state.get_recent_errors(limit=2)
    assert len(entries) == 2
    assert entries[0]["tool_name"] == "tool_4"  # newest first


def test_get_recent_errors_respects_since():
    state = RuntimeState()
    state.record_error("old_tool", "TIMEOUT", "old")
    cutoff = time.time()
    time.sleep(0.01)
    state.record_error("new_tool", "TIMEOUT", "new")
    entries = state.get_recent_errors(since=cutoff)
    assert len(entries) == 1
    assert entries[0]["tool_name"] == "new_tool"


def test_error_history_is_bounded():
    state = RuntimeState()
    for i in range(MAX_ERROR_HISTORY + 50):
        state.record_error("tool", "UNO_EXCEPTION", str(i))
    assert len(state.get_recent_errors(limit=MAX_ERROR_HISTORY + 50)) == MAX_ERROR_HISTORY


def test_clear_errors_empties_history_and_resets_error_count():
    state = RuntimeState()
    state.record_error("tool", "UNO_EXCEPTION", "boom")
    state.clear_errors()
    assert state.get_recent_errors() == []
    assert state.get_diagnostics_counters()["error_count"] == 0


def test_diagnostics_counters_track_calls_and_errors():
    state = RuntimeState()
    state.record_call()
    state.record_call()
    state.record_error("tool", "TIMEOUT", "slow")
    counters = state.get_diagnostics_counters()
    assert counters["call_count"] == 2
    assert counters["error_count"] == 1
    assert counters["error_history_size"] == 1


if __name__ == "__main__":
    tests = [
        test_starts_with_default_profile_and_fresh_session_id,
        test_two_instances_get_different_session_ids,
        test_uptime_seconds_increases,
        test_set_profile_accepts_every_valid_profile,
        test_set_profile_rejects_unknown_profile,
        test_record_error_then_get_recent_errors_newest_first,
        test_get_recent_errors_respects_limit,
        test_get_recent_errors_respects_since,
        test_error_history_is_bounded,
        test_clear_errors_empties_history_and_resets_error_count,
        test_diagnostics_counters_track_calls_and_errors,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} RuntimeState tests passed.")
