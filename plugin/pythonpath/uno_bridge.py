"""
LibreOffice MCP Extension - UNO Bridge Module

This module provides a bridge between MCP operations and LibreOffice UNO API,
enabling direct manipulation of LibreOffice documents.
"""

import builtins
import uno
import unohelper
from com.sun.star.beans import NamedValue, PropertyValue
from com.sun.star.presentation import EffectNodeType
from com.sun.star.sheet import CellFlags
from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK
from com.sun.star.util import NumberFormat
from typing import Any, Optional, Dict, List
import collections
import logging
import os
import re
import threading
import time
import traceback

from uno_datetime import uno_datetime_to_iso, uno_temporal_value_to_plain
from tools.documents import WrongDocumentTypeError

# Optional imports - these may not be available in all configurations
try:
    from com.sun.star.text import XTextDocument
except ImportError:
    XTextDocument = None

try:
    from com.sun.star.sheet import XSpreadsheetDocument
except ImportError:
    XSpreadsheetDocument = None

try:
    from com.sun.star.presentation import XPresentationDocument
except ImportError:
    XPresentationDocument = None

try:
    from com.sun.star.document import XDocumentEventListener
except ImportError:
    XDocumentEventListener = None

try:
    from com.sun.star.awt import XActionListener
except ImportError:
    XActionListener = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_instance(obj, cls):
    """Safe isinstance check that handles None class types"""
    if cls is None:
        return False
    return isinstance(obj, cls)


# Bounded so a long-running session's document-event capture can't grow
# without limit -- get_document_events_live/wait_for_document_event_live
# only ever need recent history, per docs/MCP_TOOLING_SCAFFOLD_PLAN.md's
# design note for this pair. Each entry carries a monotonically
# increasing `seq` (not a raw deque index/length) specifically so
# wait_for_document_event's "since" bookkeeping doesn't silently break
# once eviction starts once maxlen is hit.
_DOCUMENT_EVENT_BUFFER_MAXLEN = 500

# Per docs/EVENT_WAIT_CONCURRENCY_DECISION.md: wait_for_document_event()
# holds ai_interface.py's process-wide _UNO_EXECUTION_LOCK for its full
# wait duration (that lock wraps the entire tool-execution sequence, not
# just mutations -- see the comment above its definition), so an
# uncapped wait starves any OTHER concurrent tool call queued behind it
# for up to the full requested timeout_ms. Clamped instead of carving an
# exception into that lock (disproportionate risk to a correctness-
# critical, already-hardened primitive for one P3 tool -- see the
# decision doc's alternatives section).
#
# 500ms, derived from measurement, not guessed: edit-latency-probe-
# windows.py ran 100 real HTTP round trips of append_paragraph_live/
# insert_heading_live (the typeset-run's dominant call shape) against a
# real headless LibreOffice instance -- min 5.0ms, median 29.1ms, p95
# 44.8ms, max 62.7ms, each already including its own full
# _UNO_EXECUTION_LOCK hold. 500ms gives roughly 8x headroom over the
# measured max for heavier, unmeasured call shapes this pass didn't
# probe (image/table inserts, saves) while keeping the worst case a
# single wait call can cost a queued OTHER call an order of magnitude
# below the original 2000ms placeholder.
#
# IMPORTANT, live-verified 2026-08-21 (event-wait-concurrency-probe-
# windows.py, both directions): this cap does NOT restore the tool's
# advertised primary use case ("one agent edits, same agent waits"). A
# same-HTTP-path edit and a wait call fully serialize on this one lock --
# the edit can only run in the gap between one wait call ending and the
# next starting, and by the time it completes (firing its event
# synchronously, still holding the lock) that event is already behind
# the NEXT wait call's fresh entry-time snapshot (`snapshot_seq =
# self._event_seq`) -- confirmed the event genuinely fires and is
# captured (present in the buffer), just never seen as "new" by any
# poll, across 8 attempts / 4s, twice independently. This is a property
# of the cap being any positive size, not of 500ms specifically -- a
# 1ms or 100000ms cap would fail identically. The negative control (an
# edit from OUTSIDE this lock entirely -- a separate raw UNO connection,
# same mechanism as a human GUI edit -- fired genuinely concurrently
# with an active wait call) IS reliably observed, no regression from
# pre-fix behavior. See docs/HARDENING_PLAN.md's Phase 5 note for the
# full evidence and the open question this raises for Morgan.
_MAX_WAIT_LOCK_HOLD_MS = 500


if XDocumentEventListener is not None:
    class _DocumentEventCapture(unohelper.Base, XDocumentEventListener):
        """Registered once, process-wide, against
        com.sun.star.frame.GlobalEventBroadcaster (see
        UNOBridge._ensure_document_event_capture). Kept deliberately
        trivial -- append to the owning bridge's buffer and notify,
        nothing else -- so the callback never risks stalling
        LibreOffice's own event-dispatch thread with a UNO call back
        out."""

        def __init__(self, bridge: "UNOBridge") -> None:
            self._bridge = bridge

        def documentEventOccured(self, event: Any) -> None:  # noqa: N802 --
            # XDocumentEventListener's own interface spells this without
            # the second 'r' ("Occured", not "Occurred"); matching the
            # real UNO method name exactly, not a typo to fix.
            self._bridge._record_document_event(event)

        def disposing(self, event: Any) -> None:
            pass
else:
    _DocumentEventCapture = None


class UNOBridge:
    """Bridge between MCP operations and LibreOffice UNO API"""

    def __init__(self):
        """Initialize the UNO bridge"""
        try:
            self.ctx = uno.getComponentContext()
            self.smgr = self.ctx.ServiceManager
            self.desktop = self.smgr.createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx)
            # Document-event capture state (get_document_events_live/
            # wait_for_document_event_live) -- see
            # _ensure_document_event_capture()/_record_document_event()
            # below. Lazily registered on first use, not here, so
            # constructing a UNOBridge never depends on
            # GlobalEventBroadcaster being reachable.
            self._event_buffer = collections.deque(maxlen=_DOCUMENT_EVENT_BUFFER_MAXLEN)
            self._event_lock = threading.Lock()
            self._event_condition = threading.Condition(self._event_lock)
            self._event_seq = 0
            self._event_listener = None
            logger.info("UNO Bridge initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize UNO Bridge: {e}")
            raise
    
    def get_application_version(self) -> Dict[str, Any]:
        """
        Return the running LibreOffice application's version info via UNO
        configuration, not the extension's own version.

        Reads /org.openoffice.Setup/Product from the UNO configuration
        provider -- the standard way an extension queries "what LibreOffice
        am I running inside", independent of any document being open.

        Returns:
            {"success": True, "name": ..., "version": ..., "version_about_box": ...}
            or {"success": False, "error": ...} if the configuration query fails.
        """
        try:
            provider = self.smgr.createInstanceWithContext(
                "com.sun.star.configuration.ConfigurationProvider", self.ctx)

            node_path = PropertyValue()
            node_path.Name = "nodepath"
            node_path.Value = "/org.openoffice.Setup/Product"

            access = provider.createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationAccess", (node_path,))

            return {
                "success": True,
                "name": access.getByName("ooName"),
                "version": access.getByName("ooSetupVersion"),
                "version_about_box": access.getByName("ooSetupVersionAboutBox"),
            }
        except Exception as e:
            logger.error(f"Failed to read application version: {e}")
            return {"success": False, "error": str(e)}

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return which optional UNO interfaces this bridge resolved at import
        time, and which document types create_document()/the doc-type
        detection in _get_document_type() actually support.

        This reflects real state (the module-level guarded imports at the
        top of this file succeeding or falling back to None), not a
        hardcoded claim -- on a LibreOffice build/platform where one of
        these interfaces is unavailable, the corresponding flag is False.
        """
        return {
            "supported_document_types": ["writer", "calc", "impress", "draw"],
            "optional_uno_interfaces": {
                "XTextDocument": XTextDocument is not None,
                "XSpreadsheetDocument": XSpreadsheetDocument is not None,
                "XPresentationDocument": XPresentationDocument is not None,
                "XDocumentEventListener": XDocumentEventListener is not None,
                "XActionListener": XActionListener is not None,
            },
        }

    def create_document(self, doc_type: str = "writer") -> Any:
        """
        Create new document using UNO API

        Args:
            doc_type: Type of document ('writer', 'calc', 'impress', 'draw')

        Returns:
            Document object

        BUG #2 fix (live-verified): loadComponentFromURL() creating a new
        top-level frame does NOT make desktop.getCurrentComponent() see it
        in this headless server -- confirmed directly: a fresh
        private:factory/swriter load left getCurrentComponent() at None
        (or a prior document) every time, with no window manager present
        to fire the focus/activate event an interactive session gets for
        free. That's the mechanism behind "session gets permanently stuck
        after the last open document is closed" -- create_document_live
        reported success but get_active_document_live still saw
        NO_ACTIVE_DOCUMENT. Fixed by explicitly activating the new
        document's own frame (the same activate_document() helper
        activate_document_live already uses) before returning it, so the
        new document is unconditionally the active one regardless of
        whatever had focus before.
        """
        try:
            url_map = {
                "writer": "private:factory/swriter",
                "calc": "private:factory/scalc",
                "impress": "private:factory/simpress",
                "draw": "private:factory/sdraw"
            }

            url = url_map.get(doc_type, "private:factory/swriter")
            doc = self.desktop.loadComponentFromURL(url, "_blank", 0, ())
            self.activate_document(doc)
            logger.info(f"Created new {doc_type} document")
            return doc

        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise
    
    def get_active_document(self) -> Optional[Any]:
        """Get currently active document"""
        try:
            doc = self.desktop.getCurrentComponent()
            if doc:
                logger.info("Retrieved active document")
            return doc
        except Exception as e:
            logger.error(f"Failed to get active document: {e}")
            return None
    
    def get_document_info(self, doc: Any = None) -> Dict[str, Any]:
        """Get information about a document"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"error": "No document available"}

            doc_type = self._get_document_type(doc)

            info = {
                "title": getattr(doc, 'Title', 'Unknown') if hasattr(doc, 'Title') else "Unknown",
                "url": doc.getURL() if hasattr(doc, 'getURL') else "",
                "modified": doc.isModified() if hasattr(doc, 'isModified') else False,
                "type": doc_type,
                "has_selection": self._has_selection(doc)
            }

            # Add document-specific information
            if _is_instance(doc, XTextDocument):
                text = doc.getText()
                info["word_count"] = len(text.getString().split())
                info["character_count"] = len(text.getString())

                # Add track_changes status for Writer documents
                tc_status = self.get_track_changes_status(doc)
                if tc_status.get("success"):
                    info["track_changes"] = {
                        "recording": tc_status.get("recording", False),
                        "showing": tc_status.get("showing", False),
                        "pending_count": tc_status.get("pending_count", 0)
                    }
            elif _is_instance(doc, XSpreadsheetDocument):
                sheets = doc.getSheets()
                info["sheet_count"] = sheets.getCount()
                info["sheet_names"] = [sheets.getByIndex(i).getName()
                                     for i in range(sheets.getCount())]

            return info

        except Exception as e:
            logger.error(f"Failed to get document info: {e}")
            return {"error": str(e)}
    
    def insert_text(self, text: str, position: Optional[int] = None, doc: Any = None) -> Dict[str, Any]:
        """
        Insert text into a document
        
        Args:
            text: Text to insert
            position: Position to insert at (None for current cursor position)
            doc: Document to insert into (None for active document)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc:
                return {"success": False, "error": "No active document"}

            # Check if it's a Writer document
            is_writer = _is_instance(doc, XTextDocument) or \
                        (hasattr(doc, 'supportsService') and doc.supportsService("com.sun.star.text.TextDocument")) or \
                        hasattr(doc, 'getText')

            # Handle Writer documents
            if is_writer:
                text_obj = doc.getText()

                if position is None:
                    # Insert at current cursor position
                    cursor = doc.getCurrentController().getViewCursor()
                else:
                    # Insert at specific position
                    cursor = text_obj.createTextCursor()
                    cursor.gotoStart(False)
                    cursor.goRight(position, False)

                text_obj.insertString(cursor, text, False)
                logger.info(f"Inserted {len(text)} characters into Writer document")
                return {"success": True, "message": f"Inserted {len(text)} characters"}

            # Handle other document types
            else:
                return {"success": False, "error": f"Text insertion not supported for {self._get_document_type(doc)}"}
                
        except Exception as e:
            logger.error(f"Failed to insert text: {e}")
            return {"success": False, "error": str(e)}
    
    def format_text(self, formatting: Dict[str, Any], doc: Any = None) -> Dict[str, Any]:
        """
        Apply formatting to selected text
        
        Args:
            formatting: Dictionary of formatting options
            doc: Document to format (None for active document)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc or not _is_instance(doc, XTextDocument):
                return {"success": False, "error": "No Writer document available"}
            
            # Get current selection
            selection = doc.getCurrentController().getSelection()
            if selection.getCount() == 0:
                return {"success": False, "error": "No text selected"}
            
            # Apply formatting to selection
            text_range = selection.getByIndex(0)
            
            # Apply various formatting options
            if "bold" in formatting:
                text_range.CharWeight = 150.0 if formatting["bold"] else 100.0
            
            if "italic" in formatting:
                text_range.CharPosture = 2 if formatting["italic"] else 0
            
            if "underline" in formatting:
                text_range.CharUnderline = 1 if formatting["underline"] else 0
            
            if "font_size" in formatting:
                text_range.CharHeight = formatting["font_size"]
            
            if "font_name" in formatting:
                text_range.CharFontName = formatting["font_name"]
            
            logger.info("Applied formatting to selected text")
            return {"success": True, "message": "Formatting applied successfully"}
            
        except Exception as e:
            logger.error(f"Failed to format text: {e}")
            return {"success": False, "error": str(e)}
    
    def save_document(self, doc: Any = None, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Save a document
        
        Args:
            doc: Document to save (None for active document)
            file_path: Path to save to (None to save to current location)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc:
                return {"success": False, "error": "No document to save"}
            
            if file_path:
                # Save as new file
                url = uno.systemPathToFileUrl(file_path)
                doc.storeAsURL(url, ())
                logger.info(f"Saved document to {file_path}")
                return {"success": True, "message": f"Document saved to {file_path}"}
            else:
                # Save to current location
                if doc.hasLocation():
                    doc.store()
                    logger.info("Saved document to current location")
                    return {"success": True, "message": "Document saved"}
                else:
                    return {"success": False, "error": "Document has no location, specify file_path"}
                    
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return {"success": False, "error": str(e)}
    
    def export_document(self, export_format: str, file_path: str, doc: Any = None) -> Dict[str, Any]:
        """
        Export document to different format
        
        Args:
            export_format: Target format ('pdf', 'docx', 'odt', 'txt', etc.)
            file_path: Path to export to
            doc: Document to export (None for active document)
            
        Returns:
            Result dictionary
        """
        try:
            if doc is None:
                doc = self.get_active_document()
            
            if not doc:
                return {"success": False, "error": "No document to export"}
            
            # Filter map for different formats
            filter_map = {
                'pdf': 'writer_pdf_Export',
                'docx': 'MS Word 2007 XML',
                'doc': 'MS Word 97',
                'odt': 'writer8',
                'txt': 'Text',
                'rtf': 'Rich Text Format',
                'html': 'HTML (StarWriter)'
            }
            
            filter_name = filter_map.get(export_format.lower())
            if not filter_name:
                return {"success": False, "error": f"Unsupported export format: {export_format}"}
            
            # Prepare export properties
            properties = (
                PropertyValue("FilterName", 0, filter_name, 0),
                PropertyValue("Overwrite", 0, True, 0),
            )
            
            # Export document
            url = uno.systemPathToFileUrl(file_path)
            doc.storeToURL(url, properties)
            
            logger.info(f"Exported document to {file_path} as {export_format}")
            return {"success": True, "message": f"Document exported to {file_path}"}

        except Exception as e:
            logger.error(f"Failed to export document: {e}")
            return {"success": False, "error": str(e)}

    # -- Document lifecycle (open/close/save-as/properties/etc.) --------
    #
    # These methods raise on failure rather than returning a
    # {"success": False, ...} dict, matching create_document()'s contract
    # (not save_document()/export_document()'s). The tools/document_lifecycle.py
    # callers need to distinguish specific failure reasons (file already
    # exists vs. permission denied vs. a UNO exception) to map onto the
    # spec's distinct error codes, which a single generic error string
    # can't support cleanly.

    def open_document(self, file_path: str, read_only: bool = False, hidden: bool = False,
                       password: Optional[str] = None, filter_name: Optional[str] = None) -> Any:
        """Open an existing file as a new document. Returns the loaded document component."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"No such file: {file_path}")
        url = uno.systemPathToFileUrl(file_path)
        props = [
            PropertyValue("ReadOnly", 0, read_only, 0),
            PropertyValue("Hidden", 0, hidden, 0),
        ]
        if password:
            props.append(PropertyValue("Password", 0, password, 0))
        if filter_name:
            props.append(PropertyValue("FilterName", 0, filter_name, 0))
        doc = self.desktop.loadComponentFromURL(url, "_blank", 0, tuple(props))
        if doc is None:
            raise RuntimeError(f"LibreOffice returned no document for {file_path} (unsupported format or filter?)")
        if not hidden:
            # Same BUG #2 mechanism as create_document(): a non-hidden load
            # doesn't become getCurrentComponent()'s answer on its own in
            # this headless server. Skip for hidden=True -- there's no
            # foreground concept for a document the caller explicitly asked
            # to stay off-screen, and activating it would silently steal
            # "active document" status from whatever the caller is actually
            # working on.
            self.activate_document(doc)
        logger.info(f"Opened document from {file_path}")
        return doc

    def open_from_template(self, template_path: str, as_template: bool = True) -> Any:
        """Create a new document from an ODF/compatible template. Returns the new document component."""
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"No such template: {template_path}")
        url = uno.systemPathToFileUrl(template_path)
        props = (PropertyValue("AsTemplate", 0, as_template, 0),)
        doc = self.desktop.loadComponentFromURL(url, "_blank", 0, props)
        if doc is None:
            raise RuntimeError(f"LibreOffice returned no document for template {template_path}")
        self.activate_document(doc)  # BUG #2 fix, same mechanism as create_document()
        logger.info(f"Created document from template {template_path} (as_template={as_template})")
        return doc

    def close_document(self, doc: Any, save: Any = False) -> None:
        """Close a document with explicit save/discard behavior.

        Args:
            save: True (store before closing), False (discard changes), or
                "prompt" -- not supported headlessly (there is no UI to
                answer a prompt), raises ValueError so the caller can
                surface a clear error instead of hanging.
        """
        if save == "prompt":
            raise ValueError("save='prompt' is not supported by a headless extension; pass true or false explicitly.")
        if save is True:
            if not doc.hasLocation():
                raise ValueError("Document has no location to save to; use save_as_document_live first.")
            doc.store()
        doc.close(False)
        logger.info("Closed document")

    def activate_document(self, doc: Any) -> None:
        """Bring a document's frame to the foreground."""
        controller = doc.getCurrentController()
        if controller is None:
            raise RuntimeError("Document has no controller to activate.")
        frame = controller.getFrame()
        if frame is None:
            raise RuntimeError("Document's controller has no frame to activate.")
        frame.activate()
        try:
            frame.getContainerWindow().toFront()
        except Exception:
            pass  # best-effort in headless environments with no real window

    def get_document_statistics(self, doc: Any) -> Dict[str, Any]:
        """Return counts appropriate to the document's type (pages/words/
        chars for Writer; sheets for Calc; slides/pages for Impress/Draw)."""
        doc_type = self._get_document_type(doc)
        stats: Dict[str, Any] = {"type": doc_type}

        if doc_type == "writer":
            text = doc.getText()
            content = text.getString()
            stats["word_count"] = len(content.split())
            stats["character_count"] = len(content)
            # BUG #14 fix (live-verified): this used to enumerate every
            # top-level text element and count them all, including
            # non-paragraph content (e.g. a TextTable counts as one element
            # of its own) -- confirmed live it diverges from
            # get_paragraph_count_live by exactly the table count (12 real
            # paragraphs + 1 table -> this reported 13, not 12). Now shares
            # _count_paragraphs() (the same filtered enumeration
            # get_paragraph_count_live already uses), so the two tools
            # agree on what "paragraph" means instead of silently counting
            # different things under the same field name.
            stats["paragraph_count"] = self._count_paragraphs(doc)
            try:
                stats["page_count"] = doc.getCurrentController().PageCount
            except Exception:
                stats["page_count"] = None
        elif doc_type == "calc":
            sheets = doc.getSheets()
            stats["sheet_count"] = sheets.getCount()
            stats["sheet_names"] = [sheets.getByIndex(i).getName() for i in range(sheets.getCount())]
        elif doc_type in ("impress", "draw"):
            try:
                stats["page_count"] = doc.getDrawPages().getCount()
            except Exception:
                stats["page_count"] = None
        else:
            stats["warning"] = f"No statistics available for document type '{doc_type}'"

        return stats

    _DOCUMENT_PROPERTY_FIELDS = ("Title", "Subject", "Author", "Description", "ModifiedBy")

    def get_document_properties(self, doc: Any) -> Dict[str, Any]:
        """Return standard document metadata via XDocumentPropertiesSupplier."""
        props = doc.getDocumentProperties()
        result: Dict[str, Any] = {}
        for field in self._DOCUMENT_PROPERTY_FIELDS:
            result[field.lower() if field != "ModifiedBy" else "modified_by"] = getattr(props, field, None)
        result["keywords"] = list(getattr(props, "Keywords", ()) or ())
        result["creation_date"] = uno_datetime_to_iso(getattr(props, "CreationDate", None))
        result["modification_date"] = uno_datetime_to_iso(getattr(props, "ModificationDate", None))
        return result

    # Only these are exposed for writing -- CreationDate/ModificationDate/
    # ModifiedBy are UNO-managed and not meant to be set directly by a caller.
    _SETTABLE_DOCUMENT_PROPERTY_FIELDS = {"title": "Title", "subject": "Subject", "author": "Author",
                                           "description": "Description", "keywords": "Keywords"}

    def set_document_properties(self, doc: Any, properties: Dict[str, Any]) -> List[str]:
        """Set standard document metadata. Returns the list of field names actually applied.

        BUG #13 fix: the original report's own repro passed capitalized
        keys ({"Title": ..., "Author": ...}) and got them silently
        ignored -- the field-name lookup was exact-match against
        lowercase keys only, with no case-insensitivity and no schema
        documenting that requirement (empty inputSchema, confirmed in
        set_document_properties_live's tool registration). Not the
        "wrong shape entirely" the original report guessed (a flat dict
        IS the right shape -- confirmed by this method's own signature);
        fixed by matching field names case-insensitively instead."""
        doc_props = doc.getDocumentProperties()
        applied = []
        for key, value in properties.items():
            uno_field = self._SETTABLE_DOCUMENT_PROPERTY_FIELDS.get(key.lower())
            if uno_field is None:
                continue  # unknown/unsettable field name -- caller is told via the returned list
            if uno_field == "Keywords":
                value = tuple(value) if value else ()
            setattr(doc_props, uno_field, value)
            applied.append(key)
        return applied

    def get_custom_properties(self, doc: Any) -> Dict[str, Any]:
        """Return user-defined document properties as a flat {name: value} dict.

        A user can set a custom property's type to Text, Number, Date,
        Time, Duration, or Yes/No via LibreOffice's UI; Date/Time/Duration
        come back from getPropertyValue() as raw
        com.sun.star.util.{Date,DateTime,Duration} structs, not JSON-safe
        values -- str()'d (or json.dumps(default=str)'d) they produce an
        opaque struct repr instead of a readable value. Route every value
        through the shared converter (_uno_value_to_plain(), which
        includes this exact duck-typed Date/DateTime/Duration handling);
        plain Text/Number/Yes-No values pass through unchanged.
        """
        container = doc.getDocumentProperties().getUserDefinedProperties()
        names = [p.Name for p in container.getPropertySetInfo().getProperties()]
        return {
            name: self._uno_value_to_plain(container.getPropertyValue(name))
            for name in names
        }

    def set_custom_property(self, doc: Any, name: str, value: Any, property_type: Optional[str] = None) -> None:
        """Create or update a user-defined document property.

        Hardening-pass finding (#32/#33): addProperty() -- the CREATE
        path, used the first time a given name is set -- live-verified
        raises IllegalTypeException on a plain Python int (pyuno can't
        infer which UNO integer/float type an untyped int should become
        for a brand-new property with no existing type to coerce
        toward). setPropertyValue() -- the UPDATE path, for a name that
        already exists -- has no such problem; it auto-coerces a plain
        int against the property's already-established type just fine,
        live-verified. A plain float works on both paths without any
        special typing. Fixed by coercing a plain int (explicitly NOT
        bool, which is an int subclass in Python -- isinstance(True,
        int) is True) to float only on the CREATE path, where it's
        actually needed."""
        from com.sun.star.beans import PropertyAttribute

        container = doc.getDocumentProperties().getUserDefinedProperties()
        existing_names = {p.Name for p in container.getPropertySetInfo().getProperties()}
        if name in existing_names:
            container.setPropertyValue(name, value)
        else:
            if isinstance(value, int) and not isinstance(value, bool):
                value = float(value)
            container.addProperty(name, PropertyAttribute.REMOVABLE, value)

    def remove_custom_property(self, doc: Any, name: str) -> None:
        """Delete a user-defined document property. Raises if it doesn't exist."""
        container = doc.getDocumentProperties().getUserDefinedProperties()
        existing_names = {p.Name for p in container.getPropertySetInfo().getProperties()}
        if name not in existing_names:
            raise KeyError(f"No custom property named '{name}'")
        container.removeProperty(name)

    def get_modified_state(self, doc: Any) -> bool:
        return doc.isModified()

    def set_modified_state(self, doc: Any, modified: bool) -> None:
        doc.setModified(modified)

    # -- Undo manager (com.sun.star.document.XUndoManagerSupplier/XUndoManager) --

    def _get_undo_manager(self, doc: Any) -> Any:
        """Return doc's XUndoManager via XUndoManagerSupplier.getUndoManager().

        Duck-typed like the rest of this file (hasattr, not an explicit UNO
        interface cast) -- every document type this bridge supports
        implements com.sun.star.document.OfficeDocument, which carries
        XUndoManagerSupplier, but guard anyway in case a future document
        type/build doesn't.

        Raises:
            NotImplementedError: doc has no getUndoManager() (or it returned
                nothing) -- callers should map this to UNSUPPORTED_CAPABILITY.
        """
        get_manager = getattr(doc, "getUndoManager", None)
        if get_manager is None:
            raise NotImplementedError("This document does not support XUndoManagerSupplier.getUndoManager().")
        manager = get_manager()
        if manager is None:
            raise NotImplementedError("Document's getUndoManager() returned nothing.")
        return manager

    def get_undo_state(self, doc: Any) -> Dict[str, Any]:
        """Return undo/redo availability and the title of the next action
        each direction would apply, per XUndoManager.isUndoPossible()/
        isRedoPossible()/getCurrentUndoActionTitle()/getCurrentRedoActionTitle().
        """
        manager = self._get_undo_manager(doc)
        can_undo = manager.isUndoPossible()
        can_redo = manager.isRedoPossible()
        return {
            "can_undo": can_undo,
            "can_redo": can_redo,
            "undo_title": manager.getCurrentUndoActionTitle() if can_undo else None,
            "redo_title": manager.getCurrentRedoActionTitle() if can_redo else None,
        }

    def undo(self, doc: Any, count: int = 1) -> Dict[str, Any]:
        """Undo up to `count` actions, stopping cleanly (no exception) when
        the undo stack is exhausted rather than assuming `count` are always
        available.
        """
        manager = self._get_undo_manager(doc)
        applied = 0
        for _ in range(count):
            if not manager.isUndoPossible():
                break
            manager.undo()
            applied += 1
        return {
            "requested": count, "applied": applied,
            "can_undo": manager.isUndoPossible(), "can_redo": manager.isRedoPossible(),
        }

    def redo(self, doc: Any, count: int = 1) -> Dict[str, Any]:
        """Redo up to `count` actions, stopping cleanly when the redo stack
        is exhausted (e.g. because a new action was recorded since the last
        undo, which clears the redo stack per UNO semantics)."""
        manager = self._get_undo_manager(doc)
        applied = 0
        for _ in range(count):
            if not manager.isRedoPossible():
                break
            manager.redo()
            applied += 1
        return {
            "requested": count, "applied": applied,
            "can_undo": manager.isUndoPossible(), "can_redo": manager.isRedoPossible(),
        }

    def begin_undo_context(self, doc: Any, title: str) -> Dict[str, Any]:
        """Open a named undo context (XUndoManager.enterUndoContext) that
        coalesces every undo action recorded until end/cancel into one
        visible Undo step.

        Returns {"baseline_count": N} -- the undo stack depth (per
        getAllUndoActionTitles()) immediately before the context opened.
        Callers must hold onto this and pass it back into
        cancel_undo_context(); it's how cancel tells "the context added one
        coalesced action to revert" apart from "the context was empty and
        UNO silently discarded it" without needing an XUndoManagerListener.
        """
        manager = self._get_undo_manager(doc)
        baseline_count = len(manager.getAllUndoActionTitles())
        manager.enterUndoContext(title)
        return {"baseline_count": baseline_count}

    def end_undo_context(self, doc: Any) -> Dict[str, Any]:
        """Close the current undo context (XUndoManager.leaveUndoContext),
        coalescing everything recorded inside it into one Undo step (or, if
        nothing was recorded, UNO discards the context with no visible
        step -- see begin_undo_context's docstring).
        """
        manager = self._get_undo_manager(doc)
        manager.leaveUndoContext()
        return {"resulting_count": len(manager.getAllUndoActionTitles())}

    def cancel_undo_context(self, doc: Any, baseline_count: int) -> Dict[str, Any]:
        """Close the current undo context and revert whatever it recorded.

        XUndoManager has no direct "cancel" primitive, so this leaves the
        context the same way end_undo_context does (which is what commits
        the pending actions into one coalesced step -- undo() raises
        UndoContextNotClosedException while a context is still open), then
        calls undo() while the stack is deeper than baseline_count to
        revert exactly the step(s) that context produced. Normally that's
        at most one undo() call (a closed context coalesces to a single
        action), but the loop (capped) is defensive rather than assuming
        that invariant always holds.
        """
        manager = self._get_undo_manager(doc)
        manager.leaveUndoContext()
        reverted = 0
        max_iterations = 1000
        while len(manager.getAllUndoActionTitles()) > baseline_count and reverted < max_iterations:
            if not manager.isUndoPossible():
                break
            manager.undo()
            reverted += 1
        resulting_count = len(manager.getAllUndoActionTitles())
        return {"reverted_count": reverted, "restored": resulting_count <= baseline_count, "resulting_count": resulting_count}

    # -- View state, zoom, selection, document-update locking --------------

    # com.sun.star.view.DocumentZoomType constants. Not modeled as a
    # uno.Enum on the controller -- ZoomType is a plain short property
    # using this constants group -- so these are the caller-facing names
    # for set_zoom's `mode` parameter; BY_VALUE is used internally when
    # `percent` is set (see set_zoom) rather than exposed as a `mode` value.
    _ZOOM_MODE_TO_TYPE = {"optimal": 0, "page": 2, "width": 1}
    _ZOOM_TYPE_TO_MODE = {0: "optimal", 1: "width", 2: "page", 3: "value", 4: "width_exact"}

    def _get_controller(self, doc: Any) -> Any:
        controller = doc.getCurrentController()
        if controller is None:
            raise RuntimeError("Document has no current controller.")
        return controller

    def _get_zoom_property_set(self, controller: Any) -> Any:
        """Return the XPropertySet that carries ZoomValue/ZoomType.

        Live-verified against a real Writer document that these are NOT
        direct properties of the controller itself -- reading
        controller.ZoomValue silently returns None and writing
        controller.ZoomType raises a UNO exception. The real location is
        controller.ViewSettings (an XPropertySet; service
        com.sun.star.text.ViewSettings for Writer, and per the UNO API the
        same XViewSettingsSupplier.ViewSettings pattern is documented for
        Calc/Impress/Draw controllers too, though only Writer was
        available to live-verify this pass -- falls back to the
        controller itself if ViewSettings isn't present, in case some
        controller type doesn't follow this pattern.
        """
        view_settings = getattr(controller, "ViewSettings", None)
        if view_settings is not None and hasattr(view_settings, "getPropertyValue"):
            return view_settings
        return controller

    def get_view_state(self, doc: Any) -> Dict[str, Any]:
        """Return controller/view mode, zoom, and a document-type-specific
        visible sheet/page/slide indicator, plus a selection summary."""
        controller = self._get_controller(doc)
        doc_type = self._get_document_type(doc)
        zoom_props = self._get_zoom_property_set(controller)
        zoom_type = zoom_props.getPropertyValue("ZoomType") if hasattr(zoom_props, "getPropertyValue") else None
        state: Dict[str, Any] = {
            "type": doc_type,
            "zoom_value": zoom_props.getPropertyValue("ZoomValue") if hasattr(zoom_props, "getPropertyValue") else None,
            "zoom_mode": self._ZOOM_TYPE_TO_MODE.get(zoom_type, zoom_type),
            "has_selection": self._has_selection(doc),
        }
        if doc_type == "calc":
            try:
                active_sheet = controller.getActiveSheet()
                state["active_sheet"] = active_sheet.getName() if active_sheet else None
            except Exception as e:
                # A calc document always has an active sheet, so a failure
                # here is a real anomaly (disposed controller, etc.), not a
                # legitimate "no sheet" state -- both previously produced
                # the same active_sheet: None with no way to tell them apart.
                state["active_sheet"] = None
                state["warnings"] = [f"Could not read active sheet name: {e}"]
        elif doc_type in ("impress", "draw"):
            try:
                current_page = controller.getCurrentPage()
                state["current_page_name"] = current_page.Name if current_page else None
            except Exception as e:
                state["current_page_name"] = None
                state["warnings"] = [f"Could not read current page name: {e}"]
        elif doc_type == "writer":
            # New addition (Brian's new-tools assignment, priority #6) --
            # get_view_state_live previously reported no page position at
            # all for Writer, unlike calc's active_sheet/impress's
            # current_page_name above. The view cursor implements
            # com.sun.star.text.XPageCursor, whose getPage() returns the
            # 1-based page the cursor is currently on -- the same number
            # Writer's own status bar shows, not a 0-based index.
            try:
                view_cursor = controller.getViewCursor()
                state["current_page_number"] = view_cursor.getPage() if hasattr(view_cursor, "getPage") else None
            except Exception as e:
                state["current_page_number"] = None
                state["warnings"] = [f"Could not read current page number: {e}"]
        return state

    def goto_page(self, doc: Any, page: int) -> Dict[str, Any]:
        """Move the Writer view cursor to the start of the given page
        (new tool, Brian's new-tools assignment priority #7) -- the write
        side companion to get_view_state_live's current_page_number
        addition (#6), navigating through the same view cursor's
        com.sun.star.text.XPageCursor interface that reads it.

        Live-verified finding: jumpToPage() past the document's real last
        page does not raise and does not leave the cursor where it was --
        it silently clamps to the last real page. Reported back via a
        warning naming the real page reached, rather than claiming the
        exact requested page was hit when it wasn't.
        """
        self._require_writer(doc, "goto_page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise ValueError(f"page must be a positive integer, got {page!r}")
        view_cursor = self._get_controller(doc).getViewCursor()
        if not hasattr(view_cursor, "jumpToPage"):
            raise NotImplementedError("This document's view cursor does not support page navigation.")
        view_cursor.jumpToPage(page)
        actual_page = view_cursor.getPage() if hasattr(view_cursor, "getPage") else None
        result: Dict[str, Any] = {"page": actual_page}
        if actual_page is not None and actual_page != page:
            result["warnings"] = [
                f"Requested page {page} but the document only reaches page {actual_page} -- "
                "clamped to the last real page rather than failing."
            ]
        return result

    def set_zoom(self, doc: Any, percent: Optional[int] = None, mode: Optional[str] = None) -> Dict[str, Any]:
        """Set zoom percent (exact value) or a named fit mode. Exactly one
        of percent/mode should be meaningful; if both are given, percent
        wins (mode is applied first, then overridden by the exact value)."""
        if percent is None and mode is None:
            raise ValueError("Provide either percent or mode.")
        controller = self._get_controller(doc)
        zoom_props = self._get_zoom_property_set(controller)
        if not hasattr(zoom_props, "setPropertyValue"):
            raise NotImplementedError("This document's controller does not expose a settable zoom property set.")
        if mode is not None:
            zoom_type = self._ZOOM_MODE_TO_TYPE.get(mode)
            if zoom_type is None:
                raise ValueError(f"Unknown zoom mode '{mode}', expected one of {sorted(self._ZOOM_MODE_TO_TYPE)}")
            zoom_props.setPropertyValue("ZoomType", zoom_type)
        if percent is not None:
            zoom_props.setPropertyValue("ZoomType", 3)  # BY_VALUE -- otherwise a fit-mode set above would override ZoomValue
            zoom_props.setPropertyValue("ZoomValue", percent)
        return {"zoom_value": zoom_props.getPropertyValue("ZoomValue"),
                "zoom_mode": self._ZOOM_TYPE_TO_MODE.get(zoom_props.getPropertyValue("ZoomType"))}

    def get_selection(self, doc: Any) -> Dict[str, Any]:
        """Return a document-type-specific summary of the current selection.

        Hardening-pass finding (#33 robustness sweep): unlike every other
        best-effort try/except in this file (which either leaves a None/
        False fallback the caller can detect, e.g. get_headers_footers's
        header_X: None, or is enriching a genuinely-optional field a
        given object type may not support at all, e.g. shape rotation),
        this method's three per-doc-type blocks used to catch and
        silently discard with no fallback value and no signal
        whatsoever -- a caller had no way to distinguish "nothing
        selected" from "reading the selection details failed." Now
        records a warning string instead."""
        controller = self._get_controller(doc)
        doc_type = self._get_document_type(doc)
        result: Dict[str, Any] = {"type": doc_type, "has_selection": self._has_selection(doc)}
        warnings: List[str] = []
        selection = controller.getSelection()
        if selection is None:
            if warnings:
                result["warnings"] = warnings
            return result

        if doc_type == "writer":
            try:
                texts = [selection.getByIndex(i).getString() for i in range(selection.getCount())]
                result["selected_text"] = "".join(texts)
                result["range_count"] = selection.getCount()
            except Exception as e:
                warnings.append(f"Could not read Writer selection details: {e}")
        elif doc_type == "calc":
            try:
                if hasattr(selection, "getRangeAddress"):
                    addr = selection.getRangeAddress()
                    result["range"] = {"sheet": addr.Sheet, "start_column": addr.StartColumn,
                                        "start_row": addr.StartRow, "end_column": addr.EndColumn, "end_row": addr.EndRow}
            except Exception as e:
                warnings.append(f"Could not read Calc selection details: {e}")
        elif doc_type in ("impress", "draw"):
            try:
                if hasattr(selection, "getCount"):
                    result["shape_count"] = selection.getCount()
                    result["shape_names"] = [selection.getByIndex(i).Name for i in range(selection.getCount())]
            except Exception as e:
                warnings.append(f"Could not read {doc_type} selection details: {e}")
        if warnings:
            result["warnings"] = warnings
        return result

    def clear_selection(self, doc: Any) -> None:
        """Collapse/clear the current selection without modifying content."""
        controller = self._get_controller(doc)
        doc_type = self._get_document_type(doc)
        if doc_type == "writer":
            view_cursor = controller.getViewCursor()
            view_cursor.collapseToStart()
        elif doc_type == "calc":
            active_sheet = controller.getActiveSheet()
            controller.select(active_sheet.getCellByPosition(0, 0))
        elif doc_type in ("impress", "draw"):
            controller.select(())
        else:
            raise NotImplementedError(f"clear_selection is not implemented for document type '{doc_type}'.")

    def lock_document_updates(self, doc: Any) -> None:
        """Temporarily lock automatic view/model update via XModel.lockControllers()."""
        doc.lockControllers()

    def unlock_document_updates(self, doc: Any) -> None:
        """Release the update lock via XModel.unlockControllers() -- must be
        called exactly once per lock_document_updates() call; UNO tracks
        this as a nesting count, not a boolean."""
        doc.unlockControllers()

    # -- Document events (get_document_events_live/wait_for_document_event_live) --
    #
    # Real implementation pass, closing the last of Part 2's 12
    # scope-limited stubs. A single com.sun.star.document.XDocumentEventListener
    # (_DocumentEventCapture above) is registered once, process-wide,
    # against the com.sun.star.frame.GlobalEventBroadcaster singleton --
    # that singleton already covers every open document, not just the
    # active one, so no per-document registration is needed. Captured
    # events land in self._event_buffer (a bounded deque guarded by
    # self._event_condition), keyed by a monotonically increasing seq
    # rather than deque position/length, since a bounded deque silently
    # evicts from the left once maxlen is hit.
    #
    # Correlating event.Source back to this extension's own document_id
    # is deliberately NOT done here -- UNOBridge has no DocumentRegistry
    # reference (keeping the bridge layer document-registry-agnostic,
    # same separation document_lifecycle.py's own docstring describes).
    # tools/undo_view_selection.py does that correlation at the tools
    # layer instead, best-effort, since a document opened directly in the
    # LibreOffice GUI (not through open_document_live/create_document_live)
    # was never registered and has no document_id.

    def _ensure_document_event_capture(self) -> None:
        """Idempotently register the single process-wide document-event
        listener. Safe to call on every get/wait_for_document_event_live
        invocation -- live-verified a second call after the first
        successful registration is a no-op (the guard below short-circuits
        before ever reaching addDocumentEventListener again), so it
        can't produce a duplicate listener or duplicate captured events."""
        if _DocumentEventCapture is None:
            raise NotImplementedError(
                "com.sun.star.document.XDocumentEventListener is unavailable in this "
                "LibreOffice/PyUNO build -- document-event capture cannot be enabled."
            )
        with self._event_lock:
            if self._event_listener is not None:
                return
            broadcaster = self.smgr.createInstanceWithContext(
                "com.sun.star.frame.GlobalEventBroadcaster", self.ctx)
            listener = _DocumentEventCapture(self)
            broadcaster.addDocumentEventListener(listener)
            # Keep a reference to both -- the broadcaster only holds a weak
            # tie to the listener via its own internal container, and
            # nothing else in this process would otherwise keep `listener`
            # alive.
            self._event_broadcaster = broadcaster
            self._event_listener = listener

    def _record_document_event(self, event: Any) -> None:
        """Callback body for _DocumentEventCapture.documentEventOccured --
        append-only, no UNO calls back out (see this class's own
        docstring for why). event.Source is the raw XComponent the event
        fired on; kept by reference so the tools layer can best-effort
        resolve it to a document_id later, and document_url is captured
        now (rather than deferred) since a document that closes between
        the event firing and a later read would make event.Source.
        getURL() raise or return stale/empty data."""
        with self._event_condition:
            self._event_seq += 1
            try:
                document_url = event.Source.getURL() if hasattr(event.Source, "getURL") else None
            except Exception:
                document_url = None
            self._event_buffer.append({
                "seq": self._event_seq,
                "event_type": event.EventName,
                "document_url": document_url or None,
                "source": event.Source,
            })
            self._event_condition.notify_all()

    def get_document_events(self, limit: int = 100, event_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return up to the last `limit` captured events (oldest to
        newest), optionally filtered to `event_types`. Registers the
        listener on first call if it isn't already -- so events fired
        before the very first get/wait_for_document_event_live call of
        this process's lifetime are never captured; this is a documented
        open question (does GlobalEventBroadcaster fire OnLoad for a
        document already open before registration?), not silently
        assumed either way here."""
        self._ensure_document_event_capture()
        with self._event_lock:
            events = list(self._event_buffer)
        if event_types:
            wanted = set(event_types)
            events = [e for e in events if e["event_type"] in wanted]
        return events[-limit:] if limit else []

    def wait_for_document_event(self, event_types: List[str], timeout_ms: int) -> Optional[Dict[str, Any]]:
        """Block the calling thread (confirmed safe -- ai_interface.py's
        ReusableThreadingTCPServer runs every HTTP request on its own
        thread, separate from whatever internal thread(s) fire document
        events) until a buffered event with seq > the snapshot taken at
        entry and a matching event_type appears, or timeout_ms elapses.
        Returns None on timeout rather than raising -- a timeout is an
        expected, non-error outcome for this tool.

        The actual wait is clamped to min(timeout_ms, _MAX_WAIT_LOCK_HOLD_MS)
        regardless of the caller-requested timeout_ms -- see that
        constant's comment for why and how the cap was derived. A capped
        return still comes back as a plain timeout (this method returns
        None either way); the caller can't tell a cap from a genuine
        timeout, which is deliberate. A caller wanting to wait longer
        than the cap re-issues the call."""
        self._ensure_document_event_capture()
        wanted = set(event_types)
        clamped_timeout_ms = min(max(timeout_ms, 0), _MAX_WAIT_LOCK_HOLD_MS)
        deadline = time.monotonic() + clamped_timeout_ms / 1000.0
        with self._event_condition:
            snapshot_seq = self._event_seq
            while True:
                for candidate in self._event_buffer:
                    if candidate["seq"] > snapshot_seq and candidate["event_type"] in wanted:
                        return candidate
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._event_condition.wait(remaining)

    # -- Styles and formatting -----------------------------------------

    # Family -> UNO service name, for creating a brand-new style instance
    # via doc.createInstance(). Only these 6 families are covered this
    # pass (reasonably well-established UNO service names); an
    # unrecognized family raises NotImplementedError rather than guessing.
    _STYLE_FAMILY_SERVICES = {
        "ParagraphStyles": "com.sun.star.style.ParagraphStyle",
        "CharacterStyles": "com.sun.star.style.CharacterStyle",
        "PageStyles": "com.sun.star.style.PageStyle",
        "FrameStyles": "com.sun.star.style.FrameStyle",
        "NumberingStyles": "com.sun.star.style.NumberingStyle",
        "CellStyles": "com.sun.star.style.CellStyle",
    }

    # Family -> the text-range property that actually applies a style of
    # that family. Only Writer's two most common families are covered
    # this pass (high-confidence UNO property names, live-verified);
    # apply_style for any other family raises UNSUPPORTED_CAPABILITY
    # rather than guessing at a property name that could silently apply
    # the wrong thing.
    _STYLE_FAMILY_APPLY_PROPERTY = {
        "ParagraphStyles": "ParaStyleName",
        "CharacterStyles": "CharStyleName",
    }

    def _get_style_family(self, doc: Any, family: str) -> Any:
        """Return the XNameContainer for one style family via XStyleFamiliesSupplier.

        Raises:
            KeyError: `family` isn't a family this document has.
        """
        families = doc.getStyleFamilies()
        if not families.hasByName(family):
            raise KeyError(f"No such style family '{family}'. Available: {sorted(families.getElementNames())}")
        return families.getByName(family)

    def list_style_families(self, doc: Any) -> Dict[str, Any]:
        return {"families": sorted(doc.getStyleFamilies().getElementNames())}

    def list_styles(self, doc: Any, family: str) -> Dict[str, Any]:
        family_container = self._get_style_family(doc, family)
        styles = []
        for i in range(family_container.getCount()):
            style = family_container.getByIndex(i)
            styles.append({
                "name": style.Name,
                "is_user_defined": style.isUserDefined() if hasattr(style, "isUserDefined") else None,
                "is_in_use": style.isInUse() if hasattr(style, "isInUse") else None,
            })
        return {"family": family, "styles": styles}

    def get_style(self, doc: Any, family: str, style_name: str) -> Dict[str, Any]:
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        style = family_container.getByName(style_name)
        return {
            "name": style.Name,
            "parent_style": getattr(style, "ParentStyle", None) or None,
            "is_user_defined": style.isUserDefined() if hasattr(style, "isUserDefined") else None,
            "is_in_use": style.isInUse() if hasattr(style, "isInUse") else None,
        }

    def create_style(self, doc: Any, family: str, style_name: str, parent_style: Optional[str] = None,
                      properties: Optional[Dict[str, Any]] = None) -> List[str]:
        """Create a user style. Returns the list of `properties` keys actually applied."""
        family_container = self._get_style_family(doc, family)
        if family_container.hasByName(style_name):
            raise FileExistsError(f"Style '{style_name}' already exists in family '{family}'.")
        service_name = self._STYLE_FAMILY_SERVICES.get(family)
        if service_name is None:
            raise NotImplementedError(f"create_style is not implemented for family '{family}'.")
        new_style = doc.createInstance(service_name)
        family_container.insertByName(style_name, new_style)
        if parent_style:
            new_style.ParentStyle = parent_style
        applied = []
        for key, value in (properties or {}).items():
            try:
                new_style.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                pass
        return applied

    def clone_style(self, doc: Any, family: str, source_style: str, new_style_name: str) -> List[str]:
        """Clone an existing style: create new_style_name in the same family
        with the same parent, then copy every directly-set (non-default,
        non-readonly) property value from the source.

        Returns the list of directly-set property names that failed to
        copy. Unlike create_style/update_style (which are told which
        properties to apply and report which of *those* succeeded), this
        method decides for itself which properties to attempt, so a silent
        per-property failure here can hide a real bug (as opposed to a
        caller passing an unsettable key on purpose) -- surfaced to the
        caller instead of the previous bare `except: continue`.
        """
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(source_style):
            raise KeyError(f"No such style '{source_style}' in family '{family}'.")
        if family_container.hasByName(new_style_name):
            raise FileExistsError(f"Style '{new_style_name}' already exists in family '{family}'.")
        service_name = self._STYLE_FAMILY_SERVICES.get(family)
        if service_name is None:
            raise NotImplementedError(f"clone_style is not implemented for family '{family}'.")

        source = family_container.getByName(source_style)
        clone = doc.createInstance(service_name)
        family_container.insertByName(new_style_name, clone)
        if getattr(source, "ParentStyle", None):
            clone.ParentStyle = source.ParentStyle

        failed: List[str] = []
        info = source.getPropertySetInfo()
        for prop in info.getProperties():
            try:
                if source.getPropertyState(prop.Name) != uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE"):
                    continue
                clone.setPropertyValue(prop.Name, source.getPropertyValue(prop.Name))
            except Exception:
                failed.append(prop.Name)
                continue
        return failed

    def update_style(self, doc: Any, family: str, style_name: str, properties: Dict[str, Any]) -> List[str]:
        """Update style properties. Returns the list of keys actually applied."""
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        style = family_container.getByName(style_name)
        applied = []
        for key, value in properties.items():
            try:
                style.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                pass
        return applied

    def rename_style(self, doc: Any, family: str, old_name: str, new_name: str) -> None:
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(old_name):
            raise KeyError(f"No such style '{old_name}' in family '{family}'.")
        if family_container.hasByName(new_name):
            raise FileExistsError(f"A style named '{new_name}' already exists in family '{family}'.")
        style = family_container.getByName(old_name)
        if not hasattr(style, "setName"):
            raise NotImplementedError(f"Styles in family '{family}' do not support renaming.")
        style.setName(new_name)

    def delete_style(self, doc: Any, family: str, style_name: str) -> None:
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        style = family_container.getByName(style_name)
        if hasattr(style, "isUserDefined") and not style.isUserDefined():
            raise ValueError(f"'{style_name}' is a built-in style and cannot be deleted.")
        family_container.removeByName(style_name)

    def _resolve_text_target(self, doc: Any, target: Optional[Any]) -> Any:
        """Resolve `target` to a Writer text range.

        target=None -> the first range of the current selection.
        target={"start": int, "end": int} -> a 0-based character range,
        built the same way select_text_range() already does.

        This is the concrete resolution chosen for apply_style_live/
        get_direct_formatting_live/clear_direct_formatting_live/
        copy_formatting_live's previously-undecided `target` shape --
        Writer text ranges only this pass; other document types raise
        WRONG_DOCUMENT_TYPE via the caller's _get_document_type check.
        """
        if target is None:
            controller = self._get_controller(doc)
            selection = controller.getSelection()
            if selection is None or not hasattr(selection, "getCount") or selection.getCount() == 0:
                raise ValueError("No current selection and no target given.")
            return selection.getByIndex(0)
        if isinstance(target, dict) and "start" in target and "end" in target:
            start, end = target["start"], target["end"]
            if start < 0 or end < start:
                raise ValueError(f"Invalid target range: start={start}, end={end}")
            text = doc.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            if start > 0:
                cursor.goRight(start, False)
            length = end - start
            if length > 0:
                cursor.goRight(length, True)
            return cursor
        raise ValueError("target must be omitted (use current selection) or {'start': int, 'end': int}.")

    def apply_style(self, doc: Any, family: str, style_name: str, target: Optional[Any] = None) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise WrongDocumentTypeError(f"apply_style is only implemented for Writer documents this pass, not '{doc_type}'.")
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        apply_property = self._STYLE_FAMILY_APPLY_PROPERTY.get(family)
        if apply_property is None:
            raise NotImplementedError(f"apply_style is not implemented for family '{family}'.")
        text_range = self._resolve_text_target(doc, target)
        text_range.setPropertyValue(apply_property, style_name)

    def get_direct_formatting(self, doc: Any, target: Optional[Any] = None) -> Dict[str, Any]:
        """Return every property whose PropertyState is DIRECT_VALUE on the
        target text range.

        Scope note: Writer text ranges implement both CharacterProperties
        and ParagraphProperties, so this can include structural/paragraph-
        level properties (e.g. ParaStyleName, PageStyleName) alongside
        genuine direct character-formatting overrides -- not filtered down
        to a curated "formatting-only" subset, just JSON-safe DIRECT_VALUE
        properties. Object-reference properties (e.g. a paragraph's own
        TextParagraph self-reference) are excluded via _is_json_safe
        rather than dumped as an opaque repr string.
        """
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise WrongDocumentTypeError(f"get_direct_formatting is only implemented for Writer documents this pass, not '{doc_type}'.")
        text_range = self._resolve_text_target(doc, target)
        direct_value = uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE")
        overrides = {}
        for prop in text_range.getPropertySetInfo().getProperties():
            try:
                if text_range.getPropertyState(prop.Name) != direct_value:
                    continue
                plain_value = self._uno_value_to_plain(text_range.getPropertyValue(prop.Name))
                if self._is_json_safe(plain_value):
                    overrides[prop.Name] = plain_value
            except Exception:
                continue
        return {"direct_formatting": overrides}

    def clear_direct_formatting(self, doc: Any, target: Optional[Any] = None) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise WrongDocumentTypeError(f"clear_direct_formatting is only implemented for Writer documents this pass, not '{doc_type}'.")
        text_range = self._resolve_text_target(doc, target)
        if not hasattr(text_range, "setAllPropertiesToDefault"):
            raise NotImplementedError("This target does not support clearing direct formatting (XMultiPropertyStates).")
        text_range.setAllPropertiesToDefault()

    def copy_formatting(self, doc: Any, source: Any, target: Any, include: Optional[List[str]] = None) -> List[str]:
        """Copy every directly-set (non-default) property from source to
        target. Returns the list of property names actually copied."""
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise WrongDocumentTypeError(f"copy_formatting is only implemented for Writer documents this pass, not '{doc_type}'.")
        source_range = self._resolve_text_target(doc, source)
        target_range = self._resolve_text_target(doc, target)
        direct_value = uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE")
        applied = []
        for prop in source_range.getPropertySetInfo().getProperties():
            if include and prop.Name not in include:
                continue
            try:
                if source_range.getPropertyState(prop.Name) != direct_value:
                    continue
                value = source_range.getPropertyValue(prop.Name)
                if not self._is_json_safe(self._uno_value_to_plain(value)):
                    continue  # skip object-reference properties (e.g. TextParagraph self-reference)
                target_range.setPropertyValue(prop.Name, value)
                applied.append(prop.Name)
            except Exception:
                continue
        return applied

    def refresh_document(self, doc: Any) -> None:
        """Refresh fields/links/data via XRefreshable, where the document type supports it."""
        if not hasattr(doc, "refresh"):
            raise NotImplementedError("This document does not support XRefreshable.refresh().")
        doc.refresh()

    def reload_document(self, doc: Any, discard_changes: bool = False) -> Any:
        """Reload a document from storage. Returns the NEW document
        component -- the old one is closed and its UNO object becomes
        invalid, so callers must re-point any document_id they had for it
        at the returned object (see tools.documents.DocumentRegistry.replace_document).

        Raises:
            ValueError: no stored location to reload from, or unsaved
                changes exist and discard_changes is False (headless --
                there is no UI to prompt for confirmation).
        """
        if not doc.hasLocation():
            raise ValueError("Document has no stored location to reload from.")
        if doc.isModified() and not discard_changes:
            raise ValueError("Document has unsaved changes; pass discard_changes=true to reload anyway.")
        url = doc.getURL()
        doc.close(False)
        new_doc = self.desktop.loadComponentFromURL(url, "_blank", 0, ())
        if new_doc is None:
            raise RuntimeError(f"LibreOffice returned no document reloading {url}")
        self.activate_document(new_doc)  # BUG #2 fix, same mechanism as create_document()
        return new_doc

    @staticmethod
    def _stale_lock_file(doc: Any, file_path: str) -> Optional[str]:
        """Return the path of a LibreOffice lock marker for file_path if one
        exists on disk and it isn't doc's own (a document that already has
        file_path as its stored location legitimately holds that lock
        itself), else None.

        BUG #6 finding (from the original report, not independently
        reproduced this pass -- see save_as_document()'s docstring): a
        stale `.~lock.<name>#` file left behind by a crashed/killed prior
        soffice process, combined with a pre-existing file at the same
        output path, was reported to make storeAsURL() silently serialize
        a different (near-empty, stale-frame) document instead of the live
        one being saved -- success=true, wrong bytes on disk. The lock
        marker's own naming convention (`.~lock.<basename>#`, same
        directory) is LibreOffice's own, not this project's."""
        directory, name = os.path.split(file_path)
        lock_path = os.path.join(directory, f".~lock.{name}#")
        if not os.path.exists(lock_path):
            return None
        try:
            if doc.hasLocation() and doc.getURL() == uno.systemPathToFileUrl(file_path):
                return None  # doc's own legitimate self-lock, not a stale one
        except Exception:
            pass
        return lock_path

    def save_as_document(self, doc: Any, file_path: str, filter_name: Optional[str] = None,
                          filter_options: Optional[Dict[str, Any]] = None, overwrite: bool = False) -> None:
        """Explicit Save As: changes the document's own stored location, unlike save_copy_document().

        BUG #6 fix: refuses when a stale LibreOffice lock marker exists
        for file_path, regardless of `overwrite` -- overwrite only ever
        meant "yes, replace the file's bytes," never "yes, save through
        whatever stale frame LibreOffice may have attached because a lock
        file suggests another session already has this path open." The
        original report's own manual workaround (kill soffice, delete
        every .~lock.* AND the old output file before starting) is the
        exact condition this now enforces instead of leaving as tribal
        knowledge in a log file -- see docs/HARDENING_PLAN.md."""
        lock_path = self._stale_lock_file(doc, file_path)
        if lock_path:
            raise FileExistsError(
                f"A LibreOffice lock file exists for {file_path} ({lock_path}). Saving through a stale "
                f"lock has been reported to silently write the wrong document's content. Confirm no other "
                f"session actually holds this file, delete the lock file, then retry -- overwrite=true does "
                f"not address this."
            )
        if not overwrite and os.path.exists(file_path):
            raise FileExistsError(f"{file_path} already exists; pass overwrite=true to replace it.")
        url = uno.systemPathToFileUrl(file_path)
        props = [PropertyValue("Overwrite", 0, overwrite, 0)]
        if filter_name:
            props.append(PropertyValue("FilterName", 0, filter_name, 0))
        if filter_options:
            props.append(PropertyValue(
                "FilterData", 0,
                tuple(PropertyValue(k, 0, v, 0) for k, v in filter_options.items()), 0))
        doc.storeAsURL(url, tuple(props))

    def save_copy_document(self, doc: Any, file_path: str, filter_name: Optional[str] = None,
                            overwrite: bool = False) -> None:
        """Store a copy without changing the document's own stored location.

        BUG #6 fix: same stale-lock refusal as save_as_document() -- see
        its docstring. storeToURL() shares the same "reads a stale
        attached frame instead of the live document" risk mechanism."""
        lock_path = self._stale_lock_file(doc, file_path)
        if lock_path:
            raise FileExistsError(
                f"A LibreOffice lock file exists for {file_path} ({lock_path}). Saving through a stale "
                f"lock has been reported to silently write the wrong document's content. Confirm no other "
                f"session actually holds this file, delete the lock file, then retry -- overwrite=true does "
                f"not address this."
            )
        if not overwrite and os.path.exists(file_path):
            raise FileExistsError(f"{file_path} already exists; pass overwrite=true to replace it.")
        url = uno.systemPathToFileUrl(file_path)
        props = [PropertyValue("Overwrite", 0, overwrite, 0)]
        if filter_name:
            props.append(PropertyValue("FilterName", 0, filter_name, 0))
        doc.storeToURL(url, tuple(props))

    def convert_document_file(self, input_path: str, output_path: str,
                               output_format: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> None:
        """Open-convert-save between formats without disturbing any already-open document.

        Loads input_path hidden, stores to output_path (inferring a filter
        from output_format if given, else from output_path's extension via
        _guess_filter_name), and always closes the temporary load -- this
        document is never tracked by DocumentRegistry.
        """
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"No such file: {input_path}")
        filter_name = self._guess_filter_name(output_format, output_path)
        source_url = uno.systemPathToFileUrl(input_path)
        temp_doc = self.desktop.loadComponentFromURL(source_url, "_blank", 0, (
            PropertyValue("Hidden", 0, True, 0),
        ))
        if temp_doc is None:
            raise RuntimeError(f"LibreOffice returned no document for {input_path}")
        try:
            target_url = uno.systemPathToFileUrl(output_path)
            props = [PropertyValue("Overwrite", 0, True, 0)]
            if filter_name:
                props.append(PropertyValue("FilterName", 0, filter_name, 0))
            if options:
                props.append(PropertyValue(
                    "FilterData", 0,
                    tuple(PropertyValue(k, 0, v, 0) for k, v in options.items()), 0))
            temp_doc.storeToURL(target_url, tuple(props))
        finally:
            temp_doc.close(False)

    # Deliberately small -- only the same formats export_document() already
    # supports, plus odt/ods/odp for round-tripping. Extend as more formats
    # are needed rather than guessing at unfamiliar filter names.
    _FILTER_NAME_MAP = {
        "pdf": "writer_pdf_Export", "docx": "MS Word 2007 XML", "doc": "MS Word 97",
        "odt": "writer8", "txt": "Text", "rtf": "Rich Text Format", "html": "HTML (StarWriter)",
        "ods": "calc8", "xlsx": "Calc MS Excel 2007 XML", "csv": "Text - txt - csv (StarCalc)",
        "odp": "impress8", "pptx": "Impress MS PowerPoint 2007 XML",
    }

    def _guess_filter_name(self, output_format: Optional[str], output_path: str) -> Optional[str]:
        key = (output_format or os.path.splitext(output_path)[1].lstrip(".")).lower()
        filter_name = self._FILTER_NAME_MAP.get(key)
        if filter_name is None:
            raise ValueError(
                f"Unsupported/unrecognized output format '{key}'. "
                f"Supported: {sorted(self._FILTER_NAME_MAP)}"
            )
        return filter_name

    def list_export_filters(self, doc: Any) -> Dict[str, Any]:
        """List UNO filters registered for this document's type.

        Scope limit: filters by DocumentService match only, not by an
        import/export capability flag (the UNO FilterFlags bitmask isn't
        exercised here to avoid guessing at an undocumented value) -- the
        returned list may include import-only filters alongside export
        ones. Good enough to show what's registered; not a strict
        "export capable" guarantee.
        """
        doc_type = self._get_document_type(doc)
        service_map = {
            "writer": "com.sun.star.text.TextDocument",
            "calc": "com.sun.star.sheet.SpreadsheetDocument",
            "impress": "com.sun.star.presentation.PresentationDocument",
            "draw": "com.sun.star.drawing.DrawingDocument",
        }
        document_service = service_map.get(doc_type)
        if document_service is None:
            return {"document_type": doc_type, "filters": [], "warning": f"No known service mapping for type '{doc_type}'"}

        filter_factory = self.smgr.createInstanceWithContext("com.sun.star.document.FilterFactory", self.ctx)
        names = []
        for name in filter_factory.getElementNames():
            try:
                # getByName() returns a tuple of PropertyValue structs, not
                # a mapping -- dict() on it directly raises TypeError
                # ("cannot convert dictionary update sequence element #0
                # to a sequence"); live-verified this the hard way.
                entry = {p.Name: p.Value for p in filter_factory.getByName(name)}
            except Exception:
                continue
            if entry.get("DocumentService") == document_service:
                names.append(name)
        return {"document_type": doc_type, "filters": sorted(names)}

    @staticmethod
    def _uno_value_to_plain(value: Any) -> Any:
        """Convert common non-JSON-safe UNO value types to a plain Python
        value. Handles uno.Enum (-> its string name, e.g. "PORTRAIT"),
        Date/DateTime/Duration structs (delegated to uno_datetime.py's
        duck-typed dispatcher -> an ISO-8601 string), awt.Rectangle/Size/
        Point-shaped structs (-> a dict), and lang.Locale (-> "xx-YY",
        the same string shape _parse_locale()'s reverse direction already
        parses). Live-verified that PropertyValue sequences like
        XPrintable's getPrinter() return Enum/Size values, and that
        get_direct_formatting_live's generic property-enumeration loop
        was silently DROPPING any Locale-typed override (e.g. CharLocale)
        before this -- confirmed live: setting CharLocale to a genuinely
        different value than the document default registered as real
        PropertyState.DIRECT_VALUE, but never appeared in the tool's own
        output, because the un-converted Locale struct then failed
        _is_json_safe() and get_direct_formatting() silently excludes
        (not warns on) anything that fails that check. Was previously two
        separate, narrower converters -- this one (Enum/Size only) and
        uno_datetime.py's own uno_temporal_value_to_plain() (Date/
        DateTime/Duration only, used from exactly one call site,
        get_custom_properties) -- merged into one so every one of this
        method's ~10 call sites benefits from both, not just whichever
        one a given call site happened to already import. Still not a
        fully general UNO-struct converter -- anything else passes
        through unchanged and falls back to str() at the HTTP JSON-
        encoding boundary (ai_interface.py's json.dumps(default=str)).
        """
        if isinstance(value, uno.Enum):
            return value.value
        temporal = uno_temporal_value_to_plain(value)
        if temporal is not value:
            return temporal
        if hasattr(value, "X") and hasattr(value, "Y") and hasattr(value, "Width") and hasattr(value, "Height"):
            return {"x": value.X, "y": value.Y, "width": value.Width, "height": value.Height}
        if hasattr(value, "Width") and hasattr(value, "Height"):
            return {"width": value.Width, "height": value.Height}
        if hasattr(value, "X") and hasattr(value, "Y"):
            return {"x": value.X, "y": value.Y}
        if hasattr(value, "Language") and hasattr(value, "Country"):
            return f"{value.Language}-{value.Country}" if value.Country else value.Language
        return value

    @staticmethod
    def _is_json_safe(value: Any) -> bool:
        """True if `value` is a plain type json.dumps can serialize without
        falling back to ai_interface.py's json.dumps(default=str) -- which
        would silently dump a UNO object reference's opaque repr string
        (live-verified this happening for a Writer paragraph's
        TextParagraph property, a self-reference to the paragraph object
        itself, when enumerating all properties on a text range).
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return True
        if isinstance(value, (list, tuple)):
            return all(UNOBridge._is_json_safe(v) for v in value)
        if isinstance(value, dict):
            return all(isinstance(k, str) and UNOBridge._is_json_safe(v) for k, v in value.items())
        return False

    def get_print_settings(self, doc: Any) -> Dict[str, Any]:
        printer_props = doc.getPrinter()
        return {p.Name: self._uno_value_to_plain(p.Value) for p in printer_props}

    def set_print_settings(self, doc: Any, settings: Dict[str, Any]) -> None:
        doc.setPrinter(tuple(PropertyValue(k, 0, v, 0) for k, v in settings.items()))

    def print_document(self, doc: Any, printer: Optional[str] = None, page_range: Optional[str] = None,
                        copies: int = 1, options: Optional[Dict[str, Any]] = None) -> None:
        """Print via XPrintable. Not live-verified against a physical/virtual
        printer (none available in this environment) -- unit-tested with
        fakes only; treat as higher-risk than the rest of this module until
        a senior engineer validates it against a real printer."""
        if printer:
            doc.setPrinter((PropertyValue("Name", 0, printer, 0),))
        props = [PropertyValue("CopyCount", 0, copies, 0), PropertyValue("Wait", 0, True, 0)]
        if page_range:
            props.append(PropertyValue("Pages", 0, page_range, 0))
        if options:
            for key, value in options.items():
                props.append(PropertyValue(key, 0, value, 0))
        doc.print(tuple(props))

    def get_text_content(self, doc: Any = None) -> Dict[str, Any]:
        """Get text content from a document"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            # Check if it's a Writer document
            is_writer = _is_instance(doc, XTextDocument) or \
                        (hasattr(doc, 'supportsService') and doc.supportsService("com.sun.star.text.TextDocument")) or \
                        hasattr(doc, 'getText')

            if is_writer:
                text = doc.getText().getString()
                return {"success": True, "content": text, "length": len(text)}
            else:
                return {"success": False, "error": f"Text extraction not supported for {self._get_document_type(doc)}"}
                
        except Exception as e:
            logger.error(f"Failed to get text content: {e}")
            return {"success": False, "error": str(e)}
    
    def get_comments(self, doc: Any = None) -> Dict[str, Any]:
        """Get all comments/annotations from the document"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            comments = []

            # Try to get text fields enumeration (comments are stored as text fields)
            if hasattr(doc, 'getTextFields'):
                text_fields = doc.getTextFields()
                enum = text_fields.createEnumeration()

                while enum.hasMoreElements():
                    field = enum.nextElement()
                    # Check if it's an annotation (comment)
                    if hasattr(field, 'supportsService') and field.supportsService("com.sun.star.text.TextField.Annotation"):
                        comment_data = {
                            # Added so update_comment_live/delete_comment_live/
                            # resolve_comment_live (writer_text.py) can address
                            # this exact comment -- see _comment_id_for()'s
                            # docstring for what this id is (and isn't).
                            "id": self._comment_id_for(field, len(comments)),
                            "author": field.Author if hasattr(field, 'Author') else "",
                            "content": field.Content if hasattr(field, 'Content') else "",
                            # str(field.Date) previously produced the raw UNO
                            # struct repr ("(com.sun.star.util.DateTime){
                            # NanoSeconds = ... }"), not a readable date --
                            # hardening-pass finding (#33). Live-verified
                            # field.Date is actually com.sun.star.util.Date
                            # (date-only, no Hours/Minutes/Seconds) despite
                            # the property name suggesting DateTime -- an
                            # earlier version of this fix used uno_datetime_
                            # to_iso() (which requires those fields) and
                            # silently returned None even for a genuinely
                            # set date, caught by testing with a real,
                            # non-zero date via a plain duck-typed fake
                            # rather than trusting the property name. Uses
                            # the duck-typed dispatcher instead of assuming
                            # the specific struct shape.
                            "date": uno_temporal_value_to_plain(field.Date) if hasattr(field, 'Date') else "",
                        }
                        # Try to get the anchor text (what the comment is attached to)
                        if hasattr(field, 'getAnchor'):
                            anchor = field.getAnchor()
                            if hasattr(anchor, 'getString'):
                                comment_data["anchor_text"] = anchor.getString()[:100]  # First 100 chars
                        comments.append(comment_data)

            return {"success": True, "comments": comments, "count": len(comments)}

        except Exception as e:
            logger.error(f"Failed to get comments: {e}")
            return {"success": False, "error": str(e)}

    def add_comment(self, text: str, author: str = "AI Assistant", doc: Any = None) -> Dict[str, Any]:
        """Add a comment at the current cursor position"""
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            # Get the current cursor position
            controller = doc.getCurrentController()
            cursor = controller.getViewCursor()

            # Create annotation field
            annotation = doc.createInstance("com.sun.star.text.TextField.Annotation")
            annotation.Content = text
            annotation.Author = author

            # Insert at cursor position
            text_obj = doc.getText()
            text_obj.insertTextContent(cursor, annotation, False)

            logger.info(f"Added comment by {author}: {text[:50]}...")
            return {"success": True, "message": f"Comment added by {author}"}

        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            return {"success": False, "error": str(e)}

    # ============== Track Changes Tools ==============

    def get_track_changes_status(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get Track Changes status for the document.

        Args:
            doc: Document to check (None for active document)

        Returns:
            Result dictionary with recording, showing, and pending_count
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            # Get RecordChanges and ShowChanges properties
            recording = False
            showing = False
            pending_count = 0
            # recording/showing/pending_count default to the same False/0
            # a genuinely-off document reports. Without this, a read
            # failure here (e.g. the interface is present per hasattr()
            # but getPropertyValue() still raises) is silently
            # indistinguishable from "track changes is genuinely off" in
            # a "success": true response. warnings makes that visible.
            warnings: List[str] = []

            # Access document properties via XPropertySet
            if hasattr(doc, 'getPropertyValue'):
                try:
                    recording = doc.getPropertyValue("RecordChanges")
                except Exception as e:
                    warnings.append(f"Could not read RecordChanges: {e}")
                try:
                    showing = doc.getPropertyValue("ShowChanges")
                except Exception as e:
                    warnings.append(f"Could not read ShowChanges: {e}")

            # Count pending redlines using XRedlinesSupplier
            if hasattr(doc, 'getRedlines'):
                try:
                    redlines = doc.getRedlines()
                    if redlines:
                        pending_count = redlines.getCount()
                except Exception as e:
                    warnings.append(f"Could not count pending redlines: {e}")

            logger.info(f"Track Changes status: recording={recording}, showing={showing}, pending={pending_count}")
            result = {
                "success": True,
                "recording": recording,
                "showing": showing,
                "pending_count": pending_count
            }
            if warnings:
                result["warnings"] = warnings
            return result

        except Exception as e:
            logger.error(f"Failed to get track changes status: {e}")
            return {"success": False, "error": str(e)}

    def set_track_changes(self, enabled: bool, show: bool = True, doc: Any = None) -> Dict[str, Any]:
        """
        Enable or disable Track Changes recording.

        Args:
            enabled: Whether to enable Track Changes recording
            show: Whether to show tracked changes (default: True)
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with new state
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            # Set properties via XPropertySet
            if hasattr(doc, 'setPropertyValue'):
                try:
                    doc.setPropertyValue("RecordChanges", enabled)
                except Exception as e:
                    return {"success": False, "error": f"Cannot set RecordChanges: {e}"}
                try:
                    doc.setPropertyValue("ShowChanges", show)
                except Exception as e:
                    return {"success": False, "error": f"Cannot set ShowChanges: {e}"}
            else:
                return {"success": False, "error": "Document does not support property modification"}

            logger.info(f"Set Track Changes: recording={enabled}, showing={show}")
            return {
                "success": True,
                "recording": enabled,
                "showing": show
            }

        except Exception as e:
            logger.error(f"Failed to set track changes: {e}")
            return {"success": False, "error": str(e)}

    def get_tracked_changes(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get list of all tracked changes in the document.

        Args:
            doc: Document to check (None for active document)

        Returns:
            Result dictionary with list of changes
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            changes = []

            # Get redlines using XRedlinesSupplier
            if hasattr(doc, 'getRedlines'):
                redlines = doc.getRedlines()
                if redlines:
                    for i in range(redlines.getCount()):
                        try:
                            redline = redlines.getByIndex(i)

                            # Get redline properties
                            redline_type = ""
                            if hasattr(redline, 'RedlineType'):
                                redline_type = redline.RedlineType

                            text = ""
                            if hasattr(redline, 'getText'):
                                text_obj = redline.getText()
                                if text_obj and hasattr(text_obj, 'getString'):
                                    text = text_obj.getString()

                            author = ""
                            if hasattr(redline, 'RedlineAuthor'):
                                author = redline.RedlineAuthor

                            date_str = ""
                            if hasattr(redline, 'RedlineDateTime'):
                                dt = redline.RedlineDateTime
                                # Format as ISO string
                                date_str = f"{dt.Year:04d}-{dt.Month:02d}-{dt.Day:02d}T{dt.Hours:02d}:{dt.Minutes:02d}:{dt.Seconds:02d}"

                            description = ""
                            if hasattr(redline, 'RedlineComment'):
                                description = redline.RedlineComment

                            changes.append({
                                "index": i,
                                "type": redline_type.lower() if redline_type else "unknown",
                                "text": text[:500] if text else "",  # Limit text length
                                "author": author,
                                "date": date_str,
                                "description": description
                            })
                        except Exception as e:
                            logger.warning(f"Failed to read redline {i}: {e}")
                            continue

            logger.info(f"Found {len(changes)} tracked changes")
            return {
                "success": True,
                "changes": changes,
                "count": len(changes)
            }

        except Exception as e:
            logger.error(f"Failed to get tracked changes: {e}")
            return {"success": False, "error": str(e)}

    def accept_tracked_change(self, index: int, doc: Any = None) -> Dict[str, Any]:
        """
        Accept a specific tracked change by index.

        Args:
            index: Index of the change to accept (0-based)
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with accepted index
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": False, "error": "No tracked changes in document"}

            count = redlines.getCount()
            if index < 0 or index >= count:
                return {"success": False, "error": f"Index {index} out of range. Valid range: 0-{count-1}"}

            # Get the redline and accept it
            redline = redlines.getByIndex(index)

            # Accept by getting the text range and accepting via the document
            if hasattr(redline, 'getAnchor'):
                anchor = redline.getAnchor()
                if hasattr(anchor, 'getString'):
                    # Use the document's text to accept the redline
                    text = doc.getText()
                    if hasattr(text, 'createTextCursor'):
                        cursor = text.createTextCursorByRange(anchor)
                        # Accept redline - in UNO API, accepting means the change becomes permanent
                        if hasattr(doc, 'acceptRedline'):
                            doc.acceptRedline(index)
                        else:
                            # Alternative: use dispatcher
                            return {"success": False, "error": "Document does not support acceptRedline method"}

            logger.info(f"Accepted tracked change at index {index}")
            return {
                "success": True,
                "accepted_index": index
            }

        except Exception as e:
            logger.error(f"Failed to accept tracked change: {e}")
            return {"success": False, "error": str(e)}

    def reject_tracked_change(self, index: int, doc: Any = None) -> Dict[str, Any]:
        """
        Reject a specific tracked change by index.

        Args:
            index: Index of the change to reject (0-based)
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with rejected index
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": False, "error": "No tracked changes in document"}

            count = redlines.getCount()
            if index < 0 or index >= count:
                return {"success": False, "error": f"Index {index} out of range. Valid range: 0-{count-1}"}

            # Reject the redline
            if hasattr(doc, 'rejectRedline'):
                doc.rejectRedline(index)
            else:
                return {"success": False, "error": "Document does not support rejectRedline method"}

            logger.info(f"Rejected tracked change at index {index}")
            return {
                "success": True,
                "rejected_index": index
            }

        except Exception as e:
            logger.error(f"Failed to reject tracked change: {e}")
            return {"success": False, "error": str(e)}

    def accept_all_changes(self, doc: Any = None) -> Dict[str, Any]:
        """
        Accept all tracked changes in the document.

        Args:
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with count of accepted changes
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": True, "accepted_count": 0}

            count = redlines.getCount()
            if count == 0:
                return {"success": True, "accepted_count": 0}

            # Accept in reverse order to avoid index shifting
            accepted = 0
            for i in range(count - 1, -1, -1):
                try:
                    if hasattr(doc, 'acceptRedline'):
                        doc.acceptRedline(i)
                        accepted += 1
                except Exception as e:
                    logger.warning(f"Failed to accept redline {i}: {e}")

            logger.info(f"Accepted {accepted} tracked changes")
            return {
                "success": True,
                "accepted_count": accepted
            }

        except Exception as e:
            logger.error(f"Failed to accept all changes: {e}")
            return {"success": False, "error": str(e)}

    def reject_all_changes(self, doc: Any = None) -> Dict[str, Any]:
        """
        Reject all tracked changes in the document.

        Args:
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with count of rejected changes
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Track Changes not supported for {doc_type} documents"}

            if not hasattr(doc, 'getRedlines'):
                return {"success": False, "error": "Document does not support redlines"}

            redlines = doc.getRedlines()
            if not redlines:
                return {"success": True, "rejected_count": 0}

            count = redlines.getCount()
            if count == 0:
                return {"success": True, "rejected_count": 0}

            # Reject in reverse order to avoid index shifting
            rejected = 0
            for i in range(count - 1, -1, -1):
                try:
                    if hasattr(doc, 'rejectRedline'):
                        doc.rejectRedline(i)
                        rejected += 1
                except Exception as e:
                    logger.warning(f"Failed to reject redline {i}: {e}")

            logger.info(f"Rejected {rejected} tracked changes")
            return {
                "success": True,
                "rejected_count": rejected
            }

        except Exception as e:
            logger.error(f"Failed to reject all changes: {e}")
            return {"success": False, "error": str(e)}

    def _is_in_tracked_deletion(self, text_range: Any, doc: Any = None) -> bool:
        """
        Check if a text range is within a tracked deletion.

        Args:
            text_range: The text range to check
            doc: Document to check (None for active document)

        Returns:
            True if range is in a tracked deletion, False otherwise
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc or not hasattr(doc, 'getRedlines'):
                return False

            redlines = doc.getRedlines()
            if not redlines:
                return False

            text = doc.getText()

            for i in range(redlines.getCount()):
                try:
                    redline = redlines.getByIndex(i)

                    # Only check deletion redlines
                    if hasattr(redline, 'RedlineType'):
                        redline_type = redline.RedlineType
                        if redline_type and redline_type.lower() == "delete":
                            # Get redline anchor/range
                            if hasattr(redline, 'getAnchor'):
                                redline_range = redline.getAnchor()

                                # Compare ranges
                                # Check if text_range start is within redline range
                                try:
                                    start_compare = text.compareRegionStarts(text_range, redline_range)
                                    end_compare = text.compareRegionEnds(text_range, redline_range)

                                    # If text_range is fully contained within redline_range
                                    # start_compare >= 0 means text_range starts at or after redline start
                                    # end_compare <= 0 means text_range ends at or before redline end
                                    if start_compare >= 0 and end_compare <= 0:
                                        return True
                                except Exception:
                                    pass
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.warning(f"Error checking tracked deletion: {e}")
            return False

    # ============== Enhanced Editing Tools ==============

    def get_paragraph_count(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get the total number of paragraphs in the document.

        Args:
            doc: Document to analyze (None for active document)

        Returns:
            Result dictionary with paragraph count
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            # Check if it's a Writer document
            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph count not supported for {doc_type} documents"}

            # Get text and enumerate paragraphs
            text = doc.getText()
            enum = text.createEnumeration()

            count = 0
            while enum.hasMoreElements():
                para = enum.nextElement()
                # Check if it's a paragraph (not a table or other content)
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    count += 1

            logger.info(f"Document has {count} paragraphs")
            return {"success": True, "count": count}

        except Exception as e:
            logger.error(f"Failed to get paragraph count: {e}")
            return {"success": False, "error": str(e)}

    def get_document_outline(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get document outline (headings) with paragraph numbers and levels.

        Args:
            doc: Document to analyze (None for active document)

        Returns:
            Result dictionary with outline and paragraph count
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Document outline not supported for {doc_type} documents"}

            text = doc.getText()
            enum = text.createEnumeration()

            outline = []
            paragraph_count = 0

            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    paragraph_count += 1

                    # Check if paragraph has a heading style
                    if hasattr(para, 'ParaStyleName'):
                        style_name = para.ParaStyleName
                        # Check for Heading 1-6 styles
                        if style_name and style_name.startswith("Heading"):
                            try:
                                level = int(style_name.replace("Heading ", "").replace("Heading", "1"))
                            except ValueError:
                                level = 1

                            # Get paragraph text
                            para_text = para.getString() if hasattr(para, 'getString') else ""

                            outline.append({
                                "paragraph": paragraph_count,
                                "level": level,
                                "text": para_text[:200]  # Limit text length
                            })

            logger.info(f"Document outline: {len(outline)} headings, {paragraph_count} paragraphs")
            return {
                "success": True,
                "outline": outline,
                "heading_count": len(outline),
                "paragraph_count": paragraph_count
            }

        except Exception as e:
            logger.error(f"Failed to get document outline: {e}")
            return {"success": False, "error": str(e)}

    def get_paragraph(self, n: int, doc: Any = None) -> Dict[str, Any]:
        """
        Get the content of a specific paragraph by number (1-indexed).

        Args:
            n: Paragraph number (1-indexed)
            doc: Document to read from (None for active document)

        Returns:
            Result dictionary with paragraph content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph access not supported for {doc_type} documents"}

            if n < 1:
                return {"success": False, "error": "Paragraph number must be >= 1"}

            text = doc.getText()
            enum = text.createEnumeration()

            current = 0
            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    if current == n:
                        content = para.getString() if hasattr(para, 'getString') else ""

                        # Build result with original content
                        result = {
                            "success": True,
                            "paragraph_number": n,
                            "content": content
                        }

                        # Add visible_content if Track Changes is enabled
                        tc_status = self.get_track_changes_status(doc)
                        if tc_status.get("success") and tc_status.get("recording"):
                            # Filter out tracked deletions
                            visible_content = self._filter_tracked_deletions(para, doc)
                            result["visible_content"] = visible_content

                        logger.info(f"Retrieved paragraph {n}")
                        return result

            # Paragraph not found
            return {
                "success": False,
                "error": f"Paragraph {n} out of range. Valid range: 1-{current}"
            }

        except Exception as e:
            logger.error(f"Failed to get paragraph: {e}")
            return {"success": False, "error": str(e)}

    def _filter_tracked_deletions(self, para: Any, doc: Any) -> str:
        """
        Filter out tracked deletions from paragraph content.

        Args:
            para: Paragraph text element
            doc: Document containing the paragraph

        Returns:
            String with tracked deletions filtered out
        """
        try:
            if not hasattr(doc, 'getRedlines'):
                return para.getString() if hasattr(para, 'getString') else ""

            redlines = doc.getRedlines()
            if not redlines or redlines.getCount() == 0:
                return para.getString() if hasattr(para, 'getString') else ""

            # Get paragraph range
            para_start = para.getStart()
            para_end = para.getEnd()
            text = doc.getText()

            # Collect all deletion ranges within this paragraph
            deletion_ranges = []
            for i in range(redlines.getCount()):
                try:
                    redline = redlines.getByIndex(i)

                    # Only check deletion redlines
                    if hasattr(redline, 'RedlineType'):
                        redline_type = redline.RedlineType
                        if redline_type and redline_type.lower() == "delete":
                            if hasattr(redline, 'getAnchor'):
                                redline_range = redline.getAnchor()

                                # Check if deletion overlaps with this paragraph
                                try:
                                    # Use compareRegionStarts/Ends to check overlap
                                    # If deletion is within paragraph, add to list
                                    deletion_ranges.append(redline_range)
                                except Exception:
                                    pass
                except Exception:
                    continue

            # If no deletions, return original text
            if not deletion_ranges:
                return para.getString() if hasattr(para, 'getString') else ""

            # Build visible content by iterating through paragraph portions
            visible_text = []
            if hasattr(para, 'createEnumeration'):
                portion_enum = para.createEnumeration()
                while portion_enum.hasMoreElements():
                    portion = portion_enum.nextElement()

                    # Check if this portion is in a tracked deletion
                    is_deleted = False
                    for del_range in deletion_ranges:
                        try:
                            # Check if portion overlaps with deletion
                            if self._is_in_tracked_deletion(portion, doc):
                                is_deleted = True
                                break
                        except Exception:
                            pass

                    # Add portion text if not deleted
                    if not is_deleted and hasattr(portion, 'getString'):
                        visible_text.append(portion.getString())
            else:
                # Fallback to full paragraph text if can't enumerate portions
                return para.getString() if hasattr(para, 'getString') else ""

            return ''.join(visible_text)

        except Exception as e:
            logger.warning(f"Failed to filter tracked deletions: {e}")
            # Fallback to original content
            return para.getString() if hasattr(para, 'getString') else ""

    def get_paragraphs_range(self, start: int, end: int, doc: Any = None) -> Dict[str, Any]:
        """
        Get content of paragraphs in a range (inclusive, 1-indexed).

        Args:
            start: Starting paragraph number (1-indexed)
            end: Ending paragraph number (inclusive)
            doc: Document to read from (None for active document)

        Returns:
            Result dictionary with paragraphs content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph access not supported for {doc_type} documents"}

            if start < 1:
                return {"success": False, "error": "Start paragraph must be >= 1"}
            if end < start:
                return {"success": False, "error": "End paragraph must be >= start paragraph"}

            text = doc.getText()
            enum = text.createEnumeration()

            paragraphs = []
            current = 0
            total_paragraphs = 0

            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    total_paragraphs = current

                    if start <= current <= end:
                        content = para.getString() if hasattr(para, 'getString') else ""
                        paragraphs.append({
                            "number": current,
                            "content": content
                        })

                    if current > end:
                        break

            if not paragraphs:
                return {
                    "success": False,
                    "error": f"Range {start}-{end} out of bounds. Document has {total_paragraphs} paragraphs"
                }

            logger.info(f"Retrieved paragraphs {start}-{end}")
            return {
                "success": True,
                "paragraphs": paragraphs,
                "count": len(paragraphs)
            }

        except Exception as e:
            logger.error(f"Failed to get paragraphs range: {e}")
            return {"success": False, "error": str(e)}

    # ============== Cursor Navigation Tools ==============

    def goto_paragraph(self, n: int, doc: Any = None) -> Dict[str, Any]:
        """
        Move the view cursor to the beginning of paragraph n.

        Args:
            n: Paragraph number (1-indexed)
            doc: Document to navigate (None for active document)

        Returns:
            Result dictionary with cursor position
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor navigation not supported for {doc_type} documents"}

            if n < 1:
                return {"success": False, "error": "Paragraph number must be >= 1"}

            text = doc.getText()
            enum = text.createEnumeration()

            current = 0
            target_para = None
            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    if current == n:
                        target_para = para
                        break

            if target_para is None:
                return {"success": False, "error": f"Paragraph {n} out of range. Valid range: 1-{current}"}

            # Get the view cursor and move it to the paragraph start
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Get paragraph start position
            para_start = target_para.getStart()
            view_cursor.gotoRange(para_start, False)

            logger.info(f"Moved cursor to paragraph {n}")
            return {
                "success": True,
                "message": f"Cursor moved to paragraph {n}",
                "paragraph": n
            }

        except Exception as e:
            logger.error(f"Failed to goto paragraph: {e}")
            return {"success": False, "error": str(e)}

    def goto_position(self, char_pos: int, doc: Any = None) -> Dict[str, Any]:
        """
        Move the view cursor to a specific character position.

        Args:
            char_pos: Character position (0-indexed)
            doc: Document to navigate (None for active document)

        Returns:
            Result dictionary with actual position reached
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor navigation not supported for {doc_type} documents"}

            if char_pos < 0:
                return {"success": False, "error": "Character position must be >= 0"}

            text = doc.getText()
            text_cursor = text.createTextCursor()
            text_cursor.gotoStart(False)

            # Move to position (goRight returns False if it can't move that far)
            actual_moved = 0
            if char_pos > 0:
                moved = text_cursor.goRight(char_pos, False)
                # Count actual position
                text_cursor_check = text.createTextCursor()
                text_cursor_check.gotoStart(False)
                text_cursor_check.gotoRange(text_cursor, True)
                actual_moved = len(text_cursor_check.getString())

            # Move view cursor to this position
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            view_cursor.gotoRange(text_cursor, False)

            logger.info(f"Moved cursor to position {actual_moved}")
            return {
                "success": True,
                "message": f"Cursor moved to position {actual_moved}",
                "position": actual_moved,
                "requested_position": char_pos
            }

        except Exception as e:
            logger.error(f"Failed to goto position: {e}")
            return {"success": False, "error": str(e)}

    def get_cursor_position(self, doc: Any = None) -> Dict[str, Any]:
        """
        Get the current cursor character position and paragraph number.

        Args:
            doc: Document to check (None for active document)

        Returns:
            Result dictionary with position and paragraph info
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor position not supported for {doc_type} documents"}

            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Get character position by measuring from start
            text = doc.getText()
            text_cursor = text.createTextCursor()
            text_cursor.gotoStart(False)
            text_cursor.gotoRange(view_cursor, True)
            char_position = len(text_cursor.getString())

            # Find paragraph number
            enum = text.createEnumeration()
            paragraph_num = 0
            char_count = 0

            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    paragraph_num += 1
                    para_text = para.getString() if hasattr(para, 'getString') else ""
                    char_count += len(para_text) + 1  # +1 for paragraph break

                    if char_count >= char_position:
                        break

            logger.info(f"Cursor at position {char_position}, paragraph {paragraph_num}")
            return {
                "success": True,
                "position": char_position,
                "paragraph": paragraph_num
            }

        except Exception as e:
            logger.error(f"Failed to get cursor position: {e}")
            return {"success": False, "error": str(e)}

    def get_context_around_cursor(self, chars: int = 100, doc: Any = None) -> Dict[str, Any]:
        """
        Get text context around the current cursor position.

        Args:
            chars: Number of characters to get before and after cursor
            doc: Document to read from (None for active document)

        Returns:
            Result dictionary with text before and after cursor
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Cursor context not supported for {doc_type} documents"}

            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text = doc.getText()

            # Get text before cursor
            before_cursor = text.createTextCursor()
            before_cursor.gotoStart(False)
            before_cursor.gotoRange(view_cursor, True)
            full_before = before_cursor.getString()
            text_before = full_before[-chars:] if len(full_before) > chars else full_before

            # Get text after cursor
            after_cursor = text.createTextCursor()
            after_cursor.gotoRange(view_cursor, False)
            after_cursor.gotoEnd(True)
            full_after = after_cursor.getString()
            text_after = full_after[:chars] if len(full_after) > chars else full_after

            # Get current position
            char_position = len(full_before)

            logger.info(f"Got context around position {char_position}")
            return {
                "success": True,
                "before": text_before,
                "after": text_after,
                "position": char_position,
                "chars_requested": chars
            }

        except Exception as e:
            logger.error(f"Failed to get context around cursor: {e}")
            return {"success": False, "error": str(e)}

    # ============== Text Selection Tools ==============

    def select_paragraph(self, n: int, doc: Any = None) -> Dict[str, Any]:
        """
        Select entire paragraph n (1-indexed).

        Args:
            n: Paragraph number (1-indexed)
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with selected text content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Paragraph selection not supported for {doc_type} documents"}

            if n < 1:
                return {"success": False, "error": "Paragraph number must be >= 1"}

            # Find the paragraph
            text = doc.getText()
            enum = text.createEnumeration()

            current = 0
            target_para = None
            while enum.hasMoreElements():
                para = enum.nextElement()
                if hasattr(para, 'supportsService') and para.supportsService("com.sun.star.text.Paragraph"):
                    current += 1
                    if current == n:
                        target_para = para
                        break

            if target_para is None:
                return {"success": False, "error": f"Paragraph {n} out of range. Valid range: 1-{current}"}

            # Get the view cursor and select the paragraph
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Move to paragraph start
            para_start = target_para.getStart()
            view_cursor.gotoRange(para_start, False)

            # Extend selection to paragraph end
            para_end = target_para.getEnd()
            view_cursor.gotoRange(para_end, True)

            # Get selected text
            selected_text = target_para.getString() if hasattr(target_para, 'getString') else ""

            logger.info(f"Selected paragraph {n}")
            return {
                "success": True,
                "selected_text": selected_text,
                "paragraph": n
            }

        except Exception as e:
            logger.error(f"Failed to select paragraph: {e}")
            return {"success": False, "error": str(e)}

    def select_text_range(self, start: int, end: int, doc: Any = None) -> Dict[str, Any]:
        """
        Select text from start to end character positions (0-indexed).

        Args:
            start: Starting character position (0-indexed)
            end: Ending character position (exclusive)
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with selected text
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Text range selection not supported for {doc_type} documents"}

            if start < 0:
                return {"success": False, "error": "Start position must be >= 0"}
            if end < start:
                return {"success": False, "error": "End position must be >= start position"}

            text = doc.getText()
            controller = doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Create text cursor for selection
            text_cursor = text.createTextCursor()
            text_cursor.gotoStart(False)

            # Move to start position
            if start > 0:
                text_cursor.goRight(start, False)

            # Store start position
            start_range = text.createTextCursor()
            start_range.gotoRange(text_cursor, False)

            # Move to end position (selecting)
            length = end - start
            if length > 0:
                text_cursor.goRight(length, True)

            # Get selected text
            selected_text = text_cursor.getString()

            # Move view cursor to match selection
            view_cursor.gotoRange(start_range, False)
            view_cursor.gotoRange(text_cursor, True)

            logger.info(f"Selected text range {start}-{end}")
            return {
                "success": True,
                "selected_text": selected_text,
                "start": start,
                "end": end,
                "length": len(selected_text)
            }

        except Exception as e:
            logger.error(f"Failed to select text range: {e}")
            return {"success": False, "error": str(e)}

    def delete_selection(self, doc: Any = None) -> Dict[str, Any]:
        """
        Delete currently selected text.

        Args:
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with deleted text content
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Delete selection not supported for {doc_type} documents"}

            # Get current selection
            controller = doc.getCurrentController()
            selection = controller.getSelection()

            if selection.getCount() == 0:
                return {"success": False, "error": "No text selected"}

            # Get the selected text range
            text_range = selection.getByIndex(0)

            # Get the text before deleting
            deleted_text = text_range.getString()

            # Delete by setting empty string
            text_range.setString("")

            logger.info(f"Deleted selection: {len(deleted_text)} characters")
            return {
                "success": True,
                "deleted_text": deleted_text,
                "length": len(deleted_text)
            }

        except Exception as e:
            logger.error(f"Failed to delete selection: {e}")
            return {"success": False, "error": str(e)}

    def replace_selection(self, text: str, doc: Any = None) -> Dict[str, Any]:
        """
        Replace currently selected text with new text.

        Args:
            text: New text to replace selection with
            doc: Document to work with (None for active document)

        Returns:
            Result dictionary with old and new text
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Replace selection not supported for {doc_type} documents"}

            # Get current selection
            controller = doc.getCurrentController()
            selection = controller.getSelection()

            if selection.getCount() == 0:
                return {"success": False, "error": "No text selected"}

            # Get the selected text range
            text_range = selection.getByIndex(0)

            # Get the old text
            old_text = text_range.getString()

            # Replace with new text
            text_range.setString(text)

            logger.info(f"Replaced selection: {len(old_text)} -> {len(text)} characters")
            return {
                "success": True,
                "old_text": old_text,
                "new_text": text,
                "old_length": len(old_text),
                "new_length": len(text)
            }

        except Exception as e:
            logger.error(f"Failed to replace selection: {e}")
            return {"success": False, "error": str(e)}

    # ============== Search and Replace Tools ==============

    def find_text(self, query: str, doc: Any = None) -> Dict[str, Any]:
        """
        Find all occurrences of query string in the document.

        Args:
            query: String to search for
            doc: Document to search in (None for active document)

        Returns:
            Result dictionary with list of matches and their positions
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Text search not supported for {doc_type} documents"}

            # Check if Track Changes is enabled
            track_changes_active = False
            warnings: List[str] = []
            if hasattr(doc, 'getPropertyValue'):
                try:
                    recording = doc.getPropertyValue("RecordChanges")
                    showing = doc.getPropertyValue("ShowChanges")
                    track_changes_active = recording or showing
                except Exception as e:
                    # track_changes_active silently staying False here is
                    # indistinguishable from "genuinely off" in the
                    # response below without this warning -- and a False
                    # here also silently skips the tracked-deletion filter
                    # a few lines down, which would leak deleted text into
                    # search results.
                    warnings.append(f"Could not read RecordChanges/ShowChanges: {e}")

            # Create search descriptor
            search = doc.createSearchDescriptor()
            search.SearchString = query

            # Find all occurrences
            found = doc.findAll(search)

            matches = []
            if found and found.getCount() > 0:
                text = doc.getText()

                for i in range(found.getCount()):
                    match_range = found.getByIndex(i)

                    # Filter out matches in tracked deletions when Track Changes is active
                    if track_changes_active and self._is_in_tracked_deletion(match_range, doc):
                        continue

                    # Calculate character position from start
                    text_cursor = text.createTextCursor()
                    text_cursor.gotoStart(False)
                    text_cursor.gotoRange(match_range.getStart(), True)
                    position = len(text_cursor.getString())

                    # Get matched text
                    matched_text = match_range.getString()

                    matches.append({
                        "position": position,
                        "text": matched_text
                    })

            logger.info(f"Found {len(matches)} occurrences of '{query}' (Track Changes: {track_changes_active})")
            result = {
                "success": True,
                "matches": matches,
                "count": len(matches),
                "query": query,
                "track_changes_active": track_changes_active
            }
            if warnings:
                result["warnings"] = warnings
            return result

        except Exception as e:
            logger.error(f"Failed to find text: {e}")
            return {"success": False, "error": str(e)}

    def find_and_replace(self, old: str, new: str, doc: Any = None) -> Dict[str, Any]:
        """
        Find and replace the first occurrence of old with new.

        When Track Changes is enabled, only replaces visible text occurrences,
        skipping matches that are within tracked deletions.

        Args:
            old: String to find
            new: String to replace with
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with replacement status and position
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Find and replace not supported for {doc_type} documents"}

            # Check if Track Changes is enabled
            track_changes_status = self.get_track_changes_status(doc)
            track_changes_active = track_changes_status.get("success") and track_changes_status.get("recording", False)

            # Create search descriptor
            search = doc.createSearchDescriptor()
            search.SearchString = old

            # Find first occurrence
            found = doc.findFirst(search)

            # If Track Changes is active, skip matches in tracked deletions
            if track_changes_active and found:
                while found and self._is_in_tracked_deletion(found, doc):
                    # Continue searching for next match
                    found = doc.findNext(found.getEnd(), search)

            if found:
                # Calculate position before replacement
                text = doc.getText()
                text_cursor = text.createTextCursor()
                text_cursor.gotoStart(False)
                text_cursor.gotoRange(found.getStart(), True)
                position = len(text_cursor.getString())

                # Replace the text
                found.setString(new)

                logger.info(f"Replaced first occurrence of '{old}' with '{new}' at position {position}")
                return {
                    "success": True,
                    "replaced": True,
                    "position": position,
                    "old": old,
                    "new": new
                }
            else:
                logger.info(f"No occurrence of '{old}' found")
                return {
                    "success": True,
                    "replaced": False,
                    "old": old,
                    "new": new
                }

        except Exception as e:
            logger.error(f"Failed to find and replace: {e}")
            return {"success": False, "error": str(e)}

    def find_and_replace_all(self, old: str, new: str, doc: Any = None) -> Dict[str, Any]:
        """
        Find and replace all occurrences of old with new.

        Track Changes aware: When Track Changes is enabled, this method iterates
        through matches manually to skip replacements in tracked deletions.
        When Track Changes is disabled, it uses native replaceAll for performance.

        Args:
            old: String to find
            new: String to replace with
            doc: Document to modify (None for active document)

        Returns:
            Result dictionary with count of replacements
        """
        try:
            if doc is None:
                doc = self.get_active_document()

            if not doc:
                return {"success": False, "error": "No document available"}

            doc_type = self._get_document_type(doc)
            if doc_type != "writer":
                return {"success": False, "error": f"Find and replace all not supported for {doc_type} documents"}

            # Check if Track Changes is enabled
            track_changes_active = False
            warnings: List[str] = []
            if hasattr(doc, 'getPropertyValue'):
                try:
                    track_changes_active = doc.getPropertyValue("RecordChanges")
                except Exception as e:
                    # A read failure here silently falls through to the
                    # "Track Changes disabled" fast path below (native
                    # replaceAll, which does NOT skip tracked deletions),
                    # exactly as if RecordChanges genuinely were False.
                    # Preserving that existing behavior per the no-success-
                    # path-changes rule, but a caller needs to be able to
                    # tell "genuinely off" from "read failed, replaceAll ran
                    # without the tracked-deletion guard it would normally
                    # get."
                    warnings.append(f"Could not read RecordChanges: {e}")

            # If Track Changes is disabled, use native replaceAll for performance
            if not track_changes_active:
                replace = doc.createReplaceDescriptor()
                replace.SearchString = old
                replace.ReplaceString = new
                count = doc.replaceAll(replace)

                logger.info(f"Replaced {count} occurrences of '{old}' with '{new}' (Track Changes disabled)")
                result = {
                    "success": True,
                    "count": count,
                    "old": old,
                    "new": new,
                    "track_changes_active": False
                }
                if warnings:
                    result["warnings"] = warnings
                return result

            # Track Changes is enabled - must iterate manually to skip tracked deletions
            # Native replaceAll ignores Track Changes, so we use findFirst/findNext
            search = doc.createSearchDescriptor()
            search.SearchString = old

            count = 0
            found = doc.findFirst(search)

            while found:
                # Check if this match is in a tracked deletion
                if not self._is_in_tracked_deletion(found, doc):
                    # Replace this visible occurrence
                    found.setString(new)
                    count += 1

                # Find next occurrence
                # Note: We need to recreate the search after replacement
                # to avoid issues with modified text ranges
                search = doc.createSearchDescriptor()
                search.SearchString = old
                found = doc.findNext(found.getEnd(), search)

            logger.info(f"Replaced {count} visible occurrences of '{old}' with '{new}' (Track Changes enabled)")
            return {
                "success": True,
                "count": count,
                "old": old,
                "new": new,
                "track_changes_active": True
            }

        except Exception as e:
            logger.error(f"Failed to find and replace all: {e}")
            return {"success": False, "error": str(e)}

    def _get_document_type(self, doc: Any) -> str:
        """Determine document type"""
        # Try isinstance first if types are available
        if _is_instance(doc, XTextDocument):
            return "writer"
        elif _is_instance(doc, XSpreadsheetDocument):
            return "calc"
        elif _is_instance(doc, XPresentationDocument):
            return "impress"

        # Fallback: check supportsService (works even if types not imported)
        if hasattr(doc, 'supportsService'):
            if doc.supportsService("com.sun.star.text.TextDocument"):
                return "writer"
            elif doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
                return "calc"
            elif doc.supportsService("com.sun.star.presentation.PresentationDocument"):
                return "impress"
            elif doc.supportsService("com.sun.star.drawing.DrawingDocument"):
                return "draw"

        # Fallback: check for getText method (Writer documents)
        if hasattr(doc, 'getText'):
            return "writer"

        return "unknown"
    
    def _has_selection(self, doc: Any) -> bool:
        """Check if document has selected content"""
        try:
            if hasattr(doc, 'getCurrentController'):
                controller = doc.getCurrentController()
                if hasattr(controller, 'getSelection'):
                    selection = controller.getSelection()
                    return selection.getCount() > 0
        except Exception:
            pass
        return False

    # -- Writer paragraph/text editing (tools/writer_text.py's 18 tools) --
    #
    # Unlike the block above (this file's original 32-tool surface), every
    # method here raises on failure rather than returning a
    # {"success": False, ...} dict -- matching the document_lifecycle.py/
    # styles.py convention tools/writer_text.py's callers expect
    # (_error_response() maps the exception type to a spec error code).
    #
    # _require_writer() below deliberately uses _get_document_type() (its
    # supportsService()-first, isinstance()-as-fallback check), NOT a bare
    # isinstance(doc, XTextDocument) -- see this module's format_text()
    # for the landmine this avoids repeating: it uses a literal isinstance()
    # check and fails against a document opened via certain paths (known,
    # pre-existing, deliberately left unfixed -- see writer_text.py's
    # module docstring and the styles.py pass's commit message).

    def _require_writer(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "writer":
            raise WrongDocumentTypeError(f"{operation} is only implemented for Writer documents, not '{doc_type}'.")

    def _count_paragraphs(self, doc: Any) -> int:
        text = doc.getText()
        enum = text.createEnumeration()
        count = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph"):
                count += 1
        return count

    def _get_paragraph_object(self, doc: Any, n: int) -> Any:
        """Return the nth (1-indexed) paragraph object via the same text
        enumeration get_paragraph()/goto_paragraph()/select_paragraph()
        already use.

        Raises:
            IndexError: n < 1, or n is past the last paragraph.
        """
        if n < 1:
            raise IndexError(f"Paragraph number must be >= 1, got {n}")
        text = doc.getText()
        enum = text.createEnumeration()
        current = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph"):
                current += 1
                if current == n:
                    return para
        raise IndexError(f"Paragraph {n} out of range. Document has {current} paragraph(s).")

    def _current_paragraph_index(self, doc: Any) -> int:
        """Return the 1-indexed paragraph number containing the view
        cursor -- the same char-count-then-scan algorithm get_cursor_position()
        already uses, factored out so insert_paragraph() can resolve "the
        current paragraph" when at_paragraph is omitted."""
        controller = self._get_controller(doc)
        view_cursor = controller.getViewCursor()
        text = doc.getText()
        text_cursor = text.createTextCursor()
        text_cursor.gotoStart(False)
        text_cursor.gotoRange(view_cursor, True)
        char_position = len(text_cursor.getString())
        enum = text.createEnumeration()
        paragraph_num = 0
        char_count = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph"):
                paragraph_num += 1
                char_count += len(para.getString()) + 1
                if char_count >= char_position:
                    break
        return paragraph_num or 1

    def insert_paragraph(self, doc: Any, text: str = "", at_paragraph: Optional[int] = None,
                          position: Optional[str] = None) -> Dict[str, Any]:
        """Insert a new paragraph before/after the current or a specified
        paragraph.

        Technique (standard UNO idiom for "type Enter" at a point): place a
        collapsed cursor at the target paragraph's start (position="before")
        or end (position="after"), then insertString()+insertControlCharacter()
        (or the reverse order for "after") so the paragraph break lands on
        the correct side of the new text.

        BUG #5 fix (live-verified): when at_paragraph is omitted, the
        anchor resolves through _current_paragraph_index(doc), which reads
        the VIEW cursor's position -- but the actual edit above happens
        through a SEPARATE text cursor (text_obj.createTextCursorByRange()),
        which never touches the view cursor. Under batch_execute_live
        (every op runs back-to-back with no idle time between server-side
        calls), the view cursor never moved, so every batched
        at_paragraph=None call in a row resolved the identical anchor and
        piled up in reverse -- confirmed against the reported symptom:
        insert_table()/insert_image() don't have this bug because, when
        their own *_position is omitted, they insert directly through
        controller.getViewCursor() itself (the same object being written
        through), so it moves as a side effect of the insert. Fixed the
        same way here: explicitly resync the view cursor to the inserted
        range afterward, so the next omitted-position call (batched or
        not) resolves relative to what was just inserted instead of a
        stale position. Best-effort (doesn't fail an otherwise-successful
        insert if repositioning itself raises) -- worst case reverts to
        the pre-fix anchor behavior for the next call, not data loss.
        """
        self._require_writer(doc, "insert_paragraph")
        position = position or "after"
        if position not in ("before", "after"):
            raise ValueError(f"position must be 'before' or 'after', got {position!r}")
        anchor_n = at_paragraph if at_paragraph is not None else self._current_paragraph_index(doc)
        anchor_para = self._get_paragraph_object(doc, anchor_n)
        text_obj = doc.getText()
        if position == "before":
            cursor = text_obj.createTextCursorByRange(anchor_para.getStart())
            text_obj.insertString(cursor, text, False)
            text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            new_paragraph_number = anchor_n
        else:
            cursor = text_obj.createTextCursorByRange(anchor_para.getEnd())
            text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
            text_obj.insertString(cursor, text, False)
            new_paragraph_number = anchor_n + 1
        try:
            self._get_controller(doc).getViewCursor().gotoRange(cursor, False)
        except Exception:
            pass  # best-effort -- see BUG #5 fix note above
        return {"inserted_paragraph": new_paragraph_number, "text": text}

    def append_paragraph(self, doc: Any, text: str = "", style_name: Optional[str] = None) -> Dict[str, Any]:
        """Append a new paragraph to the end of the document. Always adds a
        new paragraph (never reuses an existing empty trailing one).

        BUG #9 fix (live-verified): an unknown style_name used to raise
        AFTER the text was already inserted -- the tool layer reports
        success=false, but the paragraph is still there, unstyled. A
        caller that only checks success would drop content that actually
        landed. Fixed by validating style_name BEFORE touching the
        document at all, so an unknown style now fails atomically (nothing
        inserted) instead of partially applying behind a failure code."""
        self._require_writer(doc, "append_paragraph")
        if style_name:
            family_container = self._get_style_family(doc, "ParagraphStyles")
            if not family_container.hasByName(style_name):
                raise KeyError(f"No such paragraph style '{style_name}'.")
        text_obj = doc.getText()
        cursor = text_obj.createTextCursor()
        cursor.gotoEnd(False)
        text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        text_obj.insertString(cursor, text, False)
        style_applied = False
        if style_name:
            cursor.ParaStyleName = style_name
            style_applied = True
        return {"appended_paragraph": self._count_paragraphs(doc), "text": text, "style_applied": style_applied}

    def insert_heading(self, doc: Any, text: str, level: int = 1, at_paragraph: Optional[int] = None,
                        position: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "insert_heading")
        if level < 1:
            raise ValueError(f"level must be >= 1, got {level}")
        style_name = f"Heading {level}"
        family_container = self._get_style_family(doc, "ParagraphStyles")
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such paragraph style '{style_name}' (level {level}).")
        result = self.insert_paragraph(doc, text=text, at_paragraph=at_paragraph, position=position)
        para = self._get_paragraph_object(doc, result["inserted_paragraph"])
        para.ParaStyleName = style_name
        result["style"] = style_name
        result["level"] = level
        return result

    def set_paragraph_text(self, doc: Any, n: int, text: str) -> Dict[str, Any]:
        """Replace paragraph n's text in place -- setString() on the same
        paragraph object preserves paragraph identity/style (no split/merge
        happens), unlike insert_paragraph/split_paragraph/merge_paragraphs."""
        self._require_writer(doc, "set_paragraph_text")
        para = self._get_paragraph_object(doc, n)
        para.setString(text)
        return {"paragraph": n, "text": text}

    def split_paragraph(self, doc: Any, n: int, offset: int) -> Dict[str, Any]:
        self._require_writer(doc, "split_paragraph")
        para = self._get_paragraph_object(doc, n)
        para_text = para.getString()
        if offset < 0 or offset > len(para_text):
            raise IndexError(f"offset {offset} out of range for paragraph {n} (length {len(para_text)})")
        text_obj = doc.getText()
        cursor = text_obj.createTextCursorByRange(para.getStart())
        if offset > 0:
            cursor.goRight(offset, False)
        text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        return {"paragraph": n, "offset": offset, "first_text": para_text[:offset], "second_text": para_text[offset:]}

    def merge_paragraphs(self, doc: Any, first_n: int, count: int = 2, separator: str = " ") -> Dict[str, Any]:
        self._require_writer(doc, "merge_paragraphs")
        if count < 2:
            raise ValueError(f"count must be >= 2 to merge, got {count}")
        last_n = first_n + count - 1
        paras = [self._get_paragraph_object(doc, i) for i in range(first_n, last_n + 1)]
        texts = [p.getString() for p in paras]
        merged_text = separator.join(texts)
        text_obj = doc.getText()
        span = text_obj.createTextCursorByRange(paras[0].getStart())
        span.gotoRange(paras[-1].getEnd(), True)
        span.setString(merged_text)
        return {"merged_into": first_n, "text": merged_text, "paragraphs_removed": count - 1}

    def _delete_paragraph_range(self, doc: Any, start: int, end: int) -> None:
        """Delete paragraphs [start, end] (1-indexed, inclusive) entirely,
        consuming exactly one adjacent paragraph break so no stray empty
        paragraph is left behind -- prefers the trailing break (into the
        next surviving paragraph) and only falls back to the leading break
        when deleting the document's own last paragraph(s), since there is
        no trailing break to take in that case."""
        total = self._count_paragraphs(doc)
        text_obj = doc.getText()
        start_para = self._get_paragraph_object(doc, start)
        end_para = self._get_paragraph_object(doc, end)
        if end < total:
            range_start = start_para.getStart()
            range_end = self._get_paragraph_object(doc, end + 1).getStart()
        elif start > 1:
            range_start = self._get_paragraph_object(doc, start - 1).getEnd()
            range_end = end_para.getEnd()
        else:
            # Deleting every paragraph in the document -- Writer always
            # keeps at least one paragraph, so this empties it instead.
            range_start = start_para.getStart()
            range_end = end_para.getEnd()
        cursor = text_obj.createTextCursorByRange(range_start)
        cursor.gotoRange(range_end, True)
        cursor.setString("")

    def _insert_paragraph_block(self, doc: Any, entries: List[Any], destination: int) -> int:
        """Insert `entries` (a list of (text, para_style_name) pairs) as
        new, consecutive paragraphs so the first one lands at 1-indexed
        paragraph number `destination` in the resulting document.
        destination beyond the current paragraph count appends at the end
        instead of raising. Each paragraph's ParaStyleName is reapplied
        after insertion (best-effort -- an unrecognized/unsettable style
        name is silently skipped rather than failing the whole block, same
        "best effort" spirit as _apply_direct_properties). Returns the
        resolved starting paragraph number the first inserted paragraph
        actually landed at.

        Live-verified real bug this fixed: an earlier version of
        move_paragraphs/copy_paragraphs only carried getString() (plain
        text), silently dropping the source paragraph's style (e.g. moving
        a "Heading 1" paragraph landed as a plain-styled paragraph with the
        same text) -- see the commit message.
        """
        total = self._count_paragraphs(doc)
        if destination > total:
            anchor_n = total
            insert_position = "after"
        else:
            anchor_n = destination
            insert_position = "before"
        for offset, (text, para_style_name) in enumerate(entries):
            para_n = anchor_n + offset
            self.insert_paragraph(doc, text=text, at_paragraph=para_n, position=insert_position)
            landed_n = para_n if insert_position == "before" else para_n + 1
            if para_style_name:
                try:
                    self._get_paragraph_object(doc, landed_n).ParaStyleName = para_style_name
                except Exception:
                    pass
        return anchor_n + 1 if insert_position == "after" else anchor_n

    def move_paragraphs(self, doc: Any, start: int, end: int, destination: int) -> Dict[str, Any]:
        self._require_writer(doc, "move_paragraphs")
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        total = self._count_paragraphs(doc)
        if start < 1 or end > total:
            raise IndexError(f"range {start}-{end} out of bounds (document has {total} paragraph(s))")
        if start <= destination <= end:
            raise ValueError(f"destination {destination} falls inside the block being moved ({start}-{end})")
        count = end - start + 1
        paras = [self._get_paragraph_object(doc, i) for i in range(start, end + 1)]
        entries = [(p.getString(), p.ParaStyleName) for p in paras]
        self._delete_paragraph_range(doc, start, end)
        resolved_destination = destination - count if destination > end else destination
        resolved_start = self._insert_paragraph_block(doc, entries, resolved_destination)
        return {"moved_count": count, "destination": resolved_start}

    def copy_paragraphs(self, doc: Any, start: int, end: int, destination: int) -> Dict[str, Any]:
        self._require_writer(doc, "copy_paragraphs")
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
        total = self._count_paragraphs(doc)
        if start < 1 or end > total:
            raise IndexError(f"range {start}-{end} out of bounds (document has {total} paragraph(s))")
        paras = [self._get_paragraph_object(doc, i) for i in range(start, end + 1)]
        entries = [(p.getString(), p.ParaStyleName) for p in paras]
        resolved_start = self._insert_paragraph_block(doc, entries, destination)
        return {"copied_count": len(entries), "destination": resolved_start}

    def _apply_direct_properties(self, text_range: Any, properties: Dict[str, Any]) -> List[str]:
        """Set each property directly on a Writer text range via
        setPropertyValue, skipping (not raising on) any name/value UNO
        rejects -- same "best-effort, report what applied" contract as
        update_style()/create_style() above. UNO does not distinguish
        paragraph-format from character-format properties at this level
        (both live on the same text range), so set_paragraph_format() and
        set_character_format() both delegate here."""
        applied = []
        for key, value in properties.items():
            try:
                text_range.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                continue
        return applied

    def set_paragraph_format(self, doc: Any, target: Optional[Any], properties: Dict[str, Any]) -> List[str]:
        self._require_writer(doc, "set_paragraph_format")
        text_range = self._resolve_text_target(doc, target)
        return self._apply_direct_properties(text_range, properties)

    def set_character_format(self, doc: Any, target: Optional[Any], properties: Dict[str, Any]) -> List[str]:
        self._require_writer(doc, "set_character_format")
        text_range = self._resolve_text_target(doc, target)
        return self._apply_direct_properties(text_range, properties)

    def get_text_range_format(self, doc: Any, start: int, end: int) -> Dict[str, Any]:
        """Return every JSON-safe effective character/paragraph property
        value on a 0-based Writer character range, plus which of those are
        direct overrides (PropertyState DIRECT_VALUE) rather than inherited
        from the paragraph/character style -- a superset of
        get_direct_formatting_live (styles.py), which only reports the
        DIRECT_VALUE subset."""
        self._require_writer(doc, "get_text_range_format")
        if start < 0 or end < start:
            raise ValueError(f"Invalid range: start={start}, end={end}")
        text_range = self._resolve_text_target(doc, {"start": start, "end": end})
        direct_value = uno.Enum("com.sun.star.beans.PropertyState", "DIRECT_VALUE")
        effective: Dict[str, Any] = {}
        direct_overrides = []
        for prop in text_range.getPropertySetInfo().getProperties():
            try:
                plain_value = self._uno_value_to_plain(text_range.getPropertyValue(prop.Name))
                if not self._is_json_safe(plain_value):
                    continue
                effective[prop.Name] = plain_value
                if text_range.getPropertyState(prop.Name) == direct_value:
                    direct_overrides.append(prop.Name)
            except Exception:
                continue
        return {"effective_formatting": effective, "direct_override_properties": sorted(direct_overrides)}

    def find_regex(self, doc: Any, pattern: str, case_sensitive: bool = False) -> Dict[str, Any]:
        """Find via XSearchable with SearchRegularExpression=True -- real
        LibreOffice/ICU regex support, not hand-rolled Python re + manual
        cursor walking (this gives matches with usable positions directly,
        same technique find_text() already uses for plain-text search)."""
        self._require_writer(doc, "find_regex")
        search = doc.createSearchDescriptor()
        search.SearchString = pattern
        search.SearchRegularExpression = True
        search.SearchCaseSensitive = case_sensitive
        found = doc.findAll(search)
        text = doc.getText()
        matches = []
        if found:
            for i in range(found.getCount()):
                match_range = found.getByIndex(i)
                text_cursor = text.createTextCursor()
                text_cursor.gotoStart(False)
                text_cursor.gotoRange(match_range.getStart(), True)
                position = len(text_cursor.getString())
                matched_text = match_range.getString()
                matches.append({"position": position, "text": matched_text, "length": len(matched_text)})
        return {"matches": matches, "count": len(matches), "pattern": pattern, "case_sensitive": case_sensitive}

    def replace_regex(self, doc: Any, pattern: str, replacement: str, all: bool = True) -> Dict[str, Any]:
        """Replace via XReplaceable with SearchRegularExpression=True (native
        regex, including $1-style backreferences in `replacement`)."""
        self._require_writer(doc, "replace_regex")
        if all:
            replace = doc.createReplaceDescriptor()
            replace.SearchString = pattern
            replace.ReplaceString = replacement
            replace.SearchRegularExpression = True
            count = doc.replaceAll(replace)
            return {"count": count, "pattern": pattern, "replacement": replacement, "all": True}
        search = doc.createSearchDescriptor()
        search.SearchString = pattern
        search.SearchRegularExpression = True
        found = doc.findFirst(search)
        if not found:
            return {"replaced": False, "pattern": pattern, "replacement": replacement, "all": False}
        text = doc.getText()
        text_cursor = text.createTextCursor()
        text_cursor.gotoStart(False)
        text_cursor.gotoRange(found.getStart(), True)
        position = len(text_cursor.getString())
        found.setString(replacement)
        return {"replaced": True, "position": position, "pattern": pattern, "replacement": replacement, "all": False}

    def find_by_style(self, doc: Any, family: str, style_name: str) -> Dict[str, Any]:
        """Find paragraphs (family="ParagraphStyles") or character-styled
        runs (family="CharacterStyles") using a named style -- the same
        _STYLE_FAMILY_APPLY_PROPERTY mapping apply_style()/replace_style()
        use, so this only recognizes the two families that mapping covers."""
        self._require_writer(doc, "find_by_style")
        apply_property = self._STYLE_FAMILY_APPLY_PROPERTY.get(family)
        if apply_property is None:
            raise NotImplementedError(f"find_by_style is not implemented for family '{family}'.")
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(style_name):
            raise KeyError(f"No such style '{style_name}' in family '{family}'.")
        text = doc.getText()
        enum = text.createEnumeration()
        matches = []
        paragraph_num = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if not (hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph")):
                continue
            paragraph_num += 1
            if family == "ParagraphStyles":
                if para.getPropertyValue(apply_property) == style_name:
                    matches.append({"paragraph": paragraph_num, "text": para.getString()})
            else:  # CharacterStyles
                portion_enum = para.createEnumeration()
                while portion_enum.hasMoreElements():
                    portion = portion_enum.nextElement()
                    if portion.getPropertyValue(apply_property) == style_name:
                        matches.append({"paragraph": paragraph_num, "text": portion.getString()})
        return {"family": family, "style_name": style_name, "matches": matches, "count": len(matches)}

    def replace_style(self, doc: Any, family: str, old_style: str, new_style: str) -> Dict[str, Any]:
        """Replace every paragraph/run using old_style with new_style."""
        self._require_writer(doc, "replace_style")
        apply_property = self._STYLE_FAMILY_APPLY_PROPERTY.get(family)
        if apply_property is None:
            raise NotImplementedError(f"replace_style is not implemented for family '{family}'.")
        family_container = self._get_style_family(doc, family)
        if not family_container.hasByName(old_style):
            raise KeyError(f"No such style '{old_style}' in family '{family}'.")
        if not family_container.hasByName(new_style):
            raise KeyError(f"No such style '{new_style}' in family '{family}'.")
        text = doc.getText()
        enum = text.createEnumeration()
        count = 0
        while enum.hasMoreElements():
            para = enum.nextElement()
            if not (hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph")):
                continue
            if family == "ParagraphStyles":
                if para.getPropertyValue(apply_property) == old_style:
                    para.setPropertyValue(apply_property, new_style)
                    count += 1
            else:  # CharacterStyles
                portion_enum = para.createEnumeration()
                while portion_enum.hasMoreElements():
                    portion = portion_enum.nextElement()
                    if portion.getPropertyValue(apply_property) == old_style:
                        portion.setPropertyValue(apply_property, new_style)
                        count += 1
        return {"family": family, "old_style": old_style, "new_style": new_style, "replaced_count": count}

    # -- Comments (update/delete/resolve) --------------------------------
    #
    # get_comments()/add_comment() above already enumerate/create Writer
    # comments as com.sun.star.text.TextField.Annotation text fields; these
    # three tools address the SAME fields the same way (via
    # doc.getTextFields()'s enumeration, filtered to that service), not a
    # parallel comment model. The only gap they close is identity: neither
    # get_comments() nor the Annotation field service guarantees a stable
    # id: _comment_id_for() below prefers a real UNO "Id" property when this
    # LibreOffice build exposes one on annotation fields (durable), and
    # falls back to the field's ordinal position in document order
    # (session-stable only -- shifts if an earlier comment is added or
    # removed) when it doesn't. Which case this build actually hits is
    # live-verified, see the commit message for this pass.

    def _enumerate_comments(self, doc: Any) -> List[Any]:
        """Return annotation TextField objects in document order -- the
        exact same enumeration get_comments() performs, factored out so
        update/delete/resolve_comment index into a matching order."""
        fields = []
        if hasattr(doc, "getTextFields"):
            text_fields = doc.getTextFields()
            enum = text_fields.createEnumeration()
            while enum.hasMoreElements():
                field = enum.nextElement()
                if hasattr(field, "supportsService") and field.supportsService("com.sun.star.text.TextField.Annotation"):
                    fields.append(field)
        return fields

    def _comment_id_for(self, field: Any, index: int) -> str:
        try:
            if field.getPropertySetInfo().hasPropertyByName("Id"):
                raw_id = field.getPropertyValue("Id")
                if raw_id:
                    return str(raw_id)
        except Exception:
            pass
        return str(index)

    def find_comment_by_id(self, doc: Any, comment_id: str) -> Any:
        """Raises KeyError if no comment has this id."""
        for index, field in enumerate(self._enumerate_comments(doc)):
            if self._comment_id_for(field, index) == comment_id:
                return field
        raise KeyError(f"No comment with id '{comment_id}'.")

    def update_comment(self, doc: Any, comment_id: str, text: Optional[str] = None,
                        author: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "update_comment")
        field = self.find_comment_by_id(doc, comment_id)
        applied = []
        if text is not None:
            field.Content = text
            applied.append("text")
        if author is not None:
            field.Author = author
            applied.append("author")
        return {"comment_id": comment_id, "applied": applied}

    def delete_comment(self, doc: Any, comment_id: str) -> None:
        self._require_writer(doc, "delete_comment")
        field = self.find_comment_by_id(doc, comment_id)
        doc.getText().removeTextContent(field)

    _RESOLVED_MARKER = "[RESOLVED] "

    def resolve_comment(self, doc: Any, comment_id: str, resolved: bool = True) -> Dict[str, Any]:
        """Mark a comment resolved via a real UNO "Resolved" property when
        this LibreOffice build's annotation fields expose one; otherwise
        emulate it with a "[RESOLVED] " Content marker (round-trips through
        get_comments_live's content field, but is not a native resolved
        state -- documented, not hidden, per this tool's own spec purpose:
        "where supported; otherwise emulate with metadata")."""
        self._require_writer(doc, "resolve_comment")
        field = self.find_comment_by_id(doc, comment_id)
        try:
            info = field.getPropertySetInfo()
            if info.hasPropertyByName("Resolved"):
                field.setPropertyValue("Resolved", resolved)
                return {"comment_id": comment_id, "resolved": resolved, "emulated": False}
        except Exception:
            pass
        content = field.Content or ""
        has_marker = content.startswith(self._RESOLVED_MARKER)
        if resolved and not has_marker:
            field.Content = self._RESOLVED_MARKER + content
        elif not resolved and has_marker:
            field.Content = content[len(self._RESOLVED_MARKER):]
        return {"comment_id": comment_id, "resolved": resolved, "emulated": True}

    # -- Common drawing objects (tools/drawing_objects.py's 31 tools) --
    #
    # Same raise-on-failure convention as the writer_text.py/styles.py
    # sections above (_error_response() in the tool layer maps exceptions
    # to spec error codes) -- not the {"success": False, ...} dict
    # convention the original 32 use.
    #
    # shape_id/object_id resolution (the ObjectRegistry from
    # docs/OBJECT_HANDLE_DESIGN.md) happens in tools/drawing_objects.py,
    # NOT here -- this bridge layer only ever deals in already-resolved
    # UNO shape objects, exactly like _resolve_text_target() hands
    # already-resolved text ranges to styles.py's methods. Methods below
    # that create a NEW shape (insert_shape/duplicate_shape/insert_image)
    # return the raw UNO shape object; the tool layer registers it to
    # mint its id.
    #
    # container resolution (sheet/page addressing) is live name-or-index
    # resolution, no registry, per docs/OBJECT_HANDLE_DESIGN.md's
    # category split -- _resolve_sheet_by_name_or_index()/
    # _resolve_page_by_name_or_index() below are exactly the
    # "_resolve_sheet()/_resolve_slide() helpers" that design doc left
    # for this pass.
    #
    # Scope limit, deliberate: combine_shapes/split_shape/bind_shapes/
    # unbind_shape (all P3) and insert_embedded_object/
    # activate_embedded_object (also P3) raise NotImplementedError
    # instead of a real implementation. combine/split/bind/unbind only
    # exist as .uno: dispatch commands (no direct UNO API equivalent);
    # live-tested this pass with a real selection + view -- .uno:Combine
    # executed and appeared to work, but crashed the headless soffice
    # process outright on the very next UNO call (a
    # DisposedException: "Binary URP bridge disposed during call"),
    # which would take down the extension's whole host process for every
    # connected MCP client, not just the caller. Not safe to ship without
    # a dedicated isolation/testing pass. insert_embedded_object/
    # activate_embedded_object are the same risk class (OLE
    # activation is also dispatch/verb-based) and were not exploration-
    # tested this pass given the crash above -- left unimplemented rather
    # than guessed at.

    def _require_shape_capable(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type not in ("writer", "calc", "impress", "draw"):
            raise NotImplementedError(f"{operation} is not supported for document type '{doc_type}'.")

    @staticmethod
    def _resolve_sheet_by_name_or_index(sheets: Any, sheet_ref: str) -> Any:
        if sheets.hasByName(sheet_ref):
            return sheets.getByName(sheet_ref)
        if sheet_ref.isdigit():
            index = int(sheet_ref)
            if 0 <= index < sheets.getCount():
                return sheets.getByIndex(index)
        raise KeyError(f"No such sheet '{sheet_ref}'.")

    @staticmethod
    def _resolve_page_by_name_or_index(pages: Any, page_ref: Any) -> Any:
        """page_ref may be an int (0-based index) or a str (page Name,
        with the same digit-string-falls-back-to-index convention
        _resolve_sheet_by_name_or_index uses)."""
        if isinstance(page_ref, bool):
            raise TypeError("page reference must be an int index or a str name, not bool.")
        if isinstance(page_ref, int):
            if 0 <= page_ref < pages.getCount():
                return pages.getByIndex(page_ref)
            raise IndexError(f"Page index {page_ref} out of range (document has {pages.getCount()} page(s)).")
        page_ref = str(page_ref)
        if pages.hasByName(page_ref):
            return pages.getByName(page_ref)
        if page_ref.isdigit():
            index = int(page_ref)
            if 0 <= index < pages.getCount():
                return pages.getByIndex(index)
        raise KeyError(f"No such page '{page_ref}'.")

    def _resolve_shape_container(self, doc: Any, container: Optional[Any] = None) -> Any:
        """Return the XDrawPage 'container' addresses: Writer's single
        document-wide draw page (container ignored -- there is only
        ever one), a specific Calc sheet's own draw page (container
        required, sheet name or digit-string index), or a specific
        Impress/Draw page (container optional, defaults to page 0;
        int index or name)."""
        self._require_shape_capable(doc, "drawing objects")
        doc_type = self._get_document_type(doc)
        if doc_type == "writer":
            return doc.getDrawPage()
        if doc_type == "calc":
            if container is None:
                raise ValueError("container (sheet name or index) is required for Calc documents.")
            sheet = self._resolve_sheet_by_name_or_index(doc.getSheets(), str(container))
            return sheet.getDrawPage()
        # impress, draw
        pages = doc.getDrawPages()
        if container is None:
            if pages.getCount() == 0:
                raise IndexError("Document has no pages.")
            return pages.getByIndex(0)
        return self._resolve_page_by_name_or_index(pages, container)

    _SHAPE_SERVICE_TYPE_NAMES = (
        ("com.sun.star.drawing.OLE2Shape", "ole"),
        # Writer's own embedded-object type -- confirmed live
        # com.sun.star.drawing.OLE2Shape isn't creatable via Writer's
        # document-level createInstance() (ServiceNotRegisteredException);
        # Writer uses this text-content type instead (see
        # insert_embedded_object()'s docstring). Classified the same
        # short name "ole" so list_embedded_objects_live's type_filter
        # and get_shape_summary/get_shape_details treat both the same.
        ("com.sun.star.text.TextEmbeddedObject", "ole"),
        ("com.sun.star.drawing.GraphicObjectShape", "image"),
        ("com.sun.star.drawing.GroupShape", "group"),
        ("com.sun.star.drawing.ConnectorShape", "connector"),
        ("com.sun.star.drawing.CustomShape", "custom"),
        ("com.sun.star.drawing.RectangleShape", "rectangle"),
        ("com.sun.star.drawing.EllipseShape", "ellipse"),
        ("com.sun.star.drawing.LineShape", "line"),
        ("com.sun.star.drawing.PolyPolygonShape", "polygon"),
        ("com.sun.star.drawing.PolyLineShape", "polyline"),
        ("com.sun.star.drawing.OpenBezierShape", "bezier"),
        ("com.sun.star.drawing.ClosedBezierShape", "bezier"),
        ("com.sun.star.drawing.TextShape", "text"),
    )

    @classmethod
    def _get_shape_type(cls, shape: Any) -> str:
        """Best-effort short type name for a shape via supportsService(),
        checked most-specific-first (e.g. an OLE2Shape's ShapeType string
        also often mentions generic drawing terms, so service checks are
        more reliable than string-matching ShapeType directly)."""
        for service_name, short_name in cls._SHAPE_SERVICE_TYPE_NAMES:
            if shape.supportsService(service_name):
                return short_name
        return "other"

    @staticmethod
    def _shape_geometry(shape: Any) -> Dict[str, Any]:
        """x/y are best-effort, not required -- live-verified a Writer
        text-content object inserted via insertTextContent() (see
        insert_embedded_object()) with its default AT_PARAGRAPH
        AnchorType raises com.sun.star.beans.UnknownPropertyException
        ("cannot get value Position") on a plain read, not just a set;
        Size has no such restriction (confirmed live: reads/sets fine
        regardless of anchor type), so width/height stay required. Same
        try/except-and-omit convention this method already used for
        RotateAngle/ShearAngle below."""
        size = shape.Size
        geometry = {"width": size.Width, "height": size.Height}
        try:
            position = shape.Position
            geometry["x"] = position.X
            geometry["y"] = position.Y
        except Exception:
            pass
        try:
            geometry["rotation"] = shape.RotateAngle
        except Exception:
            pass
        try:
            geometry["shear"] = shape.ShearAngle
        except Exception:
            pass
        return geometry

    @classmethod
    def _shape_summary(cls, shape: Any, shape_id: str) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "shape_id": shape_id,
            "type": cls._get_shape_type(shape),
        }
        summary.update(cls._shape_geometry(shape))
        try:
            if hasattr(shape, "getString"):
                text = shape.getString()
                if text:
                    summary["text"] = text
        except Exception:
            pass
        return summary

    def list_shapes_in_container(self, doc: Any, container: Optional[Any] = None,
                                  type_filter: Optional[str] = None) -> List[Any]:
        """Return the raw UNO shape objects on 'container' (see
        _resolve_shape_container), optionally filtered to one
        _get_shape_type() short name. Registering each into an
        ObjectRegistry (to mint shape_ids) is the tool layer's job."""
        page = self._resolve_shape_container(doc, container)
        shapes = []
        for i in range(page.getCount()):
            shape = page.getByIndex(i)
            if type_filter is not None and self._get_shape_type(shape) != type_filter:
                continue
            shapes.append(shape)
        return shapes

    def get_shape_summary(self, shape: Any, shape_id: str) -> Dict[str, Any]:
        return self._shape_summary(shape, shape_id)

    def get_shape_details(self, shape: Any, shape_id: str) -> Dict[str, Any]:
        details: Dict[str, Any] = {
            "shape_id": shape_id,
            "type": self._get_shape_type(shape),
        }
        details.update(self._shape_geometry(shape))
        try:
            details["z_order"] = shape.ZOrder
        except Exception:
            pass
        try:
            if hasattr(shape, "getString"):
                details["text"] = shape.getString()
        except Exception:
            pass
        for attr, key in (("Title", "title"), ("Description", "description")):
            try:
                value = shape.getPropertyValue(attr)
                if value:
                    details[key] = value
            except Exception:
                pass
        style: Dict[str, Any] = {}
        for prop_name in ("FillColor", "FillStyle", "LineColor", "LineWidth", "LineStyle",
                           "Shadow", "FillTransparence", "LineTransparence"):
            try:
                value = self._uno_value_to_plain(shape.getPropertyValue(prop_name))
                if self._is_json_safe(value):
                    style[prop_name] = value
            except Exception:
                continue
        details["style"] = style
        return details

    _FIND_SHAPE_TEXT_MAX_SCANNED_SHAPES = 5000

    def _iter_shape_text_containers(self, doc: Any, container: Optional[Any] = None) -> List[Any]:
        """Return [(label, page)] pairs to search -- Writer has exactly
        one (its single document-wide draw page, `container` ignored,
        same as `_resolve_shape_container`); Calc searches one sheet's
        draw page if `container` names a sheet, else every sheet's;
        Impress/Draw searches one page if `container` names/indexes one,
        else every page. Mirrors find_cells()'s "container given -> just
        that one; omitted -> every candidate, each match reporting which
        one it came from" scope discipline."""
        self._require_shape_capable(doc, "find_shape_text")
        doc_type = self._get_document_type(doc)
        if doc_type == "writer":
            return [("document", doc.getDrawPage())]
        if doc_type == "calc":
            sheets = doc.getSheets()
            if container is not None:
                sheet = self._resolve_sheet_by_name_or_index(sheets, str(container))
                return [(sheet.Name, sheet.getDrawPage())]
            return [(sheets.getByIndex(i).Name, sheets.getByIndex(i).getDrawPage()) for i in range(sheets.getCount())]
        # impress, draw
        pages = doc.getDrawPages()
        if container is not None:
            page = self._resolve_page_by_name_or_index(pages, container)
            return [(page.Name, page)]
        return [(pages.getByIndex(i).Name, pages.getByIndex(i)) for i in range(pages.getCount())]

    def find_shape_text(self, doc: Any, query: str, container: Optional[Any] = None,
                         match: str = "contains", case_sensitive: bool = False,
                         max_results: int = 100) -> Dict[str, Any]:
        """New tool (Brian's new-tools assignment, priority #4, "shared
        search across Impress/Draw shapes, optionally Writer/Calc drawing
        objects"). No exact schema was given for this one; `query`/
        `match`/`case_sensitive`/`max_results` reuse find_cells_live's
        established search-tool shape rather than inventing a new one,
        since both are "find text somewhere in the document" primitives.

        Returns {"shapes": [(container_label, shape)], "truncated": bool}
        -- raw UNO shape objects, not JSON; minting shape_ids via
        ObjectRegistry is the tool layer's job (find_shape_text_live),
        same split list_shapes_in_container() already established.

        Stops as soon as `max_results` matches are found OR
        _FIND_SHAPE_TEXT_MAX_SCANNED_SHAPES shapes have been examined --
        same runaway-scan backstop shape find_cells() uses, scaled down
        since a document's shape count is normally orders of magnitude
        below its cell count.
        """
        if match not in ("contains", "exact", "regex"):
            raise ValueError(f"match must be one of contains/exact/regex, got {match!r}")
        if match == "regex":
            try:
                pattern = re.compile(query, flags=0 if case_sensitive else re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid regex {query!r}: {e}")

            def is_match(candidate: str) -> bool:
                return pattern.search(candidate) is not None
        elif match == "exact":
            needle = query if case_sensitive else query.lower()

            def is_match(candidate: str) -> bool:
                return (candidate if case_sensitive else candidate.lower()) == needle
        else:  # contains
            needle = query if case_sensitive else query.lower()

            def is_match(candidate: str) -> bool:
                return needle in (candidate if case_sensitive else candidate.lower())

        matches: List[Any] = []
        scanned = 0
        truncated = False
        for label, page in self._iter_shape_text_containers(doc, container):
            for i in range(page.getCount()):
                if len(matches) >= max_results:
                    truncated = True
                    break
                if scanned >= self._FIND_SHAPE_TEXT_MAX_SCANNED_SHAPES:
                    truncated = True
                    break
                scanned += 1
                shape = page.getByIndex(i)
                if not hasattr(shape, "getString"):
                    continue
                try:
                    text = shape.getString()
                except Exception:
                    continue
                if not text or not is_match(text):
                    continue
                matches.append((label, shape))
            if truncated:
                break
        return {"shapes": matches, "truncated": truncated}

    _SHAPE_TYPE_SERVICES = {
        "rectangle": "com.sun.star.drawing.RectangleShape",
        "ellipse": "com.sun.star.drawing.EllipseShape",
        "line": "com.sun.star.drawing.LineShape",
        "polygon": "com.sun.star.drawing.PolyPolygonShape",
        "polyline": "com.sun.star.drawing.PolyLineShape",
        "bezier": "com.sun.star.drawing.OpenBezierShape",
        "text": "com.sun.star.drawing.TextShape",
        "custom": "com.sun.star.drawing.CustomShape",
    }

    def insert_shape(self, doc: Any, shape_type: str, position: Dict[str, Any], size: Dict[str, Any],
                      container: Optional[Any] = None, properties: Optional[Dict[str, Any]] = None) -> Any:
        service_name = self._SHAPE_TYPE_SERVICES.get(shape_type)
        if service_name is None:
            raise ValueError(f"Unknown shape_type '{shape_type}'. Supported: {sorted(self._SHAPE_TYPE_SERVICES)}")
        page = self._resolve_shape_container(doc, container)
        shape = doc.createInstance(service_name)
        page.add(shape)
        shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", int(position.get("x", 0)), int(position.get("y", 0)))
        shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", int(size.get("width", 1000)), int(size.get("height", 1000)))
        if properties:
            self._apply_direct_properties(shape, properties)
        return shape

    def delete_shape(self, doc: Any, shape: Any) -> None:
        if hasattr(shape, "getParent"):
            page = shape.getParent()
            page.remove(shape)
        else:
            # Writer text-content objects (e.g. a TextEmbeddedObject
            # inserted via insertTextContent(), see
            # insert_embedded_object()) don't implement XChild/
            # getParent() at all -- confirmed live this is a genuine
            # AttributeError, not just an empty/None parent, so it's not
            # something a try/except around getParent() alone would
            # distinguish from "shape not attached yet". Removed via
            # XText.removeTextContent() instead, confirmed live this
            # works cleanly for that object type.
            doc.getText().removeTextContent(shape)

    def duplicate_shape(self, doc: Any, shape: Any, offset: Optional[Dict[str, Any]] = None) -> Any:
        """UNO has no direct 'clone shape' API -- create a new shape of
        the same service and copy every settable property, live-verified
        this captures fill/line/text/geometry style (214 of ~229
        properties copied in testing; the rest are read-only derived
        properties UNO itself refuses to set, silently skipped, matching
        this file's established best-effort setPropertyValue convention)."""
        page = shape.getParent()
        # SupportedServiceNames[0] is always the concrete, most-specific
        # shape service (e.g. "com.sun.star.drawing.RectangleShape") --
        # live-verified for both RectangleShape and EllipseShape; the
        # generic "com.sun.star.drawing.Shape"/"...Text" interfaces this
        # sequence also contains always come later.
        concrete = shape.SupportedServiceNames[0]
        new_shape = doc.createInstance(concrete)
        page.add(new_shape)
        for prop in shape.getPropertySetInfo().getProperties():
            try:
                new_shape.setPropertyValue(prop.Name, shape.getPropertyValue(prop.Name))
            except Exception:
                continue
        if offset:
            pos = new_shape.Position
            new_shape.Position = uno.createUnoStruct(
                "com.sun.star.awt.Point",
                pos.X + int(offset.get("x", 0)),
                pos.Y + int(offset.get("y", 0)),
            )
        return new_shape

    def set_shape_geometry(self, shape: Any, geometry: Dict[str, Any]) -> List[str]:
        applied = []
        if "x" in geometry or "y" in geometry:
            pos = shape.Position
            shape.Position = uno.createUnoStruct(
                "com.sun.star.awt.Point",
                int(geometry.get("x", pos.X)), int(geometry.get("y", pos.Y)),
            )
            applied.extend(k for k in ("x", "y") if k in geometry)
        if "width" in geometry or "height" in geometry:
            size = shape.Size
            shape.Size = uno.createUnoStruct(
                "com.sun.star.awt.Size",
                int(geometry.get("width", size.Width)), int(geometry.get("height", size.Height)),
            )
            applied.extend(k for k in ("width", "height") if k in geometry)
        for key, attr in (("rotation", "RotateAngle"), ("shear", "ShearAngle")):
            if key in geometry:
                try:
                    shape.setPropertyValue(attr, int(geometry[key]))
                    applied.append(key)
                except Exception:
                    continue
        if "flip_horizontal" in geometry or "flip_vertical" in geometry:
            size = shape.Size
            new_width = -abs(size.Width) if geometry.get("flip_horizontal") else abs(size.Width)
            new_height = -abs(size.Height) if geometry.get("flip_vertical") else abs(size.Height)
            try:
                shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", new_width, new_height)
                applied.extend(k for k in ("flip_horizontal", "flip_vertical") if k in geometry)
            except Exception:
                pass
        return applied

    def set_shape_style(self, shape: Any, properties: Dict[str, Any]) -> List[str]:
        return self._apply_direct_properties(shape, properties)

    def set_shape_text(self, shape: Any, text: str) -> None:
        if not hasattr(shape, "setString"):
            raise NotImplementedError("This shape type does not support text.")
        shape.setString(text)

    def format_shape_text(self, shape: Any, properties: Dict[str, Any], range: Optional[Any] = None) -> List[str]:
        if not hasattr(shape, "getText"):
            raise NotImplementedError("This shape type does not support text.")
        text = shape.getText()
        text_range = text  # whole-text default
        if range is not None:
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.goRight(int(range.get("start", 0)), False)
            cursor.goRight(int(range.get("end", 0)) - int(range.get("start", 0)), True)
            text_range = cursor
        return self._apply_direct_properties(text_range, properties)

    def set_shape_alt_text(self, shape: Any, title: Optional[str] = None, description: Optional[str] = None) -> List[str]:
        applied = []
        if title is not None:
            shape.setPropertyValue("Title", title)
            applied.append("title")
        if description is not None:
            shape.setPropertyValue("Description", description)
            applied.append("description")
        return applied

    def set_shape_z_order(self, shape: Any, action: Optional[str] = None, z_order: Optional[int] = None) -> int:
        page = shape.getParent()
        max_order = page.getCount() - 1
        if z_order is not None:
            shape.ZOrder = max(0, min(int(z_order), max_order))
        elif action == "front":
            shape.ZOrder = max_order
        elif action == "back":
            shape.ZOrder = 0
        elif action == "forward":
            shape.ZOrder = min(shape.ZOrder + 1, max_order)
        elif action == "backward":
            shape.ZOrder = max(shape.ZOrder - 1, 0)
        else:
            raise ValueError("Either action or z_order must be given.")
        return shape.ZOrder

    @staticmethod
    def _shape_bounds(shape: Any) -> Dict[str, int]:
        pos, size = shape.Position, shape.Size
        return {"left": pos.X, "top": pos.Y, "right": pos.X + size.Width, "bottom": pos.Y + size.Height,
                "center_x": pos.X + size.Width // 2, "center_y": pos.Y + size.Height // 2}

    def align_shapes(self, shapes: List[Any], alignment: str, reference_bounds: Optional[Dict[str, int]] = None) -> None:
        if not shapes:
            return
        all_bounds = [self._shape_bounds(s) for s in shapes]
        bounds = reference_bounds or {
            "left": min(b["left"] for b in all_bounds),
            "top": min(b["top"] for b in all_bounds),
            "right": max(b["right"] for b in all_bounds),
            "bottom": max(b["bottom"] for b in all_bounds),
        }
        bounds.setdefault("center_x", (bounds["left"] + bounds["right"]) // 2)
        bounds.setdefault("center_y", (bounds["top"] + bounds["bottom"]) // 2)
        for shape in shapes:
            pos, size = shape.Position, shape.Size
            new_x, new_y = pos.X, pos.Y
            if alignment == "left":
                new_x = bounds["left"]
            elif alignment == "right":
                new_x = bounds["right"] - size.Width
            elif alignment == "center":
                new_x = bounds["center_x"] - size.Width // 2
            elif alignment == "top":
                new_y = bounds["top"]
            elif alignment == "bottom":
                new_y = bounds["bottom"] - size.Height
            elif alignment == "middle":
                new_y = bounds["center_y"] - size.Height // 2
            else:
                raise ValueError(f"Unknown alignment '{alignment}'.")
            shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", new_x, new_y)

    def distribute_shapes(self, shapes: List[Any], direction: str, mode: Optional[str] = None) -> None:
        if len(shapes) < 3:
            return  # nothing to distribute between fewer than 3 shapes
        axis = "center_x" if direction == "horizontal" else "center_y"
        ordered = sorted(shapes, key=lambda s: self._shape_bounds(s)[axis])
        first_center = self._shape_bounds(ordered[0])[axis]
        last_center = self._shape_bounds(ordered[-1])[axis]
        step = (last_center - first_center) / (len(ordered) - 1)
        for i, shape in enumerate(ordered[1:-1], start=1):
            target_center = first_center + step * i
            pos, size = shape.Position, shape.Size
            if direction == "horizontal":
                new_x = int(target_center - size.Width / 2)
                shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", new_x, pos.Y)
            else:
                new_y = int(target_center - size.Height / 2)
                shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", pos.X, new_y)

    def group_shapes(self, shapes: List[Any]) -> Any:
        if len(shapes) < 2:
            raise ValueError("group_shapes needs at least 2 shapes.")
        page = shapes[0].getParent()
        collection = self.smgr.createInstanceWithContext("com.sun.star.drawing.ShapeCollection", self.ctx)
        for shape in shapes:
            collection.add(shape)
        return page.group(collection)

    def ungroup_shape(self, shape: Any) -> None:
        page = shape.getParent()
        page.ungroup(shape)

    # combine_shapes/split_shape/bind_shapes/unbind_shape (P3): re-enabled
    # by the draw.py pass's dispatch-safety correction -- the
    # drawing_objects.py pass's original conclusion (.uno: dispatch
    # commands broadly unsafe, since .uno:Combine crashed headless
    # soffice on the next UNO call) turned out to be an artifact of the
    # *external test script's* pattern (URP connection + dispatch + a
    # same-document doc.close() right after), not a real production
    # risk -- see docs/MCP_TOOLING_SCAFFOLD_PLAN.md's draw.py entry for
    # the full re-investigation, live-verified through the real running
    # server this time, not an external script.

    def _select_and_dispatch(self, doc: Any, shapes: List[Any], command: str) -> None:
        controller = doc.getCurrentController()
        if len(shapes) == 1:
            controller.select(shapes[0])
        else:
            collection = self.smgr.createInstanceWithContext("com.sun.star.drawing.ShapeCollection", self.ctx)
            for shape in shapes:
                collection.add(shape)
            controller.select(collection)
        frame = controller.getFrame()
        dispatch_helper = self.smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.ctx)
        dispatch_helper.executeDispatch(frame, command, "", 0, ())

    def combine_shapes(self, doc: Any, shapes: List[Any]) -> Any:
        if len(shapes) < 2:
            raise ValueError("combine_shapes needs at least 2 shapes.")
        self._select_and_dispatch(doc, shapes, ".uno:Combine")
        selection = doc.getCurrentController().getSelection()
        if hasattr(selection, "getCount") and selection.getCount() == 1:
            return selection.getByIndex(0)
        raise NotImplementedError(
            "Combine did not produce a single combined shape for the given shapes -- "
            "LibreOffice's .uno:Combine may not support this shape combination."
        )

    def split_shape(self, doc: Any, shape: Any) -> Any:
        self._select_and_dispatch(doc, [shape], ".uno:Split")
        return doc.getCurrentController().getSelection()

    def bind_shapes(self, doc: Any, shapes: List[Any]) -> Any:
        """Live-verified .uno:Bind no-ops (leaves the input shapes
        unchanged, selection count stays at the input count) for both
        primitive (rectangle/ellipse) and polygon shapes in this
        LibreOffice 26.2 build -- not a dispatch-safety problem (the
        server stays healthy either way, confirmed), genuinely no bound
        shape gets created. Detected explicitly here rather than letting
        the caller crash trying to read .Position off a multi-item
        selection; matches the spec's own "where supported" hedge for
        this tool exactly -- it isn't, in this build, for the shape
        types tested."""
        if len(shapes) < 2:
            raise ValueError("bind_shapes needs at least 2 shapes.")
        self._select_and_dispatch(doc, shapes, ".uno:Bind")
        selection = doc.getCurrentController().getSelection()
        if hasattr(selection, "getCount") and selection.getCount() == 1:
            return selection.getByIndex(0)
        raise NotImplementedError(
            "Bind did not produce a single bound shape for the given shapes -- "
            "live-testing found .uno:Bind no-ops for both primitive and polygon "
            "shapes in this LibreOffice build; matches this tool's own spec "
            "purpose text ('where supported') exactly."
        )

    def unbind_shape(self, doc: Any, shape: Any) -> Any:
        """Not independently live-verified against a genuinely-bound
        shape this pass -- bind_shapes() could not produce one to unbind
        (see its own docstring). Implemented symmetrically with
        split_shape() on the reasonable assumption Unbind's UNO behavior
        mirrors Split's; flagged here rather than silently presented as
        verified."""
        self._select_and_dispatch(doc, [shape], ".uno:Unbind")
        return doc.getCurrentController().getSelection()

    def insert_connector(self, doc: Any, from_shape: Any, to_shape: Any, from_glue: Optional[str] = None,
                          to_glue: Optional[str] = None, connector_type: Optional[str] = None) -> Any:
        page = from_shape.getParent()
        connector = doc.createInstance("com.sun.star.drawing.ConnectorShape")
        page.add(connector)
        connector.StartShape = from_shape
        connector.EndShape = to_shape
        if from_glue is not None:
            connector.StartGluePointIndex = int(from_glue)
        if to_glue is not None:
            connector.EndGluePointIndex = int(to_glue)
        if connector_type is not None:
            try:
                connector.EdgeKind = uno.Enum("com.sun.star.drawing.ConnectorType", connector_type.upper())
            except Exception as e:
                # A bad connector_type (typo/unsupported value) previously
                # failed silently: the connector was still created and
                # returned as if the call fully succeeded, just with
                # whatever EdgeKind default it started with. That's a real
                # caller input error, not an optional/absent feature --
                # surface it like insert_shape() does for an unknown
                # shape_type. connector is already page.add()-ed; remove it
                # so a bad connector_type doesn't leave an orphaned,
                # unregistered connector shape in the document.
                page.remove(connector)
                raise ValueError(f"Unknown connector_type '{connector_type}': {e}") from e
        return connector

    def list_glue_points(self, shape: Any) -> List[Dict[str, Any]]:
        glue_points = shape.getGluePoints()
        result = []
        for i in range(glue_points.getCount()):
            gp = glue_points.getByIndex(i)
            result.append({
                "glue_point_id": str(i),
                "x": gp.Position.X, "y": gp.Position.Y,
                "is_user_defined": bool(gp.IsUserDefined),
            })
        return result

    def add_glue_point(self, shape: Any, position: Dict[str, Any], direction: Optional[str] = None) -> str:
        glue_points = shape.getGluePoints()
        new_gp = uno.createUnoStruct("com.sun.star.drawing.GluePoint2")
        new_gp.Position = uno.createUnoStruct("com.sun.star.awt.Point", int(position.get("x", 0)), int(position.get("y", 0)))
        new_gp.Escape = uno.Enum("com.sun.star.drawing.EscapeDirection", (direction or "SMART").upper())
        new_gp.IsUserDefined = True
        index = glue_points.insert(new_gp)
        return str(index)

    def delete_glue_point(self, shape: Any, glue_point_id: str) -> None:
        glue_points = shape.getGluePoints()
        # Live-verified this container's real method name is
        # removeByIndex(), not remove() -- it doesn't exist (AttributeError).
        glue_points.removeByIndex(int(glue_point_id))

    def insert_image(self, doc: Any, file_path: str, container: Optional[Any] = None,
                      position: Optional[Dict[str, Any]] = None, size: Optional[Dict[str, Any]] = None,
                      anchor: Optional[str] = None, wrap: Optional[str] = None) -> Any:
        page = self._resolve_shape_container(doc, container)
        graphic_provider = self.smgr.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", self.ctx)
        file_url = uno.systemPathToFileUrl(file_path) if "://" not in file_path else file_path
        graphic = graphic_provider.queryGraphic((PropertyValue("URL", 0, file_url, 0),))
        shape = doc.createInstance("com.sun.star.drawing.GraphicObjectShape")
        page.add(shape)
        shape.Graphic = graphic
        if position:
            shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", int(position.get("x", 0)), int(position.get("y", 0)))
        if size:
            shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", int(size.get("width", shape.Size.Width)), int(size.get("height", shape.Size.Height)))
        if anchor is not None and hasattr(shape, "AnchorType"):
            try:
                shape.AnchorType = uno.Enum("com.sun.star.text.TextContentAnchorType", anchor.upper())
            except Exception as e:
                # Same reasoning as insert_connector's connector_type: a
                # bad anchor value is a real caller input error that
                # previously vanished silently, leaving the shape's default
                # anchor in place with no indication anything was wrong.
                # shape is already page.add()-ed at this point (Graphic is
                # set from file_path, which is the far more likely thing to
                # fail and did so before this point) -- remove it before
                # raising so a bad anchor/wrap value doesn't leave an
                # orphaned, unregistered image shape in the document.
                page.remove(shape)
                raise ValueError(f"Unknown anchor '{anchor}': {e}") from e
        if wrap is not None and hasattr(shape, "Surround"):
            try:
                shape.Surround = uno.Enum("com.sun.star.text.WrapTextMode", wrap.upper())
            except Exception as e:
                page.remove(shape)
                raise ValueError(f"Unknown wrap '{wrap}': {e}") from e
        return shape

    def replace_image(self, shape: Any, file_path: str) -> None:
        if not hasattr(shape, "Graphic"):
            raise NotImplementedError("This shape is not an image (no Graphic property).")
        graphic_provider = self.smgr.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", self.ctx)
        file_url = uno.systemPathToFileUrl(file_path) if "://" not in file_path else file_path
        graphic = graphic_provider.queryGraphic((PropertyValue("URL", 0, file_url, 0),))
        shape.Graphic = graphic

    def set_image_properties(self, shape: Any, properties: Dict[str, Any]) -> List[str]:
        if not hasattr(shape, "Graphic"):
            raise NotImplementedError("This shape is not an image (no Graphic property).")
        return self._apply_direct_properties(shape, properties)

    def export_shape(self, shape: Any, file_path: str, format: Optional[str] = None, dpi: Optional[int] = None) -> None:
        """dpi, when given, is converted to explicit PixelWidth/PixelHeight
        FilterData from the shape's own Size (1/100mm) -- live-verified
        this is the property pair GraphicExportFilter actually honors
        (a raw "dpi"-named property is not one of its FilterData keys);
        confirmed the exported PNG's real pixel dimensions via a
        readback through GraphicProvider, not just trusting the filter
        call's own success."""
        export_filter = self.smgr.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", self.ctx)
        export_filter.setSourceDocument(shape)
        media_type = {
            "png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg", "svg": "image/svg+xml",
        }.get((format or "png").lower(), "image/png")
        props = [
            PropertyValue("URL", 0, uno.systemPathToFileUrl(file_path), 0),
            PropertyValue("MediaType", 0, media_type, 0),
        ]
        if dpi:
            size = shape.Size  # 1/100 mm
            pixel_width = round((size.Width / 100 / 25.4) * dpi)
            pixel_height = round((size.Height / 100 / 25.4) * dpi)
            filter_data = uno.Any("[]com.sun.star.beans.PropertyValue", (
                PropertyValue("PixelWidth", 0, max(pixel_width, 1), 0),
                PropertyValue("PixelHeight", 0, max(pixel_height, 1), 0),
            ))
            props.append(PropertyValue("FilterData", 0, filter_data, 0))
        export_filter.filter(tuple(props))

    def list_embedded_objects(self, doc: Any, container: Optional[Any] = None) -> List[Any]:
        return self.list_shapes_in_container(doc, container, type_filter="ole")

    # CLSID identifying each embeddable OLE2Shape's component type --
    # com.sun.star.drawing.OLE2Shape.CLSID is a UNO-wrapped class-id
    # string LibreOffice itself resolves against its own small fixed set
    # of embeddable component types, independent of any real Windows COM
    # registration. Only "formula" is populated: the Math-formula CLSID
    # below is repeated identically and consistently across many
    # independent sources, high enough confidence to ship without a live
    # round trip to confirm it. The other common types (embedded Calc
    # sheet, embedded Writer text, embedded chart) have CLSIDs floating
    # around various tutorials too, but not the same repeated-independent-
    # source confidence -- a wrong CLSID here doesn't fail loudly the way
    # a wrong service name would, exactly the silent-wrong-behavior risk
    # this project's CoreReflection-verification precedent exists to
    # catch. insert_embedded_object() below raises a clear
    # NotImplementedError naming the gap for any other object_type rather
    # than shipping a guessed GUID as fact -- widen this map only once a
    # live pass confirms the next one.
    _EMBEDDED_OBJECT_CLSIDS = {
        "formula": "078B7ABA-54FC-457F-8551-6147E776A997",
    }

    def insert_embedded_object(self, doc: Any, object_type: str, container: Optional[Any] = None,
                                position: Optional[Dict[str, Any]] = None, size: Optional[Dict[str, Any]] = None,
                                data: Optional[Dict[str, Any]] = None) -> Any:
        """Insert an embedded OLE object, CLSID set to identify the
        component type. Two different real mechanisms depending on
        document type -- live-verified both, not assumed:

        - Writer: `doc.createInstance("com.sun.star.drawing.OLE2Shape")`
          raises `com.sun.star.lang.ServiceNotRegisteredException` --
          confirmed live this service is genuinely not on Writer's own
          document-level shape factory (unlike RectangleShape/
          GraphicObjectShape/etc., which ARE, so this isn't a general
          "Writer can't createInstance drawing.* shapes" problem). Writer
          instead needs `com.sun.star.text.TextEmbeddedObject`, inserted
          as text content via `text.insertTextContent()` at a cursor --
          confirmed this still exposes CLSID, Size (it also implements
          XShape), Model, and ExtendedControlOverEmbeddedObject the same
          as OLE2Shape does elsewhere in this file, so nothing downstream
          (get_shape_summary/activate_embedded_object) needs to know
          which route created a given shape. Also added to
          _SHAPE_SERVICE_TYPE_NAMES (short name "ole") so type
          classification/list_embedded_objects_live's filter still finds
          it. Position is the one exception: a freshly-inserted text-
          content object's default AnchorType (AT_PARAGRAPH, confirmed
          live) determines its position from where it landed in the text
          flow -- setting Position directly raises
          `com.sun.star.uno.RuntimeException` ("position cannot be
          changed with this method"), confirmed live, so `position` is
          silently not applied for Writer (Size still is). See
          insert_embedded_object() below for where that's implemented.
        - Calc/Impress/Draw: `com.sun.star.drawing.OLE2Shape` + `page.add()`
          -- the original documented OOo/LibreOffice Basic macro pattern,
          confirmed live still correct for Calc (creates cleanly, Model/
          Formula settable); Impress/Draw share the same document-level
          drawing-shape factory Calc uses so are expected, not
          individually live-verified this pass, to behave the same --
          flagging that honestly rather than assuming silently.

        Scoped to object_type='formula' this pass -- see
        _EMBEDDED_OBJECT_CLSIDS's docstring for why the other embeddable
        types aren't included yet. data={'formula': '<text>'} sets the
        new Math object's formula via its Model's own Formula property,
        the one piece of formula-object content worth setting at
        creation time; any other data key is silently ignored (matching
        this file's established best-effort-property convention)."""
        clsid = self._EMBEDDED_OBJECT_CLSIDS.get(object_type)
        if clsid is None:
            raise NotImplementedError(
                f"insert_embedded_object_live is scoped to object_type='formula' this pass "
                f"(got '{object_type}'). Other embeddable types (Calc sheet, Writer text, "
                "chart, etc.) each need their own live-confirmed CLSID before being added -- "
                "see this method's own docstring."
            )
        is_writer = self._get_document_type(doc) == "writer"
        if is_writer:
            shape = doc.createInstance("com.sun.star.text.TextEmbeddedObject")
            shape.CLSID = clsid
            text = doc.getText()
            cursor = text.createTextCursorByRange(text.getEnd())
            text.insertTextContent(cursor, shape, False)
        else:
            page = self._resolve_shape_container(doc, container)
            shape = doc.createInstance("com.sun.star.drawing.OLE2Shape")
            shape.CLSID = clsid
            page.add(shape)
        # Writer's default AnchorType for a freshly-inserted text-content
        # object is AT_PARAGRAPH (confirmed live) -- position is
        # determined by where it landed in the text flow, and setting
        # Position directly raises com.sun.star.uno.RuntimeException
        # ("position cannot be changed with this method"), confirmed
        # live. Size has no such restriction (confirmed live: sets fine
        # regardless of anchor type). Skipping Position for Writer only;
        # every other insert_*_live tool in this module that supports
        # Writer (insert_image_live) exposes its own `anchor` parameter
        # for exactly this reason -- adding one here, and a matching
        # AT_PAGE/AT_CHARACTER-anchored path that DOES accept Position,
        # is future scope, not attempted this pass.
        if not is_writer:
            shape.Position = uno.createUnoStruct(
                "com.sun.star.awt.Point", int((position or {}).get("x", 0)), int((position or {}).get("y", 0)))
        shape.Size = uno.createUnoStruct(
            "com.sun.star.awt.Size", int((size or {}).get("width", 2000)), int((size or {}).get("height", 1000)))
        if object_type == "formula" and data and data.get("formula") is not None:
            model = shape.Model
            if hasattr(model, "Formula"):
                model.Formula = str(data["formula"])
        return shape

    # Mechanism for activate_embedded_object below, sourced from the
    # documented OOo/LibreOffice Basic macro pattern for driving an
    # embedded OLE object's activation state (Apache OpenOffice Community
    # Forum "Activate Math OLE without window?" thread, corroborated by
    # the XEmbeddedObjectSupplier2/XEmbeddedObject IDL reference at
    # api.libreoffice.org):
    #
    #   oXEO = oShape.ExtendedControlOverEmbeddedObject   ' -> XEmbeddedObject
    #   iCurrentState = oXEO.CurrentState
    #   oXEO.changeState(com.sun.star.embed.EmbedStates.UI_ACTIVE)
    #
    # ExtendedControlOverEmbeddedObject is a property on the embedded
    # object shape (void if the shape has no CLSID / isn't an embedded
    # object), separate from the shape's own Model property
    # insert_embedded_object() above already uses for direct content
    # edits (e.g. a formula's Formula string) -- Model gives the embedded
    # document's own component, ExtendedControlOverEmbeddedObject gives
    # the *lifecycle* control object (com.sun.star.embed.XEmbeddedObject:
    # changeState()/getCurrentState()) that drives verb-based activation
    # independent of what the embedded content is. EmbedStates is a UNO
    # constants group, not an enum -- resolved through
    # uno.getConstantByName() the same way every other constants-group
    # lookup in this file already works (e.g. NumberingType,
    # ReferenceFieldSource above), so no numeric value is hardcoded/
    # guessed here for either direction of the lookup.
    #
    # Live-verified against a real inserted formula object, and the
    # result is why _EMBED_STATE_NAMES below is scoped to 2 of the 4
    # documented states, not all 4: LOADED and RUNNING both change state
    # and read back correctly, near-instantly. ACTIVE and UI_ACTIVE --
    # the two verbs that open an in-place/UI editing view -- each hung
    # `changeState()` indefinitely against this headless soffice
    # instance, reproducibly (confirmed twice, independently, isolating
    # the exact call), wedging the ENTIRE process: every other tool call
    # (including ones with no relation to this shape or this document)
    # timed out until soffice was killed and relaunched. Not a clean
    # error the caller could recover from -- this project's own headless-
    # mode precedent (next/previous_slideshow_effect_live/
    # goto_slideshow_slide_live -- XSlideShowController confirmed always
    # None headless) fails clean; this one doesn't. Given the severity, a
    # UI-opening verb request raises a clear, named error instead of
    # attempting the call -- see this method's docstring. This project's
    # own documented deployment mode is exactly the environment this
    # failed in (README's own dev-workflow/smoke-test scripts launch
    # headless); whether ACTIVE/UI_ACTIVE work in a real GUI-visible
    # session (this project's *other* documented usage: Tools -> MCP
    # Server -> Start MCP Server from an open window) is a real open
    # question for the next live pass, not assumed either way here.
    _EMBED_STATE_NAMES = ("LOADED", "RUNNING")
    _EMBED_STATE_NAMES_BLOCKED_HEADLESS = ("INPLACE_ACTIVE", "UI_ACTIVE", "ACTIVE")

    def activate_embedded_object(self, shape: Any, verb: Optional[str] = None) -> str:
        """Drive an embedded OLE object's activation state via
        XEmbeddedObject.changeState(). verb names one of
        _EMBED_STATE_NAMES (case-insensitive; defaults to "RUNNING", the
        least surprising of the two confirmed-safe states -- LOADED
        actively unloads a running object's UI state, RUNNING is the
        closer match to "activate"'s everyday meaning of "make it live"
        without opening a UI). Raises NotImplementedError, naming the
        live-verified hang, for INPLACE_ACTIVE/UI_ACTIVE/ACTIVE -- see
        this class's own comment above for the finding. Returns the
        resulting state's name, read back from getCurrentState() rather
        than assumed, in case LibreOffice settles on a different state
        than requested."""
        control = getattr(shape, "ExtendedControlOverEmbeddedObject", None)
        if control is None:
            raise ValueError(
                "Shape has no ExtendedControlOverEmbeddedObject -- not an embedded "
                "OLE object (no CLSID set), or the embedded object's control interface "
                "isn't available in this LibreOffice version."
            )
        requested = (verb or "RUNNING").upper()
        if requested in self._EMBED_STATE_NAMES_BLOCKED_HEADLESS:
            raise NotImplementedError(
                f"activate_embedded_object_live verb='{requested}' is not available -- "
                "live-verified this hangs changeState() indefinitely (and wedges the whole "
                "soffice process, not just this call) against a headless instance. Scoped "
                f"to {self._EMBED_STATE_NAMES} until a GUI-visible-session live pass confirms "
                "whether this is headless-specific -- see activate_embedded_object()'s docstring."
            )
        if requested not in self._EMBED_STATE_NAMES:
            raise ValueError(
                f"Unknown verb '{verb}', expected one of {self._EMBED_STATE_NAMES}"
            )
        state = uno.getConstantByName(f"com.sun.star.embed.EmbedStates.{requested}")
        control.changeState(state)
        current = control.getCurrentState()
        for name in self._EMBED_STATE_NAMES:
            if uno.getConstantByName(f"com.sun.star.embed.EmbedStates.{name}") == current:
                return name
        return str(current)

    def delete_embedded_object(self, doc: Any, shape: Any) -> None:
        self.delete_shape(doc, shape)

    # -- Calc sheets, cells, ranges, formulas (tools/calc_sheets.py's 42 tools) --
    #
    # Same raise-on-failure convention as writer_text.py/drawing_objects.py
    # above. Sheet resolution is the live name-or-index scheme
    # docs/OBJECT_HANDLE_DESIGN.md designed (no registry) --
    # _resolve_sheet_by_name_or_index() (already shared with
    # drawing_objects.py's container resolution) is reused directly;
    # _resolve_sheet() below adds the "omitted -> active sheet" fallback
    # this module's tools need on top of it.
    #
    # Cell/range addressing uses A1 notation directly via
    # XCellRangeAccess.getCellRangeByName() -- live-verified this accepts
    # both single cells ("B3") and ranges ("A1:C3") with no manual address
    # parsing needed; the object it returns implements both XCell and
    # XCellRange simultaneously for a single-cell reference.

    def _require_calc(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "calc":
            raise WrongDocumentTypeError(f"{operation} is only implemented for Calc documents, not '{doc_type}'.")

    def _resolve_sheet(self, doc: Any, sheet: Optional[str] = None) -> Any:
        self._require_calc(doc, "sheet resolution")
        if sheet is None:
            return doc.getCurrentController().getActiveSheet()
        return self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet)

    @staticmethod
    def _column_row_to_a1(col: int, row: int) -> str:
        letters = ""
        c = col
        while True:
            letters = chr(ord('A') + c % 26) + letters
            c = c // 26 - 1
            if c < 0:
                break
        return f"{letters}{row + 1}"

    def list_sheets(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_calc(doc, "list_sheets")
        sheets = doc.getSheets()
        result = []
        for i in range(sheets.getCount()):
            sheet = sheets.getByIndex(i)
            result.append({
                "index": i, "name": sheet.Name, "visible": bool(sheet.IsVisible),
                "protected": bool(sheet.isProtected()) if hasattr(sheet, "isProtected") else False,
            })
        return result

    def get_active_sheet(self, doc: Any) -> Dict[str, Any]:
        self._require_calc(doc, "get_active_sheet")
        sheet = doc.getCurrentController().getActiveSheet()
        # A sheet's own index isn't exposed directly -- read it off any
        # cell's address on that sheet (RangeAddress.Sheet), the standard
        # UNO idiom for this.
        index = sheet.getCellRangeByName("A1").RangeAddress.Sheet
        return {"index": index, "name": sheet.Name, "visible": bool(sheet.IsVisible)}

    def activate_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "activate_sheet")
        sheet_obj = self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet)
        doc.getCurrentController().setActiveSheet(sheet_obj)

    def insert_sheet(self, doc: Any, name: str, position: Optional[int] = None) -> None:
        self._require_calc(doc, "insert_sheet")
        sheets = doc.getSheets()
        index = position if position is not None else sheets.getCount()
        sheets.insertNewByName(name, index)

    def delete_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "delete_sheet")
        sheets = doc.getSheets()
        sheet_obj = self._resolve_sheet_by_name_or_index(sheets, sheet)
        sheets.removeByName(sheet_obj.Name)

    def rename_sheet(self, doc: Any, sheet: str, new_name: str) -> None:
        self._require_calc(doc, "rename_sheet")
        sheet_obj = self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet)
        sheet_obj.Name = new_name

    def move_sheet(self, doc: Any, sheet: str, destination_index: int) -> None:
        self._require_calc(doc, "move_sheet")
        sheets = doc.getSheets()
        sheet_obj = self._resolve_sheet_by_name_or_index(sheets, sheet)
        sheets.moveByName(sheet_obj.Name, destination_index)

    def copy_sheet(self, doc: Any, sheet: str, new_name: str, destination_index: Optional[int] = None) -> None:
        self._require_calc(doc, "copy_sheet")
        sheets = doc.getSheets()
        sheet_obj = self._resolve_sheet_by_name_or_index(sheets, sheet)
        index = destination_index if destination_index is not None else sheets.getCount()
        sheets.copyByName(sheet_obj.Name, new_name, index)

    def hide_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "hide_sheet")
        self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet).IsVisible = False

    def show_sheet(self, doc: Any, sheet: str) -> None:
        self._require_calc(doc, "show_sheet")
        self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet).IsVisible = True

    def get_cell(self, doc: Any, cell: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "get_cell")
        cell_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(cell)
        return {
            "cell": cell, "value": cell_obj.getValue(), "formula": cell_obj.getFormula(),
            "display": cell_obj.getString(), "error": cell_obj.getError(),
        }

    def set_cell(self, doc: Any, cell: str, sheet: Optional[str] = None,
                 value: Optional[Any] = None, formula: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "set_cell")
        cell_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(cell)
        if formula is not None:
            cell_obj.setFormula(formula)
        elif value is not None:
            if isinstance(value, bool):
                cell_obj.setValue(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                cell_obj.setValue(float(value))
            else:
                cell_obj.setString(str(value))
        else:
            cell_obj.setString("")
        return {"cell": cell, "display": cell_obj.getString()}

    def get_range(self, doc: Any, range: str, sheet: Optional[str] = None, mode: str = "values") -> Dict[str, Any]:
        self._require_calc(doc, "get_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        result: Dict[str, Any] = {"range": range}
        if mode in ("values", "all"):
            result["values"] = [list(row) for row in range_obj.getDataArray()]
        if mode in ("formulas", "all"):
            result["formulas"] = [list(row) for row in range_obj.getFormulaArray()]
        if mode in ("display", "all"):
            # NOTE: `range` is shadowed by this method's own parameter --
            # builtins.range(...) here is deliberate, not a typo.
            addr = range_obj.RangeAddress
            display = []
            for r in builtins.range(addr.StartRow, addr.EndRow + 1):
                row = [sheet_obj.getCellByPosition(c, r).getString() for c in builtins.range(addr.StartColumn, addr.EndColumn + 1)]
                display.append(row)
            result["display"] = display
        return result

    def set_range(self, doc: Any, values: List[List[Any]], sheet: Optional[str] = None,
                   range: Optional[str] = None, start_cell: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "set_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        if range is not None:
            target = sheet_obj.getCellRangeByName(range)
        elif start_cell is not None:
            start_addr = sheet_obj.getCellRangeByName(start_cell).RangeAddress
            end_row = start_addr.StartRow + len(values) - 1
            end_col = start_addr.StartColumn + max((len(r) for r in values), default=1) - 1
            target = sheet_obj.getCellRangeByPosition(start_addr.StartColumn, start_addr.StartRow, end_col, end_row)
        else:
            raise ValueError("Either range or start_cell must be given.")
        # Stringify every value so Calc's own formula-parser auto-detects
        # numbers/text/formulas the same way typing into a cell would --
        # live-verified setDataArray() does NOT do this (a string like
        # "=1+1" is stored as literal text, not evaluated); setFormulaArray()
        # is the one that does real input-style parsing.
        string_rows = tuple(tuple("" if v is None else str(v) for v in row) for row in values)
        target.setFormulaArray(string_rows)
        return {"applied_rows": len(values)}

    _CLEAR_FLAG_PRESETS = {
        "contents": 1 | 2 | 4 | 16,      # VALUE|DATETIME|STRING|FORMULA
        "formats": 32 | 64 | 256 | 512,  # HARDATTR|STYLES|EDITATTR|FORMATTED
        "comments": 8,                   # ANNOTATION
        "objects": 128,                  # OBJECTS
        "all": 1023,
    }

    def clear_range(self, doc: Any, range: str, sheet: Optional[str] = None, what: str = "contents") -> None:
        self._require_calc(doc, "clear_range")
        flags = self._CLEAR_FLAG_PRESETS.get(what)
        if flags is None:
            raise ValueError(f"Unknown 'what' value '{what}'. Supported: {sorted(self._CLEAR_FLAG_PRESETS)}")
        self._resolve_sheet(doc, sheet).getCellRangeByName(range).clearContents(flags)

    def get_used_range(self, doc: Any, sheet: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "get_used_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        start_cursor = sheet_obj.createCursor()
        start_cursor.gotoStartOfUsedArea(False)
        start_addr = start_cursor.RangeAddress
        end_cursor = sheet_obj.createCursor()
        end_cursor.gotoEndOfUsedArea(False)
        end_addr = end_cursor.RangeAddress
        return {
            "start_column": start_addr.StartColumn, "start_row": start_addr.StartRow,
            "end_column": end_addr.EndColumn, "end_row": end_addr.EndRow,
        }

    _FIND_CELLS_MAX_SCANNED_CELLS = 200000

    def find_cells(self, doc: Any, query: str, sheet: Optional[str] = None, range: Optional[str] = None,
                    look_in: str = "values", match: str = "contains", case_sensitive: bool = False,
                    max_results: int = 100) -> Dict[str, Any]:
        """Search cell values/formulas/comments for `query`, across one
        sheet or the whole workbook. New tool (Brian's priority #2, "the
        biggest obvious Calc hole") -- no prior mechanism in this catalog
        did substring/regex search over cell content at all.

        Scope, deliberately bounded rather than scanning the full
        1M+-row grid: `range` given -> just that range (on `sheet` if
        also given, else the active sheet); `range` omitted -> each
        candidate sheet's own used range (via the same cursor-based
        gotoStartOfUsedArea/gotoEndOfUsedArea technique get_used_range()
        already established), never the whole sheet. `sheet` omitted ->
        every sheet in the workbook (matching "find this anywhere in the
        workbook" from the spec) -- each match reports which sheet it
        came from.

        `look_in="comments"`/`"all"` looks up each candidate cell's
        annotation via a single pre-built {(col,row): text} dict per
        sheet (one pass over that sheet's Annotations), not a fresh
        linear _find_annotation_at() scan per cell -- avoids O(cells x
        annotations) on a sheet with many comments.

        `match="regex"` uses re.search (a `query` matching anywhere in
        the candidate string), consistent with "contains"; not
        re.fullmatch. An invalid regex raises ValueError with the
        original re.error message rather than silently matching nothing
        or crashing with an opaque traceback.

        Stops as soon as `max_results` matches are found OR
        _FIND_CELLS_MAX_SCANNED_CELLS cells have been examined (a
        runaway-scan backstop distinct from max_results -- protects a
        huge used range with very few/no matches from scanning
        indefinitely); `truncated` in the result distinguishes "hit
        max_results" from "hit the scan backstop" from neither.
        """
        self._require_calc(doc, "find_cells")
        if look_in not in ("values", "formulas", "comments", "all"):
            raise ValueError(f"look_in must be one of values/formulas/comments/all, got {look_in!r}")
        if match not in ("contains", "exact", "regex"):
            raise ValueError(f"match must be one of contains/exact/regex, got {match!r}")

        if match == "regex":
            try:
                pattern = re.compile(query, flags=0 if case_sensitive else re.IGNORECASE)
            except re.error as e:
                raise ValueError(f"Invalid regex {query!r}: {e}")

            def is_match(candidate: str) -> bool:
                return pattern.search(candidate) is not None
        elif match == "exact":
            needle = query if case_sensitive else query.lower()

            def is_match(candidate: str) -> bool:
                return (candidate if case_sensitive else candidate.lower()) == needle
        else:  # contains
            needle = query if case_sensitive else query.lower()

            def is_match(candidate: str) -> bool:
                return needle in (candidate if case_sensitive else candidate.lower())

        sheets = doc.getSheets()
        if sheet is not None:
            candidate_sheets = [self._resolve_sheet_by_name_or_index(sheets, sheet)]
        else:
            candidate_sheets = [sheets.getByIndex(i) for i in builtins.range(sheets.getCount())]

        matches: List[Dict[str, Any]] = []
        scanned = 0
        truncated = False
        for sheet_obj in candidate_sheets:
            if len(matches) >= max_results:
                truncated = True
                break
            if range is not None:
                bounds = sheet_obj.getCellRangeByName(range).RangeAddress
            else:
                start_cursor = sheet_obj.createCursor()
                start_cursor.gotoStartOfUsedArea(False)
                end_cursor = sheet_obj.createCursor()
                end_cursor.gotoEndOfUsedArea(False)
                bounds = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
                bounds.StartColumn = start_cursor.RangeAddress.StartColumn
                bounds.StartRow = start_cursor.RangeAddress.StartRow
                bounds.EndColumn = end_cursor.RangeAddress.EndColumn
                bounds.EndRow = end_cursor.RangeAddress.EndRow

            annotation_by_position = {}
            if look_in in ("comments", "all"):
                annotations = sheet_obj.Annotations
                for i in builtins.range(annotations.getCount()):
                    ann = annotations.getByIndex(i)
                    pos = ann.Position
                    if bounds.StartColumn <= pos.Column <= bounds.EndColumn and bounds.StartRow <= pos.Row <= bounds.EndRow:
                        annotation_by_position[(pos.Column, pos.Row)] = ann.getString()

            for row in builtins.range(bounds.StartRow, bounds.EndRow + 1):
                if len(matches) >= max_results:
                    truncated = True
                    break
                for col in builtins.range(bounds.StartColumn, bounds.EndColumn + 1):
                    scanned += 1
                    if scanned > self._FIND_CELLS_MAX_SCANNED_CELLS:
                        truncated = True
                        break
                    cell_obj = sheet_obj.getCellByPosition(col, row)
                    display_value = cell_obj.getString() if look_in in ("values", "all") else None
                    formula = cell_obj.getFormula() if look_in in ("formulas", "all") else None
                    comment = annotation_by_position.get((col, row)) if look_in in ("comments", "all") else None

                    hit = False
                    if display_value and is_match(display_value):
                        hit = True
                    elif formula and is_match(formula):
                        hit = True
                    elif comment and is_match(comment):
                        hit = True
                    if hit:
                        # Report value/formula per the schema regardless of
                        # which look_in mode found the hit -- a caller
                        # matching on a comment still wants to see what's
                        # actually in the cell.
                        matches.append({
                            "sheet": sheet_obj.Name,
                            "address": self._column_row_to_a1(col, row),
                            "value": cell_obj.getString() or None,
                            "formula": cell_obj.getFormula() or None,
                        })
                        if len(matches) >= max_results:
                            truncated = True
                            break
                if scanned > self._FIND_CELLS_MAX_SCANNED_CELLS:
                    truncated = True
                    break

        return {"matches": matches, "count": len(matches), "truncated": truncated}

    def insert_rows(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "insert_rows")
        self._resolve_sheet(doc, sheet).getRows().insertByIndex(index, count)

    def delete_rows(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "delete_rows")
        self._resolve_sheet(doc, sheet).getRows().removeByIndex(index, count)

    def insert_columns(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "insert_columns")
        self._resolve_sheet(doc, sheet).getColumns().insertByIndex(index, count)

    def delete_columns(self, doc: Any, index: int, sheet: Optional[str] = None, count: int = 1) -> None:
        self._require_calc(doc, "delete_columns")
        self._resolve_sheet(doc, sheet).getColumns().removeByIndex(index, count)

    _CELL_SHIFT_INSERT = {"right": "RIGHT", "down": "DOWN"}
    _CELL_SHIFT_DELETE = {"left": "LEFT", "up": "UP"}

    def insert_cells(self, doc: Any, range: str, shift: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "insert_cells")
        mode_name = self._CELL_SHIFT_INSERT.get(shift.lower())
        if mode_name is None:
            raise ValueError(f"shift must be one of {sorted(self._CELL_SHIFT_INSERT)}, got '{shift}'")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_addr = sheet_obj.getCellRangeByName(range).RangeAddress
        sheet_obj.insertCells(range_addr, uno.Enum("com.sun.star.sheet.CellInsertMode", mode_name))

    def delete_cells(self, doc: Any, range: str, shift: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "delete_cells")
        mode_name = self._CELL_SHIFT_DELETE.get(shift.lower())
        if mode_name is None:
            raise ValueError(f"shift must be one of {sorted(self._CELL_SHIFT_DELETE)}, got '{shift}'")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_addr = sheet_obj.getCellRangeByName(range).RangeAddress
        # Live-verified this container's real method name is removeRange(),
        # not removeCells() -- it doesn't exist (AttributeError) -- the
        # same class of "guessed name is wrong" mistake as
        # delete_glue_point_live's fix in the drawing_objects.py pass.
        sheet_obj.removeRange(range_addr, uno.Enum("com.sun.star.sheet.CellDeleteMode", mode_name))

    @staticmethod
    def _cell_address_from_range(range_obj: Any) -> Any:
        addr = range_obj.RangeAddress
        return uno.createUnoStruct("com.sun.star.table.CellAddress", addr.Sheet, addr.StartColumn, addr.StartRow)

    def copy_range(self, doc: Any, source_range: str, dest_cell: str, source_sheet: Optional[str] = None,
                    dest_sheet: Optional[str] = None, include: Optional[Dict[str, Any]] = None) -> None:
        self._require_calc(doc, "copy_range")
        src_sheet_obj = self._resolve_sheet(doc, source_sheet)
        dst_sheet_obj = self._resolve_sheet(doc, dest_sheet) if dest_sheet is not None else src_sheet_obj
        source_addr = src_sheet_obj.getCellRangeByName(source_range).RangeAddress
        dest_addr = self._cell_address_from_range(dst_sheet_obj.getCellRangeByName(dest_cell))
        dst_sheet_obj.copyRange(dest_addr, source_addr)

    def move_range(self, doc: Any, source_range: str, dest_cell: str,
                    source_sheet: Optional[str] = None, dest_sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "move_range")
        src_sheet_obj = self._resolve_sheet(doc, source_sheet)
        dst_sheet_obj = self._resolve_sheet(doc, dest_sheet) if dest_sheet is not None else src_sheet_obj
        source_addr = src_sheet_obj.getCellRangeByName(source_range).RangeAddress
        dest_addr = self._cell_address_from_range(dst_sheet_obj.getCellRangeByName(dest_cell))
        dst_sheet_obj.moveRange(dest_addr, source_addr)

    _FILL_DIRECTIONS = {"down": "TO_BOTTOM", "up": "TO_TOP", "right": "TO_RIGHT", "left": "TO_LEFT"}
    _FILL_MODES = {"linear": "LINEAR", "growth": "GROWTH", "date": "DATE", "auto": "AUTO", "simple": "SIMPLE"}

    def fill_series(self, doc: Any, range: str, direction: str, mode: str, sheet: Optional[str] = None,
                     start: Optional[Any] = None, step: Optional[float] = None, end: Optional[Any] = None) -> None:
        self._require_calc(doc, "fill_series")
        direction_name = self._FILL_DIRECTIONS.get(direction.lower())
        if direction_name is None:
            raise ValueError(f"direction must be one of {sorted(self._FILL_DIRECTIONS)}, got '{direction}'")
        mode_name = self._FILL_MODES.get(mode.lower())
        if mode_name is None:
            raise ValueError(f"mode must be one of {sorted(self._FILL_MODES)}, got '{mode}'")
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        if start is not None:
            # fillSeries needs a seed value already present in the range's
            # first cell -- live-verified an empty first cell produces an
            # entirely empty result, not a series starting from 0.
            first_addr = range_obj.RangeAddress
            first_cell = sheet_obj.getCellByPosition(first_addr.StartColumn, first_addr.StartRow)
            if isinstance(start, (int, float)) and not isinstance(start, bool):
                first_cell.setValue(float(start))
            else:
                first_cell.setString(str(start))
        range_obj.fillSeries(
            uno.Enum("com.sun.star.sheet.FillDirection", direction_name),
            uno.Enum("com.sun.star.sheet.FillMode", mode_name),
            uno.Enum("com.sun.star.sheet.FillDateMode", "FILL_DATE_DAY"),
            float(step) if step is not None else 1.0,
            float(end) if end is not None else 1e20,
        )

    def autofill(self, doc: Any, source_range: str, destination_range: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "autofill")
        sheet_obj = self._resolve_sheet(doc, sheet)
        source_addr = sheet_obj.getCellRangeByName(source_range).RangeAddress
        dest_addr = sheet_obj.getCellRangeByName(destination_range).RangeAddress
        if dest_addr.StartColumn > source_addr.EndColumn:
            direction = "TO_RIGHT"
        elif dest_addr.EndColumn < source_addr.StartColumn:
            direction = "TO_LEFT"
        elif dest_addr.StartRow > source_addr.EndRow:
            direction = "TO_BOTTOM"
        else:
            direction = "TO_TOP"
        source_count = (source_addr.EndRow - source_addr.StartRow + 1) * (source_addr.EndColumn - source_addr.StartColumn + 1)
        # fillAuto's own range argument must span source+destination
        # together (live-verified against a simple down-fill case) --
        # not just the destination.
        full_range = sheet_obj.getCellRangeByPosition(
            min(source_addr.StartColumn, dest_addr.StartColumn), min(source_addr.StartRow, dest_addr.StartRow),
            max(source_addr.EndColumn, dest_addr.EndColumn), max(source_addr.EndRow, dest_addr.EndRow),
        )
        full_range.fillAuto(uno.Enum("com.sun.star.sheet.FillDirection", direction), source_count)

    def _resolve_number_format_key(self, doc: Any, format_string: str, locale: Optional[Any] = None) -> int:
        formats = doc.getNumberFormats()
        locale = locale if locale is not None else uno.createUnoStruct("com.sun.star.lang.Locale")
        key = formats.queryKey(format_string, locale, False)
        if key == -1:
            key = formats.addNew(format_string, locale)
        return key

    def set_range_format(self, doc: Any, range: str, properties: Dict[str, Any], sheet: Optional[str] = None) -> List[str]:
        self._require_calc(doc, "set_range_format")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        applied = []
        for key, val in properties.items():
            try:
                if key == "NumberFormat" and isinstance(val, str):
                    range_obj.setPropertyValue("NumberFormat", self._resolve_number_format_key(doc, val))
                else:
                    range_obj.setPropertyValue(key, val)
                applied.append(key)
            except Exception:
                continue
        return applied

    _RANGE_FORMAT_PROPERTIES = (
        "CellBackColor", "CharColor", "CharWeight", "CharPosture", "CharHeight",
        "HoriJustify", "VertJustify", "IsTextWrapped", "NumberFormat", "IsCellProtected",
    )

    def get_range_format(self, doc: Any, range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "get_range_format")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        result: Dict[str, Any] = {}
        for prop_name in self._RANGE_FORMAT_PROPERTIES:
            try:
                value = self._uno_value_to_plain(range_obj.getPropertyValue(prop_name))
                if self._is_json_safe(value):
                    result[prop_name] = value
            except Exception:
                continue
        return result

    def merge_cells(self, doc: Any, range: str, sheet: Optional[str] = None, center: bool = False) -> None:
        self._require_calc(doc, "merge_cells")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        range_obj.merge(True)
        if center:
            range_obj.HoriJustify = uno.Enum("com.sun.star.table.CellHoriJustify", "CENTER")
            range_obj.VertJustify = uno.Enum("com.sun.star.table.CellVertJustify", "CENTER")

    def unmerge_cells(self, doc: Any, range: str, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "unmerge_cells")
        self._resolve_sheet(doc, sheet).getCellRangeByName(range).merge(False)

    _LENGTH_UNIT_TO_MM100 = {"mm100": 1, "mm": 100, "cm": 1000, "in": 2540, "pt": 35.28}

    def set_row_height(self, doc: Any, rows: List[int], sheet: Optional[str] = None,
                        height: Optional[float] = None, unit: Optional[str] = None, optimal: bool = False) -> None:
        self._require_calc(doc, "set_row_height")
        row_container = self._resolve_sheet(doc, sheet).getRows()
        factor = self._LENGTH_UNIT_TO_MM100.get((unit or "mm100").lower(), 1)
        for idx in rows:
            row_obj = row_container.getByIndex(idx)
            if optimal:
                row_obj.OptimalHeight = True
            elif height is not None:
                row_obj.Height = int(height * factor)

    def set_column_width(self, doc: Any, columns: List[int], sheet: Optional[str] = None,
                          width: Optional[float] = None, unit: Optional[str] = None, optimal: bool = False) -> None:
        self._require_calc(doc, "set_column_width")
        col_container = self._resolve_sheet(doc, sheet).getColumns()
        factor = self._LENGTH_UNIT_TO_MM100.get((unit or "mm100").lower(), 1)
        for idx in columns:
            col_obj = col_container.getByIndex(idx)
            if optimal:
                col_obj.OptimalWidth = True
            elif width is not None:
                col_obj.Width = int(width * factor)

    def hide_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "hide_rows")
        row_container = self._resolve_sheet(doc, sheet).getRows()
        for idx in rows:
            row_container.getByIndex(idx).IsVisible = False

    def show_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "show_rows")
        row_container = self._resolve_sheet(doc, sheet).getRows()
        for idx in rows:
            row_container.getByIndex(idx).IsVisible = True

    def hide_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "hide_columns")
        col_container = self._resolve_sheet(doc, sheet).getColumns()
        for idx in columns:
            col_container.getByIndex(idx).IsVisible = False

    def show_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "show_columns")
        col_container = self._resolve_sheet(doc, sheet).getColumns()
        for idx in columns:
            col_container.getByIndex(idx).IsVisible = True

    def freeze_panes(self, doc: Any, cell: str, sheet: Optional[str] = None) -> None:
        """Live-verified this only takes effect with a real, visible
        controller/window -- same caveat undo_view_selection.py's
        Zoom-property work already documented for view-related state.
        This server's documents are opened with Hidden=False in normal
        operation, so this isn't a practical limitation, just a scope
        note for headless-only testing setups."""
        self._require_calc(doc, "freeze_panes")
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = sheet_obj.getCellRangeByName(cell).RangeAddress
        controller = doc.getCurrentController()
        controller.setActiveSheet(sheet_obj)
        controller.freezeAtPosition(addr.StartColumn, addr.StartRow)

    def unfreeze_panes(self, doc: Any, sheet: Optional[str] = None) -> None:
        self._require_calc(doc, "unfreeze_panes")
        controller = doc.getCurrentController()
        if sheet is not None:
            controller.setActiveSheet(self._resolve_sheet(doc, sheet))
        controller.freezeAtPosition(0, 0)

    def recalculate(self, doc: Any, hard: bool = False) -> None:
        self._require_calc(doc, "recalculate")
        if hard:
            doc.calculateAll()
        else:
            doc.calculate()

    def evaluate_formula(self, doc: Any, formula: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate in workbook context without permanently writing: use
        the target sheet's own last cell (Calc's actual maximum extent,
        AMJ1048576) as scratch space -- so relative references in
        `formula` (e.g. "=A1+B2") resolve against the intended sheet, not
        some other sheet or workbook, while being about as unlikely to
        collide with real data as any single cell can be. Original
        content is saved and restored in a finally block regardless."""
        self._require_calc(doc, "evaluate_formula")
        sheet_obj = self._resolve_sheet(doc, sheet)
        scratch = sheet_obj.getCellByPosition(16383, 1048575)
        original_formula = scratch.getFormula()
        try:
            scratch.setFormula(formula)
            return {
                "formula": formula, "value": scratch.getValue(),
                "display": scratch.getString(), "error": scratch.getError(),
            }
        finally:
            scratch.setFormula(original_formula)

    def _range_address_to_a1(self, doc: Any, addr: Any) -> str:
        sheet_name = doc.getSheets().getByIndex(addr.Sheet).Name
        start = self._column_row_to_a1(addr.StartColumn, addr.StartRow)
        end = self._column_row_to_a1(addr.EndColumn, addr.EndRow)
        return f"{sheet_name}.{start}" if start == end else f"{sheet_name}.{start}:{end}"

    def get_formula_dependencies(self, doc: Any, range: str, sheet: Optional[str] = None,
                                  direction: str = "both") -> Dict[str, Any]:
        self._require_calc(doc, "get_formula_dependencies")
        range_obj = self._resolve_sheet(doc, sheet).getCellRangeByName(range)
        result: Dict[str, Any] = {"range": range}
        if direction in ("precedents", "both"):
            precedents = range_obj.queryPrecedents(False)
            result["precedents"] = [self._range_address_to_a1(doc, a) for a in precedents.RangeAddresses]
        if direction in ("dependents", "both"):
            dependents = range_obj.queryDependents(False)
            result["dependents"] = [self._range_address_to_a1(doc, a) for a in dependents.RangeAddresses]
        return result

    def get_formula_errors(self, doc: Any, sheet: Optional[str] = None, range: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_calc(doc, "get_formula_errors")
        sheet_obj = self._resolve_sheet(doc, sheet)
        if range is not None:
            addr = sheet_obj.getCellRangeByName(range).RangeAddress
        else:
            # Live-verified gotoEndOfUsedArea(False) alone on a fresh
            # cursor (starting at A1) collapses to a single cell -- the
            # end cell -- rather than expanding to cover A1-to-end;
            # gotoStartOfUsedArea() first, then gotoEndOfUsedArea(True)
            # (True = extend the existing selection) on the same cursor
            # is what actually spans the whole used area. Same fix
            # get_used_range() already applied via two separate cursors;
            # this method missed it originally.
            cursor = sheet_obj.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)
            addr = cursor.RangeAddress
        # NOTE: `range` is shadowed by this method's own parameter --
        # builtins.range(...) here is deliberate, not a typo.
        errors = []
        for r in builtins.range(addr.StartRow, addr.EndRow + 1):
            for c in builtins.range(addr.StartColumn, addr.EndColumn + 1):
                cell = sheet_obj.getCellByPosition(c, r)
                err = cell.getError()
                if err != 0:
                    errors.append({"cell": self._column_row_to_a1(c, r), "error_code": err, "display": cell.getString()})
        return errors

    # -- Draw: pages, masters, layers, vector operations (tools/draw.py's 16 tools) --
    #
    # Same raise-on-failure convention as calc_sheets.py/drawing_objects.py
    # above. Page addressing (page: index or name) is the same live
    # name-or-index resolution docs/OBJECT_HANDLE_DESIGN.md designed for
    # Impress/Draw pages -- _resolve_page_by_name_or_index() (already
    # shared with drawing_objects.py's container resolution) is reused
    # directly.
    #
    # Dispatch-safety correction from the drawing_objects.py pass: that
    # pass concluded .uno: dispatch commands were broadly unsafe after
    # .uno:Combine crashed headless soffice. This pass re-investigated
    # that conclusion before assuming it also blocked move_draw_page_live
    # (no non-dispatch UNO API exists for arbitrary page reordering) --
    # and found the crash was an artifact of the *external test script's*
    # own pattern (connect over URP, dispatch, then call doc.close() on
    # the same document), not a defect in dispatch commands themselves.
    # Live-verified through the *actual running extension* (a real
    # tools/_diagnostic module wired into the live server this pass,
    # deleted after the investigation): .uno:MovePageFirst dispatched
    # via the server's own in-process code, confirmed via curl the
    # server stayed healthy afterward, confirmed via an independent raw
    # UNO read that soffice.bin was still running and the page had
    # genuinely moved, and confirmed via a second independent read
    # (without calling close()) that the move was real and stable. So
    # move_draw_page_live IS implemented for real here via
    # .uno:MovePageUp/.uno:MovePageDown dispatch -- see
    # docs/MCP_TOOLING_SCAFFOLD_PLAN.md's draw.py pass for the full
    # writeup, including the follow-up this unblocks for
    # drawing_objects.py's combine/split/bind/unbind.

    def _require_draw(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "draw":
            raise WrongDocumentTypeError(f"{operation} is only implemented for Draw documents, not '{doc_type}'.")

    def _resolve_draw_page(self, doc: Any, page: Optional[Any] = None) -> Any:
        self._require_draw(doc, "draw page resolution")
        if page is None:
            return doc.getCurrentController().getCurrentPage()
        return self._resolve_page_by_name_or_index(doc.getDrawPages(), page)

    @staticmethod
    def _draw_page_index(pages: Any, page_obj: Any) -> Optional[int]:
        for i in range(pages.getCount()):
            if pages.getByIndex(i).Name == page_obj.Name:
                return i
        return None

    def list_draw_pages(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_draw(doc, "list_draw_pages")
        pages = doc.getDrawPages()
        return [{"index": i, "name": pages.getByIndex(i).Name} for i in range(pages.getCount())]

    def get_active_draw_page(self, doc: Any) -> Dict[str, Any]:
        self._require_draw(doc, "get_active_draw_page")
        page = doc.getCurrentController().getCurrentPage()
        return {"index": self._draw_page_index(doc.getDrawPages(), page), "name": page.Name}

    def insert_draw_page(self, doc: Any, position: Optional[int] = None, name: Optional[str] = None) -> Dict[str, Any]:
        self._require_draw(doc, "insert_draw_page")
        pages = doc.getDrawPages()
        index = position if position is not None else pages.getCount()
        new_page = pages.insertNewByIndex(index)
        if name:
            new_page.Name = name
        return {"index": index, "name": new_page.Name}

    def _move_draw_page_to_index(self, doc: Any, current_index: int, destination_index: int) -> None:
        pages = doc.getDrawPages()
        if not (0 <= destination_index < pages.getCount()):
            raise IndexError(f"destination_index {destination_index} out of range (document has {pages.getCount()} page(s)).")
        if current_index == destination_index:
            return
        controller = doc.getCurrentController()
        controller.setCurrentPage(pages.getByIndex(current_index))
        frame = controller.getFrame()
        dispatch_helper = self.smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.ctx)
        command = ".uno:MovePageDown" if destination_index > current_index else ".uno:MovePageUp"
        for _ in range(abs(destination_index - current_index)):
            dispatch_helper.executeDispatch(frame, command, "", 0, ())

    def duplicate_draw_page(self, doc: Any, page: Any, destination: Optional[int] = None) -> Dict[str, Any]:
        """doc.duplicate() (XDrawPageDuplicator) copies the page and all
        its shapes and inserts the copy immediately after the source --
        there's no direct 'duplicate at index N' primitive, so an
        explicit destination is applied afterward via the same
        dispatch-based move insert_draw_page/move_draw_page use."""
        self._require_draw(doc, "duplicate_draw_page")
        source_page = self._resolve_draw_page(doc, page)
        new_page = doc.duplicate(source_page)
        pages = doc.getDrawPages()
        current_index = self._draw_page_index(pages, new_page)
        if destination is not None and destination != current_index:
            self._move_draw_page_to_index(doc, current_index, destination)
            current_index = destination
        return {"index": current_index, "name": new_page.Name}

    def delete_draw_page(self, doc: Any, page: Any) -> None:
        self._require_draw(doc, "delete_draw_page")
        pages = doc.getDrawPages()
        pages.remove(self._resolve_draw_page(doc, page))

    def move_draw_page(self, doc: Any, page: Any, destination_index: int) -> None:
        self._require_draw(doc, "move_draw_page")
        pages = doc.getDrawPages()
        page_obj = self._resolve_draw_page(doc, page)
        current_index = self._draw_page_index(pages, page_obj)
        self._move_draw_page_to_index(doc, current_index, destination_index)

    def rename_draw_page(self, doc: Any, page: Any, name: str) -> None:
        self._require_draw(doc, "rename_draw_page")
        self._resolve_draw_page(doc, page).Name = name

    def set_draw_page_size(self, doc: Any, width: float, height: float, unit: str, page: Optional[Any] = None) -> None:
        """No `orientation` parameter exists in this tool's spec schema
        (only width/height/unit, despite the purpose text mentioning
        orientation) -- matches spec exactly rather than inventing one;
        landscape vs. portrait is expressed by which of width/height is
        larger, the same convention the spec's own parameter list implies."""
        self._require_draw(doc, "set_draw_page_size")
        page_obj = self._resolve_draw_page(doc, page)
        factor = self._LENGTH_UNIT_TO_MM100.get(unit.lower(), 1)
        page_obj.Width = int(width * factor)
        page_obj.Height = int(height * factor)

    def set_draw_page_background(self, doc: Any, page: Any, properties: Dict[str, Any]) -> List[str]:
        """Live-verified a Draw page's fill properties (FillColor,
        FillStyle, etc.) are NOT direct properties of the page itself --
        setting them there raises AttributeError. The real mechanism:
        create a fresh com.sun.star.drawing.Background instance via
        doc.createInstance() (a document-scoped service, not the global
        ServiceManager -- that returns None), apply properties to that
        object (it's a genuine FillProperties implementor), then assign
        it to page.Background. The page's own PropertySetInfo only
        exposes "Background" (an opaque object reference) and
        "IsBackgroundDark" (read-only) -- not "IsBackgroundVisible" or
        "FillColor" as this tool's own scaffolded parameter naming might
        suggest."""
        page_obj = self._resolve_draw_page(doc, page)
        background = doc.createInstance("com.sun.star.drawing.Background")
        applied = self._apply_direct_properties(background, properties)
        page_obj.Background = background
        return applied

    def list_layers(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_draw(doc, "list_layers")
        layer_manager = doc.getLayerManager()
        result = []
        for i in range(layer_manager.getCount()):
            layer = layer_manager.getByIndex(i)
            result.append({
                "index": i, "name": layer.Name, "visible": bool(layer.IsVisible),
                "locked": bool(layer.IsLocked), "printable": bool(layer.IsPrintable),
            })
        return result

    def create_layer(self, doc: Any, name: str, visible: bool = True, locked: bool = False, printable: bool = True) -> Dict[str, Any]:
        self._require_draw(doc, "create_layer")
        layer_manager = doc.getLayerManager()
        layer = layer_manager.insertNewByIndex(layer_manager.getCount())
        layer.Name = name
        layer.IsVisible = visible
        layer.IsLocked = locked
        layer.IsPrintable = printable
        return {"name": layer.Name}

    def update_layer(self, doc: Any, layer: str, properties: Dict[str, Any]) -> List[str]:
        self._require_draw(doc, "update_layer")
        layer_obj = doc.getLayerManager().getByName(layer)
        applied = []
        for key, value in properties.items():
            try:
                if key == "name":
                    layer_obj.Name = value
                else:
                    layer_obj.setPropertyValue(key, value)
                applied.append(key)
            except Exception:
                continue
        return applied

    def delete_layer(self, doc: Any, layer: str) -> None:
        self._require_draw(doc, "delete_layer")
        layer_manager = doc.getLayerManager()
        layer_manager.remove(layer_manager.getByName(layer))

    def assign_shape_layer(self, doc: Any, shape: Any, layer: str) -> None:
        self._require_draw(doc, "assign_shape_layer")
        layer_manager = doc.getLayerManager()
        layer_manager.attachShapeToLayer(shape, layer_manager.getByName(layer))

    _EXPORT_MEDIA_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg", "svg": "image/svg+xml"}

    def export_draw_page(self, doc: Any, page: Any, file_path: str, format: str, options: Optional[Dict[str, Any]] = None) -> None:
        page_obj = self._resolve_draw_page(doc, page)
        media_type = self._EXPORT_MEDIA_TYPES.get(format.lower())
        if media_type is None:
            raise NotImplementedError(
                f"export_draw_page format '{format}' is not implemented -- supported: "
                f"{sorted(self._EXPORT_MEDIA_TYPES)}. PDF export needs the whole-document "
                "storeToURL('impress_pdf_Export'/'draw_pdf_Export') path convert_document_file_live "
                "already uses, not GraphicExportFilter, which is image/vector-graphics only."
            )
        export_filter = self.smgr.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", self.ctx)
        export_filter.setSourceDocument(page_obj)
        props = [
            PropertyValue("URL", 0, uno.systemPathToFileUrl(file_path), 0),
            PropertyValue("MediaType", 0, media_type, 0),
        ]
        if options:
            filter_data = uno.Any("[]com.sun.star.beans.PropertyValue", tuple(
                PropertyValue(k, 0, v, 0) for k, v in options.items()
            ))
            props.append(PropertyValue("FilterData", 0, filter_data, 0))
        export_filter.filter(tuple(props))

    def export_selection(self, doc: Any, file_path: str, format: str = "png", dpi: Optional[int] = None) -> None:
        """Live-verified GraphicExportFilter.setSourceDocument() accepts a
        multi-shape ShapeCollection directly -- no need to group the
        selection first (which would mutate the document as an unwanted
        side effect of what's meant to be a read-only export)."""
        self._require_draw(doc, "export_selection")
        selection = doc.getCurrentController().getSelection()
        if not hasattr(selection, "getCount") or selection.getCount() == 0:
            raise ValueError("No shapes are currently selected.")
        export_filter = self.smgr.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", self.ctx)
        export_filter.setSourceDocument(selection)
        media_type = self._EXPORT_MEDIA_TYPES.get(format.lower())
        if media_type is None:
            raise NotImplementedError(f"export_selection format '{format}' is not implemented -- supported: {sorted(self._EXPORT_MEDIA_TYPES)}.")
        props = [
            PropertyValue("URL", 0, uno.systemPathToFileUrl(file_path), 0),
            PropertyValue("MediaType", 0, media_type, 0),
        ]
        if dpi:
            # Combined bounding box across every selected shape, same
            # 1/100mm-to-pixel conversion export_shape() uses for a
            # single shape.
            lefts, tops, rights, bottoms = [], [], [], []
            for i in range(selection.getCount()):
                bounds = self._shape_bounds(selection.getByIndex(i))
                lefts.append(bounds["left"]); tops.append(bounds["top"])
                rights.append(bounds["right"]); bottoms.append(bounds["bottom"])
            width_mm100 = max(rights) - min(lefts)
            height_mm100 = max(bottoms) - min(tops)
            pixel_width = round((width_mm100 / 100 / 25.4) * dpi)
            pixel_height = round((height_mm100 / 100 / 25.4) * dpi)
            filter_data = uno.Any("[]com.sun.star.beans.PropertyValue", (
                PropertyValue("PixelWidth", 0, max(pixel_width, 1), 0),
                PropertyValue("PixelHeight", 0, max(pixel_height, 1), 0),
            ))
            props.append(PropertyValue("FilterData", 0, filter_data, 0))
        export_filter.filter(tuple(props))


    # -- Charts and data visualizations (tools/charts.py's 20 tools) --
    #
    # Same raise-on-failure convention as drawing_objects.py/calc_sheets.py
    # above. Scope, deliberate: Calc-native embedded charts only this
    # pass (chart_id resolves via XTablesSupplier.getCharts(), the
    # UNO-guaranteed-unique-Name container docs/OBJECT_HANDLE_DESIGN.md
    # already designed this exact resolution for -- no registry needed,
    # same category as sheets/Writer tables). Writer/Impress/Draw
    # embedded charts (generic OLE2Shape wrapping a chart document, not
    # addressable through a dedicated named container) are NOT
    # implemented this pass -- see docs/OBJECT_HANDLE_DESIGN.md's own
    # note that chart_id resolution is "genuinely mixed by host document
    # type"; extending list_charts_live/create_chart_live to the
    # ObjectRegistry-backed path for non-Calc hosts is left for a
    # follow-up, matching the project's established pattern of an
    # honest, documented per-doctype scope limit (e.g. styles.py's
    # apply_style_live being Writer-only its first pass).
    #
    # series_id is a plain string index into
    # XChartType.getDataSeries() (0-based) -- chart2's own data series
    # have no persistent name/identity of their own to key by, only
    # positional order within their chart type, so index is the natural
    # (and spec-compatible, since series_id is just an opaque string)
    # choice, mirroring writer_text.py's 1-based paragraph-ordinal
    # precedent for "no natural identity, use position."
    #
    # A chart's real geometry/export both go through its backing OLE2Shape
    # on the sheet's draw page, found by matching PersistName == chart_id
    # (live-verified this is the actual UNO linkage -- the shape's own
    # .Name is empty; TableChart itself exposes no Position/Size).

    def _require_chart_capable(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "calc":
            raise WrongDocumentTypeError(
                f"{operation} is only implemented for Calc-native embedded charts this pass, not '{doc_type}' documents."
            )

    def _find_chart_by_name(self, doc: Any, chart_id: str) -> "tuple[Any, Any, Any]":
        """Search every sheet's native chart collection for chart_id (the
        chart's own unique Name). Returns (sheet, charts_collection,
        chart_table_object)."""
        self._require_chart_capable(doc, "chart resolution")
        sheets = doc.getSheets()
        for i in range(sheets.getCount()):
            sheet = sheets.getByIndex(i)
            charts = sheet.getCharts()
            if charts.hasByName(chart_id):
                return sheet, charts, charts.getByName(chart_id)
        raise KeyError(f"No such chart '{chart_id}'.")

    def _find_chart_shape(self, sheet: Any, chart_id: str) -> Any:
        page = sheet.getDrawPage()
        for i in range(page.getCount()):
            shape = page.getByIndex(i)
            try:
                if shape.getPropertyValue("PersistName") == chart_id:
                    return shape
            except Exception:
                continue
        raise KeyError(f"No shape found backing chart '{chart_id}'.")

    @staticmethod
    def _get_chart_document(chart_table: Any) -> Any:
        return chart_table.getEmbeddedObject()

    @staticmethod
    def _get_first_chart_type(chart_doc: Any) -> "tuple[Any, Any]":
        """Returns (coordinate_system, chart_type) for the first/only
        coordinate system and chart type -- every chart this module
        creates has exactly one of each; multi-coordinate-system combo
        charts are out of scope."""
        diagram = chart_doc.getFirstDiagram()
        cs = diagram.getCoordinateSystems()[0]
        return cs, cs.getChartTypes()[0]

    _CHART_TYPE_SERVICES = {
        "bar": "com.sun.star.chart2.BarChartType",
        "column": "com.sun.star.chart2.ColumnChartType",
        "line": "com.sun.star.chart2.LineChartType",
        "pie": "com.sun.star.chart2.PieChartType",
        "area": "com.sun.star.chart2.AreaChartType",
        "scatter": "com.sun.star.chart2.ScatterChartType",
        "xy": "com.sun.star.chart2.ScatterChartType",
        "bubble": "com.sun.star.chart2.BubbleChartType",
        "net": "com.sun.star.chart2.NetChartType",
        "radar": "com.sun.star.chart2.NetChartType",
        "stock": "com.sun.star.chart2.CandleStickChartType",
        "candlestick": "com.sun.star.chart2.CandleStickChartType",
        "filled_net": "com.sun.star.chart2.FilledNetChartType",
    }

    def list_charts(self, doc: Any, container: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_chart_capable(doc, "list_charts")
        sheets = doc.getSheets()
        targets = [self._resolve_sheet_by_name_or_index(sheets, container)] if container is not None else \
            [sheets.getByIndex(i) for i in range(sheets.getCount())]
        result = []
        for sheet in targets:
            charts = sheet.getCharts()
            for name in charts.getElementNames():
                chart_table = charts.getByName(name)
                result.append({
                    "chart_id": name, "sheet": sheet.Name,
                    "ranges": [self._range_address_to_a1(doc, r) for r in chart_table.Ranges],
                })
        return result

    def create_chart(self, doc: Any, chart_type: str, source: Optional[str] = None,
                      data: Optional[List[List[Any]]] = None, container: Optional[str] = None,
                      position: Optional[Dict[str, Any]] = None, size: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._require_chart_capable(doc, "create_chart")
        service_name = self._CHART_TYPE_SERVICES.get(chart_type.lower())
        if service_name is None:
            raise ValueError(f"Unknown chart_type '{chart_type}'. Supported: {sorted(self._CHART_TYPE_SERVICES)}")
        sheet = self._resolve_sheet(doc, container)
        if source is not None:
            ranges = (sheet.getCellRangeByName(source).RangeAddress,)
        elif data is not None:
            raise NotImplementedError(
                "create_chart_live with explicit 'data' (no 'source') is not implemented this pass -- "
                "write the values to a range first (e.g. via set_range_live) and pass that as 'source'."
            )
        else:
            raise ValueError("Either source or data must be given.")
        pos = position or {}
        sz = size or {}
        rect = uno.createUnoStruct("com.sun.star.awt.Rectangle")
        rect.X, rect.Y = int(pos.get("x", 0)), int(pos.get("y", 0))
        rect.Width, rect.Height = int(sz.get("width", 10000)), int(sz.get("height", 8000))
        charts = sheet.getCharts()
        index = 1
        while charts.hasByName(f"Chart {index}"):
            index += 1
        name = f"Chart {index}"
        charts.addNewByName(name, rect, ranges, True, True)
        chart_doc = self._get_chart_document(charts.getByName(name))
        cs, default_ct = self._get_first_chart_type(chart_doc)
        if not default_ct.supportsService(service_name):
            new_ct = self.smgr.createInstanceWithContext(service_name, self.ctx)
            new_ct.setDataSeries(default_ct.getDataSeries())
            cs.setChartTypes((new_ct,))
        return {"chart_id": name, "sheet": sheet.Name}

    def get_chart(self, doc: Any, chart_id: str) -> Dict[str, Any]:
        sheet, charts, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        cs, ct = self._get_first_chart_type(chart_doc)
        title_obj = chart_doc.getTitleObject()
        title_text = " ".join(s.getString() for s in title_obj.getText()) if title_obj is not None else None
        return {
            "chart_id": chart_id, "sheet": sheet.Name,
            "chart_type": ct.SupportedServiceNames[0] if hasattr(ct, "SupportedServiceNames") else ct.getSupportedServiceNames()[0],
            "title": title_text, "has_legend": bool(chart_doc.HasLegend),
            "series_count": len(ct.getDataSeries()),
            "ranges": [self._range_address_to_a1(doc, r) for r in chart_table.Ranges],
        }

    def delete_chart(self, doc: Any, chart_id: str) -> None:
        sheet, charts, chart_table = self._find_chart_by_name(doc, chart_id)
        charts.removeByName(chart_id)

    def set_chart_type(self, doc: Any, chart_id: str, chart_type: str, subtype: Optional[str] = None) -> None:
        service_name = self._CHART_TYPE_SERVICES.get(chart_type.lower())
        if service_name is None:
            raise ValueError(f"Unknown chart_type '{chart_type}'. Supported: {sorted(self._CHART_TYPE_SERVICES)}")
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        cs, old_ct = self._get_first_chart_type(chart_doc)
        new_ct = self.smgr.createInstanceWithContext(service_name, self.ctx)
        new_ct.setDataSeries(old_ct.getDataSeries())
        cs.setChartTypes((new_ct,))

    def set_chart_data(self, doc: Any, chart_id: str, source_range: Optional[str] = None,
                        data: Optional[List[List[Any]]] = None, categories: Optional[List[str]] = None) -> None:
        sheet, charts, chart_table = self._find_chart_by_name(doc, chart_id)
        if source_range is not None:
            range_addr = sheet.getCellRangeByName(source_range).RangeAddress
            chart_table.setRanges((range_addr,))
        elif data is not None:
            raise NotImplementedError(
                "set_chart_data_live with explicit 'data' (no 'source_range') is not implemented this pass -- "
                "write the values to a range first and pass that as 'source_range'."
            )
        else:
            raise ValueError("Either source_range or data must be given.")

    def set_chart_title(self, doc: Any, chart_id: str, title: Optional[str] = None,
                         subtitle: Optional[str] = None, properties: Optional[Dict[str, Any]] = None) -> List[str]:
        """subtitle isn't a distinct concept in chart2's XTitled (one main
        title object) -- appended as a second line of the same title,
        the closest real-UNO equivalent, documented rather than silently
        dropped."""
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        applied = []
        if title is not None:
            title_obj = self.smgr.createInstanceWithContext("com.sun.star.chart2.Title", self.ctx)
            texts = []
            main_fs = self.smgr.createInstanceWithContext("com.sun.star.chart2.FormattedString", self.ctx)
            main_fs.setString(title)
            texts.append(main_fs)
            if subtitle is not None:
                sub_fs = self.smgr.createInstanceWithContext("com.sun.star.chart2.FormattedString", self.ctx)
                sub_fs.setString(subtitle)
                texts.append(sub_fs)
            title_obj.setText(tuple(texts))
            chart_doc.setTitleObject(title_obj)
            applied.append("title")
            if subtitle is not None:
                applied.append("subtitle")
        if properties:
            title_obj = chart_doc.getTitleObject()
            if title_obj is not None:
                applied.extend(self._apply_direct_properties(title_obj, properties))
        return applied

    # Live-verified via CoreReflection: com.sun.star.chart2.LegendPosition
    # has NO TOP/BOTTOM/LEFT/RIGHT members (a legend.AnchorPosition = TOP
    # attempt raises "value TOPis unknown in enum ..."-- caught testing
    # this pass) -- only LINE_START/LINE_END/PAGE_START/PAGE_END/CUSTOM.
    # "top"/"bottom"/"left"/"right" are convenience aliases onto the real
    # enum values (PAGE_START/PAGE_END sit above/below the diagram,
    # LINE_START/LINE_END sit to its start/end side in reading order).
    _LEGEND_POSITIONS = {
        "top": "PAGE_START", "bottom": "PAGE_END", "left": "LINE_START", "right": "LINE_END",
        "line_start": "LINE_START", "line_end": "LINE_END", "page_start": "PAGE_START", "page_end": "PAGE_END",
        "custom": "CUSTOM",
    }

    def set_chart_legend(self, doc: Any, chart_id: str, visible: Optional[bool] = None,
                          position: Optional[str] = None, properties: Optional[Dict[str, Any]] = None) -> List[str]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        applied = []
        if visible is not None:
            chart_doc.HasLegend = visible
            applied.append("visible")
        legend = chart_doc.getFirstDiagram().getLegend()
        if legend is not None:
            if position is not None:
                pos_name = self._LEGEND_POSITIONS.get(position.lower())
                if pos_name is not None:
                    legend.AnchorPosition = uno.Enum("com.sun.star.chart2.LegendPosition", pos_name)
                    applied.append("position")
            if properties:
                applied.extend(self._apply_direct_properties(legend, properties))
        return applied

    def get_chart_series(self, doc: Any, chart_id: str) -> List[Dict[str, Any]]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = ct.getDataSeries()
        result = []
        for i, series in enumerate(series_list):
            entry = {"series_id": str(i)}
            try:
                entry["color"] = series.Color
            except Exception:
                pass
            result.append(entry)
        return result

    def set_chart_series(self, doc: Any, chart_id: str, series_id: str, properties: Dict[str, Any]) -> List[str]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = ct.getDataSeries()
        index = int(series_id)
        if not (0 <= index < len(series_list)):
            raise IndexError(f"series_id {series_id} out of range (chart has {len(series_list)} series).")
        return self._apply_direct_properties(series_list[index], properties)

    def add_chart_series(self, doc: Any, chart_id: str, values: List[float], label: Optional[str] = None,
                          categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """Real implementation. Live-verified this pass: chart2's public
        XDataProvider has no createDataSequenceByValueArray -- a Calc chart's
        data provider only builds XDataSequence objects from a range
        representation string (createDataSequenceByRangeRepresentation),
        confirmed against the interface reference. So raw in-memory `values`
        get written to a real, untouched scratch range first -- two columns
        past the sheet's current used area (a gap column, then the series'
        own column(s)), found fresh via gotoEndOfUsedArea each call so
        repeated add_chart_series_live calls on the same chart stagger
        further right automatically rather than colliding -- then that range
        is wired into a new chart2 DataSeries via XDataSink.setData(), same
        mechanism doc creates read for get_chart_series_live/
        set_chart_series_live above.

        Scope limit: only the "values-y" role is populated (the primary
        value role every chart type in _CHART_TYPE_SERVICES supports); a
        values-x role for scatter/bubble charts is left for a follow-up,
        same honest-cut precedent as create_chart_live's data-array branch.

        `categories` is wired as its own Role="categories" labeled sequence
        on the new series, not just written to cells -- an earlier version
        of this method wrote the category cells but never attached them to
        any data sequence, silently orphaning the values (caught by
        independently reading the raw chart2 series back after this pass's
        REST round trip, not by trusting this method's own return value).
        """
        sheet, charts, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        cs, ct = self._get_first_chart_type(chart_doc)
        series_list = list(ct.getDataSeries())
        if not values:
            raise ValueError("values must be a non-empty list.")

        used_cursor = sheet.createCursor()
        used_cursor.gotoEndOfUsedArea(False)
        used_addr = used_cursor.RangeAddress
        values_col = used_addr.EndColumn + 2
        start_row = 1 if label is not None else 0

        if label is not None:
            sheet.getCellByPosition(values_col, 0).setString(label)
        for i, value in enumerate(values):
            sheet.getCellByPosition(values_col, start_row + i).setValue(float(value))
        if categories:
            cats_col = values_col - 1
            for i, category in enumerate(categories):
                sheet.getCellByPosition(cats_col, start_row + i).setString(category)

        end_row = start_row + len(values) - 1
        values_range = sheet.getCellRangeByPosition(values_col, start_row, values_col, end_row)
        values_range_str = self._range_address_to_a1(doc, values_range.RangeAddress)

        data_provider = chart_doc.getDataProvider()
        values_seq = data_provider.createDataSequenceByRangeRepresentation(values_range_str)
        values_seq.setPropertyValue("Role", "values-y")
        labeled_seq = self.smgr.createInstanceWithContext(
            "com.sun.star.chart2.data.LabeledDataSequence", self.ctx)
        labeled_seq.setValues(values_seq)
        if label is not None:
            label_range = sheet.getCellRangeByPosition(values_col, 0, values_col, 0)
            label_seq = data_provider.createDataSequenceByRangeRepresentation(
                self._range_address_to_a1(doc, label_range.RangeAddress))
            label_seq.setPropertyValue("Role", "label")
            labeled_seq.setLabel(label_seq)

        data_sequences = [labeled_seq]
        if categories:
            cats_col = values_col - 1
            cats_range = sheet.getCellRangeByPosition(cats_col, start_row, cats_col, end_row)
            cats_range_str = self._range_address_to_a1(doc, cats_range.RangeAddress)
            cats_seq = data_provider.createDataSequenceByRangeRepresentation(cats_range_str)
            cats_seq.setPropertyValue("Role", "categories")
            cats_labeled_seq = self.smgr.createInstanceWithContext(
                "com.sun.star.chart2.data.LabeledDataSequence", self.ctx)
            cats_labeled_seq.setValues(cats_seq)
            data_sequences.append(cats_labeled_seq)

        new_series = self.smgr.createInstanceWithContext("com.sun.star.chart2.DataSeries", self.ctx)
        new_series.setData(tuple(data_sequences))
        ct.setDataSeries(tuple(series_list + [new_series]))

        return {"series_id": str(len(series_list)), "range": values_range_str}

    def remove_chart_series(self, doc: Any, chart_id: str, series_id: str) -> None:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = list(ct.getDataSeries())
        index = int(series_id)
        if not (0 <= index < len(series_list)):
            raise IndexError(f"series_id {series_id} out of range (chart has {len(series_list)} series).")
        del series_list[index]
        ct.setDataSeries(tuple(series_list))

    _AXIS_DIMENSIONS = {"x": 0, "y": 1, "z": 2}

    def _resolve_axis(self, chart_doc: Any, axis: str) -> Any:
        cs, _ = self._get_first_chart_type(chart_doc)
        dimension = self._AXIS_DIMENSIONS.get(axis.lower())
        if dimension is None:
            raise ValueError(f"axis must be one of {sorted(self._AXIS_DIMENSIONS)}, got '{axis}'")
        return cs.getAxisByDimension(dimension, 0)

    def set_chart_axis(self, doc: Any, chart_id: str, axis: str, properties: Dict[str, Any]) -> List[str]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        axis_obj = self._resolve_axis(chart_doc, axis)
        applied = []
        scale = axis_obj.getScaleData()
        scale_changed = False
        for key in ("min", "minimum"):
            if key in properties:
                scale.Minimum = float(properties[key])
                applied.append(key)
                scale_changed = True
        for key in ("max", "maximum"):
            if key in properties:
                scale.Maximum = float(properties[key])
                applied.append(key)
                scale_changed = True
        if scale_changed:
            axis_obj.setScaleData(scale)
        remaining = {k: v for k, v in properties.items() if k not in ("min", "minimum", "max", "maximum")}
        applied.extend(self._apply_direct_properties(axis_obj, remaining))
        return applied

    # The visibility toggles (ShowNumber/ShowCategoryName/etc.) live-verified
    # to NOT be direct settable properties on XDataSeries -- they're fields
    # of its "Label" property, a com.sun.star.chart2.DataPointLabel struct
    # (setPropertyValue("ShowNumber", ...) directly is a silent no-op via
    # _apply_direct_properties's own unsettable-property skip, caught
    # testing this pass). Handled here by read-modify-write on the whole
    # struct; every other DataPointLabel field name is passed straight
    # through the same way.
    _DATA_LABEL_STRUCT_FIELDS = {
        "ShowNumber", "ShowNumberInPercent", "ShowCategoryName",
        "ShowLegendSymbol", "ShowCustomLabel", "ShowSeriesName",
    }

    def set_chart_data_labels(self, doc: Any, chart_id: str, properties: Dict[str, Any],
                               series_id: Optional[str] = None) -> List[str]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = ct.getDataSeries()
        targets = [series_list[int(series_id)]] if series_id is not None else list(series_list)

        struct_updates = {k: v for k, v in properties.items() if k in self._DATA_LABEL_STRUCT_FIELDS}
        remaining = {k: v for k, v in properties.items() if k not in self._DATA_LABEL_STRUCT_FIELDS}

        applied_sets = []
        for target in targets:
            applied = []
            if struct_updates:
                label = target.getPropertyValue("Label")
                for key, value in struct_updates.items():
                    setattr(label, key, value)
                    applied.append(key)
                target.setPropertyValue("Label", label)
            applied.extend(self._apply_direct_properties(target, remaining))
            applied_sets.append(applied)
        return applied_sets[0] if applied_sets else []

    def set_chart_gridlines(self, doc: Any, chart_id: str, axis: str, major: Optional[bool] = None,
                             minor: Optional[bool] = None, properties: Optional[Dict[str, Any]] = None) -> List[str]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        axis_obj = self._resolve_axis(chart_doc, axis)
        applied = []
        if major is not None:
            axis_obj.getGridProperties().Show = major
            applied.append("major")
        if minor is not None:
            axis_obj.getSubGridProperties()[0].Show = minor
            applied.append("minor")
        if properties:
            applied.extend(self._apply_direct_properties(axis_obj.getGridProperties(), properties))
        return applied

    _TRENDLINE_SERVICES = {
        "linear": "com.sun.star.chart2.LinearRegressionCurve",
        "exponential": "com.sun.star.chart2.ExponentialRegressionCurve",
        "logarithmic": "com.sun.star.chart2.LogarithmicRegressionCurve",
        "power": "com.sun.star.chart2.PotentialRegressionCurve",
        "polynomial": "com.sun.star.chart2.PolynomialRegressionCurve",
        "moving_average": "com.sun.star.chart2.MovingAverageRegressionCurve",
    }

    def add_chart_trendline(self, doc: Any, chart_id: str, series_id: str, type: str,
                             properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        service_name = self._TRENDLINE_SERVICES.get(type.lower())
        if service_name is None:
            raise ValueError(f"Unknown trendline type '{type}'. Supported: {sorted(self._TRENDLINE_SERVICES)}")
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = ct.getDataSeries()
        index = int(series_id)
        if not (0 <= index < len(series_list)):
            raise IndexError(f"series_id {series_id} out of range (chart has {len(series_list)} series).")
        series = series_list[index]
        curve = self.smgr.createInstanceWithContext(service_name, self.ctx)
        if properties:
            self._apply_direct_properties(curve, properties)
        series.addRegressionCurve(curve)
        return {"series_id": series_id, "type": type, "trendline_id": str(len(series.getRegressionCurves()) - 1)}

    def remove_chart_trendline(self, doc: Any, chart_id: str, series_id: str, trendline_id: Optional[str] = None) -> None:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = ct.getDataSeries()
        index = int(series_id)
        if not (0 <= index < len(series_list)):
            raise IndexError(f"series_id {series_id} out of range (chart has {len(series_list)} series).")
        series = series_list[index]
        curves = series.getRegressionCurves()
        curve_index = int(trendline_id) if trendline_id is not None else 0
        if not (0 <= curve_index < len(curves)):
            raise IndexError(f"trendline_id {trendline_id} out of range (series has {len(curves)} trendline(s)).")
        series.removeRegressionCurve(curves[curve_index])

    def set_chart_error_bars(self, doc: Any, chart_id: str, series_id: str, properties: Dict[str, Any]) -> List[str]:
        _, _, chart_table = self._find_chart_by_name(doc, chart_id)
        chart_doc = self._get_chart_document(chart_table)
        _, ct = self._get_first_chart_type(chart_doc)
        series_list = ct.getDataSeries()
        index = int(series_id)
        if not (0 <= index < len(series_list)):
            raise IndexError(f"series_id {series_id} out of range (chart has {len(series_list)} series).")
        series = series_list[index]
        error_bar = self.smgr.createInstanceWithContext("com.sun.star.chart2.ErrorBar", self.ctx)
        applied = self._apply_direct_properties(error_bar, properties)
        series.setPropertyValue("ErrorBarY", error_bar)
        return applied

    def set_chart_geometry(self, doc: Any, chart_id: str, position: Optional[Dict[str, Any]] = None,
                            size: Optional[Dict[str, Any]] = None) -> List[str]:
        sheet, charts, chart_table = self._find_chart_by_name(doc, chart_id)
        shape = self._find_chart_shape(sheet, chart_id)
        applied = []
        if position:
            pos = shape.Position
            shape.Position = uno.createUnoStruct(
                "com.sun.star.awt.Point", int(position.get("x", pos.X)), int(position.get("y", pos.Y)),
            )
            applied.extend(k for k in ("x", "y") if k in position)
        if size:
            sz = shape.Size
            shape.Size = uno.createUnoStruct(
                "com.sun.star.awt.Size", int(size.get("width", sz.Width)), int(size.get("height", sz.Height)),
            )
            applied.extend(k for k in ("width", "height") if k in size)
        return applied

    def export_chart(self, doc: Any, chart_id: str, file_path: str, format: str = "png",
                      dpi: Optional[int] = None) -> None:
        sheet, charts, chart_table = self._find_chart_by_name(doc, chart_id)
        shape = self._find_chart_shape(sheet, chart_id)
        self.export_shape(shape, file_path, format, dpi)

    # -- Impress: slides, masters, notes, transitions, animations, slideshow
    # (tools/impress.py's 41 tools) --
    #
    # Same raise-on-failure convention as draw.py/charts.py above. Slide
    # addressing (`slide`: index or name) reuses `_resolve_page_by_name_or_
    # index()`, the same live name-or-index resolution draw.py/
    # drawing_objects.py already share. `_move_draw_page_to_index()`
    # (draw.py's section) is itself document-type-agnostic -- it only
    # calls doc.getDrawPages()/doc.getCurrentController(), nothing
    # Draw-specific -- so it's reused directly here for move_slide_live's
    # dispatch-based reorder, not duplicated.
    #
    # **Known verification gap, found live-testing this pass, NOT silently
    # presented as verified:** move_slide_live's dispatch-based reorder
    # (.uno:MovePageUp/.uno:MovePageDown, the same mechanism draw.py
    # proved safe and effective for Draw documents) reports the dispatch
    # as genuinely enabled (confirmed via XStatusListener: IsEnabled=True)
    # and the dispatch pipeline itself is confirmed working in this exact
    # setup (a control test with .uno:DuplicatePage on the same frame DID
    # visibly add a page) -- but repeated attempts (setCurrentPage(),
    # select(), both together, via frame.queryDispatch().dispatch(), via
    # DispatchHelper, via desktop.getCurrentFrame(), with up to 1.5s
    # settle time) never produced an observed reorder in
    # doc.getDrawPages() for an Impress document specifically, headless.
    # The code below is the correct, spec-compliant implementation (no
    # native "move page to index" UNO API exists for Impress either, same
    # as Draw) and is left in rather than stubbed, but this pass could NOT
    # live-verify it takes effect -- flagged for a follow-up with a real
    # GUI/virtual-display session, not silently claimed as working.
    #
    # AutoLayout is an unvalidated integer property (0-20 all accepted
    # without error) with no queryable name table via CoreReflection this
    # pass (it isn't a discoverable IDL enum/constants group the way
    # LegendPosition was for charts.py). Only 4 values were empirically
    # verified by inspecting the actual placeholder shapes a fresh slide
    # gets at each value: 0 = title+subtitle, 1 = title+content,
    # 19 = title only, 20 = blank. _LAYOUT_NAMES below covers only those
    # 4 confirmed values; every other AutoLayout number is still usable
    # via a raw int, matching the honest-scope-limit precedent (guessing
    # the rest of the ~20-entry table risked repeating the LegendPosition/
    # DataPointLabel mistake from the charts.py pass instead of learning
    # from it).
    #
    # Similarly, set_slide_transition_live's `effect` accepts a raw
    # TransitionType integer or the literal "none" (both empirically
    # verified: TransitionType/TransitionSubtype default to 0/0 on a
    # fresh slide, and arbitrary ints are accepted unvalidated) -- the
    # full ODF/OOXML named-transition table (fade, wipe, push, ...) was
    # not mapped this pass, for the same reason.

    def _require_impress(self, doc: Any, operation: str) -> None:
        doc_type = self._get_document_type(doc)
        if doc_type != "impress":
            raise WrongDocumentTypeError(f"{operation} is only implemented for Impress documents, not '{doc_type}'.")

    def _resolve_slide(self, doc: Any, slide: Optional[Any] = None) -> Any:
        self._require_impress(doc, "slide resolution")
        if slide is None:
            return doc.getCurrentController().getCurrentPage()
        return self._resolve_page_by_name_or_index(doc.getDrawPages(), slide)

    @staticmethod
    def _slide_index(pages: Any, page_obj: Any) -> Optional[int]:
        for i in range(pages.getCount()):
            if pages.getByIndex(i).Name == page_obj.Name:
                return i
        return None

    def _resolve_master_by_name(self, doc: Any, name: Any) -> Any:
        """Master pages are index-only (no XNameAccess -- confirmed via
        dir() introspection this pass, unlike slides), so resolving by
        name means a linear scan."""
        masters = doc.getMasterPages()
        name = str(name)
        for i in range(masters.getCount()):
            master = masters.getByIndex(i)
            if master.Name == name:
                return master
        raise KeyError(f"No such master page '{name}'.")

    _LAYOUT_NAMES = {"title_slide": 0, "title_content": 1, "title_only": 19, "blank": 20}

    def _resolve_layout(self, layout: Any) -> int:
        if isinstance(layout, bool):
            raise TypeError("layout must be an int or a str, not bool.")
        if isinstance(layout, int):
            return layout
        key = str(layout).lower()
        if key in self._LAYOUT_NAMES:
            return self._LAYOUT_NAMES[key]
        raise ValueError(
            f"Unknown layout '{layout}'. Supported names: {sorted(self._LAYOUT_NAMES)}, "
            "or pass a raw AutoLayout integer (0-20; the full name table wasn't mapped this pass)."
        )

    def list_slides(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_impress(doc, "list_slides")
        pages = doc.getDrawPages()
        result = []
        for i in range(pages.getCount()):
            page = pages.getByIndex(i)
            result.append({
                "index": i, "name": page.Name, "layout": page.Layout,
                "master": page.MasterPage.Name if page.MasterPage is not None else None,
                "hidden": not page.Visible,
            })
        return result

    def get_active_slide(self, doc: Any) -> Dict[str, Any]:
        self._require_impress(doc, "get_active_slide")
        page = doc.getCurrentController().getCurrentPage()
        return {"index": self._slide_index(doc.getDrawPages(), page), "name": page.Name}

    def activate_slide(self, doc: Any, slide: Any) -> None:
        self._require_impress(doc, "activate_slide")
        doc.getCurrentController().setCurrentPage(self._resolve_slide(doc, slide))

    def insert_slide(self, doc: Any, position: Optional[int] = None, layout: Optional[Any] = None,
                      master: Optional[Any] = None) -> Dict[str, Any]:
        self._require_impress(doc, "insert_slide")
        pages = doc.getDrawPages()
        index = position if position is not None else pages.getCount()
        new_page = pages.insertNewByIndex(index)
        if layout is not None:
            new_page.Layout = self._resolve_layout(layout)
        if master is not None:
            new_page.MasterPage = self._resolve_master_by_name(doc, master)
        return {"index": self._slide_index(pages, new_page), "name": new_page.Name}

    def duplicate_slide(self, doc: Any, slide: Any, destination: Optional[int] = None) -> Dict[str, Any]:
        """doc.duplicate() (XDrawPageDuplicator) copies the page and all
        its shapes and inserts the copy immediately after the source --
        same mechanism draw.py's duplicate_draw_page uses. An explicit
        destination is applied afterward via the same dispatch-based move
        move_slide_live uses -- see this section's docstring for that
        mechanism's unverified-for-Impress caveat, which applies here too
        when destination is given."""
        self._require_impress(doc, "duplicate_slide")
        source_page = self._resolve_slide(doc, slide)
        new_page = doc.duplicate(source_page)
        pages = doc.getDrawPages()
        current_index = self._slide_index(pages, new_page)
        if destination is not None and destination != current_index:
            self._move_draw_page_to_index(doc, current_index, destination)
            current_index = destination
        return {"index": current_index, "name": new_page.Name}

    def delete_slide(self, doc: Any, slide: Any) -> None:
        self._require_impress(doc, "delete_slide")
        doc.getDrawPages().remove(self._resolve_slide(doc, slide))

    def move_slide(self, doc: Any, slide: Any, destination_index: int) -> None:
        self._require_impress(doc, "move_slide")
        pages = doc.getDrawPages()
        page_obj = self._resolve_slide(doc, slide)
        current_index = self._slide_index(pages, page_obj)
        self._move_draw_page_to_index(doc, current_index, destination_index)

    def rename_slide(self, doc: Any, slide: Any, name: str) -> None:
        self._require_impress(doc, "rename_slide")
        self._resolve_slide(doc, slide).Name = name

    def hide_slide(self, doc: Any, slide: Any) -> None:
        self._require_impress(doc, "hide_slide")
        self._resolve_slide(doc, slide).Visible = False

    def show_slide(self, doc: Any, slide: Any) -> None:
        self._require_impress(doc, "show_slide")
        self._resolve_slide(doc, slide).Visible = True

    def get_slide_layout(self, doc: Any, slide: Any) -> Dict[str, Any]:
        page = self._resolve_slide(doc, slide)
        return {
            "layout": page.Layout,
            "master": page.MasterPage.Name if page.MasterPage is not None else None,
            "width": page.Width, "height": page.Height,
            "orientation": "landscape" if page.Width >= page.Height else "portrait",
            "footer_visible": page.IsFooterVisible, "footer_text": page.FooterText,
            "background_visible": page.IsBackgroundVisible,
        }

    def set_slide_layout(self, doc: Any, slide: Any, layout: Any) -> None:
        self._resolve_slide(doc, slide).Layout = self._resolve_layout(layout)

    def set_slide_size(self, doc: Any, width: float, height: float, unit: str) -> None:
        """No `slide` parameter in this tool's spec schema -- an Impress
        presentation has one page size shared by every slide and master,
        not a per-slide one (unlike Draw), so this applies to every page
        in both getDrawPages() and getMasterPages()."""
        self._require_impress(doc, "set_slide_size")
        factor = self._LENGTH_UNIT_TO_MM100.get(unit.lower(), 1)
        w, h = int(width * factor), int(height * factor)
        for container in (doc.getDrawPages(), doc.getMasterPages()):
            for i in range(container.getCount()):
                page = container.getByIndex(i)
                page.Width = w
                page.Height = h

    def set_slide_background(self, doc: Any, slide: Any, properties: Dict[str, Any]) -> List[str]:
        """Same doc.createInstance(...) (document-scoped, not the global
        smgr) Background-object mechanism draw.py's set_draw_page_background
        needed -- a Draw/Impress page's fill properties are never direct
        page properties."""
        page = self._resolve_slide(doc, slide)
        background = doc.createInstance("com.sun.star.drawing.Background")
        applied = self._apply_direct_properties(background, properties)
        page.Background = background
        return applied

    def list_master_pages(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_impress(doc, "list_master_pages")
        masters = doc.getMasterPages()
        return [{"index": i, "name": masters.getByIndex(i).Name} for i in range(masters.getCount())]

    def apply_master_page(self, doc: Any, master: Any, slides: List[Any]) -> List[str]:
        self._require_impress(doc, "apply_master_page")
        master_obj = self._resolve_master_by_name(doc, master)
        applied = []
        for slide in slides:
            page = self._resolve_slide(doc, slide)
            page.MasterPage = master_obj
            applied.append(page.Name)
        return applied

    def create_master_page(self, doc: Any, name: str, based_on: Optional[Any] = None) -> Dict[str, Any]:
        """`based_on` is accepted but not honored this pass -- no copy-
        properties-from-another-master mechanism was exploration-tested;
        the new master is a fresh default master under the requested
        name, same honest-scope-limit call as the transition/layout name
        tables above rather than guessing at a copy mechanism.

        insertNamedNewByIndex(index, name) -- index first, name second.
        Live-verified: the reversed order this pass first tried raised a
        raw "invalid STRING value!" UNO_EXCEPTION instead of a clean tool
        response (getting this backwards was an easy mistake -- dir()
        introspection lists the method name but not its parameter order)."""
        self._require_impress(doc, "create_master_page")
        masters = doc.getMasterPages()
        new_master = masters.insertNamedNewByIndex(masters.getCount(), name)
        return {"name": new_master.Name}

    def delete_master_page(self, doc: Any, master: Any) -> None:
        self._require_impress(doc, "delete_master_page")
        doc.getMasterPages().remove(self._resolve_master_by_name(doc, master))

    @staticmethod
    def _find_notes_shape(notes_page: Any) -> Any:
        """getShapeType(), not supportsService() -- live-verified a real
        NotesShape's supportsService("com.sun.star.presentation.
        NotesShape") returns False despite getShapeType() returning
        exactly that string; presentation placeholder shapes expose their
        role through their shape type, not through XServiceInfo the way
        most other shapes do."""
        for i in range(notes_page.getCount()):
            shape = notes_page.getByIndex(i)
            if shape.getShapeType() == "com.sun.star.presentation.NotesShape":
                return shape
        raise LookupError("Notes page has no NotesShape.")

    def get_speaker_notes(self, doc: Any, slide: Any) -> str:
        page = self._resolve_slide(doc, slide)
        return self._find_notes_shape(page.NotesPage).getString()

    def set_speaker_notes(self, doc: Any, slide: Any, text: str) -> None:
        page = self._resolve_slide(doc, slide)
        self._find_notes_shape(page.NotesPage).setString(text)

    def get_slide_content(self, doc: Any, slide: Any = None, include_notes: bool = True,
                           include_shape_metadata: bool = False) -> Dict[str, Any]:
        """New tool (Brian's new-tools assignment, priority #3, "give me
        all the content of slide 7" instead of list_shapes_live + N
        get_shape_live calls). Returns the same per-slide shape
        get_presentation_content_live (priority #5, still queued) will
        wrap in bulk -- built once here so that tool can reuse it via a
        loop later rather than duplicating this logic.

        Only shapes with non-empty getString() text are included in
        `text` (same "skip if falsy" convention _shape_summary() already
        uses) -- an empty placeholder or a pure image shape contributes
        nothing to a text-content read. Each entry's `shape` key is the
        shape's own UNO Name (e.g. "Title 1", "Content 2"), not a
        registry shape_id -- this is a read-only content dump, not an
        addressable-object mint; list_shapes_live already covers minting
        shape_ids for callers that need to act on a specific shape after.
        include_shape_metadata=True additionally reports each text
        entry's short type name and geometry (reusing _get_shape_type/
        _shape_geometry, the same helpers list_shapes_in_container's
        summaries use) -- optional, since most callers just want text.

        include_notes=False omits the `notes` key entirely rather than
        setting it to None, so a caller can tell "didn't ask" apart from
        "asked, page genuinely has no NotesShape" (LookupError -> None).
        """
        page = self._resolve_slide(doc, slide)
        text_entries: List[Dict[str, Any]] = []
        for i in range(page.getCount()):
            shape = page.getByIndex(i)
            if not hasattr(shape, "getString"):
                continue
            try:
                text = shape.getString()
            except Exception:
                continue
            if not text:
                continue
            entry: Dict[str, Any] = {"shape": shape.Name, "text": text}
            if include_shape_metadata:
                entry["type"] = self._get_shape_type(shape)
                entry.update(self._shape_geometry(shape))
            text_entries.append(entry)
        result: Dict[str, Any] = {
            "index": self._slide_index(doc.getDrawPages(), page),
            "name": page.Name,
            "hidden": not page.Visible,
            "text": text_entries,
        }
        if include_notes:
            try:
                result["notes"] = self._find_notes_shape(page.NotesPage).getString()
            except LookupError:
                result["notes"] = None
        return result

    def get_presentation_content(self, doc: Any, slides: Optional[List[Any]] = None,
                                  include_notes: bool = True, include_shape_metadata: bool = False,
                                  include_hidden: bool = True) -> Dict[str, Any]:
        """New tool (Brian's new-tools assignment, priority #5, "give me
        all the content of the whole deck" -- the bulk counterpart to
        get_slide_content_live #3). Wraps get_slide_content() in a loop
        exactly as flagged when that tool was built, rather than
        duplicating its per-slide read logic.

        slides omitted -> every slide in the deck, in order. slides given
        -> just those (index or name each, same _resolve_slide()
        convention every other per-slide impress.py tool uses; scoping a
        bulk read to specific slides mirrors find_cells_live's sheet/range
        scoping). include_hidden=False additionally filters out slides
        whose own get_slide_content() reports hidden=True -- useful for a
        caller that wants "what the audience sees" without a second
        get_slide_content_live round-trip per slide to check.

        include_notes/include_shape_metadata pass straight through to
        get_slide_content() for every slide, same meaning as there.
        """
        self._require_impress(doc, "get_presentation_content")
        pages = doc.getDrawPages()
        refs: List[Any] = list(range(pages.getCount())) if slides is None else list(slides)
        entries: List[Dict[str, Any]] = []
        for ref in refs:
            content = self.get_slide_content(doc, ref, include_notes, include_shape_metadata)
            if not include_hidden and content["hidden"]:
                continue
            entries.append(content)
        return {"slides": entries, "count": len(entries)}

    def get_slide_transition(self, doc: Any, slide: Any) -> Dict[str, Any]:
        page = self._resolve_slide(doc, slide)
        return {
            "transition_type": page.TransitionType, "transition_subtype": page.TransitionSubtype,
            "transition_direction": page.TransitionDirection, "duration": page.HighResDuration,
            "advance": {0: "on_click", 1: "auto"}.get(page.Change, "unknown"),
            "auto_after": page.Duration if page.Change == 1 else None,
            "sound": page.Sound or None, "loop_sound": page.LoopSound,
        }

    _CHANGE_MODES = {"on_click": 0, "auto": 1}

    def set_slide_transition(self, doc: Any, slide: Any, effect: Optional[Any] = None,
                              duration: Optional[float] = None, advance: Optional[str] = None,
                              auto_after: Optional[float] = None) -> List[str]:
        """`auto_after` (page.Duration) and `duration` (page.HighResDuration)
        are applied in that order deliberately, not the parameter order --
        live-verified this LibreOffice build two-way-couples them (setting
        either one syncs the other to a rounded copy of it: Duration=4.0
        makes HighResDuration read back 4.0; HighResDuration=2.5
        afterward makes Duration read back 3, round(2.5)) rather than
        keeping transition speed and auto-advance timing independent, as
        their names/spec purposes would suggest. Applying auto_after
        first and duration last means an explicit `duration` value is
        never silently overwritten, at the cost of `auto_after` only
        being approximately honored when both are given in the same
        call -- tools/impress.py's set_slide_transition_live warns the
        caller about this when both are present, rather than silently
        claiming both landed exactly as requested."""
        page = self._resolve_slide(doc, slide)
        applied = []
        if effect is not None:
            if isinstance(effect, bool):
                raise TypeError("effect must be an int or a str, not bool.")
            if isinstance(effect, int):
                page.TransitionType = effect
            elif str(effect).lower() == "none":
                page.TransitionType = 0
                page.TransitionSubtype = 0
            else:
                raise NotImplementedError(
                    f"Named transition effect '{effect}' is not implemented this pass -- pass effect=0 "
                    "(or another raw TransitionType integer) directly, or effect='none'. The full "
                    "ODF/OOXML transition-type name table wasn't mapped this pass."
                )
            applied.append("effect")
        if advance is not None:
            key = str(advance).lower()
            if key not in self._CHANGE_MODES:
                raise ValueError(f"advance must be one of {sorted(self._CHANGE_MODES)}, got '{advance}'")
            page.Change = self._CHANGE_MODES[key]
            applied.append("advance")
        if auto_after is not None:
            page.Duration = float(auto_after)
            applied.append("auto_after")
        if duration is not None:
            page.HighResDuration = float(duration)
            applied.append("duration")
        return applied

    # EffectNodeType values LibreOffice's own UI writes into UserData's
    # "node-type" entry (see describe_animation_node()'s docstring for how
    # this was found) -- inverted here once for friendly-string display.
    _EFFECT_NODE_TYPE_NAMES = {
        EffectNodeType.ON_CLICK: "on_click",
        EffectNodeType.WITH_PREVIOUS: "with_previous",
        EffectNodeType.AFTER_PREVIOUS: "after_previous",
        EffectNodeType.MAIN_SEQUENCE: "main_sequence",
        EffectNodeType.TIMING_ROOT: "timing_root",
        EffectNodeType.INTERACTIVE_SEQUENCE: "interactive_sequence",
    }
    _TRIGGER_NODE_TYPES = {
        "on_click": EffectNodeType.ON_CLICK,
        "with_previous": EffectNodeType.WITH_PREVIOUS,
        "after_previous": EffectNodeType.AFTER_PREVIOUS,
    }
    # Scoped effect set: only what's live-verified so far. Real preset
    # effects (LibreOffice ships hundreds, "Fade In"/"Wipe"/"Fly In"/etc.)
    # are built by sd's internal C++ CustomAnimationPresets from a bundled
    # XML template library (sd/source/core/CustomAnimationEffect.cxx,
    # EffectSequenceHelper::append(CustomAnimationPresetPtr, ...)) that
    # isn't reachable from the public UNO API at all -- only the generic
    # animations module (AnimateSet/AnimateColor/AnimateMotion/Command +
    # Parallel/SequenceTimeContainer) is. This is a real, hand-built
    # substitute using that generic module directly, not a port of LO's
    # preset library. Widening this set (fades via interpolated Animate on
    # Opacity, motion paths via AnimateMotion, color emphasis via
    # AnimateColor) is future work, same honest-scope-limit precedent as
    # insert_embedded_object_live (add_chart_series_live has since gone
    # real -- see its own docstring above).
    _EFFECT_PRESETS = {
        "appear": {"attribute": "Visibility", "to": True},
        "disappear": {"attribute": "Visibility", "to": False},
    }

    def describe_animation_node(self, node: Any) -> Dict[str, Any]:
        """Describe a single XAnimationNode: Begin/Duration/Fill are plain
        XAnimationNode interface attributes on every node this pass has
        seen (no XPropertySet in supportedInterfaces). "NodeType" is NOT
        one of them, despite being an XAnimationNode-shaped name -- live-
        verified (getattr raises AttributeError) against every node type
        the generic animations module can build (AnimateSet,
        Parallel/SequenceTimeContainer). LibreOffice's own UI stores that
        semantic (ON_CLICK/WITH_PREVIOUS/AFTER_PREVIOUS/MAIN_SEQUENCE/...)
        as a "node-type" NamedValue inside UserData instead --
        CustomAnimationEffect::setNodeType() in sd/source/core/
        CustomAnimationEffect.cxx does exactly this, confirmed by live-
        reading a node LibreOffice itself auto-tagged MAIN_SEQUENCE (value
        4) the first time this pass touched a slide's animation tree.
        Read that instead of the never-present NodeType attribute."""
        entry: Dict[str, Any] = {"node_type": node.getImplementationName()}
        for attr in ("Begin", "Duration", "Fill"):
            try:
                entry[attr.lower()] = self._uno_value_to_plain(getattr(node, attr))
            except AttributeError:
                pass
        try:
            user_data = node.UserData
        except AttributeError:
            user_data = ()
        for named_value in user_data:
            if named_value.Name == "node-type":
                trigger_value = named_value.Value
                entry["trigger"] = self._EFFECT_NODE_TYPE_NAMES.get(trigger_value, trigger_value)
                break
        return entry

    def list_animations(self, doc: Any, slide: Any) -> List[Any]:
        """Walks the real com.sun.star.animations.XAnimationNode tree
        (root is slide.AnimationNode, an XEnumerationAccess container --
        confirmed via introspection it does NOT support XIndexAccess, so
        createEnumeration() is the only way to walk it). Returns raw
        (node, parent_node) pairs in walk order -- registering them into
        the caller's ObjectRegistry is the tools-layer's job, same
        division as list_shapes_live/get_shape_summary in
        drawing_objects.py.

        Known limitation, live-verified via a real MCP REST round trip
        (add_animation_live an effect, then list_animations_live the same
        slide): the animation_id this produces for that same effect is a
        DIFFERENT registry entry than the one add_animation_live already
        returned, not a deduped match -- animcore XAnimationNode proxies
        don't compare equal across independently-obtained references in
        PyUNO (unlike shape/document proxies elsewhere in this file,
        confirmed working for those). Both ids still resolve to a working
        handle for the real underlying node (confirmed: update_animation_
        live succeeded through both), so this is a cosmetic
        non-deduplication, not a correctness bug -- but don't rely on
        ObjectRegistry identity-dedup to merge them, and see
        reorder_animations()'s docstring for where this same fact forced
        a different verification strategy (removeChild() as the
        membership oracle, not a set()/== comparison).

        Target (the animated shape/paragraph) deliberately isn't resolved
        to a shape_id this pass -- it isn't a plain value (a raw shape
        reference or a ParagraphTarget struct) and reverse-resolving it
        through ObjectRegistry wasn't exploration-tested here."""
        page = self._resolve_slide(doc, slide)
        result: List[Any] = []

        def walk(node: Any, parent_node: Optional[Any]) -> None:
            result.append((node, parent_node))
            if hasattr(node, "createEnumeration"):
                child_enum = node.createEnumeration()
                while child_enum.hasMoreElements():
                    walk(child_enum.nextElement(), node)

        walk(page.AnimationNode, None)
        return result

    def _find_or_create_main_sequence(self, root: Any) -> Any:
        """Find root's (slide.AnimationNode's) direct child tagged
        EffectNodeType.MAIN_SEQUENCE via the UserData mechanism described
        on describe_animation_node(). Live-verified: a brand new slide's
        root has zero children (no main sequence exists until something
        needs one) -- LibreOffice itself lazily creates a properly-tagged
        one, observed happening the first time this pass touched an
        unrelated animation on the same slide. Mirror that instead of
        depending on LibreOffice to have done it first: create + tag +
        append one if none is found."""
        child_enum = root.createEnumeration()
        while child_enum.hasMoreElements():
            child = child_enum.nextElement()
            try:
                user_data = child.UserData
            except AttributeError:
                continue
            if any(nv.Name == "node-type" and nv.Value == EffectNodeType.MAIN_SEQUENCE for nv in user_data):
                return child

        main_sequence = self.smgr.createInstanceWithContext(
            "com.sun.star.animations.SequenceTimeContainer", self.ctx)
        node_type = NamedValue()
        node_type.Name = "node-type"
        node_type.Value = uno.Any("short", EffectNodeType.MAIN_SEQUENCE)
        main_sequence.UserData = (node_type,)
        root.appendChild(main_sequence)
        return main_sequence

    def add_animation(self, doc: Any, shape: Any, effect: str,
                       trigger: Optional[str] = None, duration: Optional[float] = None,
                       delay: Optional[float] = None) -> Any:
        """Build a real com.sun.star.animations.AnimateSet effect, wrap it
        in a ParallelTimeContainer tagged with the requested trigger's
        EffectNodeType (via the UserData mechanism -- see
        describe_animation_node()), and append it to the slide's main
        sequence. Returns (wrapper, main_sequence) -- the caller registers
        the pair as one opaque animation_id (see impress.py) so delete/
        reorder_animations_live can remove/reorder against the actual
        parent container without re-deriving it from a shape_id (delete_
        animation_live's schema doesn't take one). Effect nodes are
        created via self.smgr.createInstanceWithContext(), not
        doc.createInstance() -- live-verified doc.createInstance() raises
        ServiceNotRegisteredException for these; they're generic
        animations-module services, not document-scoped ones (same
        pattern as chart2.Title elsewhere in this file). Click-advance
        runtime behavior (does the effect actually wait for a click during
        a slideshow) is NOT verifiable in this environment -- headless
        mode's XSlideShowController is always None, same documented dead
        end as next/previous/goto_slideshow_effect_live in tools/
        impress.py; only the tree construction itself is live-verified
        here."""
        preset = self._EFFECT_PRESETS.get(effect)
        if preset is None:
            raise ValueError(f"Unknown effect '{effect}'. Supported: {sorted(self._EFFECT_PRESETS)}")

        node_type_value = self._TRIGGER_NODE_TYPES.get(trigger or "on_click")
        if node_type_value is None:
            raise ValueError(f"Unknown trigger '{trigger}'. Supported: {sorted(self._TRIGGER_NODE_TYPES)}")

        self._require_impress(doc, "add_animation")
        # shape.Parent is the owning SdDrawPage (live-verified) -- no
        # add_animation_live schema param carries an explicit slide/index,
        # so this is the only way to find the page a shape's effect
        # belongs on.
        page = shape.Parent

        animate = self.smgr.createInstanceWithContext("com.sun.star.animations.AnimateSet", self.ctx)
        animate.Target = shape
        animate.AttributeName = preset["attribute"]
        animate.To = preset["to"]
        animate.Duration = float(duration) if duration is not None else 0.001

        wrapper = self.smgr.createInstanceWithContext("com.sun.star.animations.ParallelTimeContainer", self.ctx)
        wrapper.appendChild(animate)
        wrapper.Begin = float(delay) if delay is not None else 0.0
        node_type = NamedValue()
        node_type.Name = "node-type"
        node_type.Value = uno.Any("short", node_type_value)
        wrapper.UserData = (node_type,)

        main_sequence = self._find_or_create_main_sequence(page.AnimationNode)
        main_sequence.appendChild(wrapper)
        return wrapper, main_sequence

    def update_animation(self, wrapper: Any, properties: Dict[str, Any]) -> List[str]:
        """Update timing/trigger on an existing effect wrapper (the node
        add_animation() returns/registers). Scoped to what a wrapper
        container actually owns -- duration lives on the leaf AnimateSet,
        not the wrapper, so it's reached via the wrapper's single child.
        Switching to a different effect type isn't supported (would mean
        rebuilding the AnimateSet from scratch); same scope-limit as
        elsewhere in this pass."""
        applied: List[str] = []
        if "duration" in properties:
            child_enum = wrapper.createEnumeration()
            if child_enum.hasMoreElements():
                child_enum.nextElement().Duration = float(properties["duration"])
                applied.append("duration")
        if "delay" in properties:
            wrapper.Begin = float(properties["delay"])
            applied.append("delay")
        if "trigger" in properties:
            node_type_value = self._TRIGGER_NODE_TYPES.get(properties["trigger"])
            if node_type_value is None:
                raise ValueError(f"Unknown trigger '{properties['trigger']}'. Supported: {sorted(self._TRIGGER_NODE_TYPES)}")
            node_type = NamedValue()
            node_type.Name = "node-type"
            node_type.Value = uno.Any("short", node_type_value)
            wrapper.UserData = (node_type,)
            applied.append("trigger")
        if not applied:
            raise ValueError(f"No supported properties in {sorted(properties)}. Supported: duration, delay, trigger")
        return applied

    def delete_animation(self, wrapper: Any, main_sequence: Any) -> None:
        """Remove an effect wrapper from its main sequence -- both come
        from the (wrapper, main_sequence) pair add_animation() returns and
        the caller registered as one animation_id, since
        delete_animation_live's schema has no shape_id/slide to
        re-derive a parent from."""
        main_sequence.removeChild(wrapper)

    def reorder_animations(self, doc: Any, slide: Any, wrappers: List[Any]) -> None:
        """Set the slide main sequence's effect order to exactly `wrappers`
        (in the given order). Requires `wrappers` to be the complete,
        exact set of the main sequence's current children -- a partial or
        mismatched list raises rather than silently reordering a subset,
        since XTimeContainer has no atomic "replace all children"
        operation and a partial reorder would leave an ambiguous mix of
        moved and untouched effects.

        Membership is verified via main_sequence.removeChild() actually
        succeeding, NOT via comparing `wrappers` against a freshly
        re-enumerated child list with `==`/set() -- live-verified this
        pass that two independently-obtained animcore XAnimationNode
        proxies for the exact same server-side effect do NOT compare
        equal in PyUNO (unlike shape/document proxies elsewhere in this
        file, which do; confirmed via a real MCP REST round trip:
        add_animation_live's returned animation_id and the id
        list_animations_live discovers for that same freshly-added effect
        are different registry entries, though both resolve to a working
        handle for the same real node). A set()-based pre-check against
        that identity would always spuriously reject a fully valid,
        complete reorder. Using the server's own removeChild() as the
        membership oracle sidesteps the broken client-side identity
        comparison entirely. If any removeChild() fails partway through
        (a genuinely foreign/stale wrapper), whatever was already removed
        is re-appended before raising, so a rejected reorder never loses a
        node -- though on that failure path the restored nodes land at
        the end in `wrappers` order, not necessarily their exact original
        relative order (acceptable: this is the failure path, and no
        effect is dropped)."""
        page = self._resolve_slide(doc, slide)
        main_sequence = self._find_or_create_main_sequence(page.AnimationNode)

        original_count = 0
        child_enum = main_sequence.createEnumeration()
        while child_enum.hasMoreElements():
            child_enum.nextElement()
            original_count += 1

        if len(wrappers) != original_count:
            raise ValueError(
                f"reorder_animations_live requires the complete current effect set "
                f"({original_count} effects) in animation_ids -- got {len(wrappers)}.")

        removed: List[Any] = []
        try:
            for wrapper in wrappers:
                main_sequence.removeChild(wrapper)
                removed.append(wrapper)
        except Exception as e:
            for wrapper in removed:
                main_sequence.appendChild(wrapper)
            raise ValueError(
                f"reorder_animations_live: one of the given animation_ids is not "
                f"a current member of this slide's main sequence ({e}).") from e

        for wrapper in wrappers:
            main_sequence.appendChild(wrapper)

    _CLICK_ACTIONS = {
        "none": "NONE", "previous_page": "PREVPAGE", "next_page": "NEXTPAGE",
        "first_page": "FIRSTPAGE", "last_page": "LASTPAGE", "bookmark": "BOOKMARK",
        "document": "DOCUMENT", "program": "PROGRAM", "sound": "SOUND", "verb": "VERB",
        "vanish": "VANISH", "invisible": "INVISIBLE", "stop_presentation": "STOPPRESENTATION",
    }

    def set_shape_click_action(self, doc: Any, shape: Any, action: str, target: Optional[str] = None) -> List[str]:
        action_name = self._CLICK_ACTIONS.get(action.lower())
        if action_name is None:
            raise ValueError(f"Unknown action '{action}'. Supported: {sorted(self._CLICK_ACTIONS)}")
        shape.setPropertyValue("OnClick", uno.Enum("com.sun.star.presentation.ClickAction", action_name))
        applied = ["action"]
        if target is not None:
            shape.setPropertyValue("Bookmark", str(target))
            applied.append("target")
        return applied

    _PRESENTATION_SETTINGS_PROPS = (
        "AllowAnimations", "CustomShow", "Display", "FirstPage", "IsAlwaysOnTop", "IsAutomatic",
        "IsEndless", "IsFullScreen", "IsMouseVisible", "IsShowAll", "IsShowLogo",
        "IsTransitionOnClick", "Pause", "StartWithNavigator", "UsePen",
    )

    def get_presentation_settings(self, doc: Any) -> Dict[str, Any]:
        """FirstPage is already a plain slide-name string (empty string
        when unset), NOT a page object reference -- live-verified this
        pass; the original .Name-access assumption raised a raw
        "'str' object has no attribute 'Name'" UNO_EXCEPTION instead of a
        clean tool response."""
        self._require_impress(doc, "get_presentation_settings")
        pres = doc.getPresentation()
        settings = {}
        for name in self._PRESENTATION_SETTINGS_PROPS:
            try:
                value = pres.getPropertyValue(name)
            except Exception:
                continue
            if name == "FirstPage" and value == "":
                value = None
            settings[name] = self._uno_value_to_plain(value)
        return settings

    def set_presentation_settings(self, doc: Any, settings: Dict[str, Any]) -> List[str]:
        """FirstPage takes a plain slide-name string directly -- see
        get_presentation_settings' docstring. _resolve_slide() (needed
        for start_slideshow's `first_slide`, which accepts an index too)
        would be wrong here since XPresentation.FirstPage itself is
        string-typed, not an index-or-name selector."""
        self._require_impress(doc, "set_presentation_settings")
        pres = doc.getPresentation()
        if "FirstPage" in settings:
            settings = dict(settings)
            settings["FirstPage"] = self._resolve_slide(doc, settings["FirstPage"]).Name
        return self._apply_direct_properties(pres, settings)

    def list_custom_shows(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_impress(doc, "list_custom_shows")
        shows = doc.getCustomPresentations()
        result = []
        for name in shows.getElementNames():
            cp = shows.getByName(name)
            result.append({"name": name, "slides": [cp.getByIndex(i).Name for i in range(cp.Count)]})
        return result

    def create_custom_show(self, doc: Any, name: str, slides: List[Any]) -> Dict[str, Any]:
        self._require_impress(doc, "create_custom_show")
        shows = doc.getCustomPresentations()
        cp = shows.createInstance()
        cp.Name = name
        for i, slide in enumerate(slides):
            cp.insertByIndex(i, self._resolve_slide(doc, slide))
        shows.insertByName(name, cp)
        return {"name": name, "count": cp.Count}

    def update_custom_show(self, doc: Any, name: str, slides: List[Any]) -> Dict[str, Any]:
        self._require_impress(doc, "update_custom_show")
        shows = doc.getCustomPresentations()
        if not shows.hasByName(name):
            raise KeyError(f"No such custom show '{name}'.")
        cp = shows.getByName(name)
        while cp.Count > 0:
            cp.removeByIndex(cp.Count - 1)
        for i, slide in enumerate(slides):
            cp.insertByIndex(i, self._resolve_slide(doc, slide))
        return {"name": name, "count": cp.Count}

    def delete_custom_show(self, doc: Any, name: str) -> None:
        self._require_impress(doc, "delete_custom_show")
        shows = doc.getCustomPresentations()
        if not shows.hasByName(name):
            raise KeyError(f"No such custom show '{name}'.")
        shows.removeByName(name)

    def start_slideshow(self, doc: Any, custom_show: Optional[str] = None, first_slide: Optional[Any] = None) -> None:
        """Live-verified pres.start()/end() execute without error in
        headless mode, but Presentation.Controller stays None throughout
        (confirmed via an independent readback right after start()) --
        no window manager to actually render a slideshow view to. That's
        a real, provable environment limit, not a code defect: the same
        None-Controller gap is why next_slideshow_effect_live/
        previous_slideshow_effect_live/goto_slideshow_slide_live (which
        all need a live Controller) stay status="stub" this pass -- see
        tools/impress.py."""
        self._require_impress(doc, "start_slideshow")
        pres = doc.getPresentation()
        if custom_show is not None:
            pres.CustomShow = custom_show
            pres.IsShowAll = False
        if first_slide is not None:
            pres.FirstPage = self._resolve_slide(doc, first_slide).Name
        pres.start()

    def stop_slideshow(self, doc: Any) -> None:
        self._require_impress(doc, "stop_slideshow")
        doc.getPresentation().end()

    # next_slideshow_effect_live/previous_slideshow_effect_live/
    # goto_slideshow_slide_live have no bridge methods -- all three need
    # a live com.sun.star.presentation.XSlideShowController
    # (Presentation.Controller), which this pass confirmed is always None
    # headless (see start_slideshow's docstring above). Left stub rather
    # than shipping code that can never be exercised or verified in this
    # environment; a follow-up with a real GUI/virtual-display session
    # should implement and verify these together with move_slide_live's
    # own flagged reorder gap.

    def export_slide(self, doc: Any, slide: Any, file_path: str, format: str = "png",
                      width: Optional[int] = None, height: Optional[int] = None,
                      dpi: Optional[int] = None) -> None:
        """Same GraphicExportFilter mechanism draw.py's export_draw_page
        uses, with explicit pixel width/height (this tool's own spec
        parameters, unlike export_draw_page/export_chart) taking priority
        over a dpi-derived size when both are given."""
        page = self._resolve_slide(doc, slide)
        export_filter = self.smgr.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", self.ctx)
        export_filter.setSourceDocument(page)
        media_type = self._EXPORT_MEDIA_TYPES.get(format.lower())
        if media_type is None:
            raise NotImplementedError(f"export_slide_image_live format '{format}' is not implemented -- supported: {sorted(self._EXPORT_MEDIA_TYPES)}.")
        props = [
            PropertyValue("URL", 0, uno.systemPathToFileUrl(file_path), 0),
            PropertyValue("MediaType", 0, media_type, 0),
        ]
        pixel_width = pixel_height = None
        if width is not None and height is not None:
            pixel_width, pixel_height = int(width), int(height)
        elif dpi:
            pixel_width = round((page.Width / 100 / 25.4) * dpi)
            pixel_height = round((page.Height / 100 / 25.4) * dpi)
        if pixel_width and pixel_height:
            filter_data = uno.Any("[]com.sun.star.beans.PropertyValue", (
                PropertyValue("PixelWidth", 0, max(pixel_width, 1), 0),
                PropertyValue("PixelHeight", 0, max(pixel_height, 1), 0),
            ))
            props.append(PropertyValue("FilterData", 0, filter_data, 0))
        export_filter.filter(tuple(props))

    def export_all_slides(self, doc: Any, output_dir: str, format: str = "png",
                           slides: Optional[List[Any]] = None, naming: Optional[str] = None) -> List[str]:
        self._require_impress(doc, "export_all_slides_images")
        pages = doc.getDrawPages()
        targets = [self._resolve_slide(doc, s) for s in slides] if slides else \
            [pages.getByIndex(i) for i in range(pages.getCount())]
        ext = "jpg" if format.lower() in ("jpeg", "jpg") else format.lower()
        prefix = naming or "slide"
        results = []
        for page in targets:
            index = self._slide_index(pages, page)
            file_path = os.path.join(output_dir, f"{prefix}_{index + 1}.{ext}")
            self.export_slide(doc, page.Name, file_path, format)
            results.append(file_path)
        return results

    # -- Calc data management, analysis, pivots, validation, external data
    # (tools/calc_data.py's 42 tools) --
    #
    # Same raise-on-failure convention as calc_sheets.py above. Sheet
    # resolution reuses _resolve_sheet()/_require_calc() from that
    # section. All 42 tools are real as of this pass; create_external_
    # link_live/refresh_external_link_live/delete_external_link_live were
    # the last 3 -- live-verified real UNO mechanism is
    # com.sun.star.sheet.XAreaLinks (doc.AreaLinks), NOT doc.
    # ExternalDocLinks. Those are two genuinely separate, non-overlapping
    # mechanisms -- live-verified inserting via one does not populate the
    # other: ExternalDocLinks is a read-only cache auto-created when a
    # formula references an external file's cell (no write/refresh/remove
    # API exists for it at all -- live-verified no XRefreshable on the
    # doc, the links collection, or an individual entry; no dispatchable
    # `.uno:UpdateLinks`-style command resolves; doc.calculateAll() does
    # NOT refresh its cached values even after the source file changes on
    # disk and is re-saved). AreaLinks is the "linked data area"
    # mechanism (Calc's Sheet > Insert Sheet from File... as a link, or
    # equivalently Data > External Data): genuinely CRUD-capable via
    # XAreaLinks.insertAtPosition()/removeByIndex(), and each entry
    # queryInterface()s to a real, working XRefreshable. This also fixes
    # a real purpose/implementation mismatch: list_external_links_live's
    # own registered purpose has always said "List area/external links
    # and refresh state," but the original implementation only read
    # ExternalDocLinks, which has no refresh state at all -- AreaLinks
    # entries are the ones that do (RefreshDelay). See
    # list_external_links()/create_external_link()'s own docstrings
    # below for the exact live-verified call shapes.
    #
    # scope (named ranges) means: a sheet name/index -> that sheet's own
    # NamedRanges container; omitted -> the workbook-level
    # doc.NamedRanges container. Matches the spec's own "workbook/sheet
    # named ranges" wording for this section.
    #
    # Conditional formats and pivot tables use the same "uno_bridge
    # returns raw UNO objects, the tools/ layer registers them"
    # ObjectRegistry split drawing_objects.py established (see e.g.
    # list_shapes_live: uno_bridge.list_shapes_in_container() returns
    # plain shapes, the tool function registers each and calls
    # uno_bridge.get_shape_summary(shape, shape_id) to build the response)
    # -- uno_bridge.py itself never imports/touches ObjectRegistry.
    #
    # Conditional formats use the legacy per-range XSheetConditionalEntries
    # (range.ConditionalFormat), NOT the newer sheet.ConditionalFormats/
    # XConditionalFormat API -- live-verified the newer API's
    # createEntry(long, long) has a genuinely different, much less
    # tractable signature than its own IDL method-parameter types implied
    # (neither parameter is a condition-type enum or a cell address, both
    # are just "long", and passing what seemed like the obvious values
    # raised CannotConvertException) and wasn't successfully mapped in the
    # time available. The legacy API (addNew() takes a plain sequence of
    # PropertyValue: Operator/Formula1/Formula2/StyleName) is simpler,
    # well-documented, and fully live-verified working. A conditional
    # format entry has no UNO-native persistent id of its own (it's a
    # plain index position in a mutable per-range property), so deletion
    # re-locates the entry by identity within its range's *current*
    # ConditionalFormat collection rather than trusting a possibly-stale
    # stored index -- the same "filled slot is not the right slot" risk a
    # raw index would carry across intervening add/remove calls on the
    # same range.

    def _named_range_container(self, doc: Any, scope: Optional[str] = None) -> Any:
        self._require_calc(doc, "named range resolution")
        if scope is None:
            return doc.NamedRanges
        return self._resolve_sheet(doc, scope).NamedRanges

    def _find_named_range(self, doc: Any, name: str) -> "tuple[Any, Any, Optional[str]]":
        """Returns (container, named_range_object, scope) -- scope is None
        for a workbook-level range, else the sheet name it belongs to.
        Named ranges have no scope parameter on update/delete in the spec,
        so both levels are searched."""
        if doc.NamedRanges.hasByName(name):
            return doc.NamedRanges, doc.NamedRanges.getByName(name), None
        sheets = doc.getSheets()
        for i in range(sheets.getCount()):
            sheet = sheets.getByIndex(i)
            container = sheet.NamedRanges
            if container is not None and container.hasByName(name):
                return container, container.getByName(name), sheet.Name
        raise KeyError(f"No such named range '{name}'.")

    def list_named_ranges(self, doc: Any, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        container = self._named_range_container(doc, scope)
        result = []
        for name in container.getElementNames():
            nr = container.getByName(name)
            result.append({"name": nr.Name, "refers_to": nr.Content, "scope": scope})
        return result

    def create_named_range(self, doc: Any, name: str, refers_to: str, scope: Optional[str] = None) -> Dict[str, Any]:
        container = self._named_range_container(doc, scope)
        base = uno.createUnoStruct("com.sun.star.table.CellAddress")
        base.Sheet, base.Column, base.Row = 0, 0, 0
        container.addNewByName(name, refers_to, base, 0)
        return {"name": name, "scope": scope}

    def update_named_range(self, doc: Any, name: str, refers_to: str) -> None:
        _, nr, _ = self._find_named_range(doc, name)
        nr.Content = refers_to

    def delete_named_range(self, doc: Any, name: str) -> None:
        container, _, _ = self._find_named_range(doc, name)
        container.removeByName(name)

    def sort_range(self, doc: Any, range: str, keys: List[Dict[str, Any]], sheet: Optional[str] = None,
                    has_header: Optional[bool] = None) -> None:
        """`keys` items: {"column": <0-based index within the range>,
        "ascending": bool (default True)} -- TableSortField.Field is a
        0-based index relative to the sorted range's own first column,
        not an absolute sheet column, live-verified matches
        createSortDescriptor()'s own SortFields usage.

        SortFields' own Value must be wrapped in an explicit
        uno.Any("[]com.sun.star.table.TableSortField", ...) here --
        live-verified a plain Python tuple of structs, which works fine
        for every OTHER sequence-valued property in this codebase
        (FilterFields, DataPilotFields entries, etc.), is silently
        ignored by range.sort() specifically: no exception, no error, the
        range just comes back in its original order. Re-using the
        PropertyValue objects createSortDescriptor() itself returned
        (mutating only the ones that need to change) carries the correct
        typing without needing this workaround, but this pass rebuilds
        the whole descriptor from a plain dict for clarity, so the
        explicit Any is required."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        desc = {p.Name: p.Value for p in range_obj.createSortDescriptor()}
        fields = []
        for key in keys:
            field = uno.createUnoStruct("com.sun.star.table.TableSortField")
            field.Field = int(key["column"])
            field.IsAscending = bool(key.get("ascending", True))
            fields.append(field)
        desc["SortFields"] = uno.Any("[]com.sun.star.table.TableSortField", tuple(fields))
        if has_header is not None:
            desc["ContainsHeader"] = has_header
        range_obj.sort(tuple(PropertyValue(k, 0, v, 0) for k, v in desc.items()))

    _FILTER_OPERATORS = {
        "equal": "EQUAL", "not_equal": "NOT_EQUAL", "greater": "GREATER", "greater_equal": "GREATER_EQUAL",
        "less": "LESS", "less_equal": "LESS_EQUAL", "top_values": "TOP_VALUES", "top_percent": "TOP_PERCENT",
        "bottom_values": "BOTTOM_VALUES", "bottom_percent": "BOTTOM_PERCENT", "contains": "CONTAINS",
        "does_not_contain": "DOES_NOT_CONTAIN", "empty": "EMPTY", "not_empty": "NOT_EMPTY",
    }

    def apply_filter(self, doc: Any, range: str, conditions: List[Dict[str, Any]], sheet: Optional[str] = None,
                      options: Optional[Dict[str, Any]] = None) -> None:
        """conditions items: {"column": <0-based index within the range>,
        "operator": one of _FILTER_OPERATORS, "value": str|number,
        "connector": "and"|"or" (ignored on the first condition)}."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        options = options or {}
        contains_header = bool(options.get("has_header", True))
        filter_desc = range_obj.createFilterDescriptor(True)
        fields = []
        for i, cond in enumerate(conditions):
            field = uno.createUnoStruct("com.sun.star.sheet.TableFilterField")
            field.Field = int(cond["column"])
            op_name = self._FILTER_OPERATORS.get(str(cond.get("operator", "equal")).lower())
            if op_name is None:
                raise ValueError(f"Unknown filter operator '{cond.get('operator')}'. Supported: {sorted(self._FILTER_OPERATORS)}")
            field.Operator = uno.Enum("com.sun.star.sheet.FilterOperator", op_name)
            value = cond.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                field.IsNumeric = True
                field.NumericValue = float(value)
            else:
                field.IsNumeric = False
                field.StringValue = "" if value is None else str(value)
            if i > 0:
                connector = str(cond.get("connector", "and")).upper()
                field.Connection = uno.Enum("com.sun.star.sheet.FilterConnection", connector)
            fields.append(field)
        filter_desc.FilterFields = tuple(fields)
        filter_desc.ContainsHeader = contains_header
        remaining = {k: v for k, v in options.items() if k != "has_header"}
        if remaining:
            self._apply_direct_properties(filter_desc, remaining)
        range_obj.filter(filter_desc)

    def _filter_scope_range(self, doc: Any, sheet: Optional[str], range: Optional[str]) -> Any:
        """range omitted -> the sheet's used range, the same fallback
        clear_filter_live/get_filter_state_live's own optional `range`
        parameter implies (neither has `range` in its required list)."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        if range is not None:
            return sheet_obj.getCellRangeByName(range)
        cursor = sheet_obj.createCursor()
        cursor.gotoStartOfUsedArea(False)
        cursor.gotoEndOfUsedArea(True)
        addr = cursor.RangeAddress
        return sheet_obj.getCellRangeByPosition(addr.StartColumn, addr.StartRow, addr.EndColumn, addr.EndRow)

    def clear_filter(self, doc: Any, sheet: Optional[str] = None, range: Optional[str] = None) -> None:
        range_obj = self._filter_scope_range(doc, sheet, range)
        empty_desc = range_obj.createFilterDescriptor(True)
        empty_desc.FilterFields = ()
        range_obj.filter(empty_desc)

    def get_filter_state(self, doc: Any, sheet: Optional[str] = None, range: Optional[str] = None) -> Dict[str, Any]:
        range_obj = self._filter_scope_range(doc, sheet, range)
        filter_desc = range_obj.createFilterDescriptor(False)
        fields = []
        for field in filter_desc.FilterFields:
            fields.append({
                "column": field.Field, "operator": field.Operator.value,
                "value": field.NumericValue if field.IsNumeric else field.StringValue,
            })
        return {"active": len(fields) > 0, "conditions": fields}

    def list_conditional_format_entries(self, doc: Any, sheet: Optional[str] = None,
                                         range: Optional[str] = None) -> List[Any]:
        """Returns (sheet_name, range_string, index) addresses, NOT raw
        (range, entry) object pairs -- live-verified a legacy
        ConditionalFormat entry does NOT compare equal to itself across
        two separate fetches (cf.getByIndex(i) == cf.getByIndex(i) taken
        from two different range.ConditionalFormat reads is False),
        unlike shapes/documents elsewhere in this codebase. Registering
        the raw object pair (this section's first draft) meant
        ObjectRegistry's own identity-based dedup silently minted a
        different rule_id every time the same rule was listed, and
        update/delete's own re-location by identity always failed with
        "no longer exists" even on a rule that plainly still existed --
        caught testing this pass. Index-based addressing avoids that, at
        the honest cost (documented in tools/calc_data.py) that a
        rule_id can point at the wrong entry if unrelated add/remove
        calls change that same range's rule order first -- the "filled
        slot is not the right slot" risk a raw index always carries, but
        at least a reproducible, working mechanism, unlike the identity
        approach which didn't work at all."""
        sheet_name = self._resolve_sheet(doc, sheet).Name
        range_obj = self._filter_scope_range(doc, sheet, range)
        range_string = self._range_address_to_a1(doc, range_obj.RangeAddress).split(".", 1)[1]
        cf = range_obj.ConditionalFormat
        return [(sheet_name, range_string, i) for i in builtins.range(cf.Count)]

    def _resolve_conditional_format_ref(self, doc: Any, ref: Any) -> "tuple[Any, Any, int]":
        sheet_name, range_string, index = ref
        range_obj = self._resolve_sheet(doc, sheet_name).getCellRangeByName(range_string)
        cf = range_obj.ConditionalFormat
        if not (0 <= index < cf.Count):
            raise KeyError("This conditional format rule no longer exists (removed by another call).")
        return range_obj, cf, index

    def get_conditional_format_summary(self, doc: Any, ref: Any, rule_id: str) -> Dict[str, Any]:
        _, cf, index = self._resolve_conditional_format_ref(doc, ref)
        entry = cf.getByIndex(index)
        return {
            "rule_id": rule_id, "operator": entry.Operator.value,
            "formula1": entry.Formula1, "formula2": entry.Formula2, "style": entry.StyleName,
        }

    def add_conditional_format(self, doc: Any, range: str, rule: Dict[str, Any],
                                sheet: Optional[str] = None, style: Optional[str] = None) -> Any:
        """`rule`: {"operator": <raw com.sun.star.sheet.ConditionOperator
        name, e.g. "GREATER"/"EQUAL"/"BETWEEN"/"FORMULA">,
        "formula1": str, "formula2": str (BETWEEN/NOT_BETWEEN only)}.
        Raw enum name, not a friendly-name table -- ConditionOperator has
        ~25 members spanning value comparisons, text-match, duplicate/
        top-N/average-relative, and formula conditions; mapping the whole
        table wasn't attempted this pass, matching the transition-effect/
        AutoLayout precedent from the impress.py pass rather than
        guessing at a subset. Returns a (sheet_name, range_string, index)
        address -- see list_conditional_format_entries()'s docstring for
        why this, not the raw entry object, is what tools/calc_data.py
        registers."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        try:
            operator = uno.Enum("com.sun.star.sheet.ConditionOperator", str(rule["operator"]).upper())
        except Exception as e:
            raise ValueError(f"Unknown condition operator '{rule.get('operator')}': {e}") from e
        cf = range_obj.ConditionalFormat
        props = [
            PropertyValue("Operator", 0, operator, 0),
            PropertyValue("Formula1", 0, str(rule.get("formula1", "")), 0),
        ]
        if "formula2" in rule:
            props.append(PropertyValue("Formula2", 0, str(rule["formula2"]), 0))
        if style is not None:
            props.append(PropertyValue("StyleName", 0, style, 0))
        cf.addNew(tuple(props))
        range_obj.ConditionalFormat = cf
        return (sheet_obj.Name, range, cf.Count - 1)

    def update_conditional_format(self, doc: Any, ref: Any, properties: Dict[str, Any]) -> List[str]:
        range_obj, cf, index = self._resolve_conditional_format_ref(doc, ref)
        entry = cf.getByIndex(index)
        applied = []
        for key, value in properties.items():
            try:
                if key.lower() == "operator":
                    entry.Operator = uno.Enum("com.sun.star.sheet.ConditionOperator", str(value).upper())
                else:
                    setattr(entry, key, value)
                applied.append(key)
            except Exception:
                continue
        range_obj.ConditionalFormat = cf
        return applied

    def delete_conditional_format(self, doc: Any, ref: Any) -> None:
        range_obj, cf, index = self._resolve_conditional_format_ref(doc, ref)
        cf.removeByIndex(index)
        range_obj.ConditionalFormat = cf

    _VALIDATION_TYPES = {
        "any": "ANY", "whole_number": "WHOLE", "decimal": "DECIMAL", "list": "LIST", "date": "DATE",
        "time": "TIME", "text_length": "TEXTLEN", "custom": "CUSTOM",
    }
    _VALIDATION_OPERATORS = {
        "equal": "EQUAL", "not_equal": "NOT_EQUAL", "greater": "GREATER", "greater_equal": "GREATER_EQUAL",
        "less": "LESS", "less_equal": "LESS_EQUAL", "between": "BETWEEN", "not_between": "NOT_BETWEEN",
    }

    def get_data_validation(self, doc: Any, range: str, sheet: Optional[str] = None) -> Dict[str, Any]:
        sheet_obj = self._resolve_sheet(doc, sheet)
        cell = sheet_obj.getCellRangeByName(range).getCellByPosition(0, 0)
        validation = cell.Validation
        return {
            "type": validation.Type.value, "operator": validation.Operator.value,
            "formula1": validation.Formula1, "formula2": validation.Formula2,
            "show_list": bool(validation.getPropertyValue("ShowList")) if validation.getPropertySetInfo().hasPropertyByName("ShowList") else None,
            "ignore_blank": bool(validation.IgnoreBlankCells) if hasattr(validation, "IgnoreBlankCells") else None,
        }

    def set_data_validation(self, doc: Any, range: str, rule: Dict[str, Any], sheet: Optional[str] = None) -> List[str]:
        """`rule`: {"type": one of _VALIDATION_TYPES, "operator": one of
        _VALIDATION_OPERATORS (value-comparison types only), "formula1":
        str, "formula2": str (BETWEEN/NOT_BETWEEN), "show_list": bool,
        "ignore_blank": bool, "error_message"/"error_title": str,
        "input_message"/"input_title": str}. Applies to every cell in
        `range`, not just its first cell -- Validation is a per-cell
        property with no bulk-range setter; live-verified assigning the
        same configured object back to each cell in turn is the working
        pattern."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        type_name = self._VALIDATION_TYPES.get(str(rule.get("type", "any")).lower())
        if type_name is None:
            raise ValueError(f"Unknown validation type '{rule.get('type')}'. Supported: {sorted(self._VALIDATION_TYPES)}")
        addr = range_obj.getRangeAddress()
        for row in builtins.range(addr.EndRow - addr.StartRow + 1):
            for col in builtins.range(addr.EndColumn - addr.StartColumn + 1):
                cell = range_obj.getCellByPosition(col, row)
                validation = cell.Validation
                validation.Type = uno.Enum("com.sun.star.sheet.ValidationType", type_name)
                if "operator" in rule:
                    op_name = self._VALIDATION_OPERATORS.get(str(rule["operator"]).lower())
                    if op_name is None:
                        raise ValueError(f"Unknown validation operator '{rule['operator']}'. Supported: {sorted(self._VALIDATION_OPERATORS)}")
                    validation.setOperator(uno.Enum("com.sun.star.sheet.ConditionOperator", op_name))
                if "formula1" in rule:
                    validation.Formula1 = str(rule["formula1"])
                if "formula2" in rule:
                    validation.Formula2 = str(rule["formula2"])
                if "show_list" in rule:
                    validation.setPropertyValue("ShowList", 1 if rule["show_list"] else 0)
                if "ignore_blank" in rule and hasattr(validation, "IgnoreBlankCells"):
                    validation.IgnoreBlankCells = bool(rule["ignore_blank"])
                if "error_message" in rule:
                    validation.setPropertyValue("ErrorMessage", str(rule["error_message"]))
                if "error_title" in rule:
                    validation.setPropertyValue("ErrorTitle", str(rule["error_title"]))
                if "input_message" in rule:
                    validation.setPropertyValue("InputMessage", str(rule["input_message"]))
                if "input_title" in rule:
                    validation.setPropertyValue("InputTitle", str(rule["input_title"]))
                cell.Validation = validation
        return [k for k in rule if k in (
            "type", "operator", "formula1", "formula2", "show_list", "ignore_blank",
            "error_message", "error_title", "input_message", "input_title",
        )]

    def clear_data_validation(self, doc: Any, range: str, sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        addr = range_obj.getRangeAddress()
        for row in builtins.range(addr.EndRow - addr.StartRow + 1):
            for col in builtins.range(addr.EndColumn - addr.StartColumn + 1):
                cell = range_obj.getCellByPosition(col, row)
                validation = cell.Validation
                validation.Type = uno.Enum("com.sun.star.sheet.ValidationType", "ANY")
                cell.Validation = validation

    def create_subtotals(self, doc: Any, range: str, group_columns: List[int], subtotal_specs: List[Dict[str, Any]],
                          sheet: Optional[str] = None) -> None:
        """subtotal_specs items: {"column": <0-based index within range>,
        "function": one of GeneralFunction ("SUM"/"COUNT"/"AVERAGE"/
        "MAX"/"MIN"/"PRODUCT"/"COUNTNUMS"/"STDEV"/"STDEVP"/"VAR"/
        "VARP")}. Only the first entry in `group_columns` is honored --
        XSubTotalDescriptor.addNew() groups by one column per call, and
        the spec's own group_columns is a flat list with no per-level
        function grouping, so a single-level subtotal (the common case)
        is what this maps onto; multi-level nested subtotals would need
        one addNew() per group level, not attempted this pass."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        descriptor = range_obj.createSubTotalDescriptor(True)
        columns = []
        for spec in subtotal_specs:
            col = uno.createUnoStruct("com.sun.star.sheet.SubTotalColumn")
            col.Column = int(spec["column"])
            col.Function = uno.Enum("com.sun.star.sheet.GeneralFunction", str(spec.get("function", "sum")).upper())
            columns.append(col)
        descriptor.addNew(tuple(columns), int(group_columns[0]))
        range_obj.applySubTotals(descriptor, True)

    def remove_subtotals(self, doc: Any, range: str, sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        sheet_obj.getCellRangeByName(range).removeSubTotals()

    def list_pivot_tables(self, doc: Any, sheet: Optional[str] = None) -> List[Any]:
        """Returns raw XDataPilotTable objects for the tools/ layer to
        register. CAVEAT, live-verified: a fresh tables.getByName(name)
        fetch does NOT compare equal to an earlier fetch of the exact
        same pivot table (unlike shapes/documents elsewhere in this
        codebase), so ObjectRegistry's identity-based dedup can't
        recognize "the same" pivot table across two separate calls to
        this method -- calling list_pivot_tables_live twice mints a
        different pivot_id each time for the same underlying pivot
        table. This does NOT break the ids themselves: every pivot_id
        this mints still works correctly for get/update/refresh/delete,
        since those all operate on the held reference directly (read
        .Name/.OutputRange, call .refresh()) rather than re-locating by
        comparison. See tools/calc_data.py's module docstring and
        list_pivot_tables_live's own purpose= string for the
        caller-facing version of this warning."""
        sheets = [self._resolve_sheet(doc, sheet)] if sheet is not None else \
            [doc.getSheets().getByIndex(i) for i in range(doc.getSheets().getCount())]
        result = []
        for sheet_obj in sheets:
            tables = sheet_obj.DataPilotTables
            for name in tables.getElementNames():
                result.append(tables.getByName(name))
        return result

    def get_pivot_table_summary(self, doc: Any, pivot: Any, pivot_id: str) -> Dict[str, Any]:
        output = pivot.OutputRange
        fields = pivot.DataPilotFields
        layout = {"rows": [], "columns": [], "data": [], "filters": []}
        orientation_key = {"ROW": "rows", "COLUMN": "columns", "DATA": "data", "PAGE": "filters"}
        for i in range(fields.getCount()):
            field = fields.getByIndex(i)
            key = orientation_key.get(field.Orientation.value)
            if key:
                layout[key].append(field.Name)
        return {
            "pivot_id": pivot_id, "name": pivot.Name, "sheet": doc.getSheets().getByIndex(output.Sheet).Name,
            "output_range": self._range_address_to_a1(doc, output),
            "layout": layout,
        }

    def create_pivot_table(self, doc: Any, source: str, destination: str, rows: List[str], columns: List[str],
                            data_fields: List[Dict[str, Any]], filters: Optional[List[str]] = None) -> Any:
        """`source`/`destination` are A1-style range/cell references on
        the active sheet. `rows`/`columns`/`filters` are source field
        (column header) names; `data_fields` items are {"field": str,
        "function": one of GeneralFunction (default "sum")}. Returns the
        raw XDataPilotTable for the tools/ layer to register."""
        sheet_obj = self._resolve_sheet(doc, None)
        source_range = sheet_obj.getCellRangeByName(source).RangeAddress
        dest_cell = sheet_obj.getCellRangeByName(destination).RangeAddress
        dest_addr = uno.createUnoStruct("com.sun.star.table.CellAddress")
        dest_addr.Sheet, dest_addr.Column, dest_addr.Row = dest_cell.Sheet, dest_cell.StartColumn, dest_cell.StartRow

        tables = sheet_obj.DataPilotTables
        descriptor = tables.createDataPilotDescriptor()
        descriptor.SourceRange = source_range
        fields = descriptor.DataPilotFields
        for name in rows:
            fields.getByName(name).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW")
        for name in columns:
            fields.getByName(name).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "COLUMN")
        for name in (filters or []):
            fields.getByName(name).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "PAGE")
        for spec in data_fields:
            field = fields.getByName(spec["field"])
            field.Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA")
            field.Function = uno.Enum("com.sun.star.sheet.GeneralFunction", str(spec.get("function", "sum")).upper())

        index = 1
        name = f"Pivot{index}"
        while tables.hasByName(name):
            index += 1
            name = f"Pivot{index}"
        tables.insertNewByName(name, dest_addr, descriptor)
        return tables.getByName(name)

    def update_pivot_table(self, pivot: Any, configuration: Dict[str, Any]) -> List[str]:
        """`configuration`: any of rows/columns/data_fields/filters (same
        shapes create_pivot_table_live accepts) -- reassigns field
        orientations on the existing pivot and refreshes."""
        fields = pivot.DataPilotFields
        applied = []
        for i in range(fields.getCount()):
            fields.getByIndex(i).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "HIDDEN")
        if "rows" in configuration:
            for name in configuration["rows"]:
                fields.getByName(name).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW")
            applied.append("rows")
        if "columns" in configuration:
            for name in configuration["columns"]:
                fields.getByName(name).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "COLUMN")
            applied.append("columns")
        if "filters" in configuration:
            for name in configuration["filters"]:
                fields.getByName(name).Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "PAGE")
            applied.append("filters")
        if "data_fields" in configuration:
            for spec in configuration["data_fields"]:
                field = fields.getByName(spec["field"])
                field.Orientation = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA")
                field.Function = uno.Enum("com.sun.star.sheet.GeneralFunction", str(spec.get("function", "sum")).upper())
            applied.append("data_fields")
        pivot.refresh()
        return applied

    @staticmethod
    def refresh_pivot_table(pivot: Any) -> None:
        pivot.refresh()

    @staticmethod
    def delete_pivot_table(doc: Any, pivot: Any) -> None:
        name = pivot.Name
        sheet_obj = doc.getSheets().getByIndex(pivot.OutputRange.Sheet)
        sheet_obj.DataPilotTables.removeByName(name)

    def list_scenarios(self, doc: Any, sheet: Optional[str] = None) -> List[Dict[str, Any]]:
        """ScenarioComment, not the guessed "Comment" -- live-verified via
        the sheet's own real property list (a Scenario sheet has no plain
        "Comment" property at all; the raw UNO_EXCEPTION just names the
        missing property, caught testing this pass)."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        scenarios = sheet_obj.Scenarios
        return [{"name": n, "comment": scenarios.getByName(n).ScenarioComment} for n in scenarios.getElementNames()]

    def create_scenario(self, doc: Any, name: str, ranges: List[str], comment: Optional[str] = None,
                         options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        sheet_obj = self._resolve_sheet(doc, None)
        range_addrs = tuple(sheet_obj.getCellRangeByName(r).RangeAddress for r in ranges)
        sheet_obj.Scenarios.addNewByName(name, range_addrs, comment or "")
        if options:
            self._apply_direct_properties(sheet_obj.Scenarios.getByName(name), options)
        return {"name": name}

    def apply_scenario(self, doc: Any, name: str) -> None:
        sheet_obj = self._resolve_sheet(doc, None)
        scenarios = sheet_obj.Scenarios
        if not scenarios.hasByName(name):
            raise KeyError(f"No such scenario '{name}'.")
        scenarios.getByName(name).apply()

    def delete_scenario(self, doc: Any, name: str) -> None:
        sheet_obj = self._resolve_sheet(doc, None)
        scenarios = sheet_obj.Scenarios
        if not scenarios.hasByName(name):
            raise KeyError(f"No such scenario '{name}'.")
        scenarios.removeByName(name)

    def goal_seek(self, doc: Any, formula_cell: str, target_value: float, variable_cell: str) -> Dict[str, Any]:
        """doc.seekGoal() computes and returns the answer but does NOT
        write it back to the variable cell itself -- live-verified the
        cell's own value is unchanged after the call returns. Applied
        here explicitly to match Calc's own Goal Seek dialog behavior
        (which does commit on accept), since a caller asking this tool
        to "perform goal seek" almost certainly wants the sheet updated,
        not just the number reported."""
        sheet_obj = self._resolve_sheet(doc, None)
        formula_addr = sheet_obj.getCellRangeByName(formula_cell).RangeAddress
        variable_addr = sheet_obj.getCellRangeByName(variable_cell).RangeAddress
        formula_cell_addr = uno.createUnoStruct("com.sun.star.table.CellAddress")
        formula_cell_addr.Sheet, formula_cell_addr.Column, formula_cell_addr.Row = \
            formula_addr.Sheet, formula_addr.StartColumn, formula_addr.StartRow
        variable_cell_addr = uno.createUnoStruct("com.sun.star.table.CellAddress")
        variable_cell_addr.Sheet, variable_cell_addr.Column, variable_cell_addr.Row = \
            variable_addr.Sheet, variable_addr.StartColumn, variable_addr.StartRow
        result = doc.seekGoal(formula_cell_addr, variable_cell_addr, float(target_value))
        converged = abs(result.Divergence) < 1e-6
        if converged:
            sheet_obj.getCellByPosition(variable_cell_addr.Column, variable_cell_addr.Row).setValue(result.Result)
        return {"converged": converged, "result": result.Result, "divergence": result.Divergence}

    _SOLVER_OPERATORS = {"<=": "LESS_EQUAL", ">=": "GREATER_EQUAL", "=": "EQUAL"}

    def solver_solve(self, doc: Any, objective_cell: str, optimize: str, variable_cells: List[str],
                      constraints: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Uses whichever com.sun.star.sheet.Solver implementation this
        LibreOffice build registers first (live-verified this one
        resolves to the bundled NLPSolver/DEPS evolutionary solver) --
        the spec's own "when solver service is available" wording
        anticipates this varying by build/install, so a missing service
        is surfaced as a real UNO_EXCEPTION, not pre-checked. optimize
        supports "min"/"max" via Solver.Maximize; "value" (target a
        specific objective value rather than extremize it) has no
        corresponding XSolver property and isn't implemented this pass."""
        if optimize not in ("min", "max"):
            raise NotImplementedError(
                f"solver_solve_live's optimize='{optimize}' is not implemented this pass -- only 'min'/'max' "
                "map onto XSolver.Maximize; 'value' (target a specific objective value) has no equivalent "
                "XSolver property in this API."
            )
        sheet_obj = self._resolve_sheet(doc, None)

        def to_addr(a1: str) -> Any:
            addr = sheet_obj.getCellRangeByName(a1).RangeAddress
            cell_addr = uno.createUnoStruct("com.sun.star.table.CellAddress")
            cell_addr.Sheet, cell_addr.Column, cell_addr.Row = addr.Sheet, addr.StartColumn, addr.StartRow
            return cell_addr

        solver = self.smgr.createInstanceWithContext("com.sun.star.sheet.Solver", self.ctx)
        solver.Document = doc
        solver.Objective = to_addr(objective_cell)
        solver.Variables = tuple(to_addr(c) for c in variable_cells)
        solver.Maximize = (optimize == "max")
        solver_constraints = []
        for constraint in (constraints or []):
            op_name = self._SOLVER_OPERATORS.get(str(constraint["operator"]))
            if op_name is None:
                raise ValueError(f"Unknown solver constraint operator '{constraint['operator']}'. Supported: {sorted(self._SOLVER_OPERATORS)}")
            sc = uno.createUnoStruct("com.sun.star.sheet.SolverConstraint")
            sc.Left = to_addr(constraint["cell"])
            sc.Operator = uno.Enum("com.sun.star.sheet.SolverConstraintOperator", op_name)
            right = constraint["value"]
            sc.Right = to_addr(right) if isinstance(right, str) else float(right)
            solver_constraints.append(sc)
        solver.Constraints = tuple(solver_constraints)
        solver.solve()
        return {
            "success": bool(solver.Success), "result_value": solver.ResultValue if solver.Success else None,
            "solution": list(solver.Solution) if solver.Success else [],
            "status": solver.StatusDescription,
        }

    def list_database_ranges(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_calc(doc, "list_database_ranges")
        ranges = doc.DatabaseRanges
        result = []
        for name in ranges.getElementNames():
            db_range = ranges.getByName(name)
            addr = db_range.DataArea
            result.append({
                "name": name, "sheet": doc.getSheets().getByIndex(addr.Sheet).Name,
                "range": self._range_address_to_a1(doc, addr),
            })
        return result

    def create_database_range(self, doc: Any, name: str, sheet: str, range: str) -> Dict[str, Any]:
        self._require_calc(doc, "create_database_range")
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = sheet_obj.getCellRangeByName(range).RangeAddress
        doc.DatabaseRanges.addNewByName(name, addr)
        return {"name": name}

    def delete_database_range(self, doc: Any, name: str) -> None:
        self._require_calc(doc, "delete_database_range")
        ranges = doc.DatabaseRanges
        if not ranges.hasByName(name):
            raise KeyError(f"No such database range '{name}'.")
        ranges.removeByName(name)

    def list_external_links(self, doc: Any) -> Dict[str, List[Dict[str, Any]]]:
        """Reports both of Calc's genuinely separate cross-file-reference
        mechanisms -- see this section's header comment above for how
        they were live-verified as non-overlapping. `formula_links` is
        the pre-existing read-only ExternalDocLinks enumeration
        (link_id/url only -- no refresh state, no write side).
        `area_links` is the AreaLinks mechanism create_external_link()/
        refresh_external_link()/delete_external_link() operate on below,
        with real refresh state (`refresh_delay_seconds`)."""
        self._require_calc(doc, "list_external_links")
        formula_links = [{"link_id": name, "url": name} for name in doc.ExternalDocLinks.getElementNames()]
        area_links = [self._describe_area_link(doc, i) for i in range(doc.AreaLinks.getCount())]
        return {"formula_links": formula_links, "area_links": area_links}

    def _area_link_id(self, sheet_name: str, dest_col: int, dest_row: int) -> str:
        return f"{sheet_name}!{self._column_row_to_a1(dest_col, dest_row)}"

    def _describe_area_link(self, doc: Any, index: int) -> Dict[str, Any]:
        item = doc.AreaLinks.getByIndex(index)
        dest = item.DestArea
        sheet_name = doc.getSheets().getByIndex(dest.Sheet).Name
        dest_a1 = (
            f"{sheet_name}.{self._column_row_to_a1(dest.StartColumn, dest.StartRow)}"
            f":{self._column_row_to_a1(dest.EndColumn, dest.EndRow)}"
        )
        return {
            "link_id": self._area_link_id(sheet_name, dest.StartColumn, dest.StartRow),
            "url": item.Url,
            "source_area": item.SourceArea,
            "destination": dest_a1,
            "filter": item.Filter,
            "refresh_delay_seconds": item.RefreshDelay,
        }

    def _find_area_link_index(self, doc: Any, link_id: str) -> int:
        for i in range(doc.AreaLinks.getCount()):
            item = doc.AreaLinks.getByIndex(i)
            dest = item.DestArea
            sheet_name = doc.getSheets().getByIndex(dest.Sheet).Name
            if self._area_link_id(sheet_name, dest.StartColumn, dest.StartRow) == link_id:
                return i
        raise KeyError(f"No such external link '{link_id}'.")

    # Filter names live-verified against real LibreOffice for
    # insertAtPosition()'s required "filter" argument -- only these
    # extensions are mapped; anything else raises rather than guessing a
    # filter name that would silently fail to open.
    _AREA_LINK_FILTERS = {
        ".ods": "calc8",
        ".xlsx": "Calc MS Excel 2007 XML",
        ".xls": "MS Excel 97",
        ".csv": "Text - txt - csv (StarCalc)",
    }

    def create_external_link(self, doc: Any, source_url: str, source_area: str, destination: str,
                              filter: Optional[str] = None) -> Dict[str, Any]:
        """Live-verified real mechanism: com.sun.star.sheet.XAreaLinks.
        insertAtPosition(destCellAddress, url, sourceArea, filterName,
        filterOptions) on doc.AreaLinks -- NOT doc.ExternalDocLinks,
        which has no write side at all (see list_external_links()'s
        docstring). `destination` accepts "SheetName.A1" (Calc-native
        dot notation, matching `source_area`'s own format); a bare
        "A1" with no "." resolves against the active sheet. `filter`
        defaults to a guess from source_url's extension for the small
        set of formats this pass verified a working filter name for
        (see _AREA_LINK_FILTERS) -- pass filter explicitly for anything
        else rather than have this silently guess wrong."""
        self._require_calc(doc, "create_external_link")
        if "." in destination:
            sheet_name, cell_ref = destination.split(".", 1)
            dest_sheet_obj = self._resolve_sheet_by_name_or_index(doc.getSheets(), sheet_name)
        else:
            cell_ref = destination
            dest_sheet_obj = self._resolve_sheet(doc, None)
        dest_addr = self._cell_address_from_range(dest_sheet_obj.getCellRangeByName(cell_ref))

        resolved_filter = filter
        if resolved_filter is None:
            suffix = os.path.splitext(source_url)[1].lower()
            resolved_filter = self._AREA_LINK_FILTERS.get(suffix)
            if resolved_filter is None:
                raise NotImplementedError(
                    f"create_external_link_live could not infer a filter for '{source_url}' -- "
                    f"pass filter explicitly (verified names: {sorted(self._AREA_LINK_FILTERS.values())})."
                )

        doc.AreaLinks.insertAtPosition(dest_addr, source_url, source_area, resolved_filter, "")
        link_id = self._area_link_id(dest_sheet_obj.Name, dest_addr.Column, dest_addr.Row)
        return self._describe_area_link(doc, self._find_area_link_index(doc, link_id))

    def refresh_external_link(self, doc: Any, link_id: str) -> Dict[str, Any]:
        """Live-verified: each AreaLinks entry queryInterface()s to a
        real, working com.sun.star.util.XRefreshable -- .refresh() pulls
        fresh values from the source file on disk into the destination
        range immediately, live-verified against a source file modified
        and re-saved after the link was created."""
        self._require_calc(doc, "refresh_external_link")
        index = self._find_area_link_index(doc, link_id)
        item = doc.AreaLinks.getByIndex(index)
        refreshable = item.queryInterface(uno.getTypeByName("com.sun.star.util.XRefreshable"))
        if refreshable is None:
            raise RuntimeError(f"Area link '{link_id}' does not expose XRefreshable.")
        refreshable.refresh()
        return self._describe_area_link(doc, index)

    def delete_external_link(self, doc: Any, link_id: str, keep_values: bool = True) -> Dict[str, Any]:
        """XAreaLinks.removeByIndex() only detaches the link definition
        -- live-verified the destination cells keep whatever values were
        last refreshed into them, matching Edit > Links > Break Link's
        real behavior and this tool's keep_values=True default. For
        keep_values=False, live-verified a plain clearContents() with
        every content flag set (there is no separate "remove and clear"
        UNO mode) empties the destination range after the link is
        removed."""
        self._require_calc(doc, "delete_external_link")
        index = self._find_area_link_index(doc, link_id)
        dest = doc.AreaLinks.getByIndex(index).DestArea
        doc.AreaLinks.removeByIndex(index)
        if not keep_values:
            sheet_obj = doc.getSheets().getByIndex(dest.Sheet)
            dest_range = sheet_obj.getCellRangeByPosition(dest.StartColumn, dest.StartRow, dest.EndColumn, dest.EndRow)
            all_flags = (
                CellFlags.VALUE | CellFlags.DATETIME | CellFlags.STRING | CellFlags.ANNOTATION
                | CellFlags.FORMULA | CellFlags.HARDATTR | CellFlags.STYLES | CellFlags.OBJECTS | CellFlags.EDITATTR
            )
            dest_range.clearContents(all_flags)
        return {"deleted": link_id, "kept_values": keep_values}

    _CSV_CHARSETS = {"utf-8": 76, "utf8": 76}

    def import_csv_to_range(self, doc: Any, file_path: str, destination: str, delimiter: str = ",",
                             encoding: str = "utf-8", options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Loads the CSV as a temporary hidden Calc document via the same
        "Text - txt - csv (StarCalc)" import filter Calc's own File > Open
        uses, then copies its used-range values into `destination` on the
        real document, then closes the temp document -- there's no
        direct "import CSV into an existing range" UNO API. Only
        encoding="utf-8" is mapped to a verified FilterOptions charset
        code this pass; any other encoding raises rather than guessing at
        the charset-code table."""
        self._require_calc(doc, "import_csv_to_range")
        charset = self._CSV_CHARSETS.get(encoding.lower())
        if charset is None:
            raise NotImplementedError(
                f"import_csv_to_range_live encoding='{encoding}' is not implemented this pass -- "
                f"only {sorted(self._CSV_CHARSETS)} are mapped to a verified charset code."
            )
        filter_options = f"{ord(delimiter)},34,{charset},1"
        temp_doc = self.desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(file_path), "_blank", 0,
            (
                PropertyValue("FilterName", 0, "Text - txt - csv (StarCalc)", 0),
                PropertyValue("FilterOptions", 0, filter_options, 0),
                PropertyValue("Hidden", 0, True, 0),
            ),
        )
        try:
            temp_sheet = temp_doc.getSheets().getByIndex(0)
            cursor = temp_sheet.createCursor()
            cursor.gotoStartOfUsedArea(False)
            cursor.gotoEndOfUsedArea(True)
            used = cursor.RangeAddress
            rows = used.EndRow - used.StartRow + 1
            cols = used.EndColumn - used.StartColumn + 1
            source_range = temp_sheet.getCellRangeByPosition(used.StartColumn, used.StartRow, used.EndColumn, used.EndRow)
            values = source_range.getDataArray()

            dest_sheet = self._resolve_sheet(doc, None)
            dest_cell = dest_sheet.getCellRangeByName(destination)
            dest_addr = dest_cell.RangeAddress
            dest_range = dest_sheet.getCellRangeByPosition(
                dest_addr.StartColumn, dest_addr.StartRow,
                dest_addr.StartColumn + cols - 1, dest_addr.StartRow + rows - 1,
            )
            dest_range.setDataArray(values)
        finally:
            temp_doc.close(False)
        return {"rows": rows, "columns": cols}

    def export_range_to_csv(self, doc: Any, range: str, file_path: str, sheet: Optional[str] = None,
                             delimiter: str = ",", encoding: str = "utf-8") -> None:
        """No direct "export just this range" UNO filter call -- copies
        the range into a temporary hidden Calc document (same pattern
        import_csv_to_range uses in reverse) and storeToURL's that."""
        charset = self._CSV_CHARSETS.get(encoding.lower())
        if charset is None:
            raise NotImplementedError(
                f"export_range_to_csv_live encoding='{encoding}' is not implemented this pass -- "
                f"only {sorted(self._CSV_CHARSETS)} are mapped to a verified charset code."
            )
        sheet_obj = self._resolve_sheet(doc, sheet)
        source_range = sheet_obj.getCellRangeByName(range)
        values = source_range.getDataArray()

        temp_doc = self.desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (PropertyValue("Hidden", 0, True, 0),))
        try:
            temp_sheet = temp_doc.getSheets().getByIndex(0)
            rows, cols = len(values), (len(values[0]) if values else 0)
            if rows and cols:
                dest_range = temp_sheet.getCellRangeByPosition(0, 0, cols - 1, rows - 1)
                dest_range.setDataArray(values)
            filter_options = f"{ord(delimiter)},34,{charset},1"
            temp_doc.storeToURL(uno.systemPathToFileUrl(file_path), (
                PropertyValue("FilterName", 0, "Text - txt - csv (StarCalc)", 0),
                PropertyValue("FilterOptions", 0, filter_options, 0),
            ))
        finally:
            temp_doc.close(False)

    def group_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        addr.Sheet, addr.StartColumn, addr.EndColumn = 0, 0, 0
        addr.StartRow, addr.EndRow = min(rows), max(rows)
        sheet_obj.group(addr, uno.Enum("com.sun.star.table.TableOrientation", "ROWS"))

    def ungroup_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        addr.Sheet, addr.StartColumn, addr.EndColumn = 0, 0, 0
        addr.StartRow, addr.EndRow = min(rows), max(rows)
        sheet_obj.ungroup(addr, uno.Enum("com.sun.star.table.TableOrientation", "ROWS"))

    def group_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        addr.Sheet, addr.StartRow, addr.EndRow = 0, 0, 0
        addr.StartColumn, addr.EndColumn = min(columns), max(columns)
        sheet_obj.group(addr, uno.Enum("com.sun.star.table.TableOrientation", "COLUMNS"))

    def ungroup_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        addr.Sheet, addr.StartRow, addr.EndRow = 0, 0, 0
        addr.StartColumn, addr.EndColumn = min(columns), max(columns)
        sheet_obj.ungroup(addr, uno.Enum("com.sun.star.table.TableOrientation", "COLUMNS"))

    # -- Calc page setup, print ranges, annotations, protection
    # (tools/calc_page.py's 15 tools) --
    #
    # Same raise-on-failure convention as calc_sheets.py/calc_data.py
    # above. All 15 tools are real this pass.

    def _sheet_page_style(self, doc: Any, sheet: Optional[str] = None) -> "tuple[Any, Any]":
        """Returns (page_style_object, sheet_object). A Calc page's
        layout (size/margins/orientation/scale/header/footer) lives on
        the com.sun.star.style.PageStyle the sheet references by name
        (sheet.PageStyle), the same StyleFamilies("PageStyles") family
        styles.py already resolves through _get_style_family() -- not a
        direct sheet property."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        page_styles = doc.StyleFamilies.getByName("PageStyles")
        return page_styles.getByName(sheet_obj.PageStyle), sheet_obj

    _PAGE_LAYOUT_PROPS = (
        "Width", "Height", "IsLandscape", "LeftMargin", "RightMargin", "TopMargin", "BottomMargin",
        "HeaderIsOn", "FooterIsOn", "HeaderHeight", "FooterHeight", "PageScale",
        "ScaleToPages", "ScaleToPagesX", "ScaleToPagesY", "PrintHeaders",
    )

    def get_sheet_page_layout(self, doc: Any, sheet: Optional[str] = None) -> Dict[str, Any]:
        page_style, sheet_obj = self._sheet_page_style(doc, sheet)
        result: Dict[str, Any] = {"page_style": sheet_obj.PageStyle}
        for name in self._PAGE_LAYOUT_PROPS:
            try:
                result[name] = self._uno_value_to_plain(page_style.getPropertyValue(name))
            except Exception:
                continue
        return result

    def set_sheet_page_layout(self, doc: Any, sheet: Optional[str] = None, width: Optional[float] = None,
                               height: Optional[float] = None, unit: Optional[str] = None,
                               orientation: Optional[str] = None, margins: Optional[Dict[str, Any]] = None,
                               scale: Optional[Dict[str, Any]] = None) -> List[str]:
        """`margins`: {"left"/"right"/"top"/"bottom": number, same `unit`
        as width/height}. `scale`: {"percent": int} (PageScale) or
        {"pages_wide": int, "pages_tall": int} (ScaleToPagesX/Y, 0 means
        "as many as needed" on that axis, matching Calc's own "fit to N
        pages wide by M tall" UI semantics) -- live-verified both are
        real, independent PageStyle properties, not mutually exclusive
        at the API level even though Calc's UI presents them as
        radio-button alternatives."""
        page_style, _ = self._sheet_page_style(doc, sheet)
        factor = self._LENGTH_UNIT_TO_MM100.get((unit or "mm100").lower(), 1)
        applied = []
        if width is not None:
            page_style.Width = int(width * factor)
            applied.append("width")
        if height is not None:
            page_style.Height = int(height * factor)
            applied.append("height")
        if orientation is not None:
            page_style.IsLandscape = str(orientation).lower() == "landscape"
            applied.append("orientation")
        if margins:
            margin_props = {"left": "LeftMargin", "right": "RightMargin", "top": "TopMargin", "bottom": "BottomMargin"}
            for key, prop_name in margin_props.items():
                if key in margins:
                    setattr(page_style, prop_name, int(margins[key] * factor))
                    applied.append(f"margins.{key}")
        if scale:
            if "percent" in scale:
                page_style.PageScale = int(scale["percent"])
                applied.append("scale.percent")
            if "pages_wide" in scale or "pages_tall" in scale:
                page_style.ScaleToPagesX = int(scale.get("pages_wide", 0))
                page_style.ScaleToPagesY = int(scale.get("pages_tall", 0))
                applied.append("scale.pages")
        return applied

    def set_print_area(self, doc: Any, ranges: List[str], sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        sheet_obj.PrintAreas = tuple(sheet_obj.getCellRangeByName(r).RangeAddress for r in ranges)

    def clear_print_area(self, doc: Any, sheet: Optional[str] = None) -> None:
        self._resolve_sheet(doc, sheet).PrintAreas = ()

    def set_repeating_print_rows(self, doc: Any, rows: List[int], sheet: Optional[str] = None) -> None:
        """TitleRows is a single CellRangeAddress spanning the given
        rows (0-based) -- its Column bounds are live-verified irrelevant
        to the real effect (a fresh sheet's default TitleRows already
        reads Column 0-0 despite meaning "no repeat", i.e. Calc reads
        this as a row-index range regardless of the column span)."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        addr.Sheet, addr.StartColumn, addr.EndColumn = 0, 0, 0
        addr.StartRow, addr.EndRow = min(rows), max(rows)
        sheet_obj.TitleRows = addr

    def set_repeating_print_columns(self, doc: Any, columns: List[int], sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        addr = uno.createUnoStruct("com.sun.star.table.CellRangeAddress")
        addr.Sheet, addr.StartRow, addr.EndRow = 0, 0, 0
        addr.StartColumn, addr.EndColumn = min(columns), max(columns)
        sheet_obj.TitleColumns = addr

    def _find_annotation_at(self, annotations: Any, column: int, row: int) -> Optional[Any]:
        for i in builtins.range(annotations.getCount()):
            ann = annotations.getByIndex(i)
            if ann.Position.Column == column and ann.Position.Row == row:
                return ann
        return None

    def add_cell_comment(self, doc: Any, cell: str, text: str, sheet: Optional[str] = None,
                          author: Optional[str] = None) -> Dict[str, Any]:
        """"Add/update" per the spec's own purpose text -- an existing
        comment at the same cell is updated in place rather than
        duplicated, found by scanning Annotations for a matching
        Position (there's no direct "get comment at cell" lookup).

        Author is read-only in this LibreOffice build (auto-derived from
        the user identity, not settable) -- live-verified attempting to
        write it raises a raw "property ... is readonly" UNO_EXCEPTION,
        which previously aborted the whole call (including the text that
        had already been applied) rather than just failing to honor the
        one unsettable field. Caught explicitly now so a caller-supplied
        `author` that can't be honored doesn't take the actual comment
        text down with it; `author_applied` in the result tells the
        caller whether it landed."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        cell_addr = sheet_obj.getCellRangeByName(cell).RangeAddress
        annotations = sheet_obj.Annotations
        existing = self._find_annotation_at(annotations, cell_addr.StartColumn, cell_addr.StartRow)
        if existing is None:
            position = uno.createUnoStruct("com.sun.star.table.CellAddress")
            position.Sheet, position.Column, position.Row = cell_addr.Sheet, cell_addr.StartColumn, cell_addr.StartRow
            annotations.insertNew(position, text)
            existing = self._find_annotation_at(annotations, cell_addr.StartColumn, cell_addr.StartRow)
        else:
            existing.setString(text)
        author_applied = False
        if author is not None:
            try:
                existing.Author = author
                author_applied = True
            except Exception:
                pass
        return {"cell": cell, "author_applied": author_applied}

    def list_cell_comments(self, doc: Any, sheet: Optional[str] = None, range: Optional[str] = None) -> List[Dict[str, Any]]:
        sheet_obj = self._resolve_sheet(doc, sheet)
        bounds = sheet_obj.getCellRangeByName(range).RangeAddress if range is not None else None
        annotations = sheet_obj.Annotations
        result = []
        for i in builtins.range(annotations.getCount()):
            ann = annotations.getByIndex(i)
            pos = ann.Position
            if bounds is not None and not (
                bounds.StartColumn <= pos.Column <= bounds.EndColumn and bounds.StartRow <= pos.Row <= bounds.EndRow
            ):
                continue
            result.append({"cell": self._column_row_to_a1(pos.Column, pos.Row), "text": ann.getString(), "author": ann.Author})
        return result

    def delete_cell_comment(self, doc: Any, cell: str, sheet: Optional[str] = None) -> None:
        sheet_obj = self._resolve_sheet(doc, sheet)
        cell_addr = sheet_obj.getCellRangeByName(cell).RangeAddress
        annotations = sheet_obj.Annotations
        for i in builtins.range(annotations.getCount()):
            ann = annotations.getByIndex(i)
            if ann.Position.Column == cell_addr.StartColumn and ann.Position.Row == cell_addr.StartRow:
                annotations.removeByIndex(i)
                return
        raise KeyError(f"No comment at cell '{cell}'.")

    def protect_sheet(self, doc: Any, sheet: Optional[str] = None, password: Optional[str] = None,
                       options: Optional[Dict[str, Any]] = None) -> List[str]:
        """`options` (e.g. per-action permission flags) are applied
        best-effort as direct properties on the sheet after protecting
        it -- not exploration-tested against a specific known property
        set this pass, same best-effort skip-unsettable-keys contract
        _apply_direct_properties uses elsewhere."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        sheet_obj.protect(password or "")
        applied = ["password"] if password else []
        if options:
            applied.extend(self._apply_direct_properties(sheet_obj, options))
        return applied

    def unprotect_sheet(self, doc: Any, sheet: Optional[str] = None, password: Optional[str] = None) -> None:
        self._resolve_sheet(doc, sheet).unprotect(password or "")

    _CELL_PROTECTION_PROPS = {
        "locked": "IsLocked", "hidden": "IsHidden",
        "formula_hidden": "IsFormulaHidden", "print_hidden": "IsPrintHidden",
    }

    def set_cell_protection(self, doc: Any, range: str, properties: Dict[str, Any],
                             sheet: Optional[str] = None) -> List[str]:
        """`properties`: any of "locked"/"hidden"/"formula_hidden"/
        "print_hidden" (bool) -- the real com.sun.star.util.
        CellProtection struct's own field names, confirmed via
        CoreReflection."""
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        protection = range_obj.CellProtection
        applied = []
        for key, attr in self._CELL_PROTECTION_PROPS.items():
            if key in properties:
                setattr(protection, attr, bool(properties[key]))
                applied.append(key)
        range_obj.CellProtection = protection
        return applied

    @staticmethod
    def _parse_locale(locale_str: Optional[str]) -> Any:
        """"xx"/"xx-YY"/"xx_YY" -> a com.sun.star.lang.Locale (Language/
        Country) -- None or empty gives the default/unset locale, the
        same one _resolve_number_format_key already used before this
        pass added the optional `locale` parameter."""
        loc = uno.createUnoStruct("com.sun.star.lang.Locale")
        if locale_str:
            parts = locale_str.replace("_", "-").split("-")
            loc.Language = parts[0]
            if len(parts) > 1:
                loc.Country = parts[1]
        return loc

    _NUMBER_FORMAT_CATEGORIES = {
        "all": NumberFormat.ALL, "date": NumberFormat.DATE, "time": NumberFormat.TIME,
        "currency": NumberFormat.CURRENCY, "number": NumberFormat.NUMBER,
        "scientific": NumberFormat.SCIENTIFIC, "fraction": NumberFormat.FRACTION,
        "percent": NumberFormat.PERCENT, "text": NumberFormat.TEXT,
        "datetime": NumberFormat.DATETIME, "logical": NumberFormat.LOGICAL,
    }

    def list_number_formats(self, doc: Any, locale: Optional[str] = None) -> List[Dict[str, Any]]:
        """No direct "enumerate every format" UNO API exists --
        XNumberFormats is keyed/query access (getByKey/queryKey), not an
        indexable collection. Lists the standard format for each of the
        well-known com.sun.star.util.NumberFormat categories instead,
        live-verified via getStandardFormat(); a custom/user-defined
        format not tied to a standard category won't appear here unless
        separately looked up by create_number_format_live/
        apply_number_format_live's own format_code path."""
        self._require_calc(doc, "list_number_formats")
        formats = doc.getNumberFormats()
        loc = self._parse_locale(locale)
        result = []
        for name, category in self._NUMBER_FORMAT_CATEGORIES.items():
            try:
                key = formats.getStandardFormat(category, loc)
                entry = formats.getByKey(key)
                result.append({"category": name, "format_key": key, "format_code": entry.FormatString})
            except Exception:
                continue
        return result

    def create_number_format(self, doc: Any, format_code: str, locale: Optional[str] = None) -> Dict[str, Any]:
        self._require_calc(doc, "create_number_format")
        key = self._resolve_number_format_key(doc, format_code, self._parse_locale(locale))
        return {"format_key": key, "format_code": format_code}

    def apply_number_format(self, doc: Any, range: str, sheet: Optional[str] = None,
                             format_code: Optional[str] = None, format_key: Optional[int] = None) -> Dict[str, Any]:
        sheet_obj = self._resolve_sheet(doc, sheet)
        range_obj = sheet_obj.getCellRangeByName(range)
        if format_key is not None:
            key = int(format_key)
        elif format_code is not None:
            key = self._resolve_number_format_key(doc, format_code)
        else:
            raise ValueError("Either format_code or format_key must be given.")
        range_obj.NumberFormat = key
        return {"format_key": key}

    # -- Writer page layout, publishing, styles, headers, fields, indexes
    # (tools/writer_layout.py's 43 tools) --
    #
    # Same raise-on-failure convention as writer_text.py above. Page
    # style resolution reuses _get_style_family(doc, "PageStyles") --
    # the same family styles.py/calc_page.py already resolve through.
    # Bookmarks are UNO-guaranteed-unique-Name (doc.getBookmarks() is a
    # real XNameAccess, confirmed live), so bookmark_name IS the handle
    # directly -- no ObjectRegistry, same category as sheets/Writer
    # tables per docs/OBJECT_HANDLE_DESIGN.md. Fields, hyperlink text
    # ranges, and document indexes have no natural unique name and go
    # through the same ObjectRegistry drawing_objects.py established.
    #
    # set_chapter_numbering_live has no bridge method and stays
    # status="stub" -- live-verified ChapterNumberingRules.replaceByIndex()
    # raises a bare IllegalArgumentException (no message) even passing
    # back the *exact unmodified* PropertyValue sequence getByIndex()
    # itself returned, across several variants tried (minimal property
    # subset, single-property-at-a-time isolation, explicit uno.Any
    # sequence typing). get_chapter_numbering_live (read-only) IS real.
    # Same honest-scope-limit precedent as insert_embedded_object_live --
    # a genuinely resistant write-side API, not a shortcut (add_chart_
    # series_live/add_animation_live/create_external_link_live have all
    # since gone real).

    def _writer_page_style_family(self, doc: Any) -> Any:
        self._require_writer(doc, "page style resolution")
        return self._get_style_family(doc, "PageStyles")

    def _active_page_style_name(self, doc: Any) -> str:
        """The view cursor's PageStyleName reflects the real,
        currently-rendered page style -- unlike a plain text cursor's
        PageDescName, which is empty/None unless a paragraph explicitly
        overrides it (live-verified: a fresh document's first paragraph
        has PageDescName None despite genuinely being on "Standard")."""
        return self._get_controller(doc).getViewCursor().PageStyleName

    def _resolve_page_style(self, doc: Any, page_style: Optional[str] = None) -> "tuple[Any, str]":
        family = self._writer_page_style_family(doc)
        name = page_style or self._active_page_style_name(doc)
        if not family.hasByName(name):
            raise KeyError(f"No such page style '{name}'.")
        return family.getByName(name), name

    _WRITER_PAGE_LAYOUT_PROPS = (
        "Width", "Height", "IsLandscape", "LeftMargin", "RightMargin", "TopMargin", "BottomMargin",
        "GutterMargin", "HeaderIsOn", "FooterIsOn", "HeaderHeight", "FooterHeight",
    )

    def get_page_layout(self, doc: Any, page_style: Optional[str] = None) -> Dict[str, Any]:
        style, name = self._resolve_page_style(doc, page_style)
        result: Dict[str, Any] = {"page_style": name}
        for prop_name in self._WRITER_PAGE_LAYOUT_PROPS:
            try:
                result[prop_name] = self._uno_value_to_plain(style.getPropertyValue(prop_name))
            except Exception:
                continue
        columns = style.TextColumns
        result["column_count"] = columns.ColumnCount
        return result

    # BUG #1 fix (live-verified): the enum type is com.sun.star.style.
    # PageStyleLayout, not com.sun.star.text.PageStyleLayout -- the wrong
    # namespace is exactly why the old uno.Enum("com.sun.star.text.
    # PageStyleLayout", ...) call raised "enum com.sun.star.text.
    # PageStyleLayout is unknown" (a real type of that name simply doesn't
    # exist), not the member-name issue the original report guessed at.
    # Read back live off a real running document rather than trusted from
    # the report or set_mirror.py's own comment (which had LEFT/RIGHT
    # swapped): ALL=0, LEFT=1, RIGHT=2, MIRRORED=3. Assigning the raw int
    # sidesteps constructing a uno.Enum by name entirely -- setPropertyValue
    # auto-converts an int to the enum type, the same mechanism set_mirror.py's
    # workaround and update_page_style_live's raw-int path already rely on.
    _PAGE_STYLE_LAYOUT_ALL = 0
    _PAGE_STYLE_LAYOUT_MIRRORED = 3

    def set_page_layout(self, doc: Any, width: float, height: float, unit: str, orientation: Optional[str] = None,
                         margins: Optional[Dict[str, Any]] = None, mirrored: Optional[bool] = None,
                         gutter: Optional[float] = None, page_style: Optional[str] = None) -> List[str]:
        style, _ = self._resolve_page_style(doc, page_style)
        factor = self._LENGTH_UNIT_TO_MM100.get(unit.lower(), 1)
        applied = ["width", "height"]
        style.Width = int(width * factor)
        style.Height = int(height * factor)
        if orientation is not None:
            style.IsLandscape = str(orientation).lower() == "landscape"
            applied.append("orientation")
        if margins:
            margin_props = {"left": "LeftMargin", "right": "RightMargin", "top": "TopMargin", "bottom": "BottomMargin"}
            for key, prop_name in margin_props.items():
                if key in margins:
                    setattr(style, prop_name, int(margins[key] * factor))
                    applied.append(f"margins.{key}")
        if mirrored is not None:
            style.PageStyleLayout = self._PAGE_STYLE_LAYOUT_MIRRORED if mirrored else self._PAGE_STYLE_LAYOUT_ALL
            applied.append("mirrored")
        if gutter is not None:
            style.GutterMargin = int(gutter * factor)
            applied.append("gutter")
        return applied

    # Trim sizes only -- objectively verifiable industry-standard
    # dimensions, not genre-specific margin/typography conventions
    # (e.g. "screenplay"/"manuscript" formatting is real but disputed
    # across style guides; not guessed at rather than shipping an
    # unverified convention as if authoritative).
    _PAGE_PRESETS = {
        "letter": (8.5, 11.0, "in"), "a4": (210.0, 297.0, "mm"), "a5": (148.0, 210.0, "mm"),
        "legal": (8.5, 14.0, "in"), "novel_6x9": (6.0, 9.0, "in"), "digest_5.5x8.5": (5.5, 8.5, "in"),
    }

    def apply_page_preset(self, doc: Any, preset: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        dims = self._PAGE_PRESETS.get(preset.lower())
        if dims is None:
            raise ValueError(f"Unknown preset '{preset}'. Supported: {sorted(self._PAGE_PRESETS)}")
        width, height, unit = dims
        overrides = dict(overrides or {})
        kwargs = {"width": overrides.pop("width", width), "height": overrides.pop("height", height),
                  "unit": overrides.pop("unit", unit)}
        for key in ("orientation", "margins", "mirrored", "gutter", "page_style"):
            if key in overrides:
                kwargs[key] = overrides.pop(key)
        applied = self.set_page_layout(doc, **kwargs)
        return {"preset": preset, "applied": applied}

    def list_page_styles(self, doc: Any) -> List[Dict[str, Any]]:
        family = self._writer_page_style_family(doc)
        return [{"name": n, "in_use": family.getByName(n).isInUse()} for n in family.getElementNames()]

    def create_page_style(self, doc: Any, style_name: str, based_on: Optional[str] = None,
                           properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        family = self._writer_page_style_family(doc)
        if family.hasByName(style_name):
            raise ValueError(f"Page style '{style_name}' already exists.")
        new_style = doc.createInstance("com.sun.star.style.PageStyle")
        family.insertByName(style_name, new_style)
        if based_on:
            if not family.hasByName(based_on):
                raise KeyError(f"No such page style '{based_on}' to base on.")
            source = family.getByName(based_on)
            info = source.getPropertySetInfo()
            for prop in info.getProperties():
                try:
                    if not (prop.Attributes & 1 << 5):  # READONLY bit
                        new_style.setPropertyValue(prop.Name, source.getPropertyValue(prop.Name))
                except Exception:
                    continue
        applied = self._apply_direct_properties(new_style, properties) if properties else []
        return {"style_name": style_name, "applied": applied}

    def update_page_style(self, doc: Any, style_name: str, properties: Dict[str, Any]) -> List[str]:
        family = self._writer_page_style_family(doc)
        if not family.hasByName(style_name):
            raise KeyError(f"No such page style '{style_name}'.")
        return self._apply_direct_properties(family.getByName(style_name), properties)

    def apply_page_style(self, doc: Any, style_name: str, paragraph: Optional[int] = None,
                          insert_break: bool = False) -> Dict[str, Any]:
        """Setting a paragraph's own PageDescName is how Writer marks
        "this paragraph starts a new page with this style" -- live-
        verified this alone is sufficient to change the page style from
        that paragraph forward; `insert_break` additionally sets
        BreakType=PAGE_BEFORE for a caller that wants the explicit
        page-break semantics rather than just a style-region change.

        BUG #5-class fix (found auditing the durable-guidance writeup,
        same mechanism as insert_paragraph()/insert_page_break(), never
        triggered in the original typeset-run repro): omitted `paragraph`
        resolves through the VIEW cursor via _current_paragraph_index(doc),
        but nothing in this method ever moves that cursor -- so two
        batched, position-omitted calls in a row would resolve the
        identical paragraph both times instead of advancing. Fixed the
        same way: resync the view cursor to the paragraph just styled,
        best-effort (never fails an otherwise-successful apply)."""
        family = self._writer_page_style_family(doc)
        if not family.hasByName(style_name):
            raise KeyError(f"No such page style '{style_name}'.")
        n = paragraph if paragraph is not None else self._current_paragraph_index(doc)
        para = self._get_paragraph_object(doc, n)
        para.PageDescName = style_name
        if insert_break:
            para.BreakType = uno.Enum("com.sun.star.style.BreakType", "PAGE_BEFORE")
        try:
            self._get_controller(doc).getViewCursor().gotoRange(para.getStart(), False)
        except Exception:
            pass  # best-effort -- see BUG #5-class fix note above
        return {"paragraph": n, "style_name": style_name}

    def set_page_columns(self, doc: Any, count: int, spacing: Optional[float] = None,
                          widths: Optional[List[float]] = None, separator: Optional[str] = None,
                          page_style: Optional[str] = None) -> None:
        """`widths` (1/100mm each) -- if given, builds explicit unequal
        TextColumn entries via setColumns(); otherwise setColumnCount()
        for evenly-spaced columns (the common case). `spacing` (1/100mm)
        maps to ReferenceValue-relative AutomaticDistance when using
        setColumnCount -- live-verified separately via the equal-width
        path only; the explicit-widths path's own spacing between
        columns is expressed as gaps baked into each TextColumn's own
        Width, not a separate spacing property."""
        style, _ = self._resolve_page_style(doc, page_style)
        columns = style.TextColumns
        if widths:
            entries = []
            for w in widths:
                col = uno.createUnoStruct("com.sun.star.text.TextColumn")
                col.Width = int(w)
                entries.append(col)
            columns.setColumns(tuple(entries))
        else:
            columns.setColumnCount(int(count))
            if spacing is not None:
                columns.AutomaticDistance = int(spacing)
        if separator is not None:
            columns.SeparatorLineIsOn = str(separator).lower() not in ("none", "", "off")
        style.TextColumns = columns

    def insert_page_break(self, doc: Any, at_position: Optional[int] = None, page_style: Optional[str] = None,
                           page_number: Optional[int] = None) -> Dict[str, Any]:
        """Splits the target paragraph at its start (matching split_
        paragraph's own insertControlCharacter(PARAGRAPH_BREAK) idiom),
        then marks the resulting new paragraph BreakType=PAGE_BEFORE
        (+PageDescName/PageNumberOffset if given).

        BUG #5 fix: same view-cursor resync as insert_paragraph() -- see
        its docstring. at_position=None resolves through the view cursor
        but the actual edit uses a separate text cursor that never moves
        it, so this is batch-unsafe the same way insert_heading() was."""
        self._require_writer(doc, "insert_page_break")
        n = at_position if at_position is not None else self._current_paragraph_index(doc)
        anchor_para = self._get_paragraph_object(doc, n)
        text_obj = doc.getText()
        cursor = text_obj.createTextCursorByRange(anchor_para.getStart())
        text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)
        try:
            self._get_controller(doc).getViewCursor().gotoRange(cursor, False)
        except Exception:
            pass  # best-effort -- see BUG #5 fix note above
        new_para = self._get_paragraph_object(doc, n + 1)
        new_para.BreakType = uno.Enum("com.sun.star.style.BreakType", "PAGE_BEFORE")
        if page_style is not None:
            new_para.PageDescName = page_style
        if page_number is not None:
            new_para.PageNumberOffset = int(page_number)
        return {"paragraph": n + 1, "page_style": page_style}

    def remove_page_break(self, doc: Any, paragraph: Optional[int] = None, position: Optional[int] = None) -> Dict[str, Any]:
        """PageDescName is cleared with "" (empty string), not None --
        live-verified None raises "Type 0 is not supported!" (the
        property is string-typed; None isn't a legal UNO string value),
        while "" is accepted and reads back as the same None/unset state
        insert_page_break's own untouched paragraphs start in.

        BUG #5-class fix (same finding as apply_page_style() above): a
        batched, position-omitted call resolved through the stale view
        cursor with nothing to advance it. Resynced the same way,
        best-effort."""
        n = paragraph if paragraph is not None else (position if position is not None else self._current_paragraph_index(doc))
        para = self._get_paragraph_object(doc, n)
        para.BreakType = uno.Enum("com.sun.star.style.BreakType", "NONE")
        para.PageDescName = ""
        try:
            self._get_controller(doc).getViewCursor().gotoRange(para.getStart(), False)
        except Exception:
            pass  # best-effort -- see BUG #5-class fix note above
        return {"paragraph": n}

    _HEADER_FOOTER_TEXT_PROPS = {
        "default": ("HeaderText", "FooterText"), "left": ("HeaderTextLeft", "FooterTextLeft"),
        "first": ("HeaderTextFirst", "FooterTextFirst"),
    }

    def get_headers_footers(self, doc: Any, page_style: Optional[str] = None) -> Dict[str, Any]:
        style, name = self._resolve_page_style(doc, page_style)
        result: Dict[str, Any] = {"page_style": name, "header_on": bool(style.HeaderIsOn), "footer_on": bool(style.FooterIsOn)}
        for variant, (header_prop, footer_prop) in self._HEADER_FOOTER_TEXT_PROPS.items():
            try:
                result[f"header_{variant}"] = style.getPropertyValue(header_prop).getString()
            except Exception:
                result[f"header_{variant}"] = None
            try:
                result[f"footer_{variant}"] = style.getPropertyValue(footer_prop).getString()
            except Exception:
                result[f"footer_{variant}"] = None
        return result

    def set_header(self, doc: Any, text: str, page_style: Optional[str] = None, variant: str = "default",
                   properties: Optional[Dict[str, Any]] = None) -> List[str]:
        header_prop, _ = self._HEADER_FOOTER_TEXT_PROPS.get(variant, (None, None))
        if header_prop is None:
            raise ValueError(f"Unknown variant '{variant}'. Supported: {sorted(self._HEADER_FOOTER_TEXT_PROPS)}")
        style, _ = self._resolve_page_style(doc, page_style)
        style.HeaderIsOn = True
        style.getPropertyValue(header_prop).setString(text)
        applied = ["text"]
        if properties:
            applied.extend(self._apply_direct_properties(style, properties))
        return applied

    def set_footer(self, doc: Any, text: str, page_style: Optional[str] = None, variant: str = "default",
                   properties: Optional[Dict[str, Any]] = None) -> List[str]:
        _, footer_prop = self._HEADER_FOOTER_TEXT_PROPS.get(variant, (None, None))
        if footer_prop is None:
            raise ValueError(f"Unknown variant '{variant}'. Supported: {sorted(self._HEADER_FOOTER_TEXT_PROPS)}")
        style, _ = self._resolve_page_style(doc, page_style)
        style.FooterIsOn = True
        style.getPropertyValue(footer_prop).setString(text)
        applied = ["text"]
        if properties:
            applied.extend(self._apply_direct_properties(style, properties))
        return applied

    def clear_header(self, doc: Any, page_style: Optional[str] = None, variant: Optional[str] = None) -> None:
        header_prop, _ = self._HEADER_FOOTER_TEXT_PROPS.get(variant or "default", (None, None))
        if header_prop is None:
            raise ValueError(f"Unknown variant '{variant}'. Supported: {sorted(self._HEADER_FOOTER_TEXT_PROPS)}")
        style, _ = self._resolve_page_style(doc, page_style)
        style.getPropertyValue(header_prop).setString("")
        style.HeaderIsOn = False

    def clear_footer(self, doc: Any, page_style: Optional[str] = None, variant: Optional[str] = None) -> None:
        _, footer_prop = self._HEADER_FOOTER_TEXT_PROPS.get(variant or "default", (None, None))
        if footer_prop is None:
            raise ValueError(f"Unknown variant '{variant}'. Supported: {sorted(self._HEADER_FOOTER_TEXT_PROPS)}")
        style, _ = self._resolve_page_style(doc, page_style)
        style.getPropertyValue(footer_prop).setString("")
        style.FooterIsOn = False

    def _resolve_field_insertion_point(self, doc: Any, target: Optional[str]) -> Any:
        """`target`: None/"cursor" -> current view cursor position;
        "header"/"footer" -> that (default-variant) text object on the
        active page style, live-verified header/footer must already be
        enabled (HeaderIsOn/FooterIsOn) for their text object to be a
        real insertion point."""
        if target in (None, "cursor"):
            return self._get_controller(doc).getViewCursor()
        style, _ = self._resolve_page_style(doc, None)
        if target == "header":
            if not style.HeaderIsOn:
                raise ValueError("Header is not enabled on the active page style -- call set_header_live first.")
            header_text = style.HeaderText
            cursor = header_text.createTextCursor()
            cursor.gotoEnd(False)
            return cursor
        if target == "footer":
            if not style.FooterIsOn:
                raise ValueError("Footer is not enabled on the active page style -- call set_footer_live first.")
            footer_text = style.FooterText
            cursor = footer_text.createTextCursor()
            cursor.gotoEnd(False)
            return cursor
        raise ValueError(f"Unknown target '{target}'. Supported: cursor, header, footer.")

    _PAGE_NUMBER_FORMAT_MAP = {"arabic": "ARABIC", "roman_upper": "ROMAN_UPPER", "roman_lower": "ROMAN_LOWER",
                               "alpha_upper": "CHAR_UPPER_LETTER", "alpha_lower": "CHAR_LOWER_LETTER"}

    def _resolve_page_number_numbering_type(self, format: Optional[str]) -> int:
        """PageNumber/PageCount fields do NOT default to Arabic numbering --
        live-verified a freshly created field left at its own UNO default
        renders page 2 as "B" (alphabetic), not "2". Always set
        NumberingType explicitly; ARABIC is the default when `format` is
        omitted since that's what every caller expects "insert a page
        number" to mean."""
        name = self._PAGE_NUMBER_FORMAT_MAP.get(format, "ARABIC" if format is None else None)
        if name is None:
            raise ValueError(f"Unknown page number format '{format}'. Supported: "
                              f"{', '.join(self._PAGE_NUMBER_FORMAT_MAP)}.")
        return uno.getConstantByName(f"com.sun.star.style.NumberingType.{name}")

    def insert_page_number_field(self, doc: Any, target: Optional[str] = None, format: Optional[str] = None,
                                  offset: int = 0) -> Dict[str, Any]:
        self._require_writer(doc, "insert_page_number_field")
        cursor = self._resolve_field_insertion_point(doc, target)
        field = doc.createInstance("com.sun.star.text.TextField.PageNumber")
        field.NumberingType = self._resolve_page_number_numbering_type(format)
        if offset:
            field.SubType = uno.Enum("com.sun.star.text.PageNumberType", "CURRENT")
            field.Offset = int(offset)
        cursor.getText().insertTextContent(cursor, field, False)
        return {"target": target or "cursor"}

    def insert_page_count_field(self, doc: Any, target: Optional[str] = None, format: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "insert_page_count_field")
        cursor = self._resolve_field_insertion_point(doc, target)
        field = doc.createInstance("com.sun.star.text.TextField.PageCount")
        field.NumberingType = self._resolve_page_number_numbering_type(format)
        cursor.getText().insertTextContent(cursor, field, False)
        return {"target": target or "cursor"}

    def insert_date_time_field(self, doc: Any, target: Optional[str] = None, fixed: bool = False,
                                format: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "insert_date_time_field")
        cursor = self._resolve_field_insertion_point(doc, target)
        field = doc.createInstance("com.sun.star.text.TextField.DateTime")
        field.IsFixed = bool(fixed)
        field.IsDate = True
        cursor.getText().insertTextContent(cursor, field, False)
        return {"target": target or "cursor", "fixed": fixed}

    _DOC_PROPERTY_FIELD_SERVICES = {
        "author": "com.sun.star.text.TextField.Author",
        "title": "com.sun.star.text.TextField.DocInfo.Title",
        "subject": "com.sun.star.text.TextField.DocInfo.Subject",
        "keywords": "com.sun.star.text.TextField.DocInfo.Keywords",
        "description": "com.sun.star.text.TextField.DocInfo.Description",
        "comments": "com.sun.star.text.TextField.DocInfo.Description",
        "created": "com.sun.star.text.TextField.DocInfo.CreateDateTime",
        "modified": "com.sun.star.text.TextField.DocInfo.ChangeDateTime",
    }

    def insert_document_property_field(self, doc: Any, property_name: str, target: Optional[str] = None,
                                        fixed: bool = False) -> Dict[str, Any]:
        """Standard document-info properties only (author/title/subject/
        keywords/description/created/modified) -- a truly custom
        (user-defined) document property field needs
        "com.sun.star.text.TextField.DocInfo.Custom" plus a Name
        parameter this tool's own spec schema doesn't expose, so it's
        not attempted here."""
        self._require_writer(doc, "insert_document_property_field")
        service_name = self._DOC_PROPERTY_FIELD_SERVICES.get(property_name.lower())
        if service_name is None:
            raise NotImplementedError(
                f"insert_document_property_field_live property_name='{property_name}' is not implemented this "
                f"pass -- supported: {sorted(self._DOC_PROPERTY_FIELD_SERVICES)}."
            )
        cursor = self._resolve_field_insertion_point(doc, target)
        field = doc.createInstance(service_name)
        if hasattr(field, "IsFixed"):
            field.IsFixed = bool(fixed)
        cursor.getText().insertTextContent(cursor, field, False)
        return {"property_name": property_name, "target": target or "cursor"}

    _FIELD_TYPE_SERVICES = {
        "page_number": "com.sun.star.text.TextField.PageNumber", "page_count": "com.sun.star.text.TextField.PageCount",
        "date_time": "com.sun.star.text.TextField.DateTime", "author": "com.sun.star.text.TextField.Author",
        "cross_reference": "com.sun.star.text.TextField.GetReference", "caption": "com.sun.star.text.TextField.SetExpression",
    }

    def list_fields(self, doc: Any, field_type: Optional[str] = None) -> List[Any]:
        """Returns raw field objects for the tools/ layer to register --
        same ObjectRegistry split drawing_objects.py established."""
        self._require_writer(doc, "list_fields")
        wanted_service = self._FIELD_TYPE_SERVICES.get(field_type) if field_type else None
        fields_enum = doc.getTextFields().createEnumeration()
        result = []
        while fields_enum.hasMoreElements():
            field = fields_enum.nextElement()
            if wanted_service is not None and not field.supportsService(wanted_service):
                continue
            result.append(field)
        return result

    @staticmethod
    def get_field_summary(field: Any, field_id: str) -> Dict[str, Any]:
        try:
            text = field.getPresentation(False)
        except Exception:
            text = None
        return {"field_id": field_id, "type": field.getSupportedServiceNames()[0] if hasattr(field, "getSupportedServiceNames") else None, "text": text}

    def update_fields(self, doc: Any, field_ids: Optional[List[Any]] = None) -> int:
        """field_ids, when given, are already-resolved field objects
        (the tools/ layer resolves each id through ObjectRegistry before
        calling this) -- when omitted, refreshes every field in the
        document."""
        targets = field_ids if field_ids is not None else self.list_fields(doc)
        for field in targets:
            try:
                field.update()
            except Exception:
                continue
        return len(targets)

    def delete_field(self, field: Any, keep_text: bool = True) -> None:
        """`field` is the already-resolved field object. keep_text
        replaces the field with its current presentation text in place;
        otherwise the field (and its presentation) is simply removed."""
        if keep_text:
            presentation = field.getPresentation(False)
            anchor = field.getAnchor()
            text_obj = anchor.getText()
            cursor = text_obj.createTextCursorByRange(anchor)
            field.dispose()
            text_obj.insertString(cursor, presentation, False)
        else:
            field.dispose()

    def list_bookmarks(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_writer(doc, "list_bookmarks")
        bookmarks = doc.getBookmarks()
        result = []
        for name in bookmarks.getElementNames():
            bm = bookmarks.getByName(name)
            result.append({"name": name, "text": bm.getAnchor().getString()})
        return result

    def add_bookmark(self, doc: Any, name: str, start: Optional[int] = None, end: Optional[int] = None) -> Dict[str, Any]:
        """`start`/`end` are plain-text character offsets from document
        start (matching writer_text.py's own select_text_range_live
        convention) -- omitted means the current selection/cursor."""
        self._require_writer(doc, "add_bookmark")
        text_obj = doc.getText()
        if start is not None:
            cursor = text_obj.createTextCursor()
            cursor.gotoStart(False)
            cursor.goRight(int(start), False)
            if end is not None:
                cursor.goRight(int(end) - int(start), True)
        else:
            cursor = self._get_controller(doc).getViewCursor()
        bookmark = doc.createInstance("com.sun.star.text.Bookmark")
        bookmark.setName(name)
        text_obj.insertTextContent(cursor, bookmark, start is not None and end is not None)
        return {"name": name}

    def goto_bookmark(self, doc: Any, name: str, select: bool = False) -> Dict[str, Any]:
        bookmarks = doc.getBookmarks()
        if not bookmarks.hasByName(name):
            raise KeyError(f"No such bookmark '{name}'.")
        anchor = bookmarks.getByName(name).getAnchor()
        view_cursor = self._get_controller(doc).getViewCursor()
        if select:
            view_cursor.gotoRange(anchor.getStart(), False)
            view_cursor.gotoRange(anchor.getEnd(), True)
        else:
            view_cursor.gotoRange(anchor.getStart(), False)
        return {"name": name}

    def rename_bookmark(self, doc: Any, old_name: str, new_name: str) -> None:
        bookmarks = doc.getBookmarks()
        if not bookmarks.hasByName(old_name):
            raise KeyError(f"No such bookmark '{old_name}'.")
        bookmarks.getByName(old_name).setName(new_name)

    def delete_bookmark(self, doc: Any, name: str) -> None:
        bookmarks = doc.getBookmarks()
        if not bookmarks.hasByName(name):
            raise KeyError(f"No such bookmark '{name}'.")
        bookmarks.getByName(name).dispose()

    def insert_hyperlink(self, doc: Any, url: str, text: Optional[str] = None, target: Optional[str] = None,
                          name: Optional[str] = None) -> Any:
        """Returns the raw selecting text range (an XTextCursor snapshot
        of the just-inserted/just-selected text) for the tools/ layer to
        register as the hyperlink's handle.

        Two failed approaches, live-verified against a real running
        server, before landing on this one:
        - Setting HyperLinkURL on a COLLAPSED cursor positioned *before*
          inserting the display text does NOT apply to the inserted text.
        - "Insert with bAbsorb=False, then re-select the range with a
          second cursor snapshotted before the insert" also does NOT
          work: a plain cursor captured at the same offset as the
          insertion point tracks the edit and moves forward right along
          with it, so the two cursors end up coincident and the
          "selection" collapses to zero width -- setPropertyValue then
          silently no-ops on an empty range instead of raising.
        The fix: insertString(cursor, text, bAbsorb=True) on a cursor
        that already sits at the insertion point. bAbsorb=True makes the
        cursor itself become the selection spanning exactly the text it
        just inserted, so HyperLinkURL applies to the right range."""
        self._require_writer(doc, "insert_hyperlink")
        text_obj = doc.getText()
        view_cursor = self._get_controller(doc).getViewCursor()
        if text is not None:
            cursor = text_obj.createTextCursorByRange(view_cursor.getStart())
            text_obj.insertString(cursor, text, True)
        elif view_cursor.isCollapsed():
            cursor = text_obj.createTextCursorByRange(view_cursor.getStart())
            text_obj.insertString(cursor, url, True)
        else:
            cursor = text_obj.createTextCursorByRange(view_cursor)
        cursor.setPropertyValue("HyperLinkURL", url)
        if target is not None:
            cursor.setPropertyValue("HyperLinkTarget", target)
        if name is not None:
            cursor.setPropertyValue("HyperLinkName", name)
        return cursor

    def list_hyperlinks(self, doc: Any) -> List[Any]:
        """Returns raw text-range objects (one per contiguous hyperlinked
        text portion) for the tools/ layer to register."""
        self._require_writer(doc, "list_hyperlinks")
        result = []
        para_enum = doc.getText().createEnumeration()
        while para_enum.hasMoreElements():
            para = para_enum.nextElement()
            if not (hasattr(para, "supportsService") and para.supportsService("com.sun.star.text.Paragraph")):
                continue
            portion_enum = para.createEnumeration()
            while portion_enum.hasMoreElements():
                portion = portion_enum.nextElement()
                if getattr(portion, "HyperLinkURL", ""):
                    result.append(portion)
        return result

    @staticmethod
    def get_hyperlink_summary(range_obj: Any, hyperlink_id: str) -> Dict[str, Any]:
        return {"hyperlink_id": hyperlink_id, "url": range_obj.HyperLinkURL, "text": range_obj.getString()}

    def update_hyperlink(self, range_obj: Any, url: Optional[str] = None, text: Optional[str] = None) -> List[str]:
        applied = []
        if text is not None:
            range_obj.setString(text)
            applied.append("text")
        if url is not None:
            range_obj.setPropertyValue("HyperLinkURL", url)
            applied.append("url")
        return applied

    def remove_hyperlink(self, range_obj: Any) -> None:
        range_obj.setPropertyValue("HyperLinkURL", "")

    _REFERENCE_TYPE_MAP = {
        "bookmark": ("BOOKMARK", "TEXT"), "heading": ("BOOKMARK", "TEXT"),
        "page": ("BOOKMARK", "PAGE"), "caption": ("SEQUENCE_FIELD", "ONLY_CAPTION"),
        "caption_number": ("SEQUENCE_FIELD", "ONLY_SEQUENCE_NUMBER"),
        "caption_full": ("SEQUENCE_FIELD", "CATEGORY_AND_NUMBER"),
    }

    def insert_cross_reference(self, doc: Any, reference_type: str, target: str, display: str) -> Dict[str, Any]:
        """`target` is a bookmark name (reference_type in
        bookmark/heading/page) or a caption category's sequence name
        (reference_type in caption/caption_number/caption_full, e.g.
        "Figure"/"Table" -- the caption's own VariableName). `display`
        selects which ReferenceFieldPart to show -- only the mappings
        in _REFERENCE_TYPE_MAP were live-verified this pass (bookmark-
        sourced text/page references, and the three caption-sourced
        SEQUENCE_FIELD display parts); the full ReferenceFieldPart table
        (UP_DOWN, PAGE_DESC, CHAPTER, NUMBER_NO_CONTEXT, etc.) wasn't
        exhaustively mapped. ReferenceFieldSource/ReferenceFieldPart are
        plain SHORT-typed properties, NOT real UNO enums -- live-verified
        via getPropertySetInfo() that both report TypeClass SHORT, so
        uno.Enum(...) raises "enum ... is unknown" even for a legal
        constant name. Must resolve through uno.getConstantByName()
        against the com.sun.star.text.ReferenceFieldSource/
        ReferenceFieldPart constant groups instead, same mechanism
        insert_caption already uses for NumberingType/SetVariableType."""
        self._require_writer(doc, "insert_cross_reference")
        key = f"{reference_type.lower()}"
        mapping = self._REFERENCE_TYPE_MAP.get(key)
        if mapping is None:
            raise NotImplementedError(
                f"insert_cross_reference_live reference_type='{reference_type}' is not implemented this pass -- "
                f"supported: {sorted(self._REFERENCE_TYPE_MAP)}."
            )
        source_name, default_part = mapping
        part = display.upper() if display else default_part
        field = doc.createInstance("com.sun.star.text.TextField.GetReference")
        field.ReferenceFieldSource = uno.getConstantByName(f"com.sun.star.text.ReferenceFieldSource.{source_name}")
        field.ReferenceFieldPart = uno.getConstantByName(f"com.sun.star.text.ReferenceFieldPart.{part}")
        field.SourceName = target
        view_cursor = self._get_controller(doc).getViewCursor()
        doc.getText().insertTextContent(view_cursor, field, False)
        return {"reference_type": reference_type, "target": target}

    _CAPTION_CATEGORIES = {"figure": "Figure", "table": "Table", "illustration": "Illustration",
                            "drawing": "Drawing", "text": "Text"}

    def insert_caption(self, doc: Any, target_id: Any, label: str = "Figure", text: Optional[str] = None,
                        position: str = "below") -> Dict[str, Any]:
        """`target_id` is an already-resolved shape object (the tools/
        layer resolves it through ObjectRegistry before calling this).
        Captions use a real com.sun.star.text.TextField.SetExpression
        field in SEQUENCE subtype, attached to one of Writer's 5
        pre-existing category field masters (Illustration/Table/Text/
        Drawing/Figure) -- live-verified VariableName itself is
        read-only on the field and must be set by attaching the
        matching master instead, not directly."""
        self._require_writer(doc, "insert_caption")
        category = self._CAPTION_CATEGORIES.get(label.lower(), label)
        master_name = f"com.sun.star.text.fieldmaster.SetExpression.{category}"
        masters = doc.getTextFieldMasters()
        if masters.hasByName(master_name):
            master = masters.getByName(master_name)
        else:
            master = doc.createInstance("com.sun.star.text.fieldmaster.SetExpression")
            master.Name = category
            master.SubType = uno.getConstantByName("com.sun.star.text.SetVariableType.SEQUENCE")

        anchor = target_id.getAnchor() if hasattr(target_id, "getAnchor") else target_id
        text_obj = anchor.getText() if hasattr(anchor, "getText") else doc.getText()
        cursor = text_obj.createTextCursorByRange(anchor.getEnd() if hasattr(anchor, "getEnd") else anchor)
        if position == "below":
            text_obj.insertControlCharacter(cursor, PARAGRAPH_BREAK, False)

        field = doc.createInstance("com.sun.star.text.TextField.SetExpression")
        field.attachTextFieldMaster(master)
        field.SubType = uno.getConstantByName("com.sun.star.text.SetVariableType.SEQUENCE")
        field.NumberingType = uno.getConstantByName("com.sun.star.style.NumberingType.ARABIC")
        text_obj.insertString(cursor, f"{category} ", False)
        text_obj.insertTextContent(cursor, field, False)
        if text:
            text_obj.insertString(cursor, f": {text}", False)
        return {"category": category, "position": position}

    def list_document_indexes(self, doc: Any) -> List[Any]:
        """Returns raw index objects (ContentIndex/DocumentIndex/etc.)
        for the tools/ layer to register -- same "may mint a fresh id
        on repeat list calls for the same underlying index" caveat
        calc_data.py's pivot tables carry, not independently re-verified
        for this object type this pass; see tools/writer_layout.py's
        module docstring."""
        self._require_writer(doc, "list_document_indexes")
        indexes = doc.getDocumentIndexes()
        return [indexes.getByIndex(i) for i in builtins.range(indexes.getCount())]

    @staticmethod
    def get_index_summary(index: Any, index_id: str) -> Dict[str, Any]:
        return {
            "index_id": index_id, "title": getattr(index, "Title", None),
            "type": index.getServiceName() if hasattr(index, "getServiceName") else None,
        }

    def insert_toc(self, doc: Any, at_position: Optional[int] = None, title: Optional[str] = None,
                    max_level: int = 10, options: Optional[Dict[str, Any]] = None) -> Any:
        self._require_writer(doc, "insert_toc")
        toc = doc.createInstance("com.sun.star.text.ContentIndex")
        toc.CreateFromOutline = True
        toc.Level = int(max_level)
        if title is not None:
            toc.Title = title
        if options:
            self._apply_direct_properties(toc, options)
        if at_position is not None:
            para = self._get_paragraph_object(doc, at_position)
            cursor = doc.getText().createTextCursorByRange(para.getStart())
        else:
            cursor = self._get_controller(doc).getViewCursor()
        doc.getText().insertTextContent(cursor, toc, False)
        toc.update()
        return toc

    def update_index(self, index: Any) -> None:
        index.update()

    def delete_index(self, doc: Any, index: Any, keep_content: bool = False) -> None:
        """keep_content isn't attempted -- disposing a TOC/index removes
        its generated entries along with the index object itself
        (there's no separate "convert generated entries to plain text"
        step exploration-tested this pass); the parameter is accepted
        but the content is always removed, matching what dispose()
        actually does."""
        index.dispose()

    def insert_alphabetical_index(self, doc: Any, at_position: Optional[int] = None, title: Optional[str] = None,
                                   options: Optional[Dict[str, Any]] = None) -> Any:
        self._require_writer(doc, "insert_alphabetical_index")
        index = doc.createInstance("com.sun.star.text.DocumentIndex")
        if title is not None:
            index.Title = title
        if options:
            self._apply_direct_properties(index, options)
        if at_position is not None:
            para = self._get_paragraph_object(doc, at_position)
            cursor = doc.getText().createTextCursorByRange(para.getStart())
        else:
            cursor = self._get_controller(doc).getViewCursor()
        doc.getText().insertTextContent(cursor, index, False)
        index.update()
        return index

    def add_index_mark(self, doc: Any, index_type: str, primary_key: Optional[str] = None,
                        secondary_key: Optional[str] = None) -> Dict[str, Any]:
        """`index_type` is accepted for spec-schema completeness but
        every index mark uses the same com.sun.star.text.
        DocumentIndexMark service this pass -- alphabetical-index marks
        are the only kind exploration-tested (table-of-contents/
        illustration entries are generated automatically from outline
        levels/captions instead of manual marks, so a separate mark type
        for those wasn't needed)."""
        self._require_writer(doc, "add_index_mark")
        mark = doc.createInstance("com.sun.star.text.DocumentIndexMark")
        if primary_key is not None:
            mark.PrimaryKey = primary_key
        if secondary_key is not None:
            mark.SecondaryKey = secondary_key
        view_cursor = self._get_controller(doc).getViewCursor()
        doc.getText().insertTextContent(view_cursor, mark, False)
        return {"index_type": index_type, "primary_key": primary_key}

    def get_chapter_numbering(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_writer(doc, "get_chapter_numbering")
        rules = doc.ChapterNumberingRules
        result = []
        for i in builtins.range(rules.Count):
            level_props = {p.Name: self._uno_value_to_plain(p.Value) for p in rules.getByIndex(i)}
            level_props["level"] = i + 1
            result.append(level_props)
        return result

    # set_chapter_numbering_live has no bridge method -- see this
    # section's own docstring above for why.

    def get_line_numbering(self, doc: Any) -> Dict[str, Any]:
        self._require_writer(doc, "get_line_numbering")
        lnp = doc.LineNumberingProperties
        return {
            "enabled": bool(lnp.IsOn), "interval": lnp.Interval, "restart_each_page": bool(lnp.RestartAtEachPage),
            "count_empty_lines": bool(lnp.CountEmptyLines), "distance": lnp.Distance,
        }

    def set_line_numbering(self, doc: Any, enabled: bool, interval: Optional[int] = None,
                            restart_each_page: Optional[bool] = None) -> List[str]:
        """`doc.LineNumberingProperties` is a live-linked reference, not a
        value-type struct snapshot -- live-verified mutating its fields
        (IsOn/Interval/RestartAtEachPage) applies immediately to the
        document with no write-back needed. Writing the whole property
        back afterward (`doc.LineNumberingProperties = lnp`) is not just
        redundant, it actively raises "property ... is readonly" --
        caught only because the exception happened to still report
        `enabled` as applied on a later get_line_numbering_live call,
        i.e. the previous version of this method reported failure on a
        call that had, in fact, already taken effect."""
        self._require_writer(doc, "set_line_numbering")
        lnp = doc.LineNumberingProperties
        lnp.IsOn = bool(enabled)
        applied = ["enabled"]
        if interval is not None:
            lnp.Interval = int(interval)
            applied.append("interval")
        if restart_each_page is not None:
            lnp.RestartAtEachPage = bool(restart_each_page)
            applied.append("restart_each_page")
        return applied

    # ------------------------------------------------------------------
    # writer_tables.py: tables, sections, notes, content controls, mail
    # merge. Tables/sections resolve through their own UNO-native unique
    # Name (`getTextTables()`/`getTextSections()` are both real
    # `XNameAccess` containers, confirmed live) -- no ObjectRegistry, same
    # category as bookmarks/Writer's own page styles per
    # docs/OBJECT_HANDLE_DESIGN.md. Footnotes/endnotes/content controls
    # have no natural unique name and resolve through ObjectRegistry --
    # live-verified a narrower version of calc_data.py's pivot-table
    # id-churn gap (same shape writer_layout.py's document indexes turned
    # out to have): two separate list_*_live fetches for the SAME object
    # return the SAME id (`doc.getFootnotes().getByIndex(0) == doc.
    # getFootnotes().getByIndex(0)` is True, confirmed for all three
    # categories), but the id an insert/add call itself returns does NOT
    # match a subsequent list_*_live's id for that same object. Every id
    # still works correctly for its own later get/update/delete call.
    # ------------------------------------------------------------------

    @staticmethod
    def _table_column_index_to_letters(index0: int) -> str:
        letters = ""
        n = index0 + 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    @staticmethod
    def _table_column_letters_to_index(letters: str) -> int:
        index = 0
        for ch in letters:
            index = index * 26 + (ord(ch.upper()) - 64)
        return index - 1

    _TABLE_CELL_NAME_RE = re.compile(r"^([A-Za-z]+)(\d+)$")

    def _parse_table_cell_name(self, name: str) -> Any:
        match = self._TABLE_CELL_NAME_RE.match(name.strip())
        if not match:
            raise ValueError(f"Invalid table cell name '{name}' -- expected e.g. 'A1'.")
        col = self._table_column_letters_to_index(match.group(1))
        row = int(match.group(2)) - 1
        return col, row

    def _resolve_table(self, doc: Any, table_id: str) -> Any:
        self._require_writer(doc, "_resolve_table")
        tables = doc.getTextTables()
        if not tables.hasByName(table_id):
            raise KeyError(f"No such table {table_id!r}.")
        return tables.getByName(table_id)

    def _resolve_char_range_string(self, doc: Any, range_string: Optional[str]) -> Any:
        """Not an established Writer convention elsewhere in this codebase
        (writer_text.py's/writer_layout.py's own range-shaped params are all
        {"start": int, "end": int} dicts, e.g. add_bookmark) --
        convert_text_to_table_live/insert_content_control_live are the
        only two tools in the whole catalog scaffolded with `range` as a
        bare string, with no format ever specified. Documented choice
        made this pass: "<start>-<end>", 0-based character offsets from
        document start, end exclusive -- same offsets add_bookmark
        already uses, just string-packed instead of dict-packed. None
        means use the current selection, consistent with
        _resolve_text_target()."""
        text_obj = doc.getText()
        if range_string is None:
            controller = self._get_controller(doc)
            selection = controller.getSelection()
            if selection is None or not hasattr(selection, "getCount") or selection.getCount() == 0:
                raise ValueError("No current selection and no range given.")
            return selection.getByIndex(0)
        match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", range_string)
        if not match:
            raise ValueError(f"Invalid range {range_string!r} -- expected <start>-<end> character offsets.")
        start, end = int(match.group(1)), int(match.group(2))
        cursor = text_obj.createTextCursor()
        cursor.gotoStart(False)
        cursor.goRight(start, False)
        cursor.goRight(end - start, True)
        return cursor

    def list_tables(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_writer(doc, "list_tables")
        tables = doc.getTextTables()
        return [
            {"table_id": name, "rows": tables.getByName(name).getRows().getCount(),
             "columns": tables.getByName(name).getColumns().getCount()}
            for name in tables.getElementNames()
        ]

    def insert_table(self, doc: Any, rows: int, columns: int, at_position: Optional[int] = None,
                      name: Optional[str] = None, style: Optional[str] = None) -> Dict[str, Any]:
        self._require_writer(doc, "insert_table")
        text_obj = doc.getText()
        if at_position is not None:
            cursor = text_obj.createTextCursorByRange(self._get_paragraph_object(doc, at_position).getStart())
        else:
            cursor = self._get_controller(doc).getViewCursor()
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(int(rows), int(columns))
        text_obj.insertTextContent(cursor, table, False)
        if name:
            table.setName(name)
        applied_style = self._apply_direct_properties(table, {"TableTemplateName": style}) if style else []
        return {
            "table_id": table.Name, "rows": table.getRows().getCount(),
            "columns": table.getColumns().getCount(), "style_applied": bool(applied_style),
        }

    def get_table(self, doc: Any, table_id: str, include_cells: bool = False) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        result = {
            "table_id": table_id, "rows": table.getRows().getCount(),
            "columns": table.getColumns().getCount(),
        }
        if include_cells:
            row_count, col_count = table.getRows().getCount(), table.getColumns().getCount()
            result["cells"] = [
                [table.getCellByPosition(c, r).getString() for c in builtins.range(col_count)]
                for r in builtins.range(row_count)
            ]
        return result

    def get_table_range(self, doc: Any, table_id: str, start_cell: str, end_cell: str) -> List[List[str]]:
        table = self._resolve_table(doc, table_id)
        start_col, start_row = self._parse_table_cell_name(start_cell)
        end_col, end_row = self._parse_table_cell_name(end_cell)
        lo_col, hi_col = builtins.min(start_col, end_col), builtins.max(start_col, end_col)
        lo_row, hi_row = builtins.min(start_row, end_row), builtins.max(start_row, end_row)
        return [
            [table.getCellByPosition(c, r).getString() for c in builtins.range(lo_col, hi_col + 1)]
            for r in builtins.range(lo_row, hi_row + 1)
        ]

    def set_table_range(self, doc: Any, table_id: str, start_cell: str, values: List[List[Any]]) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        start_col, start_row = self._parse_table_cell_name(start_cell)
        written = 0
        for r, row_values in enumerate(values):
            for c, value in enumerate(row_values):
                table.getCellByPosition(start_col + c, start_row + r).setString(str(value))
                written += 1
        return {"written": written}

    def insert_table_rows(self, doc: Any, table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        table.getRows().insertByIndex(int(index), int(count))
        return {"rows": table.getRows().getCount()}

    def delete_table_rows(self, doc: Any, table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        table.getRows().removeByIndex(int(index), int(count))
        return {"rows": table.getRows().getCount()}

    def insert_table_columns(self, doc: Any, table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        table.getColumns().insertByIndex(int(index), int(count))
        return {"columns": table.getColumns().getCount()}

    def delete_table_columns(self, doc: Any, table_id: str, index: int, count: int = 1) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        table.getColumns().removeByIndex(int(index), int(count))
        return {"columns": table.getColumns().getCount()}

    def merge_table_cells(self, doc: Any, table_id: str, start_cell: str, end_cell: str) -> Dict[str, Any]:
        table = self._resolve_table(doc, table_id)
        cursor = table.createCursorByCellName(start_cell)
        cursor.gotoCellByName(end_cell, True)
        if not cursor.mergeRange():
            raise ValueError(
                f"Writer refused to merge {start_cell}:{end_cell} in table {table_id!r} -- "
                "the selection isn't a mergeable rectangle."
            )
        return {"merged": f"{start_cell}:{end_cell}"}

    def split_table_cell(self, doc: Any, table_id: str, cell: str, count: int, direction: str) -> Dict[str, Any]:
        """`direction` accepts exactly "horizontal"/"vertical", live-
        verified against the real XTextTableCursor.splitRange() boolean:
        Horizontal=True genuinely produces more ROWS (splits with a
        horizontal dividing line), matching the everyday meaning of
        "split horizontally" -- confirmed by watching a 3x3 table's own
        cell-name set change after calling it. Resulting cell names
        after a split are Writer's own irregular-grid naming (compound/
        skewed once a table stops being a uniform rectangle), not
        predictable from the inputs -- callers should re-list the table
        afterward rather than guess names."""
        table = self._resolve_table(doc, table_id)
        if direction not in ("horizontal", "vertical"):
            raise ValueError(f"Invalid direction {direction!r} -- expected horizontal or vertical.")
        cursor = table.createCursorByCellName(cell)
        if not cursor.splitRange(int(count), direction == "horizontal"):
            raise ValueError(f"Writer refused to split cell {cell!r} in table {table_id!r}.")
        return {"split": cell, "count": count, "direction": direction}

    def set_table_format(self, doc: Any, table_id: str, properties: Dict[str, Any]) -> List[str]:
        table = self._resolve_table(doc, table_id)
        return self._apply_direct_properties(table, properties)

    def set_table_cell_format(self, doc: Any, table_id: str, range: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        # builtins.range(...) here is deliberate, not a typo -- range is
        # this method's own parameter name (matches the spec's field name).
        table = self._resolve_table(doc, table_id)
        start_cell, _, end_cell = range.partition(":")
        end_cell = end_cell or start_cell
        start_col, start_row = self._parse_table_cell_name(start_cell)
        end_col, end_row = self._parse_table_cell_name(end_cell)
        lo_col, hi_col = builtins.min(start_col, end_col), builtins.max(start_col, end_col)
        lo_row, hi_row = builtins.min(start_row, end_row), builtins.max(start_row, end_row)
        applied = set()
        for r in builtins.range(lo_row, hi_row + 1):
            for c in builtins.range(lo_col, hi_col + 1):
                applied.update(self._apply_direct_properties(table.getCellByPosition(c, r), properties))
        return {"applied": sorted(applied), "cells": (hi_col - lo_col + 1) * (hi_row - lo_row + 1)}

    def sort_table(self, doc: Any, table_id: str, keys: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Same uno.Any explicit-sequence-typing requirement calc_data.py's
        own sort_range() already hit: a plain Python tuple of
        TableSortField structs is silently ignored by table.sort(), no
        exception, table just comes back unsorted.

        A second, distinct bug on top of that one, live-verified: unlike
        Calc's sort_range() (where TableSortField.Field is documented and
        confirmed 0-based relative to the range's own first column),
        Writer TextTable's own TableSortField.Field is 1-based --
        confirmed by passing back table.createSortDescriptor()'s own
        untouched default (which pre-fills Field=1 for a single-column
        table and sorts correctly) versus a rebuilt descriptor with
        Field=0 (silently no-ops, no exception) versus Field=1 (sorts
        correctly). Same struct type as Calc, opposite indexing
        convention stays hidden from callers -- `column` in `keys` is
        0-based either way (a letter via _table_column_letters_to_index(),
        or a plain int), same as every other column reference in this
        module; the +1 onto TableSortField.Field happens only internally,
        right before the struct is built."""
        table = self._resolve_table(doc, table_id)
        desc = {p.Name: p.Value for p in table.createSortDescriptor()}
        fields = []
        for key in keys:
            column = key.get("column")
            col_index_0based = self._table_column_letters_to_index(column) if isinstance(column, str) else int(column)
            field = uno.createUnoStruct("com.sun.star.table.TableSortField")
            field.Field = col_index_0based + 1
            field.IsAscending = bool(key.get("ascending", True))
            fields.append(field)
        desc["SortFields"] = uno.Any("[]com.sun.star.table.TableSortField", tuple(fields))
        table.sort(tuple(PropertyValue(k, 0, v, 0) for k, v in desc.items()))
        return {"sorted_keys": len(fields)}

    def delete_table(self, doc: Any, table_id: str) -> Dict[str, Any]:
        """removeTextContent() removes the whole table, content included
        -- live-verified doc.getTextTables().hasByName() goes False
        afterward. No keep_content option: the spec's own
        delete_table_live signature never had one, unlike
        delete_section_live/delete_content_control_live."""
        table = self._resolve_table(doc, table_id)
        doc.getText().removeTextContent(table)
        return {"deleted": table_id}

    def convert_text_to_table(self, doc: Any, range: Optional[str] = None, delimiter: str = "\t",
                               options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # builtins.range(...) here is deliberate, not a typo -- range is
        # this method's own parameter name.
        self._require_writer(doc, "convert_text_to_table")
        target = self._resolve_char_range_string(doc, range)
        raw_text = target.getString()
        rows_data = [line.split(delimiter) for line in raw_text.split("\n") if line != "" or raw_text == ""]
        if not rows_data:
            raise ValueError("No text found in the given range to convert.")
        col_count = builtins.max(len(r) for r in rows_data)
        row_count = len(rows_data)
        text_obj = doc.getText()
        insertion_cursor = text_obj.createTextCursorByRange(target.getStart())
        target.setString("")
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(row_count, col_count)
        text_obj.insertTextContent(insertion_cursor, table, False)
        for r in builtins.range(row_count):
            for c in builtins.range(col_count):
                value = rows_data[r][c] if c < len(rows_data[r]) else ""
                table.getCellByPosition(c, r).setString(value)
        return {"table_id": table.Name, "rows": row_count, "columns": col_count}

    def convert_table_to_text(self, doc: Any, table_id: str, delimiter: str = "\t") -> Dict[str, Any]:
        """Two failed attempts before this one, both live-verified against
        a real table occupying the whole document body:
        `table.getAnchor().getText()` returns None (getAnchor() itself is
        a valid XTextRange, its own getText() just doesn't resolve); and
        `doc.getText().createTextCursorByRange(table.getAnchor().getStart())`
        raises "Invalid text range" -- the anchor's start position isn't
        interchangeable with doc.getText() the way a normal in-body
        range is, at least for a table with no surrounding paragraph.
        Fixed by walking doc.getText()'s own top-level content
        enumeration to find the table and the range immediately before
        it (or text_obj.getStart() if the table is the very first
        element) -- both guaranteed to belong to the same XText."""
        table = self._resolve_table(doc, table_id)
        row_count, col_count = table.getRows().getCount(), table.getColumns().getCount()
        lines = [
            delimiter.join(table.getCellByPosition(c, r).getString() for c in builtins.range(col_count))
            for r in builtins.range(row_count)
        ]
        text_obj = doc.getText()
        enum = text_obj.createEnumeration()
        preceding = None
        while enum.hasMoreElements():
            element = enum.nextElement()
            if element == table:
                break
            preceding = element
        insertion_point = preceding.getEnd() if preceding is not None else text_obj.getStart()
        insertion_cursor = text_obj.createTextCursorByRange(insertion_point)
        text_obj.removeTextContent(table)
        text_obj.insertString(insertion_cursor, "\n".join(lines), False)
        return {"lines": len(lines)}

    # ------------------------------------------------------------------
    # Sections -- name-based via getTextSections(), same as bookmarks.
    # ------------------------------------------------------------------

    def _resolve_section(self, doc: Any, section_id: str) -> Any:
        self._require_writer(doc, "_resolve_section")
        sections = doc.getTextSections()
        if not sections.hasByName(section_id):
            raise KeyError(f"No such section {section_id!r}.")
        return sections.getByName(section_id)

    def list_sections(self, doc: Any) -> List[Dict[str, Any]]:
        self._require_writer(doc, "list_sections")
        sections = doc.getTextSections()
        result = []
        for name in sections.getElementNames():
            sec = sections.getByName(name)
            result.append({
                "section_id": name, "is_protected": bool(sec.IsProtected),
                "is_visible": bool(sec.IsVisible),
            })
        return result

    def insert_section(self, doc: Any, name: str, range: Optional[Dict[str, int]] = None,
                        columns: Optional[Dict[str, Any]] = None, protected: bool = False) -> Dict[str, Any]:
        """`range` is {"start": int, "end": int} character offsets, same
        convention add_bookmark already uses -- unlike convert_text_to_
        table_live/insert_content_control_live, this tool's own scaffold
        already typed `range` as an object, so no invented string format
        needed here.

        Genuine LibreOffice behavior, not a bug, live-verified: wrapping
        a PARTIAL paragraph in a section forces a paragraph break at the
        selection's end boundary -- sections are a paragraph-level ODF
        construct and can't occupy less than a full paragraph. The
        document grows by one paragraph mark (\\r\\n, 2 characters) at
        insertion time, and that break is permanent structure afterward
        -- delete_section_live's keep_content=True path does not (and
        cannot) undo it, since it's baked into the document the moment
        insert_section_live runs, not something the section wrapper
        itself owns."""
        self._require_writer(doc, "insert_section")
        text_obj = doc.getText()
        if range is not None:
            cursor = text_obj.createTextCursor()
            cursor.gotoStart(False)
            cursor.goRight(int(range["start"]), False)
            cursor.goRight(int(range["end"]) - int(range["start"]), True)
        else:
            cursor = self._get_controller(doc).getViewCursor()
        section = doc.createInstance("com.sun.star.text.TextSection")
        section.setName(name)
        text_obj.insertTextContent(cursor, section, True)
        if columns:
            self._apply_direct_properties(section, {"TextColumns": columns} if "TextColumns" in columns else columns)
        if protected:
            section.IsProtected = True
        return {"section_id": section.Name}

    def update_section(self, doc: Any, section_id: str, properties: Dict[str, Any]) -> List[str]:
        section = self._resolve_section(doc, section_id)
        return self._apply_direct_properties(section, properties)

    def delete_section(self, doc: Any, section_id: str, keep_content: bool = True) -> Dict[str, Any]:
        """TextSection.dispose() only removes the section WRAPPER --
        live-verified the enclosed text survives dispose() untouched
        (the opposite of TextTable.removeTextContent(), which takes the
        content with it). keep_content=True is therefore the cheap path
        (just dispose()); keep_content=False needs an explicit follow-up
        clear of the same range."""
        section = self._resolve_section(doc, section_id)
        if keep_content:
            section.dispose()
            return {"deleted": section_id, "keep_content": True}
        anchor = section.getAnchor()
        text_obj = anchor.getText()
        content_cursor = text_obj.createTextCursorByRange(anchor)
        section.dispose()
        content_cursor.setString("")
        return {"deleted": section_id, "keep_content": False}

    # ------------------------------------------------------------------
    # Footnotes / endnotes -- ObjectRegistry-backed (identity confirmed
    # stable across fetches, see module-level note above).
    # ------------------------------------------------------------------

    def add_footnote(self, doc: Any, text: str, position: Optional[int] = None) -> Any:
        self._require_writer(doc, "add_footnote")
        text_obj = doc.getText()
        if position is not None:
            cursor = text_obj.createTextCursorByRange(self._get_paragraph_object(doc, position).getEnd())
        else:
            cursor = self._get_controller(doc).getViewCursor()
        footnote = doc.createInstance("com.sun.star.text.Footnote")
        text_obj.insertTextContent(cursor, footnote, False)
        footnote.setString(text)
        return footnote

    def list_footnotes(self, doc: Any) -> List[Any]:
        self._require_writer(doc, "list_footnotes")
        footnotes = doc.getFootnotes()
        return [footnotes.getByIndex(i) for i in builtins.range(footnotes.getCount())]

    @staticmethod
    def get_footnote_summary(footnote: Any, footnote_id: str) -> Dict[str, Any]:
        return {"footnote_id": footnote_id, "text": footnote.getString()}

    def update_footnote(self, footnote: Any, text: str) -> Dict[str, Any]:
        footnote.setString(text)
        return {"text": text}

    def delete_footnote(self, footnote: Any) -> None:
        footnote.dispose()

    def add_endnote(self, doc: Any, text: str, position: Optional[int] = None) -> Any:
        self._require_writer(doc, "add_endnote")
        text_obj = doc.getText()
        if position is not None:
            cursor = text_obj.createTextCursorByRange(self._get_paragraph_object(doc, position).getEnd())
        else:
            cursor = self._get_controller(doc).getViewCursor()
        endnote = doc.createInstance("com.sun.star.text.Endnote")
        text_obj.insertTextContent(cursor, endnote, False)
        endnote.setString(text)
        return endnote

    def list_endnotes(self, doc: Any) -> List[Any]:
        self._require_writer(doc, "list_endnotes")
        endnotes = doc.getEndnotes()
        return [endnotes.getByIndex(i) for i in builtins.range(endnotes.getCount())]

    @staticmethod
    def get_endnote_summary(endnote: Any, endnote_id: str) -> Dict[str, Any]:
        return {"endnote_id": endnote_id, "text": endnote.getString()}

    def update_endnote(self, endnote: Any, text: str) -> Dict[str, Any]:
        endnote.setString(text)
        return {"text": text}

    def delete_endnote(self, endnote: Any) -> None:
        endnote.dispose()

    _NOTE_SETTINGS_GETTERS = {"footnote": "getFootnoteSettings", "endnote": "getEndnoteSettings"}

    def get_note_settings(self, doc: Any, note_type: str) -> Dict[str, Any]:
        self._require_writer(doc, "get_note_settings")
        getter_name = self._NOTE_SETTINGS_GETTERS.get(note_type)
        if getter_name is None:
            raise ValueError(f"Unknown note_type {note_type!r}. Supported: footnote, endnote.")
        settings = getattr(doc, getter_name)()
        return {
            prop.Name: self._uno_value_to_plain(settings.getPropertyValue(prop.Name))
            for prop in settings.getPropertySetInfo().getProperties()
        }

    def set_note_settings(self, doc: Any, note_type: str, settings: Dict[str, Any]) -> List[str]:
        self._require_writer(doc, "set_note_settings")
        getter_name = self._NOTE_SETTINGS_GETTERS.get(note_type)
        if getter_name is None:
            raise ValueError(f"Unknown note_type {note_type!r}. Supported: footnote, endnote.")
        target = getattr(doc, getter_name)()
        return self._apply_direct_properties(target, settings)

    # ------------------------------------------------------------------
    # Content controls -- ObjectRegistry-backed (identity confirmed
    # stable). com.sun.star.text.ContentControl is a real, current
    # LibreOffice service (added for DOCX structured-document-tag
    # round-tripping) -- live-verified via getPropertySetInfo(), not
    # assumed from the spec's Word-flavored terminology.
    # ------------------------------------------------------------------

    _CONTENT_CONTROL_TYPE_PROPS = {
        "checkbox": "Checkbox", "dropdown": "DropDown", "date": "Date",
        "combobox": "ComboBox", "picture": "Picture", "plaintext": "PlainText",
    }

    def insert_content_control(self, doc: Any, range: Optional[str] = None, tag: Optional[str] = None,
                                title: Optional[str] = None, type: Optional[str] = None) -> Any:
        self._require_writer(doc, "insert_content_control")
        target = self._resolve_char_range_string(doc, range)
        cc = doc.createInstance("com.sun.star.text.ContentControl")
        if type is not None:
            prop_name = self._CONTENT_CONTROL_TYPE_PROPS.get(type)
            if prop_name is None:
                raise ValueError(f"Unknown content control type {type!r}. Supported: {sorted(self._CONTENT_CONTROL_TYPE_PROPS)}.")
            setattr(cc, prop_name, True)
        if tag is not None:
            cc.Tag = tag
        if title is not None:
            cc.Alias = title
        doc.getText().insertTextContent(target, cc, True)
        return cc

    def list_content_controls(self, doc: Any) -> List[Any]:
        self._require_writer(doc, "list_content_controls")
        controls = doc.getContentControls()
        return [controls.getByIndex(i) for i in builtins.range(controls.getCount())]

    @staticmethod
    def get_content_control_summary(cc: Any, control_id: str) -> Dict[str, Any]:
        return {"control_id": control_id, "tag": cc.Tag, "title": cc.Alias, "text": cc.getString()}

    def get_content_control(self, cc: Any, control_id: str) -> Dict[str, Any]:
        active_type = next(
            (key for key, prop_name in self._CONTENT_CONTROL_TYPE_PROPS.items() if getattr(cc, prop_name, False)),
            "plaintext",
        )
        return {
            "control_id": control_id, "tag": cc.Tag, "title": cc.Alias, "text": cc.getString(),
            "type": active_type, "lock": cc.Lock, "showing_placeholder": bool(cc.ShowingPlaceHolder),
        }

    def set_content_control(self, cc: Any, text: Optional[str] = None,
                             properties: Optional[Dict[str, Any]] = None) -> List[str]:
        applied = []
        if text is not None:
            cc.setString(text)
            applied.append("text")
        if properties:
            applied.extend(self._apply_direct_properties(cc, properties))
        return applied

    def delete_content_control(self, doc: Any, cc: Any, keep_content: bool = True) -> bool:
        """Genuine LibreOffice limitation this build, not a coding bug --
        live-verified three different ways (cc.dispose(), doc.getText().
        removeTextContent(cc), and both together): none of them actually
        remove the ContentControl from doc.getContentControls() --
        getCount() stays the same, and the surviving entry compares `==`
        equal to the original object, confirming it is the SAME control,
        not a fresh replacement. All any of them do is clear the wrapped
        text. So this method makes no attempt to remove the wrapper (an
        earlier version tried dispose()-then-reinsert and left a
        duplicate, empty ghost control behind precisely because of this)
        -- it only clears content when keep_content=False, and returns
        False always so the tools/ layer can surface an honest warning
        that the wrapper itself persists. Returns the wrapper_removed
        flag (always False this pass)."""
        if not keep_content:
            cc.setString("")
        return False

    # ------------------------------------------------------------------
    # Mail merge. preview_mail_merge is real: an ad hoc, unregistered
    # com.sun.star.sdb.DataSource (URL + Info properties) gives a working
    # SDBC connection without needing a persisted .odb file -- live-
    # verified against a real CSV folder (query, columns, rows all read
    # back correctly). mail_merge stays status="stub": the real
    # com.sun.star.text.MailMerge service's own Model property is
    # read-only (live-verified UnknownPropertyException setting it), and
    # its alternative XJob.execute()-with-DocumentURL path requires a
    # DataSourceName resolvable through com.sun.star.sdb.DatabaseContext
    # -- which live-verified refuses to register an ad hoc DataSource at
    # all ("The data source was not saved. Please use the interface
    # XStorable to save the data source."), i.e. it wants a real,
    # persisted .odb file this pass doesn't build. Genuinely blocked
    # without that registration infrastructure, same shape as calc_data.
    # py's create/refresh/delete_external_link stubs.
    # ------------------------------------------------------------------

    def _connect_mail_merge_data_source(self, data_source: str) -> Any:
        info = (
            PropertyValue("Extension", 0, "csv", 0),
            PropertyValue("FieldDelimiter", 0, ",", 0),
            PropertyValue("HeaderLine", 0, True, 0),
            PropertyValue("CharSet", 0, "UTF-8", 0),
        )
        smgr = uno.getComponentContext().ServiceManager
        ds = smgr.createInstance("com.sun.star.sdb.DataSource")
        ds.URL = "sdbc:flat:" + data_source.replace("\\", "/")
        ds.Info = info
        return ds.getConnection("", "")

    def preview_mail_merge(self, doc: Any, data_source: str, command: str,
                            rows: Optional[List[int]] = None, output: str = "preview") -> Dict[str, Any]:
        self._require_writer(doc, "preview_mail_merge")
        conn = self._connect_mail_merge_data_source(data_source)
        stmt = conn.createStatement()
        result_set = stmt.executeQuery(f"SELECT * FROM {command}")
        meta = result_set.getMetaData()
        col_count = meta.getColumnCount()
        col_names = [meta.getColumnName(i + 1) for i in builtins.range(col_count)]
        all_rows = []
        while result_set.next():
            all_rows.append({name: result_set.getString(i + 1) for i, name in enumerate(col_names)})
        selected = [all_rows[i] for i in rows] if rows is not None else all_rows

        fields = doc.getTextFields().createEnumeration()
        bindings = []
        while fields.hasMoreElements():
            field = fields.nextElement()
            if field.supportsService("com.sun.star.text.TextField.Database"):
                bindings.append(field)

        previews = []
        for row_data in selected:
            resolved = {}
            for field in bindings:
                master = field.getTextFieldMaster() if hasattr(field, "getTextFieldMaster") else None
                column = getattr(master, "DataColumnName", None) if master is not None else None
                if column and column in row_data:
                    resolved[column] = row_data[column]
            previews.append({"row": row_data, "resolved_fields": resolved})
        return {"columns": col_names, "row_count": len(all_rows), "previews": previews}
