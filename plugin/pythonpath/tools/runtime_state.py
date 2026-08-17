"""
Server-lifetime runtime state: session identity, tool-exposure profile,
and bounded error/diagnostics history.

This is real, working code (not a stub) backing the "Core runtime,
discovery, and capability negotiation" tools. It holds no UNO references
and makes no UNO calls, so it's fully unit-testable without a live
LibreOffice instance -- see tests/test_runtime_state.py.

One instance lives for the lifetime of the embedded MCP server (created
once in mcp_server.LibreOfficeMCPServer.__init__ and installed into
tools.context so plain module-level tool functions can reach it).
"""

import threading
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional

# Spec section 3's recommended tool-exposure profiles.
VALID_PROFILES = frozenset({
    "auto", "writer", "calc", "impress", "draw", "base", "math", "all", "advanced",
})

DEFAULT_PROFILE = "auto"

# Bound the error/diagnostics history so a long-running server session
# can't accumulate unbounded memory from a client hammering a failing tool.
MAX_ERROR_HISTORY = 200


class RuntimeState:
    """Mutable, thread-safe state for one running MCP server session."""

    def __init__(self) -> None:
        self.session_id: str = uuid.uuid4().hex
        self.start_time: float = time.monotonic()
        self._lock = threading.Lock()
        self._profile: str = DEFAULT_PROFILE
        self._error_history: Deque[Dict[str, Any]] = deque(maxlen=MAX_ERROR_HISTORY)
        self._call_count: int = 0
        self._error_count: int = 0
        # The currently-open named undo context, if any (see
        # tools.undo_view_selection.begin_undo_context_live). None of the
        # values here are UNO references -- document_id is a DocumentRegistry
        # id and baseline_count is a plain int (undo-stack depth at the
        # moment the context opened) -- so this stays UNO-free like the rest
        # of this class.
        self._undo_context: Optional[Dict[str, Any]] = None

    @property
    def uptime_seconds(self) -> float:
        """Seconds since this RuntimeState (i.e. the server session) was created."""
        return time.monotonic() - self.start_time

    def get_profile(self) -> str:
        with self._lock:
            return self._profile

    def set_profile(self, profile: str) -> None:
        """Set the active tool-exposure profile.

        Raises:
            ValueError: profile is not one of VALID_PROFILES.
        """
        if profile not in VALID_PROFILES:
            raise ValueError(f"Unknown profile '{profile}', expected one of {sorted(VALID_PROFILES)}")
        with self._lock:
            self._profile = profile

    def record_call(self) -> None:
        """Increment the total-calls counter. Called once per tool invocation."""
        with self._lock:
            self._call_count += 1

    def record_error(self, tool_name: str, code: str, message: str) -> None:
        """Append a structured error entry to the bounded history.

        Args:
            tool_name: The MCP tool that produced the error.
            code: One of envelope.ERROR_CODES.
            message: Human-readable error summary (no secrets/paths beyond
                what the caller already supplied).
        """
        with self._lock:
            self._error_count += 1
            self._error_history.append({
                "tool_name": tool_name,
                "code": code,
                "message": message,
                # Wall-clock, not monotonic -- callers filter `since` against this.
                "timestamp": time.time(),
            })

    def get_recent_errors(self, limit: int = 50, since: Optional[float] = None) -> List[Dict[str, Any]]:
        """Return up to `limit` most recent errors, newest first.

        Args:
            limit: Maximum number of entries to return.
            since: Unix timestamp; only errors strictly after this are returned.
        """
        with self._lock:
            entries = list(self._error_history)
        if since is not None:
            entries = [e for e in entries if e["timestamp"] > since]
        entries.reverse()  # newest first
        return entries[:limit]

    def clear_errors(self) -> None:
        with self._lock:
            self._error_history.clear()
            self._error_count = 0

    def set_undo_context(self, title: str, document_id: Optional[str], baseline_count: int) -> None:
        """Record that a named undo context is now open.

        Args:
            title: The context's title, as passed to begin_undo_context_live.
            document_id: DocumentRegistry id of the document it was opened on.
            baseline_count: Undo-stack depth immediately before the context
                opened (see uno_bridge.UNOBridge.begin_undo_context) -- needed
                by cancel_undo_context_live to know how much to revert.
        """
        with self._lock:
            self._undo_context = {"title": title, "document_id": document_id, "baseline_count": baseline_count}

    def get_undo_context(self) -> Optional[Dict[str, Any]]:
        """Return {"title", "document_id", "baseline_count"} for the open
        undo context, or None if no context is currently open."""
        with self._lock:
            return dict(self._undo_context) if self._undo_context is not None else None

    def clear_undo_context(self) -> None:
        """Clear the open-undo-context record. Only call this once the
        context has actually been closed on the UNO side (end/cancel
        succeeded) -- clearing it after a failed leaveUndoContext() call
        would desync this tracker from the real (still-open) UNO context."""
        with self._lock:
            self._undo_context = None

    def get_diagnostics_counters(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "call_count": self._call_count,
                "error_count": self._error_count,
                "error_history_size": len(self._error_history),
            }
