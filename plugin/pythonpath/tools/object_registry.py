"""
Stable non-document object handle registry (shape_id/chart_id/table_id).

Mandated item #2 of Buddy's four-item order blocking further Phase C/D
real implementation: "Design stable non-document object handles before
drawing/charts/Impress go real. Sheets, slides, shapes, tables and charts
need identity semantics before dozens of tools start passing names/
indexes around." Full design rationale, including which object
categories this module applies to (and which deliberately don't use it
at all), lives in docs/OBJECT_HANDLE_DESIGN.md -- read that first.

Short version: this is the same mechanism DocumentRegistry already uses
for document_id (an in-memory id<->UNO-object map, keyed by the object
itself so PyUNO's re-minted-proxy-per-fetch behavior can't spoof a
duplicate registration -- see documents.py's DocumentRegistry docstring
for the live-verified bug that precedent fixes), generalized so any
object category can reuse it. It intentionally does NOT reimplement
DocumentRegistry's get_active_document() fallback -- there's no "active
shape" concept in the spec, every lookup here is by handle only.

Scoped per document, not global: see DocumentRegistry.get_object_registry()
in documents.py, which lazily creates one ObjectRegistry per document_id
and drops it in unregister_document() -- so an object handle's lifetime
is naturally bounded by its owning document's lifetime without needing
per-shape UNO dispose listeners (the same eviction gap DocumentRegistry
itself still has open for out-of-band document closes; this module
doesn't attempt to solve that for objects either -- a stale handle simply
surfaces as a normal, mapped error the next time something tries to use
it, same as a stale document_id does today).
"""

import threading
import uuid
from typing import Any, Dict, Optional


class ObjectNotFoundError(LookupError):
    """object_id was supplied but is unknown or has since been unregistered."""


class ObjectRegistry:
    """Resolves opaque handles (shape_id, chart_id, table_id, ...) to live UNO objects.

    One instance is meant to be scoped to a single document (see
    DocumentRegistry.get_object_registry()), not shared globally -- see
    this module's docstring and docs/OBJECT_HANDLE_DESIGN.md for why.
    Reused as-is for every "no natural unique persistent name" object
    category (Draw/Impress/Writer shapes; Writer/Impress embedded charts
    not addressable through Calc's dedicated XChartsSupplier). Object
    categories that already have a UNO-guaranteed-unique Name (Calc
    sheets, Writer tables, Calc's own named chart collection) should
    resolve directly against that live UNO container instead of going
    through this registry at all -- see the design doc for which is
    which.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._objects: Dict[str, Any] = {}
        # Same object-identity-keyed reverse lookup as DocumentRegistry,
        # for the same reason: re-registering an already-known live UNO
        # object (e.g. re-enumerating a draw page's shapes on a later
        # list_shapes_live call) must return the existing handle, not
        # mint a spurious duplicate, even though PyUNO may hand back a
        # freshly-minted Python-side proxy object each time.
        self._ids_by_identity: Dict[Any, str] = {}

    def register_object(self, uno_object: Any) -> str:
        """Assign and return a stable opaque id for a UNO object.

        Calling this again with an already-registered object (by
        UNO-identity, via __eq__/__hash__, not id()) returns its existing
        id rather than minting a new one -- so a discovery tool
        (list_shapes_live, etc.) can freely re-enumerate and re-register
        without handles churning between calls.
        """
        with self._lock:
            existing = self._ids_by_identity.get(uno_object)
            if existing is not None:
                return existing
            object_id = uuid.uuid4().hex
            self._objects[object_id] = uno_object
            self._ids_by_identity[uno_object] = object_id
        return object_id

    def resolve_object(self, object_id: str) -> Any:
        """Return the UNO object for object_id.

        Raises:
            ObjectNotFoundError: object_id is unknown or has since been
                unregistered -- callers should map this to the
                OBJECT_NOT_FOUND error code, same as DocumentNotFoundError.
        """
        with self._lock:
            uno_object = self._objects.get(object_id)
        if uno_object is None:
            raise ObjectNotFoundError(object_id)
        return uno_object

    def unregister_object(self, object_id: str) -> None:
        """Drop an object_id from the registry (e.g. after a delete_shape_live).

        Unknown ids are ignored (idempotent), matching
        DocumentRegistry.unregister_document()'s contract.
        """
        with self._lock:
            uno_object = self._objects.pop(object_id, None)
            if uno_object is not None:
                self._ids_by_identity.pop(uno_object, None)

    def list_object_ids(self) -> list:
        """Return every currently-registered object_id, newest-registration order not guaranteed.

        Deliberately doesn't try to introspect/describe each object the
        way DocumentRegistry.list_documents() does -- what a "shape" or
        "chart" summary should contain is a per-tool-module concern
        (get_shape_live's own response shape, etc.), not this registry's.
        """
        with self._lock:
            return list(self._objects.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._objects)
