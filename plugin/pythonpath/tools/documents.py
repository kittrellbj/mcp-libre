"""
Stable document handle registry.

The spec (section 2, "Common MCP conventions") requires stable session IDs
for documents, sheets/slides/pages, tables, shapes, charts, comments,
fields, controls, pivots, and database connections. Before this module,
uno_bridge.UNOBridge had no such concept: every method takes an optional
`doc` and falls back to desktop.getCurrentComponent() (see
plugin/pythonpath/uno_bridge.py, UNOBridge.get_active_document).

DocumentRegistry closes that gap for the top-level document_id case: an
in-memory, thread-safe id<->UNO-object map, scoped to the extension's
process lifetime (ids do not need to survive a LibreOffice restart -- the
spec only requires "stable", not "durable"). It does not require a live
UNO context itself; it only stores whatever object register_document() is
given, so it is unit-testable with plain fake objects (see
tests/test_document_registry.py).

Left for a senior engineer, because it needs validation against a live
LibreOffice/UNO context this scaffolding pass can't run:
  1. Dispose-listener eviction. A document can be closed by the user
     outside of any MCP call; right now a stale document_id is only
     detected reactively (resolve_document degrades to a wrapped UNO
     exception rather than a clean DocumentNotFoundError). Wire an
     XEventListener on the Desktop (com.sun.star.document.EventObject
     "OnUnload"/"OnViewClosed") or an XCloseListener/XComponent dispose
     listener per registered document, and call unregister_document() from
     it. register_document() takes an optional on_dispose hook for this
     purpose but nothing currently populates it.
  2. Wiring this into mcp_server.py's existing 32 tools. It is currently
     only consumed by the Phase A+ stub tools in this package; the
     original tools keep resolving "the active document" directly via
     uno_bridge, unchanged, per spec section 6 (compatibility).

Per-object handles below the document level (shape_id, chart_id,
table_id, etc.) are get_object_registry() below, backed by
object_registry.ObjectRegistry -- see docs/OBJECT_HANDLE_DESIGN.md for
the full design (mandated item #2) and object_registry.py's own
docstring for the mechanism. Each document_id gets its own ObjectRegistry
instance, created lazily on first use and dropped in
unregister_document(), so an object handle's lifetime is naturally
bounded by its owning document's -- without needing a per-shape UNO
dispose listener on top of the still-open document-level gap in item 1
above.
"""

import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

from . import object_registry


class DocumentNotFoundError(LookupError):
    """document_id was supplied but is unknown or has since been unregistered."""


class NoActiveDocumentError(LookupError):
    """document_id was omitted and no document is currently active."""


class WrongDocumentTypeError(Exception):
    """A document resolved fine, but its type doesn't match what the tool
    requires (e.g. a Writer-only tool called against a Calc document).

    Not raised from this module -- raised by uno_bridge.UNOBridge's
    _require_writer()/_require_calc()/_require_draw()/_require_impress()
    (and a few narrower gates, e.g. charts.py's Calc-native-chart check).
    Defined here rather than in uno_bridge.py itself so that document_
    lifecycle.py's _map_exception_to_code() (and any other tools/*.py
    module) can isinstance()-check it without importing uno_bridge.py,
    which pulls in the real `uno`/`unohelper` PyUNO modules that are only
    available inside a running LibreOffice process -- importing it from
    a tools/*.py module would break the entire fakes-based test suite,
    which runs in plain CPython outside LibreOffice (confirmed live: a
    module-level `import uno_bridge` from document_lifecycle.py raised
    `ModuleNotFoundError: No module named 'uno'` under the test venv).

    Hardening-pass finding (#31 error-code audit): every one of those
    document-type gates previously raised plain NotImplementedError,
    which _map_exception_to_code() maps to UNSUPPORTED_CAPABILITY -- the
    same code a genuinely-not-implemented stub option returns (e.g.
    insert_cross_reference's unknown reference_type). That conflated two
    different situations under one code and left ERROR_CODES' own
    WRONG_DOCUMENT_TYPE entry dead code, never reachable from any of the
    ~90 real tools despite being the single most common error path
    across the whole catalog -- confirmed by grep, and even documented as
    a known, deliberate shortcut in this project's own docs/
    MCP_TOOLING_SCAFFOLD_PLAN.md (the styles.py pass called it out
    explicitly as "WRONG_DOCUMENT_TYPE"-shaped UNSUPPORTED_CAPABILITY").
    This dedicated type lets _map_exception_to_code() tell the two
    situations apart."""


class DocumentRegistry:
    """Resolves MCP document_id values to live UNO document components."""

    def __init__(self, uno_bridge: Any) -> None:
        """Args: uno_bridge -- an initialized uno_bridge.UNOBridge instance."""
        self.uno_bridge = uno_bridge
        self._lock = threading.Lock()
        self._documents: Dict[str, Any] = {}
        # Reverse lookup so re-registering the same live object returns its
        # existing id instead of minting a duplicate. Keyed by the document
        # object itself, NOT id(obj) -- live-verified that PyUNO mints a
        # fresh Python-side proxy object (different id()) each time the
        # same remote document is fetched (e.g. two separate
        # desktop.getCurrentComponent() calls), which made id()-keying
        # silently fail to dedup real documents. PyUNO proxies implement
        # __eq__/__hash__ consistently for the same underlying UNO object,
        # so using the object as the key works correctly for both real UNO
        # documents and the plain-object fakes the test suite uses (whose
        # default __eq__/__hash__ is identity-based already, so this is a
        # no-op change for those).
        self._ids_by_identity: Dict[Any, str] = {}
        # One ObjectRegistry per document_id, created lazily -- see
        # get_object_registry() and this module's docstring.
        self._object_registries: Dict[str, object_registry.ObjectRegistry] = {}

    def register_document(self, uno_document: Any, on_dispose: Optional[Callable[[str], None]] = None) -> str:
        """Assign and return a stable document_id for a UNO document object.

        Should be called from any path that creates or opens a document
        (create_document_live, open_document_live, open_from_template_live)
        before the id is returned to the caller. Calling this again with an
        already-registered object returns its existing id rather than
        minting a new one.

        Args:
            uno_document: The live UNO document component.
            on_dispose: Reserved for the dispose-listener wiring described
                in this module's docstring; unused today.
        """
        with self._lock:
            existing = self._ids_by_identity.get(uno_document)
            if existing is not None:
                return existing
            document_id = uuid.uuid4().hex
            self._documents[document_id] = uno_document
            self._ids_by_identity[uno_document] = document_id
        return document_id

    def resolve_document(self, document_id: Optional[str] = None) -> Any:
        """Return the UNO document for document_id, or the active document when omitted.

        Per spec section 2: "Document selectors default to the active
        document only when unambiguous."

        Raises:
            DocumentNotFoundError: document_id was supplied but is unknown
                or has since been unregistered -- callers should map this
                to the OBJECT_NOT_FOUND error code.
            NoActiveDocumentError: document_id was omitted and
                uno_bridge.get_active_document() returned nothing -- callers
                should map this to the NO_ACTIVE_DOCUMENT error code.
        """
        if document_id is not None:
            with self._lock:
                document = self._documents.get(document_id)
            if document is None:
                raise DocumentNotFoundError(document_id)
            return document

        active = self.uno_bridge.get_active_document()
        if active is None:
            raise NoActiveDocumentError()
        return active

    def unregister_document(self, document_id: str) -> None:
        """Drop a document_id from the registry.

        Called from close_document_live today; will also be the target of
        the dispose-listener eviction described in this module's docstring
        once that's implemented. Unknown ids are ignored (idempotent).
        Also drops document_id's ObjectRegistry (if one was ever created
        via get_object_registry()), so every shape_id/chart_id/table_id
        handle minted for this document becomes unresolvable at the same
        moment the document itself does -- deliberate: a handle that
        outlives its document is never meaningful.
        """
        with self._lock:
            document = self._documents.pop(document_id, None)
            if document is not None:
                self._ids_by_identity.pop(document, None)
            self._object_registries.pop(document_id, None)

    def get_object_registry(self, document_id: str) -> object_registry.ObjectRegistry:
        """Return the ObjectRegistry scoped to document_id, creating it on first use.

        See object_registry.py and docs/OBJECT_HANDLE_DESIGN.md for what
        this is for (mandated item #2: shape_id/chart_id/table_id handle
        semantics). Does not validate that document_id is currently
        registered -- callers resolve the document itself first (via
        resolve_document()) for that check; this just needs a
        document_id string to key the nested registry by, and creating an
        ObjectRegistry for a document_id that later turns out to be
        invalid is harmless (nothing will ever look it up without first
        resolving the document, and it gets garbage collected with this
        DocumentRegistry regardless).
        """
        with self._lock:
            registry = self._object_registries.get(document_id)
            if registry is None:
                registry = object_registry.ObjectRegistry()
                self._object_registries[document_id] = registry
            return registry

    def replace_document(self, document_id: str, new_document: Any) -> None:
        """Re-point an existing document_id at a new UNO object.

        Used by reload_document_live: reloading a document closes the old
        UNO component and loads a new one with a different object identity,
        but the caller should be able to keep using the same document_id
        afterward rather than getting a new one.

        Raises:
            DocumentNotFoundError: document_id is not currently registered.
        """
        with self._lock:
            if document_id not in self._documents:
                raise DocumentNotFoundError(document_id)
            old_document = self._documents[document_id]
            self._ids_by_identity.pop(old_document, None)
            self._documents[document_id] = new_document
            self._ids_by_identity[new_document] = document_id

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return [{document_id, type, title, modified, introspection_error}, ...]
        for every registered document.

        Backs both the existing list_open_documents compatibility tool and
        the new get_active_document_live / activate_document_live stubs.
        Documents that raise while being introspected (e.g. a UNO proxy
        left dangling by an out-of-band close, until dispose-listener
        eviction lands) are reported with type/title/modified left None
        rather than dropped, so a caller can still see the id exists.
        introspection_error carries "{ExceptionType}: {message}" for that
        case so a caller (or a human reading a bug report) can tell a
        legitimately-dangling proxy apart from a real bug in
        get_document_info() -- both used to produce the exact same
        all-None result. introspection_error is None on the success path.
        """
        with self._lock:
            items = list(self._documents.items())

        results = []
        for document_id, document in items:
            info: Dict[str, Any] = {}
            introspection_error = None
            try:
                info = self.uno_bridge.get_document_info(document)
            except Exception as e:
                info = {}
                # Surface what actually went wrong instead of silently
                # blanking the fields -- a dangling proxy from an
                # out-of-band close (the documented case) and a real bug
                # in get_document_info() both land here and previously
                # produced the exact same all-None result, indistinguishable
                # to a caller.
                introspection_error = f"{type(e).__name__}: {e}"
            results.append({
                "document_id": document_id,
                "type": info.get("type"),
                "title": info.get("title"),
                "modified": info.get("modified"),
                "introspection_error": introspection_error,
            })
        return results
