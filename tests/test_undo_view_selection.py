#!/usr/bin/env python3
"""
Unit tests for the 6 real (status="implemented") undo tools in
undo_view_selection.py: get_undo_state_live, undo_live, redo_live,
begin_undo_context_live, end_undo_context_live, cancel_undo_context_live.

Uses a FakeUnoBridge modeling a simple undo/redo stack of titles, with a
simulate_edit() test helper standing in for "a UNO edit was just recorded".
Real XUndoManager coalescing semantics (does an empty leaveUndoContext()
really add nothing to the stack? does undo() really raise
UndoContextNotClosedException while a context is open?) are asserted by
this fake's behavior, matching what live testing against real LibreOffice
confirmed -- see the commit message for the live-verification pass. This
suite exercises the tool-layer logic real UNO behavior can't: parameter
validation, nesting rejection, error codes, and stack-exhaustion reporting.

Uses the REAL DocumentRegistry/RuntimeState/tools.context, same pattern as
tests/test_core_runtime.py and tests/test_document_lifecycle.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugin", "pythonpath"))

from tools import context  # noqa: E402
from tools.documents import DocumentRegistry  # noqa: E402
from tools.registry import get_registry  # noqa: E402
from tools.runtime_state import RuntimeState  # noqa: E402


class FakeDocument:
    def __init__(self, doc_type="writer", title="Untitled", url="", current_page_number=1, page_count=3):
        self.doc_type = doc_type
        self.title = title
        self.url = url
        self.modified = False
        self.zoom_value = 100
        self.zoom_mode = "optimal"
        self.has_selection = False
        self.selection_text = ""
        self.lock_count = 0
        # Writer-only -- current_page_number on get_view_state_live (Brian's
        # new-tools assignment priority #6), same convention as active_sheet
        # for calc / current_page_name for impress/draw in the real
        # uno_bridge.get_view_state().
        self.current_page_number = current_page_number
        # Writer-only -- the document's real last page, so goto_page_live's
        # (#7) clamping behavior can be modeled/tested without a live
        # LibreOffice document actually laid out.
        self.page_count = page_count


class FakeUnoBridge:
    """Stand-in for uno_bridge.UNOBridge's undo-manager methods.

    Models a single undo/redo stack of titles -- fine for the
    one-document-at-a-time scenarios these tests cover. simulate_edit()
    mimics a UNO edit being recorded right now: if a context is open, it
    just flags the context as having recorded *something* (real UNO
    coalesces everything recorded inside a context into exactly one action
    on leaveUndoContext, no matter how many edits happened inside -- this
    fake doesn't need to count them to prove that, just to know whether
    it's zero or nonzero); otherwise it lands on the stack immediately.
    """

    def __init__(self, active_document=None):
        self.ctx = object()
        self.active_document = active_document
        self._undo_stack = []
        self._redo_stack = []
        self._context_open = False
        self._context_title = None
        self._context_has_action = False

    def get_active_document(self):
        return self.active_document

    def get_document_info(self, doc):
        return {"type": doc.doc_type, "title": doc.title, "url": doc.url, "modified": doc.modified}

    def simulate_edit(self):
        if self._context_open:
            self._context_has_action = True
        else:
            self._undo_stack.append("Simulated Edit")
            self._redo_stack.clear()

    # -- undo manager --

    def get_undo_state(self, doc):
        can_undo = bool(self._undo_stack)
        can_redo = bool(self._redo_stack)
        return {
            "can_undo": can_undo, "can_redo": can_redo,
            "undo_title": self._undo_stack[-1] if can_undo else None,
            "redo_title": self._redo_stack[-1] if can_redo else None,
        }

    def undo(self, doc, count=1):
        applied = 0
        for _ in range(count):
            if not self._undo_stack:
                break
            self._redo_stack.append(self._undo_stack.pop())
            applied += 1
        return {"requested": count, "applied": applied, "can_undo": bool(self._undo_stack), "can_redo": bool(self._redo_stack)}

    def redo(self, doc, count=1):
        applied = 0
        for _ in range(count):
            if not self._redo_stack:
                break
            self._undo_stack.append(self._redo_stack.pop())
            applied += 1
        return {"requested": count, "applied": applied, "can_undo": bool(self._undo_stack), "can_redo": bool(self._redo_stack)}

    def begin_undo_context(self, doc, title):
        baseline_count = len(self._undo_stack)
        self._context_open = True
        self._context_title = title
        self._context_has_action = False
        return {"baseline_count": baseline_count}

    def end_undo_context(self, doc):
        if self._context_has_action:
            self._undo_stack.append(self._context_title)
            self._redo_stack.clear()
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
        return {
            "reverted_count": reverted,
            "restored": len(self._undo_stack) <= baseline_count,
            "resulting_count": len(self._undo_stack),
        }

    # -- view state, zoom, selection, locking --

    def get_view_state(self, doc):
        state = {"type": doc.doc_type, "zoom_value": doc.zoom_value, "zoom_mode": doc.zoom_mode,
                 "has_selection": doc.has_selection}
        if doc.doc_type == "writer":
            state["current_page_number"] = doc.current_page_number
        return state

    def goto_page(self, doc, page):
        if doc.doc_type != "writer":
            raise NotImplementedError(f"goto_page is only implemented for Writer documents, not '{doc.doc_type}'.")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise ValueError(f"page must be a positive integer, got {page!r}")
        actual = min(page, doc.page_count)
        doc.current_page_number = actual
        result = {"page": actual}
        if actual != page:
            result["warnings"] = [
                f"Requested page {page} but the document only reaches page {actual} -- "
                "clamped to the last real page rather than failing."
            ]
        return result

    def set_zoom(self, doc, percent=None, mode=None):
        if percent is None and mode is None:
            raise ValueError("Provide either percent or mode.")
        if mode is not None:
            if mode not in {"optimal", "page", "width"}:
                raise ValueError(f"Unknown zoom mode '{mode}'")
            doc.zoom_mode = mode
        if percent is not None:
            doc.zoom_value = percent
            doc.zoom_mode = "value"
        return {"zoom_value": doc.zoom_value, "zoom_mode": doc.zoom_mode}

    def get_selection(self, doc):
        return {"type": doc.doc_type, "has_selection": doc.has_selection, "selected_text": doc.selection_text}

    def clear_selection(self, doc):
        if doc.doc_type == "base":
            raise NotImplementedError("clear_selection is not implemented for document type 'base'.")
        doc.has_selection = False
        doc.selection_text = ""

    def lock_document_updates(self, doc):
        doc.lock_count += 1

    def unlock_document_updates(self, doc):
        doc.lock_count -= 1

    # -- document events --
    #
    # Models the real UNOBridge's seq-numbered bounded buffer closely
    # enough to exercise the tools-layer logic (filtering, limit, timeout
    # vs. found), without a real GlobalEventBroadcaster. push_event() is
    # the test helper standing in for "a document event just fired".

    def __init_events__(self):
        # Called explicitly by tests rather than from FakeUnoBridge.__init__
        # so plain undo/view tests above (which never touch events) don't
        # need to know this state exists.
        self._events = []
        self._event_seq = 0

    def push_event(self, event_type, source=None, document_url=None):
        self._event_seq += 1
        self._events.append({
            "seq": self._event_seq, "event_type": event_type,
            "document_url": document_url, "source": source,
        })

    def get_document_events(self, limit=100, event_types=None):
        events = self._events
        if event_types:
            wanted = set(event_types)
            events = [e for e in events if e["event_type"] in wanted]
        return events[-limit:] if limit else []

    def wait_for_document_event(self, event_types, timeout_ms):
        # Fake is synchronous/non-blocking: only ever "finds" an event
        # that was already pushed before the call, at or after whatever
        # seq the test cares about -- real timing/blocking behavior is a
        # live-verification concern, not a unit-test one (this fake can't
        # simulate a concurrent event arriving mid-wait).
        wanted = set(event_types)
        for event in self._events:
            if event["event_type"] in wanted:
                return event
        return None


def _install(active_document=None):
    uno_bridge = FakeUnoBridge(active_document=active_document)
    document_registry = DocumentRegistry(uno_bridge)
    runtime_state = RuntimeState()
    context.install(context.RuntimeContext(
        uno_bridge=uno_bridge, document_registry=document_registry,
        runtime_state=runtime_state, get_tools=lambda: {},
    ))
    return uno_bridge, document_registry, runtime_state


def _handler(name):
    return get_registry()[name]["handler"]


# -- get_undo_state_live --

def test_get_undo_state_live_reports_empty_stack():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("get_undo_state_live")()
    assert result["success"] is True
    assert result["result"] == {"can_undo": False, "can_redo": False, "undo_title": None, "redo_title": None}


def test_get_undo_state_live_reports_available_undo():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.simulate_edit()
    result = _handler("get_undo_state_live")()
    assert result["result"]["can_undo"] is True
    assert result["result"]["undo_title"] == "Simulated Edit"


def test_get_undo_state_live_no_active_document():
    context.reset()
    _install()
    result = _handler("get_undo_state_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_ACTIVE_DOCUMENT"


# -- undo_live / redo_live --

def test_undo_live_applies_and_reports_state():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.simulate_edit()
    result = _handler("undo_live")()
    assert result["success"] is True
    assert result["result"] == {"requested": 1, "applied": 1, "can_undo": False, "can_redo": True}
    assert result["warnings"] == []


def test_undo_live_stops_cleanly_when_stack_exhausted():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.simulate_edit()
    result = _handler("undo_live")(count=5)
    assert result["success"] is True
    assert result["result"]["requested"] == 5
    assert result["result"]["applied"] == 1
    assert any("exhausted" in w for w in result["warnings"])


def test_undo_live_rejects_non_positive_count():
    context.reset()
    _install(active_document=FakeDocument())
    zero = _handler("undo_live")(count=0)
    assert zero["success"] is False
    assert zero["error"]["code"] == "INVALID_PARAMETER"

    negative = _handler("undo_live")(count=-1)
    assert negative["success"] is False
    assert negative["error"]["code"] == "INVALID_PARAMETER"


def test_undo_live_rejects_non_integer_count():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("undo_live")(count="two")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_redo_live_applies_and_stops_cleanly():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.simulate_edit()
    _handler("undo_live")()

    result = _handler("redo_live")(count=3)
    assert result["success"] is True
    assert result["result"]["applied"] == 1
    assert any("exhausted" in w for w in result["warnings"])


# -- begin/end/cancel_undo_context_live --

def test_begin_end_undo_context_live_coalesces_into_one_step():
    context.reset()
    uno_bridge, _, runtime_state = _install(active_document=FakeDocument())

    begin = _handler("begin_undo_context_live")(title="Multi-step edit")
    assert begin["success"] is True
    assert runtime_state.get_undo_context()["title"] == "Multi-step edit"

    uno_bridge.simulate_edit()
    uno_bridge.simulate_edit()  # multiple edits recorded inside the context

    end = _handler("end_undo_context_live")()
    assert end["success"] is True
    assert end["result"] == {"title": "Multi-step edit", "grouped": True}
    assert runtime_state.get_undo_context() is None
    assert uno_bridge._undo_stack == ["Multi-step edit"]  # coalesced into ONE step

    undo = _handler("undo_live")()
    assert undo["result"]["applied"] == 1
    assert uno_bridge._undo_stack == []  # one undo reverses the entire group


def test_end_undo_context_live_with_no_actions_recorded_is_not_grouped():
    context.reset()
    _install(active_document=FakeDocument())
    _handler("begin_undo_context_live")(title="Empty context")
    end = _handler("end_undo_context_live")()
    assert end["success"] is True
    assert end["result"]["grouped"] is False


def test_begin_undo_context_live_rejects_nesting():
    context.reset()
    _, _, runtime_state = _install(active_document=FakeDocument())
    first = _handler("begin_undo_context_live")(title="Outer")
    assert first["success"] is True

    second = _handler("begin_undo_context_live")(title="Inner")
    assert second["success"] is False
    assert second["error"]["code"] == "INVALID_STATE"

    # the original context is untouched by the rejected nested attempt
    assert runtime_state.get_undo_context()["title"] == "Outer"


def test_end_undo_context_live_with_no_open_context():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("end_undo_context_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_STATE"


def test_cancel_undo_context_live_with_no_open_context():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("cancel_undo_context_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_STATE"


def test_cancel_undo_context_live_restores_pre_context_state():
    context.reset()
    uno_bridge, _, runtime_state = _install(active_document=FakeDocument())
    uno_bridge.simulate_edit()  # one pre-existing action, outside the context

    _handler("begin_undo_context_live")(title="Scratch edits")
    uno_bridge.simulate_edit()
    uno_bridge.simulate_edit()
    assert uno_bridge._undo_stack == ["Simulated Edit"]  # not yet committed into the stack

    cancel = _handler("cancel_undo_context_live")()
    assert cancel["success"] is True
    assert cancel["result"]["restored"] is True
    assert cancel["result"]["reverted_count"] == 1  # one coalesced action was pushed, then undone
    assert uno_bridge._undo_stack == ["Simulated Edit"]  # back to the pre-context state
    assert runtime_state.get_undo_context() is None


def test_cancel_undo_context_live_with_no_recorded_actions():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    _handler("begin_undo_context_live")(title="No-op context")

    cancel = _handler("cancel_undo_context_live")()
    assert cancel["success"] is True
    assert cancel["result"]["reverted_count"] == 0
    assert cancel["result"]["restored"] is True
    assert uno_bridge._undo_stack == []


# -- get_session_state_live reports pending_undo_context (core_runtime.py) --

def test_get_session_state_live_reports_pending_undo_context_title():
    context.reset()
    _install(active_document=FakeDocument())
    before = _handler("get_session_state_live")()
    assert before["result"]["pending_undo_context"] is None

    _handler("begin_undo_context_live")(title="In progress")
    during = _handler("get_session_state_live")()
    assert during["result"]["pending_undo_context"]["title"] == "In progress"

    _handler("end_undo_context_live")()
    after = _handler("get_session_state_live")()
    assert after["result"]["pending_undo_context"] is None


def test_get_session_state_live_reports_none_after_cancel():
    context.reset()
    _install(active_document=FakeDocument())
    _handler("begin_undo_context_live")(title="Will be cancelled")
    _handler("cancel_undo_context_live")()
    result = _handler("get_session_state_live")()
    assert result["result"]["pending_undo_context"] is None


# -- get_view_state_live / set_zoom_live --

def test_get_view_state_live_reports_zoom_and_selection():
    context.reset()
    doc = FakeDocument()
    doc.zoom_value = 150
    doc.has_selection = True
    _install(active_document=doc)
    result = _handler("get_view_state_live")()
    assert result["success"] is True
    assert result["result"] == {"type": "writer", "zoom_value": 150, "zoom_mode": "optimal",
                                 "has_selection": True, "current_page_number": 1}


def test_get_view_state_live_reports_writer_current_page_number():
    # New tool addition, 2026-08-22 (Brian's new-tools assignment,
    # priority #6) -- get_view_state_live previously reported no page
    # position at all for Writer, unlike calc's active_sheet /
    # impress's current_page_name.
    context.reset()
    doc = FakeDocument(current_page_number=4)
    _install(active_document=doc)
    result = _handler("get_view_state_live")()
    assert result["success"] is True
    assert result["result"]["current_page_number"] == 4


def test_get_view_state_live_omits_page_number_for_non_writer_docs():
    context.reset()
    _install(active_document=FakeDocument(doc_type="calc"))
    result = _handler("get_view_state_live")()
    assert result["success"] is True
    assert "current_page_number" not in result["result"]


def test_get_view_state_live_no_active_document():
    context.reset()
    _install()
    result = _handler("get_view_state_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_ACTIVE_DOCUMENT"


# -- goto_page_live --

def test_goto_page_live_moves_to_the_requested_page():
    context.reset()
    doc = FakeDocument(current_page_number=1, page_count=5)
    _install(active_document=doc)
    result = _handler("goto_page_live")(page=3)
    assert result["success"] is True
    assert result["result"]["page"] == 3
    assert doc.current_page_number == 3
    # get_view_state_live's current_page_number reflects the move too --
    # same view cursor, not two independently-tracked positions.
    state = _handler("get_view_state_live")()
    assert state["result"]["current_page_number"] == 3


def test_goto_page_live_clamps_past_the_last_real_page_and_warns():
    context.reset()
    doc = FakeDocument(current_page_number=1, page_count=2)
    _install(active_document=doc)
    result = _handler("goto_page_live")(page=99)
    assert result["success"] is True
    assert result["result"]["page"] == 2
    assert result["warnings"] and "99" in result["warnings"][0] and "2" in result["warnings"][0]


def test_goto_page_live_rejects_non_positive_page():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("goto_page_live")(page=0)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_goto_page_live_rejects_non_writer_documents():
    context.reset()
    _install(active_document=FakeDocument(doc_type="calc"))
    result = _handler("goto_page_live")(page=1)
    assert result["success"] is False


def test_set_zoom_live_by_percent():
    context.reset()
    doc = FakeDocument()
    _install(active_document=doc)
    result = _handler("set_zoom_live")(percent=125)
    assert result["success"] is True
    assert result["result"] == {"zoom_value": 125, "zoom_mode": "value"}
    assert doc.zoom_value == 125


def test_set_zoom_live_by_mode():
    context.reset()
    doc = FakeDocument()
    _install(active_document=doc)
    result = _handler("set_zoom_live")(mode="page")
    assert result["success"] is True
    assert result["result"]["zoom_mode"] == "page"


def test_set_zoom_live_requires_percent_or_mode():
    context.reset()
    _install(active_document=FakeDocument())
    result = _handler("set_zoom_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


# -- get_selection_live / clear_selection_live --

def test_get_selection_live_reports_selected_text():
    context.reset()
    doc = FakeDocument()
    doc.has_selection = True
    doc.selection_text = "hello world"
    _install(active_document=doc)
    result = _handler("get_selection_live")()
    assert result["success"] is True
    assert result["result"] == {"type": "writer", "has_selection": True, "selected_text": "hello world"}


def test_clear_selection_live_clears_selection():
    context.reset()
    doc = FakeDocument()
    doc.has_selection = True
    doc.selection_text = "hello world"
    _install(active_document=doc)
    result = _handler("clear_selection_live")()
    assert result["success"] is True
    assert result["result"] == {"cleared": True}
    assert doc.has_selection is False
    assert doc.selection_text == ""


def test_clear_selection_live_unsupported_document_type():
    context.reset()
    _install(active_document=FakeDocument(doc_type="base"))
    result = _handler("clear_selection_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "UNSUPPORTED_CAPABILITY"


# -- lock_document_updates_live / unlock_document_updates_live --

def test_lock_then_unlock_document_updates_live():
    context.reset()
    doc = FakeDocument()
    _install(active_document=doc)

    locked = _handler("lock_document_updates_live")()
    assert locked["success"] is True
    assert doc.lock_count == 1

    unlocked = _handler("unlock_document_updates_live")()
    assert unlocked["success"] is True
    assert doc.lock_count == 0


def test_lock_document_updates_live_no_active_document():
    context.reset()
    _install()
    result = _handler("lock_document_updates_live")()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_ACTIVE_DOCUMENT"


# -- get_document_events_live / wait_for_document_event_live --

def test_get_document_events_live_reports_empty_buffer():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    result = _handler("get_document_events_live")()
    assert result["success"] is True
    assert result["result"] == {"events": [], "count": 0}


def test_get_document_events_live_reports_captured_events():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    uno_bridge.push_event("OnLoad")
    uno_bridge.push_event("OnSave")
    result = _handler("get_document_events_live")()
    assert result["success"] is True
    assert result["result"]["count"] == 2
    assert [e["event_type"] for e in result["result"]["events"]] == ["OnLoad", "OnSave"]
    assert [e["seq"] for e in result["result"]["events"]] == [1, 2]


def test_get_document_events_live_filters_by_event_types():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    uno_bridge.push_event("OnLoad")
    uno_bridge.push_event("OnSave")
    uno_bridge.push_event("OnSave")
    result = _handler("get_document_events_live")(event_types=["OnSave"])
    assert result["result"]["count"] == 2
    assert all(e["event_type"] == "OnSave" for e in result["result"]["events"])


def test_get_document_events_live_respects_limit():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    for _ in range(5):
        uno_bridge.push_event("OnModifyChanged")
    result = _handler("get_document_events_live")(limit=2)
    assert result["result"]["count"] == 2
    # The most recent 2, not the oldest 2.
    assert [e["seq"] for e in result["result"]["events"]] == [4, 5]


def test_get_document_events_live_rejects_non_positive_limit():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    result = _handler("get_document_events_live")(limit=0)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_get_document_events_live_rejects_malformed_event_types():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    result = _handler("get_document_events_live")(event_types="OnSave")
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_get_document_events_live_correlates_registered_document_id():
    context.reset()
    uno_bridge, document_registry, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    other_doc = FakeDocument(title="Other")
    document_id = document_registry.register_document(other_doc)
    uno_bridge.push_event("OnSave", source=other_doc, document_url="file:///other.odt")
    result = _handler("get_document_events_live")()
    event = result["result"]["events"][0]
    assert event["document_id"] == document_id
    assert event["document_url"] == "file:///other.odt"


def test_get_document_events_live_reports_null_document_id_for_unregistered_source():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    # A document opened directly in the LibreOffice GUI, never registered
    # through open_document_live/create_document_live.
    unregistered_doc = FakeDocument(title="Human-opened")
    uno_bridge.push_event("OnLoad", source=unregistered_doc)
    result = _handler("get_document_events_live")()
    assert result["result"]["events"][0]["document_id"] is None


def test_wait_for_document_event_live_finds_matching_event():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    uno_bridge.push_event("OnSave")
    result = _handler("wait_for_document_event_live")(event_types=["OnSave"], timeout_ms=1000)
    assert result["success"] is True
    assert result["result"]["timed_out"] is False
    assert result["result"]["event"]["event_type"] == "OnSave"


def test_wait_for_document_event_live_times_out_cleanly():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    result = _handler("wait_for_document_event_live")(event_types=["OnSave"], timeout_ms=10)
    assert result["success"] is True
    assert result["result"] == {"event": None, "timed_out": True}


def test_wait_for_document_event_live_requires_event_types():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    result = _handler("wait_for_document_event_live")(event_types=None, timeout_ms=1000)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_wait_for_document_event_live_rejects_negative_timeout():
    context.reset()
    uno_bridge, _, _ = _install(active_document=FakeDocument())
    uno_bridge.__init_events__()
    result = _handler("wait_for_document_event_live")(event_types=["OnSave"], timeout_ms=-1)
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_PARAMETER"


if __name__ == "__main__":
    tests = [
        test_get_undo_state_live_reports_empty_stack,
        test_get_undo_state_live_reports_available_undo,
        test_get_undo_state_live_no_active_document,
        test_undo_live_applies_and_reports_state,
        test_undo_live_stops_cleanly_when_stack_exhausted,
        test_undo_live_rejects_non_positive_count,
        test_undo_live_rejects_non_integer_count,
        test_redo_live_applies_and_stops_cleanly,
        test_begin_end_undo_context_live_coalesces_into_one_step,
        test_end_undo_context_live_with_no_actions_recorded_is_not_grouped,
        test_begin_undo_context_live_rejects_nesting,
        test_end_undo_context_live_with_no_open_context,
        test_cancel_undo_context_live_with_no_open_context,
        test_cancel_undo_context_live_restores_pre_context_state,
        test_cancel_undo_context_live_with_no_recorded_actions,
        test_get_session_state_live_reports_pending_undo_context_title,
        test_get_session_state_live_reports_none_after_cancel,
        test_get_view_state_live_reports_zoom_and_selection,
        test_get_view_state_live_reports_writer_current_page_number,
        test_get_view_state_live_omits_page_number_for_non_writer_docs,
        test_get_view_state_live_no_active_document,
        test_goto_page_live_moves_to_the_requested_page,
        test_goto_page_live_clamps_past_the_last_real_page_and_warns,
        test_goto_page_live_rejects_non_positive_page,
        test_goto_page_live_rejects_non_writer_documents,
        test_set_zoom_live_by_percent,
        test_set_zoom_live_by_mode,
        test_set_zoom_live_requires_percent_or_mode,
        test_get_selection_live_reports_selected_text,
        test_clear_selection_live_clears_selection,
        test_clear_selection_live_unsupported_document_type,
        test_lock_then_unlock_document_updates_live,
        test_lock_document_updates_live_no_active_document,
        test_get_document_events_live_reports_empty_buffer,
        test_get_document_events_live_reports_captured_events,
        test_get_document_events_live_filters_by_event_types,
        test_get_document_events_live_respects_limit,
        test_get_document_events_live_rejects_non_positive_limit,
        test_get_document_events_live_rejects_malformed_event_types,
        test_get_document_events_live_correlates_registered_document_id,
        test_get_document_events_live_reports_null_document_id_for_unregistered_source,
        test_wait_for_document_event_live_finds_matching_event,
        test_wait_for_document_event_live_times_out_cleanly,
        test_wait_for_document_event_live_requires_event_types,
        test_wait_for_document_event_live_rejects_negative_timeout,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    context.reset()
    print(f"\nAll {len(tests)} undo_view_selection tests passed.")
