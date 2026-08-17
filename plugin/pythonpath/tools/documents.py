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
  2. Per-object handles below the document level (shape_id, chart_id,
     table_id, comment_id, etc.) -- those likely want their own
     per-document registries rather than reusing this class directly;
     this module only covers the top-level document_id.
  3. Wiring this into mcp_server.py's existing 32 tools. It is currently
     only consumed by the Phase A+ stub tools in this package; the
     original tools keep resolving "the active document" directly via
     uno_bridge, unchanged, per spec section 6 (compatibility).
"""

import threading
import uuid
from typing import Any, Callable, Dict, List, Optional


class DocumentNotFoundError(LookupError):
    """document_id was supplied but is unknown or has since been unregistered."""


class NoActiveDocumentError(LookupError):
    """document_id was omitted and no document is currently active."""


class DocumentRegistry:
    """Resolves MCP document_id values to live UNO document components."""

    def __init__(self, uno_bridge: Any) -> None:
        """Args: uno_bridge -- an initialized uno_bridge.UNOBridge instance."""
        self.uno_bridge = uno_bridge
        self._lock = threading.Lock()
        self._documents: Dict[str, Any] = {}
        # Reverse lookup so re-registering the same live object returns its
        # existing id instead of minting a duplicate. Keyed by id(obj)
        # (identity), which is only safe while the object is still
        # referenced by self._documents -- fine here since that's the only
        # place we ever drop a reference (see unregister_document).
        self._ids_by_identity: Dict[int, str] = {}

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
        identity = id(uno_document)
        with self._lock:
            existing = self._ids_by_identity.get(identity)
            if existing is not None:
                return existing
            document_id = uuid.uuid4().hex
            self._documents[document_id] = uno_document
            self._ids_by_identity[identity] = document_id
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
        """
        with self._lock:
            document = self._documents.pop(document_id, None)
            if document is not None:
                self._ids_by_identity.pop(id(document), None)

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return [{document_id, type, title, modified}, ...] for every registered document.

        Backs both the existing list_open_documents compatibility tool and
        the new get_active_document_live / activate_document_live stubs.
        Documents that raise while being introspected (e.g. a UNO proxy
        left dangling by an out-of-band close, until dispose-listener
        eviction lands) are reported with type/title/modified left None
        rather than dropped, so a caller can still see the id exists.
        """
        with self._lock:
            items = list(self._documents.items())

        results = []
        for document_id, document in items:
            info: Dict[str, Any] = {}
            try:
                info = self.uno_bridge.get_document_info(document)
            except Exception:
                info = {}
            results.append({
                "document_id": document_id,
                "type": info.get("type"),
                "title": info.get("title"),
                "modified": info.get("modified"),
            })
        return results
