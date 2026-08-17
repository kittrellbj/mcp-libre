"""
Stable document handle registry -- stub.

The spec (section 2, "Common MCP conventions") requires stable session IDs
for documents, sheets/slides/pages, tables, shapes, charts, comments,
fields, controls, pivots, and database connections. Today
uno_bridge.UNOBridge has no such concept: every method takes an optional
`doc` and falls back to desktop.getCurrentComponent() (see
plugin/pythonpath/uno_bridge.py, UNOBridge.get_active_document). This module
scaffolds the registry shape Phase A+ tool stubs are written against.

A senior engineer needs to:
  1. Implement the actual id<->UNO-object mapping. A uuid4 hex is a
     reasonable starting scheme; ids must stay stable across calls within a
     session.
  2. Hook document close/dispose events (XEventListener on the Desktop, or
     an XCloseListener/XComponent.dispose listener on each registered
     document) to evict stale entries -- a document can be closed by the
     user outside of any MCP call, and a stale handle must resolve to
     OBJECT_NOT_FOUND, not a UNO exception from a disposed proxy.
  3. Decide whether ids are scoped to the extension's process lifetime only
     (simplest, matches "stable" in the spec) or need to persist across
     LibreOffice restarts (spec does not require this).
  4. Extend the same pattern for the finer-grained handles the spec also
     wants (shape_id, chart_id, table_id, comment_id, etc.) -- those likely
     want their own per-document registries rather than reusing this class
     directly; this module only covers the top-level document_id.

Every method below raises NotImplementedError; the signatures and
docstrings are the contract new tool stubs are written against, so callers
in core_runtime.py / document_lifecycle.py / etc. can already be written
correctly even though the registry itself isn't implemented yet.
"""

from typing import Any, Dict, List, Optional


class DocumentRegistry:
    """Resolves MCP document_id values to live UNO document components."""

    def __init__(self, uno_bridge: Any) -> None:
        """Args: uno_bridge -- an initialized uno_bridge.UNOBridge instance."""
        self.uno_bridge = uno_bridge

    def register_document(self, uno_document: Any) -> str:
        """Assign and return a new stable document_id for a UNO document object.

        Should be called from any path that creates or opens a document
        (create_document_live, open_document_live, open_from_template_live)
        before the id is returned to the caller.
        """
        raise NotImplementedError("DocumentRegistry.register_document is a Phase A scaffold stub")

    def resolve_document(self, document_id: Optional[str] = None) -> Any:
        """Return the UNO document for document_id, or the active document when omitted.

        Per spec section 2: "Document selectors default to the active
        document only when unambiguous." Implementations should raise a
        lookup error the caller maps to NO_ACTIVE_DOCUMENT (document_id
        omitted and nothing active) or OBJECT_NOT_FOUND (document_id
        supplied but unknown or since closed).
        """
        raise NotImplementedError("DocumentRegistry.resolve_document is a Phase A scaffold stub")

    def unregister_document(self, document_id: str) -> None:
        """Drop a document_id from the registry, e.g. from close_document_live
        or the eventual close/dispose listener."""
        raise NotImplementedError("DocumentRegistry.unregister_document is a Phase A scaffold stub")

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return [{document_id, type, title, modified}, ...] for every registered document.

        Backs both the existing list_open_documents compatibility tool and
        the new get_active_document_live / activate_document_live stubs.
        """
        raise NotImplementedError("DocumentRegistry.list_documents is a Phase A scaffold stub")
