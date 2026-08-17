"""
Shared runtime context for tool handlers that need access to live server
state (UNOBridge, DocumentRegistry, RuntimeState, the full tool registry)
rather than just the document model.

@register_tool-decorated functions in this package are plain module-level
functions with no `self` -- that's fine for stub bodies that ignore their
arguments, but a real implementation of e.g. get_session_state_live needs
to reach the live UNOBridge and DocumentRegistry the server constructed.
Threading those through every tool function's signature would break the
decorator's plain-function contract for no real benefit in what is a
single-process, single-UNO-bridge extension, so instead this module holds
one process-wide context object, installed once by
mcp_server.LibreOfficeMCPServer.__init__ at startup and read by handler
functions via get_context(). This is the same "current app" pattern small
frameworks use (e.g. Flask's `current_app`).
"""

import threading
from typing import Any, Callable, Dict, Optional


class RuntimeContext:
    """Bundle of live server dependencies a tool handler may need.

    Args:
        uno_bridge: The server's uno_bridge.UNOBridge instance.
        document_registry: The server's tools.documents.DocumentRegistry instance.
        runtime_state: The server's tools.runtime_state.RuntimeState instance.
        get_tools: Zero-arg callable returning the live {tool_name: metadata}
            registry (i.e. `lambda: server.tools`). Passed as a callable
            rather than the dict itself so handlers always see the current
            contents, including tools registered after context install.
    """

    def __init__(self, uno_bridge: Any, document_registry: Any, runtime_state: Any,
                 get_tools: Callable[[], Dict[str, Any]]) -> None:
        self.uno_bridge = uno_bridge
        self.document_registry = document_registry
        self.runtime_state = runtime_state
        self.get_tools = get_tools


_lock = threading.Lock()
_context: Optional[RuntimeContext] = None


def install(context: RuntimeContext) -> None:
    """Install the process-wide context. Called once at server startup."""
    global _context
    with _lock:
        _context = context


def get_context() -> RuntimeContext:
    """Return the installed context.

    Raises:
        RuntimeError: install() was never called -- e.g. a core_runtime
            tool was invoked without going through
            mcp_server.LibreOfficeMCPServer.__init__ first.
    """
    if _context is None:
        raise RuntimeError(
            "tools.context has no installed RuntimeContext -- "
            "mcp_server.LibreOfficeMCPServer.__init__ must call "
            "tools.context.install(...) before any core_runtime tool is invoked"
        )
    return _context


def is_installed() -> bool:
    return _context is not None


def reset() -> None:
    """Clear the installed context. Test-only: call between test cases
    that install different fake contexts to avoid leaking state."""
    global _context
    with _lock:
        _context = None
