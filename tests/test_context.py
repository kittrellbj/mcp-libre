#!/usr/bin/env python3
"""
Unit tests for tools.context -- the process-wide RuntimeContext holder
core_runtime.py's real tool implementations read from.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402


def test_get_context_raises_clearly_when_not_installed():
    context.reset()
    assert context.is_installed() is False
    try:
        context.get_context()
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "install" in str(e)


def test_install_then_get_context_returns_the_same_object():
    context.reset()
    installed = context.RuntimeContext(
        uno_bridge="fake_uno_bridge", document_registry="fake_registry",
        runtime_state="fake_state", get_tools=lambda: {},
    )
    context.install(installed)
    assert context.is_installed() is True
    assert context.get_context() is installed


def test_reset_clears_the_installed_context():
    context.install(context.RuntimeContext(
        uno_bridge=None, document_registry=None, runtime_state=None, get_tools=lambda: {},
    ))
    context.reset()
    assert context.is_installed() is False


def test_get_tools_is_called_lazily_not_snapshotted():
    """get_tools is a callable, not a dict, so handlers always see current state."""
    context.reset()
    live_dict = {"a": 1}
    context.install(context.RuntimeContext(
        uno_bridge=None, document_registry=None, runtime_state=None, get_tools=lambda: live_dict,
    ))
    live_dict["b"] = 2
    assert context.get_context().get_tools() == {"a": 1, "b": 2}


if __name__ == "__main__":
    tests = [
        test_get_context_raises_clearly_when_not_installed,
        test_install_then_get_context_returns_the_same_object,
        test_reset_clears_the_installed_context,
        test_get_tools_is_called_lazily_not_snapshotted,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    context.reset()
    print(f"\nAll {len(tests)} context tests passed.")
